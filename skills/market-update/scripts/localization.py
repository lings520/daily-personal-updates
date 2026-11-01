"""Hash-bound Simplified Chinese display translations; never recompute market facts."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
UI_PATH = ROOT/'config/zh-Hans.json'
UI = json.loads(UI_PATH.read_text())
CJK = re.compile(r'[\u3400-\u9fff]')
# Preserve ordered numeric tokens (including source markers), signs and units.
TOKENS = re.compile(r'[<>≤≥]|\[\d+\]|\b(?:SPY|QQQ|RSP|VIX|DXY|UUP|USO|GLD|CNN|HKT|USD|WTI|XL[A-Z]+|2Y|10Y|30Y|bp|bps|pts|pp)\b|[+−-]?\$?(?:\d+(?:[,.]\d+)*)(?:%)?')


def tokens(value):
    from datetime import datetime
    value=re.sub(r'\b\d{2} [A-Z][a-z]{2} \d{4}\b',lambda m:datetime.strptime(m[0],'%d %b %Y').strftime('%Y-%m-%d'),value)
    return TOKENS.findall(value)


def tokens(value):
    from datetime import datetime
    value=re.sub(r'\b\d{2} [A-Z][a-z]{2} \d{4}\b',lambda m:datetime.strptime(m[0],'%d %b %Y').strftime('%Y-%m-%d'),value)
    return TOKENS.findall(value)


def signature(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def display_strings(d):
    values=[d[k] for k in ('report_date','headline','interpretation','session_note')]
    for key in ('equities','yields','risk'):
        for row in d[key]:
            values.extend(row['cells'])
            if row.get('context'):values.append(row['context']['label'])
    values.extend(d['breadth']);values.extend(d['sectors'].values());values.extend(d['footer'])
    for row in d['news']:
        values.append(row['text'])
        if row.get('label'):values.append(row['label'])
    for row in d['upcoming']:values.extend(row[k] for k in ('hkt','event','watch'))
    for k in ('title','rating','change','note'):
        if k in d.get('fear_greed',{}):values.append(d['fear_greed'][k])
    from risk_context import reference_legend
    values.append(reference_legend(d.get('risk_configuration')))
    values.append('P = percentile of absolute move vs '+str(d['risk_configuration']['lookback_returns'])+' prior returns; unavailable if insufficient.')
    return sorted(set(values))


def template(snapshot):
    def initial(s):
        if s in UI:return UI[s]
        # Pure numeric/ticker/date labels can stay identical. All prose must be translated.
        rest=TOKENS.sub('',s)
        return s if not re.search('[a-zA-Z]',rest) else ''
    return {'locale':'zh-Hans','source_sha256':signature(snapshot),
            'translations':{s:initial(s) for s in display_strings(snapshot)}}


def validate(snapshot,document):
    if document.get('locale')!='zh-Hans':raise ValueError('Only Simplified Chinese (zh-Hans) is supported')
    if document.get('source_sha256')!=signature(snapshot):raise ValueError('Translation is stale; regenerate against current snapshot')
    translations=document.get('translations',{})
    if set(translations)!=set(display_strings(snapshot)):raise ValueError('Translation must cover exactly every display string')
    for source,target in translations.items():
        if not isinstance(target,str) or not target.strip():raise ValueError('Missing translation: '+source)
        if tokens(source)!=tokens(target):raise ValueError('Translation changed numbers, tickers, units or citations: '+source)
        if re.search('[a-zA-Z]',TOKENS.sub('',source)) and not CJK.search(target) and not re.fullmatch(r'\d{2} [A-Z][a-z]{2} \d{4}\n\d{2}:\d{2}',source):
            raise ValueError('Translate prose into Simplified Chinese: '+source)
    if len(translations[snapshot['headline']])+len(translations[snapshot['interpretation']])>140:
        raise ValueError('Keep Chinese headline and interpretation within 140 characters combined')
    return {**UI,**translations}


def chinese_fonts(directory):
    directory=Path(directory).resolve()
    paths={k:directory/n for k,n in [('regular','NotoSansCJKsc-Regular.otf'),('bold','NotoSerifCJKsc-Bold.otf')]}
    specs=json.loads((ROOT/'config/chinese-fonts.json').read_text())
    for spec in specs:
        p=directory/spec['name']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=spec['sha256']:
            raise ValueError('Missing or changed approved Chinese font; run install_chinese_fonts.py: '+str(p))
    return {k:str(v) for k,v in paths.items()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot');parser.add_argument('output')
    args=parser.parse_args()
    Path(args.output).write_text(json.dumps(template(json.loads(Path(args.snapshot).read_text())),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
