"""Deterministic sentiment and risk context; never accepts authored percentiles."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from settings import load as load_settings, validate as validate_settings


def check(ok, message):
    if not ok:
        raise ValueError(message)


def num(value):
    check(value is not None and not isinstance(value, bool), 'Expected numeric observation')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Expected numeric observation') from exc
    check(result.is_finite(), 'Nonfinite observation')
    return result


def risk_badge(slot, item, config=None):
    config = config or load_settings('risk-context')
    validate_settings('risk-context', config)
    lookback = config['lookback_returns']
    a,b,c = config['vix_bounds']
    low,high = config['move_percentile_bounds']
    check('percentile' not in item, 'Supply raw history, not an authored percentile')
    if slot == 'vix':
        v = num(item['level'])
        label, tone = ('SUBDUED','mint') if v < a else ('MODERATE','lavender') if v < b else ('ELEVATED','peach') if v < c else ('HIGH','rose')
        return {'label': label, 'tone': tone}
    h = item.get('history')
    unavailable = {'label': 'UNAVAILABLE', 'tone': 'muted'}
    if not h:
        return unavailable
    check(h.get('instrument') == item['instrument'] and h.get('cutoff') == item['cutoff'], 'History instrument/cutoff mismatch')
    check(h.get('source_ids') == item['source_ids'], 'History must use the same source as the daily comparison')
    check(h.get('complete') is True, 'History completeness must be verified')
    rows = h.get('observations', [])
    check(isinstance(rows, list), 'History observations must be a list')
    dates = [date.fromisoformat(r['date']) for r in rows]
    levels = [num(r['level']) for r in rows]
    check(all(v > 0 for v in levels), 'History levels must be positive')
    check(dates == sorted(set(dates)), 'History dates must be unique and ascending')
    prior = date.fromisoformat(item['prior_date'])
    check(all(d <= prior for d in dates), 'History contains current/future observations')
    if rows:
        check(dates[-1] == prior and levels[-1] == num(item['prior_level']), 'History must end at the matching prior observation')
    if len(rows) < lookback+1:
        return unavailable
    levels = levels[-(lookback+1):]
    changes = [abs(b/a-1) for a,b in zip(levels,levels[1:])]
    current = abs(num(item['level'])/num(item['prior_level'])-1)
    # Midrank handles ties without declaring a zero move extreme in a flat series.
    percentile = (sum(v < current for v in changes) + Decimal('0.5')*sum(v == current for v in changes))*100/lookback
    label,tone = ('TYPICAL','lavender') if percentile < low else ('LARGE','peach') if percentile < high else ('EXTREME','rose')
    return {'label': label+' · P'+str(int(percentile.quantize(Decimal('1')))), 'tone': tone,
            'percentile': float(percentile), 'lookback_returns': lookback}


def fear_greed(item, plan, cite):
    if not item or item.get('status') == 'unavailable':
        return {'status':'unavailable', 'title':'CNN FEAR & GREED', 'note':'Target-date score unavailable'}
    check(not item.get('illustrative') or plan['example'], 'Illustrative sentiment forbidden in a live report')
    check(item.get('publisher') == 'CNN', 'Use the CNN US equity sentiment index')
    score = num(item['score'])
    check(0 <= score <= 100, 'Fear & Greed score outside 0–100')
    rating = item['rating'].lower()
    check(rating in ('extreme fear','fear','neutral','greed','extreme greed'), 'Invalid published sentiment label')
    at = datetime.fromisoformat(item['observed_at'].replace('Z','+00:00'))
    check(at.tzinfo is not None, 'Sentiment observation needs a timezone')
    day = at.astimezone(ZoneInfo('America/New_York')).date()
    check(day.isoformat() == item['date'] and day.isoformat() <= plan['report_date'], 'Invalid sentiment observation date')
    asof = datetime.fromisoformat(plan['as_of'].replace('Z','+00:00'))
    check(at <= asof, 'Sentiment observation is after retrieval')
    check(isinstance(item.get('cutoff'), str) and item['cutoff'].strip(), 'Sentiment cutoff required')
    change = 'Daily change unavailable'
    note = at.strftime('%Y-%m-%d %H:%M %z')+' · '+item['cutoff']
    if day.isoformat() != plan['report_date']:
        note = 'STALE · '+note
    if item.get('prior_score') is not None:
        prior = num(item['prior_score'])
        check(0 <= prior <= 100 and date.fromisoformat(item['prior_date']) < day, 'Invalid sentiment prior observation')
        check(item.get('prior_cutoff') == item['cutoff'], 'Sentiment cutoff mismatch')
        change = f'{score-prior:+.1f} pts vs '+item['prior_date']
    return {'status':'ok','title':'CNN FEAR & GREED '+cite(item['source_ids']),
            'score':float(score),'rating':rating.upper(),'change':change,'note':note}


def reference_legend(config=None):
    config = config or load_settings('risk-context')
    a,b,c = config['vix_bounds'];low,high = config['move_percentile_bounds']
    return (f'VIX: <{a} subdued; {a}–<{b} moderate; {b}–<{c} elevated; ≥{c} high.\n'
            f'P: <{low} typical; {low}–<{high} large; ≥{high} extreme. Display conventions, not trade signals.')
