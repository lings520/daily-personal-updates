#!/usr/bin/env python3
"""Render a verified market payload in the approved dreamy layout; see image-format.md."""
import argparse
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, M = 1200, 3600, 48
CW = W - 2*M
INK, MUTED, PURPLE = '#27334F', '#5C6580', '#7662A0'
RED, GREEN, CITATION = '#AE455C', '#287968', '#7D7892'
CITE = re.compile(r'(\[\d+\])')
SENTIMENT = {
    'negative': ('ADVERSE', '#FCEDF1', '#F2CDDA', RED),
    'positive': ('SUPPORTIVE', '#EDF8F2', '#D6EFE4', GREEN),
    'neutral': ('NEUTRAL', '#EEEAF9', '#DCD3EF', PURPLE),
    'mixed': ('MIXED', '#EEEAF9', '#DCD3EF', PURPLE),
}


def resolve_font(explicit, kind):
    if explicit:
        return explicit
    names = {
        'regular': ['dejavu/DejaVuSans.ttf', 'liberation2/LiberationSans-Regular.ttf'],
        'bold': ['dejavu/DejaVuSans-Bold.ttf', 'liberation2/LiberationSans-Bold.ttf'],
        'mono': ['dejavu/DejaVuSansMono.ttf', 'liberation2/LiberationMono-Regular.ttf'],
    }
    for relative in names[kind]:
        path = Path('/usr/share/fonts/truetype') / relative
        if path.exists():
            return str(path)
    raise ValueError(f'Supply --font-{kind} with an available TrueType font path.')


class Renderer:
    def __init__(self, regular, bold, mono):
        self.paths = regular, bold, mono
        self.fonts = {}
        # Soft sky/lavender light with mint and blush accents, behind readable cards.
        bg = Image.new('RGBA', (300, 900), '#F6F6FD')
        for bbox, color in [((-80,-100,200,250),(218,205,245,145)),
                            ((120,20,440,400),(195,225,245,145)),
                            ((-120,300,180,700),(204,236,222,120)),
                            ((100,520,420,940),(246,207,222,140))]:
            mask = Image.new('L', bg.size, 0)
            ImageDraw.Draw(mask).ellipse(bbox, fill=color[3])
            layer = Image.new('RGBA', bg.size, color[:3]+(255,))
            layer.putalpha(mask.filter(ImageFilter.GaussianBlur(50)))
            bg.alpha_composite(layer)
        self.im = bg.resize((W,H), Image.Resampling.LANCZOS)
        self.draw = ImageDraw.Draw(self.im)
        self.y = 42

    def font(self, n, bold=False, mono=False):
        key = n, bold, mono
        if key not in self.fonts:
            self.fonts[key] = ImageFont.truetype(self.paths[2 if mono else 1 if bold else 0], n)
        return self.fonts[key]

    def runs(self, value, n, bold=False, mono=False):
        if mono:
            return [(value, self.font(n, bold, mono), False)]
        return [(part, self.font(max(14,min(19,round(n*.60))), mono=True) if CITE.fullmatch(part) else self.font(n,bold), bool(CITE.fullmatch(part)))
                for part in CITE.split(value) if part]

    def width(self, value, n, bold=False, mono=False):
        return sum(self.draw.textlength(part,font=f) for part,f,_ in self.runs(value,n,bold,mono))

    def lines(self, value, width, n=27, bold=False, mono=False):
        result = []
        for paragraph in value.split('\n'):
            line = ''
            # Keep a source marker with the word it follows, never alone on a line.
            for word in re.findall(r'\S+(?:[ \t]+\[\d+\])*', paragraph):
                if self.width(word,n,bold,mono) > width:
                    raise ValueError('Shorten an unbreakable label: '+word)
                trial = (line+' '+word).strip()
                if line and self.width(trial,n,bold,mono) > width:
                    result.append(line)
                    line = word
                else:
                    line = trial
            result.append(line)
        return result

    def height(self, value, width, n=27, bold=False, mono=False):
        return len(self.lines(value,width,n,bold,mono))*round(n*1.35)

    def text(self, value, x, y, width, n=27, bold=False, color=INK, mono=False):
        step = round(n*1.35)
        wrapped = self.lines(value,width,n,bold,mono)
        ascent = self.font(n,bold,mono).getmetrics()[0]
        for i,line in enumerate(wrapped):
            cursor, baseline = x, y+i*step+ascent
            for part,f,is_cite in self.runs(line,n,bold,mono):
                yy = baseline-round(n*.32) if is_cite else baseline
                self.draw.text((cursor,yy),part,font=f,fill=CITATION if is_cite else color,anchor='ls')
                cursor += self.draw.textlength(part,font=f)
        return len(wrapped)*step

    def card(self, y, height, fill='#FFFFFF', x=M, width=CW):
        shadow = Image.new('RGBA',self.im.size,(0,0,0,0))
        ImageDraw.Draw(shadow).rounded_rectangle((x,y+5,x+width,y+height+5),22,fill=(71,56,112,19))
        self.im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(9)))
        self.draw.rounded_rectangle((x,y,x+width,y+height),22,fill=fill,outline='#E6E0EF',width=1)

    def section(self, label):
        self.draw.rounded_rectangle((M,self.y+7,M+7,self.y+30),3,fill=PURPLE)
        self.y += self.text(label,M+20,self.y,CW-20,25,True,PURPLE)+12

    def pill(self, label, x, y, fill, color, max_width=CW-52):
        width = round(self.width(label,21,True))+34
        if width > max_width:
            raise ValueError('Shorten sentiment label: '+label)
        self.draw.rounded_rectangle((x,y,x+width,y+36),18,fill=fill)
        self.text(label,x+14,y+3,width-28,21,True,color)
        return width

    def metric_cards(self, title, rows, sizes, fill, currency=False):
        self.section(title)
        gap, count = 20 if len(rows)==2 else 16, len(rows)
        width = (CW-(count-1)*gap)//count
        inner = width-44
        labels = max(self.height(r['cells'][0],inner,sizes[0],True) for r in rows)
        values = max(self.height(r['cells'][1],inner,sizes[1],True) for r in rows)
        changes = max(self.height(r['cells'][2],inner,sizes[2],True) for r in rows)
        height = 18+labels+10+values+8+changes+18
        for i,row in enumerate(rows):
            x = M+i*(width+gap)
            self.card(self.y,height,fill,x,width)
            self.text(row['cells'][0],x+22,self.y+18,inner,sizes[0],True,PURPLE if count==3 else INK)
            value = row['cells'][1]
            if currency and not value.startswith('$') and re.fullmatch(r'[\d,.]+',value):
                value='$'+value
            self.text(value,x+22,self.y+28+labels,inner,sizes[1],True)
            color={'up':GREEN,'down':RED,'neutral':MUTED}[row.get('tone','neutral')]
            self.text(row['cells'][2],x+22,self.y+36+labels+values,inner,sizes[2],True,color)
        self.y += height+22

    def breadth(self, data):
        self.section('BREADTH & SECTORS')
        heights=[self.height(t,CW-48,27) for t in data['breadth']]
        sectors=data['sectors']
        half=(CW-64)//2
        sector_height=max(self.height(sectors[k],half-28,25,True) for k in ['leader','laggard'])
        height=24+sum(heights)+10*len(heights)+56+sector_height+12+self.height(sectors['coverage'],CW-48,21)+18
        self.card(self.y,height,'#F5FCF9')
        y=self.y+18
        for i,t in enumerate(data['breadth']):
            y+=self.text(t,M+24,y,CW-48,27,i==0,INK if i==0 else MUTED)+10
        for i,(key,label,fill,ink) in enumerate([('leader','LEADER','#D6EFE4',GREEN),('laggard','LAGGARD','#F8DDE5',RED)]):
            x=M+24+i*(half+16)
            self.pill(label,x,y,fill,ink,half)
            self.text(sectors[key],x,y+44,half,25,True,ink)
        y+=44+sector_height+12
        self.text(sectors['coverage'],M+24,y,CW-48,21,False,MUTED)
        self.y+=height+22

    def table(self,title,headers,rows,widths):
        self.section(title)
        header_height=max(self.height(h,w-16,23,True) for h,w in zip(headers,widths))+30
        row_heights=[max(self.height(t,w-20,27,i==0) for i,(t,w) in enumerate(zip(row,widths)))+24 for row in rows]
        height=header_height+sum(row_heights)+18
        self.card(self.y,height,'#F8F5FF')
        self.draw.rounded_rectangle((M+1,self.y+1,W-M-1,self.y+header_height),21,fill='#DFD8F0')
        self.draw.rectangle((M+1,self.y+header_height-20,W-M-1,self.y+header_height),fill='#DFD8F0')
        x=M+24
        for h,w in zip(headers,widths):
            self.text(h,x,self.y+14,w-16,23,True,PURPLE);x+=w
        y=self.y+header_height+10
        for row,rh in zip(rows,row_heights):
            x=M+24
            for i,(t,w) in enumerate(zip(row,widths)):
                self.text(t,x,y,w-20,27,i==0,PURPLE if i==0 and title.startswith('WHAT TO WATCH') else INK);x+=w
            y+=rh
            self.draw.line((M+24,y-9,W-M-24,y-9),fill='#E3DFEC',width=1)
        self.y+=height+22

    def render(self,data,output,preview=None):
        self.y+=self.text('THE MORNING MARKET',M,self.y,CW,26,True,PURPLE)+12
        self.y+=self.text(data['report_date'],M,self.y,CW,24,False,MUTED)+20
        self.y+=self.text(data['headline'],M,self.y,CW,46,True)+22
        h=self.height(data['interpretation'],CW-52,30)+78
        self.card(self.y,h,'#EAE4F6')
        self.text('THE READ · INTERPRETATION',M+26,self.y+18,CW-52,22,True,PURPLE)
        self.text(data['interpretation'],M+26,self.y+58,CW-52,30)
        self.y+=h+22
        self.y+=self.text(data['session_note'],M,self.y,CW,23,False,MUTED)+24
        self.metric_cards('US EQUITIES',data['equities'],(25,44,29),'#FFF8FA',True)
        self.metric_cards('TREASURY YIELDS',data['yields'],(24,39,25),'#F3F0FC')
        self.breadth(data)
        self.table('RISK INDICATORS',['Benchmark','Level','Daily change'],[r['cells'] for r in data['risk']],[436,334,286])
        self.section('WHAT HAPPENED')
        for item in data['news']:
            label,fill,chip,ink=SENTIMENT[item['sentiment']]
            h=76+self.height(item['text'],CW-52,29)
            self.card(self.y,h,fill)
            self.pill(item.get('label') or label,M+26,self.y+17,chip,ink)
            self.text(item['text'],M+26,self.y+68,CW-52,29)
            self.y+=h+16
        self.y+=8
        self.table('WHAT TO WATCH NEXT · HKT',['HKT date/time','Event','What to watch'],[[r['hkt'],r['event'],r['watch']] for r in data['upcoming']],[230,536,290])
        for note in data['footer']:
            self.y+=self.text(note,M+4,self.y,CW-8,19,False,'#73758B',True)+6
        self.y+=26
        if self.y>3200:
            raise ValueError(f'Image too tall ({self.y}px): shorten copy without dropping dates, units, or material caveats. Do not shrink fonts.')
        final=self.im.crop((0,0,W,self.y)).convert('RGB')
        output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
        final.save(output,'PNG')
        if preview:
            p=Path(preview);p.parent.mkdir(parents=True,exist_ok=True)
            final.resize((600,round(self.y/2)),Image.Resampling.LANCZOS).save(p,'PNG')
        print(json.dumps({'output':str(output.resolve()),'width':W,'height':self.y}))


def validate(data):
    def string(value,name):
        if not isinstance(value,str) or not value.strip():
            raise ValueError(name+' must be a nonempty string')
    for key in ['report_date','headline','interpretation','session_note']:
        string(data.get(key),key)
    if len((data['headline']+' '+data['interpretation']).split())>40:
        raise ValueError('Headline and interpretation must be at most 40 words combined')
    for key,count in [('equities',2),('yields',3),('risk',4)]:
        rows=data.get(key)
        if not isinstance(rows,list) or len(rows)!=count:
            raise ValueError(f'{key} requires {count} rows, including unavailable entries')
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('cells'),list) or len(row['cells'])!=3:
                raise ValueError(key+' requires three display strings per row')
            for cell in row['cells']:string(cell,key)
            if row.get('tone','neutral') not in ['up','down','neutral']:
                raise ValueError('Invalid numeric tone')
    for key,maximum in [('breadth',2),('footer',5)]:
        if not isinstance(data.get(key),list) or not 1<=len(data[key])<=maximum:
            raise ValueError(f'{key} requires 1–{maximum} strings')
        for item in data[key]:string(item,key)
    if not isinstance(data.get('sectors'),dict):raise ValueError('sectors must be an object')
    for key in ['leader','laggard','coverage']:string(data['sectors'].get(key),'sectors.'+key)
    for key,maximum in [('news',2),('upcoming',3)]:
        if not isinstance(data.get(key),list) or not 1<=len(data[key])<=maximum:
            raise ValueError(f'{key} requires 1–{maximum} objects')
        if not all(isinstance(item,dict) for item in data[key]):raise ValueError(key+' requires structured objects')
    for item in data['news']:
        string(item.get('text'),'news.text')
        if item.get('sentiment') not in SENTIMENT:raise ValueError('Use positive, negative, neutral, or mixed for sentiment')
        if 'label' in item:string(item['label'],'news.label')
    for item in data['upcoming']:
        for key in ['hkt','event','watch']:string(item.get(key),'upcoming.'+key)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_json');parser.add_argument('output_png')
    parser.add_argument('--preview',help='Optional 600px-wide visual QA PNG')
    for key in ['regular','bold','mono']:parser.add_argument('--font-'+key)
    args=parser.parse_args()
    data=json.loads(Path(args.input_json).read_text(encoding='utf-8'))
    validate(data)
    Renderer(*(resolve_font(getattr(args,'font_'+key),key) for key in ['regular','bold','mono'])).render(data,args.output_png,args.preview)


if __name__=='__main__':
    main()
