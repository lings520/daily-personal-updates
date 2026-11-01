"""Read and validate shared workflow configuration without network access."""
import json
import re
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / 'config'


def load(kind, path=None):
    value = json.loads(Path(path or CONFIG / (kind+'.json')).read_text())
    validate(kind, value)
    return value


def validate(kind, value):
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ValueError('Unsupported configuration version')
    if kind == 'risk-context':
        n = value['lookback_returns']
        if isinstance(n, bool) or not isinstance(n, int) or not 2 <= n <= 1260:
            raise ValueError('Invalid history lookback')
        for key, count, upper in [('vix_bounds',3,1000),('move_percentile_bounds',2,100)]:
            bounds = value[key]
            if (not isinstance(bounds,list) or len(bounds)!=count or
                any(isinstance(x,bool) or not isinstance(x,(int,float)) or not 0 < x < upper for x in bounds) or
                bounds != sorted(set(bounds))):
                raise ValueError('Invalid thresholds: '+key)
        if value.get('percentile_method') != 'midrank':
            raise ValueError('Unsupported percentile method')
    elif kind == 'visual-style':
        for paths in value['fonts'].values():
            if not isinstance(paths,list) or not paths or not all(isinstance(p,str) and p for p in paths):
                raise ValueError('Font candidates must be paths')
        if set(value['fonts']) != {'regular','bold','mono'}:
            raise ValueError('Specify regular, bold and mono fonts')
        colours = list(value['colours'].values()) + value['fear_greed']['colours']
        if any(not isinstance(c,str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}',c) for c in colours):
            raise ValueError('Invalid palette colour')
        bounds = value['fear_greed']['bounds']
        if bounds != [0,25,45,55,75,100] or len(value['fear_greed']['colours']) != 5:
            raise ValueError('Preserve the five labelled sentiment gauge segments')
    else:
        raise ValueError('Unknown configuration: '+kind)
