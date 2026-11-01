#!/usr/bin/env python3
"""One resumable entry point. Network research and delivery remain with the assistant."""
import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import prepare_market_data as data
from settings import load as load_settings

HERE = Path(__file__).resolve().parent
STAGES = ('plan','collection','normalize','research','compose','render','review','delivery')
EXTERNAL = ('collection','research','review','delivery')
SLOTS = ('equities','treasuries','equity-source','treasury-source','editorial')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.tmp')
    temp.write_bytes(content if isinstance(content,bytes) else content.encode())
    os.replace(temp,path)


def save(path, value):
    atomic(path,json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def initialize(directory, report_date=None, as_of=None, example=False, style=None, risk=None):
    directory = Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Use a new empty run directory; existing runs are resumed, never reinitialized')
    # Validate before creating files; explicit as-of is for reproducible fixtures only.
    plan = data.make_plan(as_of or now(), report_date, example=example)
    styles = load_settings('visual-style',style)
    risks = load_settings('risk-context',risk)
    directory.mkdir(parents=True, exist_ok=True)
    save(directory/'plan.json',plan)
    atomic(directory/'equity-returns.sql',data.render_sql(plan))
    save(directory/'config/visual-style.json',styles)
    save(directory/'config/risk-context.json',risks)
    created = now()
    manifest = {'version':1,'created_at':created,'updated_at':created,'inputs':{},'events':[],
                'plan_sha256':digest(directory/'plan.json'),'stages':{s:{'status':'pending','attempts':[]} for s in STAGES}}
    manifest['stages']['plan']['status']='complete'
    manifest['stages']['collection'].update(status='waiting',started_at=created)
    save(directory/'run.json',manifest)
    return Workflow(directory).status()


class Workflow:
    def __init__(self,directory):
        self.directory=Path(directory).resolve()
        self.state=data.read_json(self.directory/'run.json')
        if self.state.get('version')!=1:
            raise ValueError('Unsupported run manifest version')
        if digest(self.directory/'plan.json')!=self.state['plan_sha256']:
            raise ValueError('Run plan changed; initialize a new run for a new date')
        self.plan=data.read_json(self.directory/'plan.json')
        data.validate_plan(self.plan)

    def persist(self):
        self.state['updated_at']=now()
        save(self.directory/'run.json',self.state)

    def path(self,slot):
        record=self.state['inputs'].get(slot)
        if not record:
            return None
        path=(self.directory/record['path']).resolve()
        if not path.is_relative_to(self.directory) or digest(path)!=record['sha256']:
            raise ValueError('Registered input was modified: '+slot+'; supply a new input with put')
        return path

    def invalidate(self,stage):
        for name in STAGES[STAGES.index(stage):]:
            row=self.state['stages'][name]
            research_started=row.get('started_at') if name=='research' and row['status']=='waiting' else None
            row['status']='pending'
            for key in ('fingerprint','outputs','evidence','started_at','finished_at'):
                row.pop(key,None)
            if research_started:row['started_at']=research_started

    def begin(self,stage):
        if stage not in EXTERNAL:
            raise ValueError('Only assistant-led stages can be timed with begin')
        row=self.state['stages'][stage]
        if row['status']!='complete' and 'started_at' not in row:
            row.update(status='waiting',started_at=now())
            self.persist()

    def finish_external(self,stage,evidence=None):
        row=self.state['stages'][stage]
        if row['status']=='complete':
            return
        end=now();start=row.get('started_at',end)
        row['attempts'].append({'started_at':start,'finished_at':end,'seconds':(datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds(),'status':'complete'})
        row.update(status='complete',finished_at=end)
        if evidence is not None:
            row['evidence']=evidence
        self.persist()

    def put(self,slot,source):
        if slot not in SLOTS:
            raise ValueError('Unknown input slot')
        source=Path(source).resolve()
        if source.suffix.lower() not in ('.csv','.json'):
            raise ValueError('Inputs must be CSV or JSON')
        if slot not in ('equities','treasuries'):
            data.read_json(source)
        if slot=='editorial' and self.state['stages']['normalize']['status']!='complete':
            raise ValueError('Run numeric validation before supplying verified editorial input')
        sha=digest(source)
        existing=self.state['inputs'].get(slot)
        if existing and existing['sha256']==sha and (slot!='editorial' or existing.get('metrics_sha256')==digest(self.directory/'artifacts/metrics.json')):
            self.path(slot)
            return self.status()
        target=self.directory/'inputs'/slot/(sha+source.suffix.lower())
        atomic(target,source.read_bytes())
        self.state['inputs'][slot]={'path':str(target.relative_to(self.directory)),'sha256':sha,'supplied_at':now()}
        if slot=='editorial':
            self.state['inputs'][slot]['metrics_sha256']=digest(self.directory/'artifacts/metrics.json')
        self.state['events'].append({'action':'put','slot':slot,'sha256':sha,'at':now()})
        # Retain external stage start time until its first successful validation.
        self.invalidate('compose' if slot=='editorial' else 'normalize')
        stage='research' if slot=='editorial' else 'collection'
        if self.state['stages'][stage]['status']=='complete':
            self.state['stages'][stage]['status']='pending'
            self.state['stages'][stage].pop('started_at',None)
        self.begin(stage)
        self.persist()
        return self.status()

    def configure(self,kind,source):
        if kind not in ('visual-style','risk-context'):
            raise ValueError('Only visual/risk settings can change within a run')
        config=load_settings(kind,source)
        path=self.directory/'config'/(kind+'.json')
        if data.read_json(path)!=config:
            save(path,config)
            self.invalidate('render' if kind=='visual-style' else 'compose')
            self.state['events'].append({'action':'configure','kind':kind,'sha256':digest(path),'at':now()})
            self.persist()

    def fingerprint(self,paths,code):
        hashes={str(p):digest(p) for p in paths if p is not None}
        hashes.update({name:digest(HERE/name) for name in code})
        return hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()

    def execute(self,stage,paths,code,outputs,operation,force=False):
        fp=self.fingerprint(paths,code)
        row=self.state['stages'][stage]
        if row['status']=='running' and row['attempts']:
            row['attempts'][-1].update(status='interrupted',finished_at=now(),timing_incomplete=True)
        intact=all((self.directory/p).exists() and digest(self.directory/p)==sha for p,sha in row.get('outputs',{}).items())
        if not force and row['status']=='complete' and row.get('fingerprint')==fp and row.get('outputs') and intact:
            return
        self.invalidate(stage)
        row=self.state['stages'][stage]
        attempt={'started_at':now(),'status':'running','fingerprint':fp}
        row['attempts'].append(attempt);row['status']='running';self.persist()
        started=time.perf_counter()
        try:
            operation()
            row.update(status='complete',fingerprint=fp,outputs={str(p.relative_to(self.directory)):digest(p) for p in outputs})
            row['dependencies']={str(p):digest(p) for p in paths if p is not None}
            row['dependencies'].update({str(HERE/name):digest(HERE/name) for name in code})
            attempt['status']='complete'
        except Exception as exc:
            row['status']='failed';attempt.update(status='failed',error=str(exc))
            raise
        finally:
            attempt.update(finished_at=now(),seconds=time.perf_counter()-started)
            self.persist()

    def run(self,rerender=False):
        paths={s:self.path(s) for s in SLOTS}
        if not paths['equities'] or not paths['treasuries']:
            self.begin('collection')
            return self.status()
        out=self.directory/'artifacts';out.mkdir(exist_ok=True)
        metrics,snapshot,png,preview=[out/n for n in ('metrics.json','snapshot.json','market-update.png','preview.png')]
        def normalize():
            result=data.normalize(self.plan,data.rows_from_file(paths['equities']),data.rows_from_file(paths['treasuries']),
                                  data.read_json(paths['treasury-source']) if paths['treasury-source'] else None,
                                  data.read_json(paths['equity-source']) if paths['equity-source'] else None)
            save(metrics,result)
        self.execute('normalize',[self.directory/'plan.json']+[paths[s] for s in SLOTS if s!='editorial'],['prepare_market_data.py'],[metrics],normalize)
        self.finish_external('collection')
        self.begin('research')
        if not paths['editorial'] or self.state['inputs']['editorial'].get('metrics_sha256')!=digest(metrics):
            return self.status()
        risk=self.directory/'config/risk-context.json'
        self.execute('compose',[metrics,paths['editorial'],risk],['prepare_market_data.py','risk_context.py','settings.py','render_snapshot.py'],[snapshot],
                     lambda:save(snapshot,data.compose(data.read_json(metrics),data.read_json(paths['editorial']),load_settings('risk-context',risk))))
        self.finish_external('research')
        style=self.directory/'config/visual-style.json'
        settings=load_settings('visual-style',style)
        # Include resolved font bytes so changed/substituted fonts invalidate visual QA.
        fonts=[]
        for candidates in settings['fonts'].values():
            fonts.append(next((Path(p) for p in candidates if Path(p).is_file()),None))
        def render():
            proc=subprocess.run([sys.executable,str(HERE/'render_snapshot.py'),str(snapshot),str(png),'--preview',str(preview),'--style',str(style)],capture_output=True,text=True)
            if proc.returncode:
                raise ValueError(proc.stderr.strip() or 'Renderer failed')
            self.state['render_warnings']=proc.stderr.strip()
        self.execute('render',[snapshot,style]+fonts,['render_snapshot.py','risk_context.py','settings.py'],[png,preview],render,rerender)
        self.begin('review')
        return self.status()

    def record(self,stage,evidence_path):
        if stage not in ('review','delivery'):
            raise ValueError('Record supports review or delivery only')
        self.run()  # Recheck hashes and dependencies before accepting an attestation.
        if self.state['stages']['render']['status']!='complete':
            raise ValueError('Render must complete first')
        evidence=data.read_json(evidence_path)
        actual=digest(self.directory/'artifacts/market-update.png')
        if evidence.get('artifact_sha256')!=actual or not evidence.get('notes'):
            raise ValueError('Evidence must identify the current PNG hash and include notes')
        if stage=='review':
            if not all(evidence.get(k) is True for k in ('full_size_checked','preview_checked','facts_checked')):
                raise ValueError('Record all three review checks only after performing them')
        else:
            if self.state['stages']['review']['status']!='complete' or not evidence.get('reference'):
                raise ValueError('Delivery requires current review and a real returned file/message reference')
        self.begin(stage)
        evidence['recorded_at']=now()
        evidence['render_fingerprint']=self.state['stages']['render']['fingerprint']
        self.finish_external(stage,evidence)
        if stage=='review':self.begin('delivery')
        return self.status()

    def status(self):
        stages=copy.deepcopy(self.state['stages'])
        for slot in self.state['inputs']:self.path(slot)
        for name in ('normalize','compose','render'):
            row=stages[name]
            files={str(self.directory/p):sha for p,sha in row.get('outputs',{}).items()}
            files.update(row.get('dependencies',{}))
            if row['status']=='complete' and any(not Path(p).exists() or digest(p)!=sha for p,sha in files.items()):
                for downstream in STAGES[STAGES.index(name):]:stages[downstream]['status']='pending'
        missing=[s for s in ('equities','treasuries','editorial') if s not in self.state['inputs']]
        metrics=self.directory/'artifacts/metrics.json'
        if stages['normalize']['status']=='complete' and 'editorial' in self.state['inputs'] and self.state['inputs']['editorial'].get('metrics_sha256')!=digest(metrics):
            missing.append('editorial (refresh against revised metrics)')
        numeric_missing=[s for s in ('equities','treasuries') if s in missing]
        next_step=('put '+', '.join(numeric_missing) if numeric_missing else
                   'run' if stages['normalize']['status']!='complete' else
                   'research and put editorial' if 'editorial' in missing else
                   'reverify and put editorial' if missing else
                   'complete' if stages['delivery']['status']=='complete' else
                   'save/display image, then record delivery' if stages['review']['status']=='complete' else
                   'inspect images, then record review' if stages['render']['status']=='complete' else 'run')
        warnings=[]
        if stages['normalize']['status']=='complete' and metrics.exists():
            warnings=data.read_json(metrics).get('warnings',[])
        result={'run_dir':str(self.directory),'report_date':self.plan['report_date'],'example':self.plan['example'],
                'next_step':next_step,'missing_inputs':missing,'warnings':warnings,'render_warnings':self.state.get('render_warnings',''),
                'stages':{k:{'status':v['status'],'attempts':len(v['attempts']),
                             'seconds':round(sum(a.get('seconds',0) for a in v['attempts']),3),
                             'last_attempt_seconds':round(v['attempts'][-1].get('seconds',0),3) if v['attempts'] else None} for k,v in stages.items()},
                'elapsed_wall_seconds':round((datetime.fromisoformat(stages['delivery']['finished_at']) if stages['delivery']['status']=='complete' else datetime.now(timezone.utc)).timestamp()-datetime.fromisoformat(self.state['created_at']).timestamp(),3),
                'timing_note':'External stages include assistant work and waits and may overlap; do not sum them as wall time. Delivery is a recorded attestation, not scheduler proof.'}
        result['timing_incomplete']=any(a.get('timing_incomplete') for v in stages.values() for a in v['attempts'])
        if stages['render']['status']=='complete':
            result.update(image=str(self.directory/'artifacts/market-update.png'),preview=str(self.directory/'artifacts/preview.png'),
                          artifact_sha256=digest(self.directory/'artifacts/market-update.png'))
            result['elapsed_to_render_seconds']=round((datetime.fromisoformat(stages['render']['attempts'][-1]['finished_at'])-datetime.fromisoformat(self.state['created_at'])).total_seconds(),3)
            first=next(a for a in stages['render']['attempts'] if a['status']=='complete')
            result['first_render_elapsed_seconds']=round((datetime.fromisoformat(first['finished_at'])-datetime.fromisoformat(self.state['created_at'])).total_seconds(),3)
        return result


@contextmanager
def locked(directory):
    with (Path(directory)/'.workflow.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Another command is updating this run') from exc
        yield


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for command in ('init','put','run','status','begin','record','configure'):
        p=sub.add_parser(command);p.add_argument('--run-dir',required=True)
        if command=='init':
            p.add_argument('--date');p.add_argument('--as-of');p.add_argument('--example',action='store_true')
            p.add_argument('--style');p.add_argument('--risk')
        if command=='put':p.add_argument('--slot',choices=SLOTS,required=True);p.add_argument('--file',required=True)
        if command=='run':p.add_argument('--rerender',action='store_true')
        if command=='begin':p.add_argument('--stage',choices=EXTERNAL,required=True)
        if command=='record':p.add_argument('--stage',choices=('review','delivery'),required=True);p.add_argument('--evidence',required=True)
        if command=='configure':p.add_argument('--kind',choices=('visual-style','risk-context'),required=True);p.add_argument('--file',required=True)
    args=parser.parse_args()
    try:
        if args.command=='init':
            result=initialize(args.run_dir,args.date,args.as_of,args.example,args.style,args.risk)
        else:
            with locked(args.run_dir):
                workflow=Workflow(args.run_dir)
                if args.command=='put':result=workflow.put(args.slot,args.file)
                elif args.command=='run':result=workflow.run(args.rerender)
                elif args.command=='record':result=workflow.record(args.stage,args.evidence)
                else:
                    if args.command=='begin':workflow.begin(args.stage)
                    if args.command=='configure':workflow.configure(args.kind,args.file)
                    result=workflow.status()
        print(json.dumps(result,indent=2))
        if args.command=='run' and result['missing_inputs']:return 3
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
