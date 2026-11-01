"""Fictional sentiment/history tests; no network or market observations."""
import copy
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import risk_context as r
import prepare_market_data as p
import render_snapshot as renderer
from test_pipeline import query_fixture


class RiskContextTests(unittest.TestCase):
    def setUp(self):
        self.plan=p.make_plan('2026-10-31T08:00:00+08:00','2026-10-30',example=True)
        self.fg={'publisher':'CNN','score':42,'rating':'fear','date':'2026-10-30',
                 'observed_at':'2026-10-30T16:00:00-04:00','cutoff':'daily close',
                 'prior_score':45,'prior_date':'2026-10-29','prior_cutoff':'daily close','source_ids':['3']}
        days=[];day=date(2026,10,29)
        while len(days)<253:
            if day.weekday()<5:days.append(day.isoformat())
            day-=timedelta(days=1)
        self.item={'instrument':'DXY','level':101,'prior_level':100,'date':'2026-10-30','prior_date':'2026-10-29',
                   'cutoff':'daily close','source_ids':['3']}
        self.item['history']={'instrument':'DXY','cutoff':'daily close','source_ids':['3'],'complete':True,
                              'observations':[{'date':d,'level':100} for d in reversed(days)]}

    def test_vix_boundaries(self):
        for level,label in [(14.99,'SUBDUED'),(15,'MODERATE'),(20,'ELEVATED'),(30,'HIGH')]:
            self.assertEqual(r.risk_badge('vix',{'level':level})['label'],label)

    def test_percentile_excludes_current_and_handles_ties(self):
        self.assertEqual(r.risk_badge('dollar',self.item)['percentile'],100)
        self.item['level']=100
        self.assertEqual(r.risk_badge('dollar',self.item)['percentile'],50)

    def test_insufficient_history_stays_unavailable(self):
        self.item['history']['observations'].pop(0)
        self.assertEqual(r.risk_badge('dollar',self.item)['label'],'UNAVAILABLE')

    def test_wrong_series_source_cutoff_and_incomplete_rejected(self):
        for key,value in [('instrument','UUP'),('cutoff','intraday'),('source_ids',['9']),('complete',False)]:
            item=copy.deepcopy(self.item);item['history'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):r.risk_badge('dollar',item)

    def test_future_duplicate_and_wrong_prior_history_rejected(self):
        for change in ('future','duplicate','prior'):
            item=copy.deepcopy(self.item);obs=item['history']['observations']
            if change=='future':obs[-1]['date']='2026-10-30'
            if change=='duplicate':obs[-2]['date']=obs[-1]['date']
            if change=='prior':obs[-1]['level']=99
            with self.subTest(change=change),self.assertRaises(ValueError):r.risk_badge('dollar',item)

    def test_authored_percentile_rejected(self):
        self.item['percentile']=93
        with self.assertRaises(ValueError):r.risk_badge('dollar',self.item)

    def test_fear_greed_change_and_stale_date(self):
        result=r.fear_greed(self.fg,self.plan,lambda ids:'[3]')
        self.assertEqual(result['score'],42)
        self.assertIn('-3.0 pts',result['change'])
        plan=dict(self.plan,report_date='2026-10-31')
        self.assertTrue(r.fear_greed(self.fg,plan,lambda ids:'[3]')['note'].startswith('STALE'))

    def test_sentiment_unknown_and_no_prior(self):
        self.assertEqual(r.fear_greed(None,self.plan,None)['status'],'unavailable')
        self.fg.pop('prior_score')
        self.assertIn('unavailable',r.fear_greed(self.fg,self.plan,lambda ids:'[3]')['change'])

    def test_sentiment_bad_score_timestamp_source_and_example_rejected(self):
        for key,value in [('score',True),('score',101),('score','NaN'),('observed_at','2026-10-30T16:00:00'),
                          ('observed_at','2026-11-02T16:00:00-05:00'),('publisher','Crypto'),('prior_cutoff','live')]:
            fg=copy.deepcopy(self.fg);fg[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):r.fear_greed(fg,self.plan,lambda ids:'[3]')
        fg=dict(self.fg,illustrative=True)
        with self.assertRaises(ValueError):r.fear_greed(fg,dict(self.plan,example=False),lambda ids:'[3]')

    def test_complete_composition_and_extreme_label_render(self):
        metrics=p.normalize(self.plan,query_fixture(self.plan),p.read_json(ROOT/'tests/fixtures/treasuries.json')['results'])
        editorial=p.read_json(ROOT/'tests/fixtures/editorial.json')
        editorial['fear_greed']=dict(self.fg,score=100,rating='extreme greed')
        editorial['risk']['dollar']=self.item
        snapshot=p.compose(metrics,editorial)
        self.assertEqual(snapshot['risk'][1]['context']['label'],'EXTREME · P100')
        self.assertEqual(snapshot['fear_greed']['rating'],'EXTREME GREED')
        with tempfile.TemporaryDirectory() as tmp:
            renderer.Renderer(*(renderer.resolve_font(None,k) for k in ['regular','bold','mono'])).render(snapshot,Path(tmp)/'test.png')


if __name__=='__main__':unittest.main()
