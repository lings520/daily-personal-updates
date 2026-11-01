"""Offline regression tests. All fixture prices/events are fictional."""
import copy
import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import prepare_market_data as p
import render_snapshot as renderer

FIXTURES = Path(__file__).parent/'fixtures'


def query_fixture(plan):
    raw = p.read_json(FIXTURES/'equities.json')
    with sqlite3.connect(':memory:') as db:
        db.row_factory = sqlite3.Row
        for role, request in zip(('current','prior'), plan['requests']):
            name = request['store_as']
            db.execute(f'CREATE TABLE {name} (T TEXT, c REAL, t_2 INTEGER)')
            db.executemany(f'INSERT INTO {name} VALUES (:T,:c,:t_2)', raw[role])
        return [dict(r) for r in db.execute(p.render_sql(plan))]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.plan = p.make_plan('2026-10-31T08:00:00+08:00','2026-10-30',example=True)
        self.equities = query_fixture(self.plan)
        self.treasuries = p.read_json(FIXTURES/'treasuries.json')['results']
        self.editorial = p.read_json(FIXTURES/'editorial.json')

    def metrics(self):
        return p.normalize(self.plan,self.equities,self.treasuries)

    def test_grouped_sql_and_decimal_returns(self):
        self.assertEqual(len(self.equities),17)
        result = self.metrics()
        self.assertEqual(result['equities']['SPY']['change_pct'],-7)
        self.assertEqual(result['equities']['QQQ']['change_pct'],-6)
        self.assertEqual(result['yields']['2Y']['change_bp'],-5)
        self.assertEqual(result['yields']['10Y']['change_bp'],-2)
        self.assertEqual(result['yields']['30Y']['change_bp'],2)
        self.assertEqual(result['warnings'],[])

    def test_plan_defaults_hkt_yesterday(self):
        plan = p.make_plan('2026-10-31T00:00:00+00:00')
        self.assertEqual(plan['report_date'],'2026-10-30')
        self.assertEqual(plan['equity_prior_session'],'2026-10-29')
        self.assertEqual(plan['next_session'],'2026-11-02')
        self.assertEqual(plan['requests'][0]['params'],{'adjusted':True,'include_otc':False})

    def test_weekend_preserves_news_date(self):
        plan=p.make_plan('2026-11-02T08:00:00+08:00')
        self.assertEqual(plan['report_date'],'2026-11-01')
        self.assertEqual(plan['equity_session'],'2026-10-30')
        self.assertTrue(plan['market_closed'])

    def test_holiday_uses_previous_session(self):
        plan=p.make_plan('2026-11-27T08:00:00+08:00')
        self.assertEqual(plan['equity_session'],'2026-11-25')
        self.assertEqual(plan['equity_prior_session'],'2026-11-24')
        self.assertTrue(plan['market_closed'])

    def test_early_close_and_incomplete_session(self):
        before=p.make_plan('2026-11-27T12:59:00-05:00','2026-11-27')
        after=p.make_plan('2026-11-27T13:01:00-05:00','2026-11-27')
        self.assertEqual(before['equity_session'],'2026-11-25')
        self.assertTrue(before['target_not_complete'])
        self.assertEqual(after['equity_session'],'2026-11-27')
        self.assertEqual(after['session_close'],'2026-11-27T13:00:00-05:00')

    def test_calendar_coverage_and_future_dates_fail(self):
        for asof,day in [('2026-11-01T00:00:00Z','2026-11-05'),('2030-02-02T00:00:00Z','2030-02-01')]:
            with self.subTest(day=day),self.assertRaises(ValueError):p.make_plan(asof,day)

    def test_calendar_override_for_exceptional_closure(self):
        calendar=copy.deepcopy(self.plan['calendar'])
        calendar['holidays'].append('2026-10-30')
        plan=p.make_plan(self.plan['as_of'],'2026-10-30',calendar=calendar)
        self.assertEqual(plan['equity_session'],'2026-10-29')

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ValueError):p.make_plan('2026-10-31T08:00:00')

    def test_changed_plan_rejected(self):
        self.plan['equity_prior_session']='2026-10-28'
        with self.assertRaises(ValueError):self.metrics()

    def test_adjustment_convention_required(self):
        config=copy.deepcopy(self.plan['config'])
        config['queries']['equities']['params']['adjusted']=False
        with self.assertRaises(ValueError):p.make_plan(self.plan['as_of'],'2026-10-30',config=config)

    def test_missing_sector_is_explicit(self):
        self.equities=[r for r in self.equities if r['ticker']!='XLE']
        metrics=self.metrics()
        self.assertEqual(metrics['equities']['XLE']['status'],'unavailable')
        snapshot=p.compose(metrics,self.editorial)
        self.assertIn('10/11',snapshot['sectors']['coverage'])

    def test_empty_responses_give_unavailable_not_zero(self):
        metrics=p.normalize(self.plan,[],[])
        snapshot=p.compose(metrics,self.editorial)
        self.assertEqual(snapshot['equities'][0]['cells'][1],'Unavailable')
        self.assertEqual(snapshot['yields'][0]['cells'][1],'Unavailable')
        self.assertEqual(snapshot['risk'][1]['cells'][1],'Unavailable')

    def test_duplicate_ticker_or_bar_rejected(self):
        with self.assertRaises(ValueError):p.normalize(self.plan,self.equities+[self.equities[0]],self.treasuries)
        self.equities[0]['current_count']=2
        with self.assertRaises(ValueError):self.metrics()

    def test_zero_nonfinite_boolean_and_invalid_prices_rejected(self):
        for value in [0,-1,'NaN','Infinity',True,'wrong price']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                rows=copy.deepcopy(self.equities);rows[0]['prior_close']=value
                p.normalize(self.plan,rows,self.treasuries)

    def test_wrong_session_timestamp_rejected(self):
        self.equities[0]['current_timestamp']=self.equities[0]['prior_timestamp']
        with self.assertRaises(ValueError):self.metrics()

    def test_wrong_return_rejected(self):
        self.equities[0]['change_pct']=999
        with self.assertRaises(ValueError):self.metrics()

    def test_stale_yields_are_dated_and_request_fallback(self):
        self.treasuries=[{'date':'2026-10-29','yield_2_year':4.15,'yield_10_year':4.32,'yield_30_year':4.48},
                         {'date':'2026-10-28','yield_2_year':4.2,'yield_10_year':4.34,'yield_30_year':4.47}]
        metrics=self.metrics()
        self.assertEqual(metrics['yields']['2Y']['status'],'dated')
        self.assertEqual(len(metrics['warnings']),3)
        self.assertIn('2026-10-29 vs 2026-10-28',p.compose(metrics,self.editorial)['footer'][0])

    def test_null_yield_does_not_become_zero(self):
        self.treasuries[0]['yield_30_year']=None
        self.assertEqual(self.metrics()['yields']['30Y']['status'],'unavailable')

    def test_treasuries_use_their_own_available_dates(self):
        self.treasuries[1]['date']='2026-10-28'
        self.assertEqual(self.metrics()['yields']['2Y']['prior_date'],'2026-10-28')

    def test_future_and_duplicate_yields_rejected(self):
        with self.assertRaises(ValueError):p.normalize(self.plan,self.equities,self.treasuries+[self.treasuries[0]])
        self.treasuries[0]['date']='2026-11-02'
        with self.assertRaises(ValueError):self.metrics()

    def test_fallback_source_preserved(self):
        source={'name':'Fictional Treasury fallback','kind':'fixture','series':'Par yields','url':'https://example.org/treasury'}
        metrics=p.normalize(self.plan,self.equities,self.treasuries,source)
        self.assertEqual(p.compose(metrics,self.editorial)['sources']['2'],source)

    def test_derived_metrics_tampering_rejected(self):
        metrics=self.metrics();metrics['equities']['SPY']['change_pct']=2
        with self.assertRaises(ValueError):p.compose(metrics,self.editorial)

    def test_unknown_citations_rejected(self):
        self.editorial['news'][0]['source_ids']=['999']
        with self.assertRaises(ValueError):p.compose(self.metrics(),self.editorial)

    def test_fixture_sources_blocked_for_live_report(self):
        self.plan=p.make_plan(self.plan['as_of'],'2026-10-30')
        with self.assertRaises(ValueError):p.compose(self.metrics(),self.editorial)

    def test_news_date_and_sentiment_validation(self):
        self.editorial['news'][0]['date']='2026-10-29'
        with self.assertRaises(ValueError):p.compose(self.metrics(),self.editorial)
        self.editorial['news'][0]['date']='2026-10-30'
        self.editorial['news'][0]['sentiment']='bullish'
        with self.assertRaises(ValueError):p.compose(self.metrics(),self.editorial)

    def test_dst_and_hkt_midnight_rollover(self):
        snapshot=p.compose(self.metrics(),self.editorial)
        self.assertEqual(snapshot['upcoming'][0]['hkt'],'02 Nov 2026\n23:00')
        self.assertEqual(snapshot['upcoming'][1]['hkt'],'03 Nov 2026\n03:00')
        self.editorial['upcoming'][0]['at']='2026-11-02T10:00:00-04:00'
        with self.assertRaises(ValueError):p.compose(self.metrics(),self.editorial)

    def test_simultaneous_events_have_separate_rows(self):
        self.editorial['upcoming'][1]['at']=self.editorial['upcoming'][0]['at']
        snapshot=p.compose(self.metrics(),self.editorial)
        self.assertEqual(len(snapshot['upcoming']),2)
        self.assertEqual(snapshot['upcoming'][0]['hkt'],snapshot['upcoming'][1]['hkt'])

    def test_past_upcoming_event_rejected(self):
        self.editorial['upcoming'][0]['at']='2026-10-30T10:00:00-04:00'
        with self.assertRaises(ValueError):p.compose(self.metrics(),self.editorial)

    def test_unknown_event_time_is_not_invented(self):
        self.editorial['upcoming']=[{'date':'2026-11-02','timezone':'America/New_York','timing':'before market',
                                    'event':'Fictional earnings','watch':'Guidance','source_ids':['3']}]
        snapshot=p.compose(self.metrics(),self.editorial)
        self.assertEqual(snapshot['upcoming'][0]['hkt'],'HKT time TBD')
        self.assertIn('before market',snapshot['upcoming'][0]['event'])

    def test_no_news_or_calendar_is_honest(self):
        self.editorial['news']=[];self.editorial['upcoming']=[]
        snapshot=p.compose(self.metrics(),self.editorial)
        self.assertIn('verification incomplete',snapshot['news'][0]['text'])
        self.assertEqual(snapshot['upcoming'][0]['hkt'],'—')

    def test_verified_quiet_calendar_requires_sources(self):
        self.editorial.update(news=[],upcoming=[],news_checked_none=True,calendar_checked_none=True)
        with self.assertRaises((ValueError,KeyError)):p.compose(self.metrics(),self.editorial)
        self.editorial.update(news_source_ids=['3'],calendar_source_ids=['3'])
        snapshot=p.compose(self.metrics(),self.editorial)
        self.assertNotIn('incomplete',snapshot['news'][0]['text'])
        self.assertIn('quiet',snapshot['upcoming'][0]['watch'])

    def test_fictional_data_are_not_attributed_to_live_connector(self):
        self.assertEqual(self.metrics()['sources']['1']['kind'],'fixture')
        self.assertEqual(self.metrics()['sources']['2']['kind'],'fixture')

    def test_proxy_labels_and_missing_risk(self):
        snapshot=p.compose(self.metrics(),self.editorial)
        self.assertIn('UUP ETF proxy',snapshot['risk'][1]['cells'][0])
        self.assertIn('USD/share',snapshot['risk'][1]['cells'][1])
        self.assertEqual(snapshot['risk'][3]['cells'][1],'Unavailable')
        self.editorial['risk']['vix']['instrument']='VXX'
        with self.assertRaises(ValueError):p.compose(self.metrics(),self.editorial)

    def test_risk_date_contract_unit_and_cutoff_validation(self):
        for key,value in [('date','2026-11-02'),('prior_instrument','VXX'),('unit','USD/share'),('prior_cutoff','live')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                e=copy.deepcopy(self.editorial);e['risk']['vix'][key]=value
                p.compose(self.metrics(),e)

    def test_breadth_denominator_checked(self):
        self.editorial['breadth']={'date':'2026-10-30','universe':'Fictional 100 issues','complete':True,
                                   'advancing':60,'declining':30,'unchanged':10,'total':100,'source_ids':['3']}
        self.assertIn('60.00%',p.compose(self.metrics(),self.editorial)['breadth'][1])
        self.editorial['breadth']['total']=90
        with self.assertRaises(ValueError):p.compose(self.metrics(),self.editorial)

    def test_display_validation_rejects_invalid_dates_prices_and_duplicates(self):
        snapshot=p.compose(self.metrics(),self.editorial)
        for field in ('date','price','duplicate','citation'):
            d=copy.deepcopy(snapshot);d['example']=False
            if field=='date':d['report_date']='wrong date'
            if field=='price':d['equities'][0]['cells'][1]='wrong price'
            if field=='duplicate':d['equities'][1]=d['equities'][0]
            if field=='citation':d['headline']+=' [999]'
            with self.subTest(field=field),self.assertRaises(ValueError):renderer.validate(d)

    def test_response_parser_rejects_errors_pagination_and_truncation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'response.json'
            for body in [{'status':'ERROR','results':[]},{'status':'OK','results':[],'next_url':'https://example.org/next'}]:
                p.write_json(path,body)
                with self.assertRaises(ValueError):p.rows_from_file(path)
            path.write_text('ticker,c\nSPY,[truncated: 200 more chars]')
            with self.assertRaises(ValueError):p.rows_from_file(path)
            path.write_text('API request failed')
            with self.assertRaises(ValueError):p.rows_from_file(path)

    def test_rounding_avoids_negative_zero(self):
        self.assertEqual(p.fmt('-0.0001',signed=True),'+0.00')
        self.assertEqual(p.fmt('1.005'),'1.01')

    def test_full_cli_to_png(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);script=ROOT/'scripts/prepare_market_data.py'
            def run(*args):subprocess.run([sys.executable,*map(str,args)],check=True,capture_output=True,text=True)
            run(script,'plan','--date','2026-10-30','--as-of','2026-10-31T08:00:00+08:00','--example',
                '--output',path/'plan.json','--sql-output',path/'query.sql')
            with (path/'equities.csv').open('w',newline='') as out:
                writer=csv.DictWriter(out,fieldnames=list(self.equities[0]));writer.writeheader();writer.writerows(self.equities)
            run(script,'normalize','--plan',path/'plan.json','--equities',path/'equities.csv',
                '--treasuries',FIXTURES/'treasuries.json','--output',path/'metrics.json')
            run(script,'compose','--metrics',path/'metrics.json','--editorial',FIXTURES/'editorial.json','--output',path/'snapshot.json')
            run(ROOT/'scripts/render_snapshot.py',path/'snapshot.json',path/'snapshot.png','--preview',path/'preview.png')
            from PIL import Image
            with Image.open(path/'snapshot.png') as img:self.assertEqual(img.width,1200);self.assertLessEqual(img.height,3200)
            with Image.open(path/'preview.png') as img:self.assertEqual(img.width,600)


if __name__=='__main__':unittest.main()
