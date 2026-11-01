#!/usr/bin/env python3
"""Plan connector requests, validate observations, and compose renderer JSON. No network/auth."""
import argparse
import csv
import io
import json
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
NY, HK = ZoneInfo('America/New_York'), ZoneInfo('Asia/Hong_Kong')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+x)))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def iso_date(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), 'Expected YYYY-MM-DD')
    return date.fromisoformat(value)


def instant(value):
    require(isinstance(value, str), 'Timestamp must be text with a UTC offset')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None and result.utcoffset() is not None, 'Timestamp needs a UTC offset')
    return result


def number(value, name, positive=False):
    require(not isinstance(value, bool) and value is not None, name+' must be numeric')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(name+' must be numeric') from exc
    require(result.is_finite(), name+' must be finite')
    require(not positive or result > 0, name+' must be positive')
    return result


def fmt(value, places=2, signed=False):
    rounded = number(value, 'display value').quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = abs(rounded)
    return format(rounded, ('+' if signed else '')+f'.{places}f')


def rows_from_file(path, required=()):
    """Accept verbatim query_data CSV, JSON row arrays, or REST results envelopes."""
    text = Path(path).read_text(encoding='utf-8').strip()
    require(text and '[truncated' not in text, 'Empty/truncated response; retrieve the complete result')
    if text[0] in '[{':
        data = read_json(path)
        if isinstance(data, dict):
            require(data.get('status', 'OK') in ('OK', 'DELAYED'), 'API returned an error')
            require(not data.get('next_url'), 'Follow pagination before normalizing')
            data = data.get('results')
        require(isinstance(data, list) and all(isinstance(r, dict) and set(required).issubset(r) for r in data), 'Expected result rows with required columns')
        return data
    reader = csv.DictReader(io.StringIO(text))
    require(reader.fieldnames and len(reader.fieldnames) >= 2 and len(reader.fieldnames) == len(set(reader.fieldnames)) and set(required).issubset(reader.fieldnames), 'Invalid CSV header or missing required columns')
    rows = list(reader)
    require(all(None not in row and all(v is not None for v in row.values()) for row in rows), 'Malformed CSV rows')
    return rows


class EquityCalendar:
    def __init__(self, data):
        self.data = data
        require(data.get('timezone') == 'America/New_York', 'Equity calendar must use America/New_York')
        self.years = set(data['years'])
        self.holidays = {iso_date(x) for x in data['holidays']}
        self.early = {iso_date(k): time.fromisoformat(v) for k, v in data['early_closes'].items()}

    def is_session(self, day):
        require(day.year in self.years, f'Calendar does not cover {day}; supply an updated verified --calendar')
        return day.weekday() < 5 and day not in self.holidays

    def at(self, day, closing=False):
        hour = self.early.get(day, time.fromisoformat(self.data['close'])) if closing else time.fromisoformat(self.data['open'])
        return datetime.combine(day, hour, NY)

    def find(self, day, direction, predicate=lambda d: True):
        for _ in range(40):
            if self.is_session(day) and predicate(day):
                return day
            day += timedelta(days=direction)
        raise ValueError('No eligible session in 40 days; verify the calendar')


def make_plan(as_of, report_date=None, config=None, calendar=None, example=False):
    cfg = config or read_json(ROOT/'config/market-data.json')
    require(list(cfg['equities']) == ['SPY','QQQ'] and len(cfg['sectors']) == 11, 'Configure SPY, QQQ and all 11 sectors')
    require(cfg['queries']['equities']['params'].get('adjusted') is True, 'Use comparable split-adjusted equity closes')
    cal_data = calendar or read_json(ROOT/'config/us-equity-calendar.json')
    cal = EquityCalendar(cal_data)
    now = instant(as_of)
    target = iso_date(report_date) if report_date else now.astimezone(HK).date()-timedelta(days=1)
    require(target <= now.astimezone(NY).date(), 'Future report date cannot be reported as completed history')
    session = cal.find(target, -1, lambda d: cal.at(d, True) <= now)
    prior = cal.find(session-timedelta(days=1), -1)
    upcoming = (cal.find(target+timedelta(days=1), 1) if report_date else
                cal.find(now.astimezone(NY).date(), 1, lambda d: cal.at(d) > now))
    tickers = list(cfg['equities'])+[cfg['participation_proxy']]+list(cfg['sectors'])
    tickers += [r['proxy'] for r in cfg['risk'].values() if 'proxy' in r]
    require(len(tickers) == len(set(tickers)) and all(re.fullmatch(r'[A-Z][A-Z0-9.:-]*', t) for t in tickers), 'Invalid/duplicate configured ticker')
    stem = 'mu_'+session.strftime('%Y%m%d')
    queries = []
    for role, day in [('current', session), ('prior', prior)]:
        spec = cfg['queries']['equities']
        queries.append({'role': role, 'path': spec['path'].format(date=day.isoformat()),
                        'params': spec['params'], 'store_as': stem+'_'+role})
    tq = cfg['queries']['treasuries']
    queries.append({'role': 'treasuries', 'path': tq['path'], 'params': dict(tq['params'], **{
        'date.gte': (target-timedelta(days=tq['lookback_days'])).isoformat(), 'date.lte': target.isoformat()})})
    return {'schema_version': 1, 'example': bool(example), 'mode': 'historical' if report_date else 'morning',
            'as_of': now.isoformat(), 'report_date': target.isoformat(), 'equity_session': session.isoformat(),
            'equity_prior_session': prior.isoformat(), 'next_session': upcoming.isoformat(),
            'session_close': cal.at(session, True).isoformat(),
            'market_closed': not cal.is_session(target), 'target_not_complete': session < target and cal.is_session(target),
            'tickers': tickers, 'requests': queries, 'config': cfg, 'calendar': cal_data}


def validate_plan(plan):
    expected = make_plan(plan['as_of'], plan['report_date'] if plan['mode'] == 'historical' else None,
                         plan['config'], plan['calendar'], plan.get('example', False))
    require(plan == expected, 'Plan differs from its calculated dates/requests; regenerate it')


def render_sql(plan):
    validate_plan(plan)
    sql = (ROOT/'queries/equity-returns.sql').read_text()
    substitutions = {'wanted': ','.join("('"+t+"')" for t in plan['tickers']),
                     'current_table': plan['requests'][0]['store_as'], 'prior_table': plan['requests'][1]['store_as']}
    for key, value in substitutions.items():
        sql = sql.replace('{{'+key+'}}', value)
    require('{{' not in sql, 'Unknown SQL placeholder')
    return sql


def timestamp_date(value):
    millis = number(value, 'bar timestamp')
    require(millis == millis.to_integral_value(), 'Bar timestamp must be integer milliseconds')
    return datetime.fromtimestamp(float(millis)/1000, timezone.utc).astimezone(NY).date().isoformat()


def normalize(plan, equity_rows, treasury_rows, treasury_source=None, equity_source=None):
    validate_plan(plan)
    cfg = plan['config']
    source = treasury_source or {'name': 'Massive Treasury yields', 'kind': 'connector', 'series': 'Daily constant-maturity yields',
                                 'endpoint': cfg['queries']['treasuries']['path']}
    if plan['example'] and treasury_source is None:
        source = {'name': 'Fictional yield fixture', 'kind': 'fixture', 'series': 'Synthetic constant-maturity yields'}
    require(source.get('name') and source.get('series'), 'Treasury source needs name and consistent series')
    equity_source = equity_source or {'name': 'Massive equity closes', 'kind': 'connector', 'adjusted': True,
                                      'endpoints': [q['path'] for q in plan['requests'][:2]]}
    if plan['example'] and equity_source.get('name') == 'Massive equity closes':
        equity_source = {'name': 'Fictional equity fixture', 'kind': 'fixture', 'adjusted': True}
    require(equity_source.get('adjusted') is True and equity_source.get('name'), 'Equity source must identify comparable split-adjusted closes')
    warnings, equities = [], {}
    by_ticker = {}
    for row in equity_rows:
        ticker = row.get('ticker')
        require(ticker in plan['tickers'], 'Unexpected ticker in filtered equity results: '+str(ticker))
        require(ticker not in by_ticker, 'Duplicate ticker: '+ticker)
        by_ticker[ticker] = row
    for ticker in plan['tickers']:
        row = by_ticker.get(ticker, {})
        record = {'ticker': ticker, 'date': plan['equity_session'], 'prior_date': plan['equity_prior_session'], 'source_id': '1'}
        values = {}
        for side, expected_date in [('current', record['date']), ('prior', record['prior_date'])]:
            count = number(row.get(side+'_count', 0), ticker+' row count')
            require(count in (0, 1), ticker+' has duplicate bars')
            if count == 0:
                require(row.get(side+'_close') in (None, '', 'null', 'None'), ticker+' has a value without a bar')
                continue
            require(timestamp_date(row[side+'_timestamp']) == expected_date, ticker+' has the wrong session timestamp')
            values[side] = number(row[side+'_close'], ticker+' close', positive=True)
        if len(values) != 2:
            record.update(status='unavailable', reason='Missing current or prior session bar')
            if ticker in list(cfg['equities'])+[cfg['participation_proxy']]+list(cfg['sectors']):
                warnings.append(ticker+': missing current/prior bar; do not infer a holiday')
        else:
            current, prior = values['current'], values['prior']
            pct = (current/prior-1)*100
            sql_pct = row.get('change_pct')
            if sql_pct not in (None, '', 'null', 'None'):
                require(abs(number(sql_pct, 'SQL return')-pct) < Decimal('0.000001'), ticker+' SQL/Python return mismatch')
            record.update(status='ok', close=float(current), prior_close=float(prior), change=float(current-prior), change_pct=float(pct))
        equities[ticker] = record
    observations = {}
    for row in treasury_rows:
        day = iso_date(row['date'])
        require(day.isoformat() <= plan['report_date'], 'Treasury observation is after the report date')
        require(day.isoformat() not in observations, 'Duplicate Treasury date')
        observations[day.isoformat()] = row
    yields = {}
    for label, field in cfg['treasury_fields'].items():
        available = []
        for day in sorted(observations, reverse=True):
            value = observations[day].get(field)
            if value not in (None, '', 'null', 'None'):
                available.append((day, number(value, field)))
        record = {'source_id': '2'}
        if len(available) < 2:
            record.update(status='unavailable', reason='Fewer than two valid observations')
            warnings.append(label+': insufficient yields; try the configured official fallback')
        else:
            (day, current), (previous, prior) = available[:2]
            stale = day != plan['report_date']
            record.update(status='dated' if stale else 'ok', date=day, prior_date=previous,
                          level=float(current), prior_level=float(prior), change_bp=float((current-prior)*100))
            if stale:
                warnings.append(label+': latest yield is '+day+'; check the official fallback/publication calendar')
        yields[label] = record
    return {'schema_version': 1, 'plan': plan, 'equities': equities, 'yields': yields, 'warnings': warnings,
            'sources': {'1': equity_source, '2': source},
            'inputs': {'equities': equity_rows, 'treasuries': treasury_rows}}


def checked_sources(base, editorial, example):
    sources = dict(base)
    for key, value in editorial.items():
        require(re.fullmatch(r'[1-9]\d*', key) and key not in sources, 'Duplicate/invalid source key: '+key)
        sources[key] = value
    for key, value in sources.items():
        require(isinstance(value, dict) and isinstance(value.get('name'), str) and value['name'].strip(), 'Missing source name: '+key)
        require(value.get('kind') in ('connector', 'web', 'fixture'), 'Invalid source kind: '+key)
        require(value['kind'] != 'fixture' or example, 'Fixture sources are forbidden in a live report')
        if value.get('url'):
            parsed = urlsplit(value['url'])
            require(parsed.scheme == 'https' and parsed.netloc and not parsed.username, 'Source URL must be public HTTPS')
        elif value['kind'] == 'web':
            raise ValueError('Web source needs its exact URL: '+key)
    return sources


def citations(ids, sources):
    require(isinstance(ids, list) and ids and all(str(k) in sources for k in ids), 'Missing/unmapped source reference')
    return ' '.join('['+str(k)+']' for k in dict.fromkeys(ids))


def risk_rows(metrics, editorial, sources):
    from risk_context import risk_badge
    result, notes = [], []
    cfg, report = metrics['plan']['config'], metrics['plan']['report_date']
    supplied = editorial.get('risk', {})
    require(set(supplied).issubset(cfg['risk']), 'Unknown risk indicator')
    for slot, spec in cfg['risk'].items():
        item = supplied.get(slot, {})
        if item.get('use_etf_proxy'):
            require(slot != 'vix' and item.get('reason'), 'ETF fallback requires a reason and cannot replace VIX')
            q = metrics['equities'][spec['proxy']]
            if q['status'] == 'ok':
                item = {'instrument': spec['proxy'], 'level': q['close'], 'prior_level': q['prior_close'],
                        'date': q['date'], 'prior_date': q['prior_date'], 'source_ids': ['1'], 'cutoff': 'US equity close'}
            else:
                item = {}
        if not item or item.get('status') == 'unavailable':
            result.append({'cells': [spec['name']+' · unavailable', 'Unavailable', 'Unavailable']})
            continue
        instrument = item['instrument']
        proxy = instrument == spec.get('proxy')
        require(instrument == spec['preferred'] or proxy or (slot == 'vix' and instrument == 'VIX'), 'Unsupported/mislabelled risk instrument')
        require(item.get('prior_instrument', instrument) == instrument, 'Do not compare different instruments/contracts')
        require(item.get('cutoff') and item.get('prior_cutoff', item['cutoff']) == item['cutoff'], 'Inconsistent risk observation cutoff')
        day, prior_day = iso_date(item['date']), iso_date(item['prior_date'])
        require(prior_day < day <= iso_date(report), 'Invalid risk comparison dates')
        current, prior = number(item['level'], slot, True), number(item['prior_level'], slot, True)
        unit = 'USD/share' if proxy else spec['unit']
        require(item.get('unit', unit) == unit, 'Incorrect risk unit')
        label = spec['name']+' · '+instrument+' ETF proxy' if proxy else instrument
        refs = citations(item['source_ids'], sources)
        delta = fmt(current-prior, signed=True)+' pts' if slot == 'vix' else fmt((current/prior-1)*100, signed=True)+'%'
        result.append({'cells': [label+' '+refs, fmt(current)+' '+unit, delta], 'context': risk_badge(slot, item)})
        notes.append(spec['name']+': '+day.isoformat()+' vs '+prior_day.isoformat()+'; '+item['cutoff'])
    return result, notes


def event_rows(plan, editorial, sources):
    rows, seen = [], set()
    events = editorial.get('upcoming', [])
    require(isinstance(events, list) and len(events) <= 3, 'Use at most three upcoming events')
    lower = (datetime.combine(iso_date(plan['report_date'])+timedelta(days=1), time(), NY)
             if plan['mode'] == 'historical' else instant(plan['as_of']))
    for item in events:
        if item.get('at'):
            at = instant(item['at'])
            zone = ZoneInfo(item['timezone'])
            require(at.astimezone(zone).replace(tzinfo=None) == at.replace(tzinfo=None), 'Event offset disagrees with its IANA timezone')
            require(at > lower and at.astimezone(NY).date().isoformat() >= plan['next_session'], 'Event is already past or precedes the next session')
            hkt = at.astimezone(HK).strftime('%d %b %Y\n%H:%M')
            label, key = item['event'], (item['event'], at.isoformat())
        else:
            day = iso_date(item['date'])
            require(item.get('timezone') == 'America/New_York', 'Uncertain event timing must retain its US/Eastern source date')
            require(day.isoformat() >= plan['next_session'] and item.get('timing') in ('before market', 'after close', 'time unconfirmed'), 'Invalid uncertain event timing')
            require(day >= lower.astimezone(NY).date(), 'Event is already past')
            hkt = 'HKT time TBD'
            label = item['event']+' · '+day.isoformat()+' ET; '+item['timing']
            key = item['event'], day.isoformat()
        require(key not in seen, 'Duplicate upcoming event')
        seen.add(key)
        rows.append({'hkt': hkt, 'event': label+' '+citations(item['source_ids'], sources), 'watch': item['watch']})
    if not rows and editorial.get('calendar_checked_none'):
        return [{'hkt': '—', 'event': 'No major next-session events verified '+citations(editorial['calendar_source_ids'], sources),
                 'watch': 'Verified calendars quiet'}]
    return rows or [{'hkt': '—', 'event': 'No upcoming events verified', 'watch': 'Calendar verification incomplete'}]


def compose(metrics, editorial):
    # Recompute from preserved observations; edited derived metrics cannot bypass checks.
    require(metrics == normalize(metrics['plan'], metrics['inputs']['equities'], metrics['inputs']['treasuries'], metrics['sources']['2'], metrics['sources']['1']),
            'Metrics were edited after normalization; rebuild from the preserved observations')
    plan, cfg = metrics['plan'], metrics['plan']['config']
    sources = checked_sources(metrics['sources'], editorial.get('sources', {}), plan['example'])
    equities = []
    for ticker, name in cfg['equities'].items():
        row = metrics['equities'][ticker]
        cells = [ticker+' · '+name+' [1]', 'Unavailable', 'Unavailable']
        tone = 'neutral'
        if row['status'] == 'ok':
            cells[1] = '$'+fmt(row['close'])
            cells[2] = ('+' if row['change'] >= 0 else '−')+'$'+fmt(abs(row['change']))+' / '+fmt(row['change_pct'], signed=True)+'%'
            tone = 'up' if row['change'] > 0 else 'down' if row['change'] < 0 else 'neutral'
        equities.append({'cells': cells, 'tone': tone})
    yields, yield_notes = [], []
    for label, row in metrics['yields'].items():
        cells = [label+' [2]', 'Unavailable', 'Unavailable']
        if row['status'] != 'unavailable':
            cells[1:] = [fmt(row['level'])+'%', fmt(row['change_bp'], places=1, signed=True)+' bp']
            yield_notes.append(label+' '+row['date']+' vs '+row['prior_date'])
        yields.append({'cells': cells, 'tone': 'neutral'})
    rsp, spy = metrics['equities'][cfg['participation_proxy']], metrics['equities']['SPY']
    breadth = ['Participation proxy unavailable. [1]']
    if rsp['status'] == spy['status'] == 'ok':
        breadth = ['Equal-weight RSP '+fmt(rsp['change_pct'], signed=True)+'% vs SPY '+fmt(spy['change_pct'], signed=True)+'%. [1]',
                   'Participation proxy gap: '+fmt(number(rsp['change_pct'], 'RSP')-number(spy['change_pct'], 'SPY'), signed=True)+' pp; not advance/decline breadth.']
    if editorial.get('breadth'):
        b = editorial['breadth']
        require(b['date'] == plan['equity_session'] and b.get('complete') is True and b.get('universe'), 'Breadth needs a complete named universe and matching date')
        counts = [number(b[k], k) for k in ('advancing', 'declining', 'unchanged', 'total')]
        require(all(n >= 0 and n == n.to_integral_value() for n in counts) and sum(counts[:3]) == counts[3] and counts[3] > 0, 'Invalid breadth denominator/counts')
        breadth = [f"{b['universe']}: {int(counts[0])} up / {int(counts[1])} down / {int(counts[2])} unchanged. "+citations(b['source_ids'], sources),
                   fmt(counts[0]/counts[3]*100)+'% advancing; denominator includes unchanged issues.']
    available = [metrics['equities'][t] for t in cfg['sectors'] if metrics['equities'][t]['status'] == 'ok']
    ordered = sorted(available, key=lambda r: (-r['change_pct'], r['ticker']))
    def sector(row):
        return cfg['sectors'][row['ticker']]+' ('+row['ticker']+') '+fmt(row['change_pct'], signed=True)+'% [1]'
    coverage = 'All 11 sector ETF proxies. [1]' if len(ordered) == 11 else f'Among {len(ordered)}/11 sector ETF proxies checked; incomplete coverage. [1]'
    sectors = {'leader': sector(ordered[0]) if ordered else 'Unavailable',
               'laggard': sector(ordered[-1]) if ordered else 'Unavailable', 'coverage': coverage}
    if ordered:
        for label, edge in [('leader', ordered[0]), ('laggard', ordered[-1])]:
            tied = [r['ticker'] for r in ordered if r['change_pct'] == edge['change_pct']]
            if len(tied) > 1:
                sectors[label] += ' (tied)'
    risk, risk_notes = risk_rows(metrics, editorial, sources)
    from risk_context import fear_greed
    sentiment = fear_greed(editorial.get('fear_greed'), plan, lambda ids: citations(ids, sources))
    news = []
    require(isinstance(editorial.get('news', []), list) and len(editorial.get('news', [])) <= 2, 'Use at most two past news items')
    for item in editorial.get('news', []):
        require(item['date'] == plan['report_date'], 'News must belong to the target US calendar day')
        row = {'text': item['text']+' '+citations(item['source_ids'], sources), 'sentiment': item['sentiment']}
        if item.get('label'):
            row['label'] = item['label']
        news.append(row)
    if not news and editorial.get('news_checked_none'):
        news = [{'text': 'No major target-day events verified. '+citations(editorial['news_source_ids'], sources), 'sentiment': 'neutral'}]
    news = news or [{'text': 'No major target-day events verified; news verification incomplete.', 'sentiment': 'neutral'}]
    note = 'Equities: '+plan['equity_session']+' vs '+plan['equity_prior_session']+'.'
    if plan['market_closed']:
        note += ' Target day closed; latest completed session shown.'
    elif plan['target_not_complete']:
        note += ' Target session incomplete; latest completed session shown.'
    # Dates/cutoffs remain in the PNG even when they differ from equity closes.
    footer = ['Yields: '+'; '.join(yield_notes)+'.' if yield_notes else 'Treasury yields unavailable.']
    if risk_notes:
        footer.append(' | '.join(risk_notes))
    footer.append('Sources: '+'; '.join('['+k+'] '+v['name'] for k,v in sources.items()))
    footer.append('As of '+instant(plan['as_of']).astimezone(HK).strftime('%Y-%m-%d %H:%M HKT'))
    if plan['example']:
        footer.append('FICTIONAL TEST · Sample values and events; not a market report.')
    snapshot = {'schema_version': 3, 'example': plan['example'], 'report_date': plan['report_date']+' · US/EASTERN'+(' · FICTIONAL TEST' if plan['example'] else ''),
                'headline': editorial['headline'], 'interpretation': editorial['interpretation'], 'session_note': note,
                'equities': equities, 'yields': yields, 'breadth': breadth, 'sectors': sectors, 'risk': risk,
                'fear_greed': sentiment, 'news': news, 'upcoming': event_rows(plan, editorial, sources), 'footer': footer, 'sources': sources,
                'data_warnings': metrics['warnings']}
    # Import lazily: planning and numeric processing need only the standard library.
    from render_snapshot import validate
    validate(snapshot)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan', help='Emit date-specific connector requests and SQL')
    p.add_argument('--date', help='Explicit historical US report date; omit for HKT yesterday')
    p.add_argument('--as-of', default=None, help='Offset-aware retrieval cutoff; defaults to now')
    p.add_argument('--calendar'); p.add_argument('--config'); p.add_argument('--example', action='store_true')
    p.add_argument('--output', required=True); p.add_argument('--sql-output', required=True)
    p = sub.add_parser('normalize', help='Validate saved connector results; print required follow-ups')
    for key in ('plan','equities','treasuries','output'):
        p.add_argument('--'+key, required=True)
    p.add_argument('--treasury-source', help='Metadata JSON for one consistent fallback source/series')
    p.add_argument('--equity-source', help='Metadata JSON when all equity comparisons use a named fallback')
    p = sub.add_parser('compose', help='Merge validated data and sourced editorial input')
    for key in ('metrics','editorial','output'):
        p.add_argument('--'+key, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            result = make_plan(args.as_of or datetime.now(timezone.utc).isoformat(), args.date,
                               read_json(args.config) if args.config else None,
                               read_json(args.calendar) if args.calendar else None, args.example)
            write_json(args.output, result)
            sql_path = Path(args.sql_output); sql_path.parent.mkdir(parents=True, exist_ok=True)
            sql_path.write_text(render_sql(result), encoding='utf-8')
        elif args.command == 'normalize':
            result = normalize(read_json(args.plan), rows_from_file(args.equities, ('ticker','current_close','prior_close','current_count','prior_count')),
                               rows_from_file(args.treasuries, ('date',)),
                               read_json(args.treasury_source) if args.treasury_source else None,
                               read_json(args.equity_source) if args.equity_source else None)
            write_json(args.output, result)
            for warning in result['warnings']:
                print('FOLLOW-UP: '+warning, file=sys.stderr)
        else:
            result = compose(read_json(args.metrics), read_json(args.editorial))
            write_json(args.output, result)
        print(json.dumps({'output': str(Path(args.output).resolve()), 'command': args.command}))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, 'ERROR: '+str(exc)+'\n')


if __name__ == '__main__':
    main()
