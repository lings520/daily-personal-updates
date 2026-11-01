"""Offline recovery, caching, evidence and configuration integration tests."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import workflow as w
import settings
import risk_context

FIXTURES=ROOT/'tests/fixtures'


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.run_dir=self.base/'run'
        w.initialize(self.run_dir,'2026-10-30','2026-10-31T08:00:00+08:00',True)

    def flow(self):return w.Workflow(self.run_dir)

    def numbers(self):
        f=self.flow();f.put('equities',FIXTURES/'equity-returns.csv');f.put('treasuries',FIXTURES/'treasuries.json');return f.run()

    def complete(self):
        self.numbers();f=self.flow();f.put('editorial',FIXTURES/'editorial.json');return f.run()

    def evidence(self,result,delivery=False):
        doc={'artifact_sha256':result['artifact_sha256'],'notes':'Fictional test evidence only',
             'full_size_checked':True,'preview_checked':True,'facts_checked':True}
        if delivery:doc['reference']='fixture-only:no-external-publication'
        path=self.base/('delivery.json' if delivery else 'review.json');w.save(path,doc);return path

    def test_init_refuses_existing_and_preserves_plan(self):
        with self.assertRaises(ValueError):w.initialize(self.run_dir)
        self.assertEqual(self.flow().status()['report_date'],'2026-10-30')
        self.assertEqual(self.flow().run()['stages']['collection']['status'],'waiting')

    def test_partial_input_resume_and_research_boundary(self):
        f=self.flow();f.put('equities',FIXTURES/'equity-returns.csv')
        self.assertIn('treasuries',f.run()['missing_inputs'])
        with self.assertRaises(ValueError):f.put('editorial',FIXTURES/'editorial.json')
        f.put('treasuries',FIXTURES/'treasuries.json');result=f.run()
        self.assertEqual(result['stages']['normalize']['status'],'complete')
        self.assertEqual(result['stages']['research']['status'],'waiting')
        self.assertEqual(result['missing_inputs'],['editorial'])

    def test_failed_stage_is_recorded_and_repairable(self):
        bad=self.base/'bad.json';w.save(bad,[{'ticker':'SPY','current_close':-1}])
        f=self.flow();f.put('equities',bad);f.put('treasuries',FIXTURES/'treasuries.json')
        with self.assertRaises((ValueError,KeyError)):f.run()
        self.assertEqual(self.flow().state['stages']['normalize']['status'],'failed')
        f=self.flow();f.put('equities',FIXTURES/'equity-returns.csv');f.run()
        self.assertEqual(len(f.state['stages']['normalize']['attempts']),2)

    def test_cached_run_and_render_only_retry(self):
        first=self.complete();second=self.flow().run()
        self.assertEqual(first['stages'],second['stages'])
        self.assertEqual(first['artifact_sha256'],second['artifact_sha256'])
        third=self.flow().run(rerender=True)
        self.assertEqual(third['stages']['normalize']['attempts'],1)
        self.assertEqual(third['stages']['compose']['attempts'],1)
        self.assertEqual(third['stages']['render']['attempts'],2)

    def test_style_change_rerenders_without_research(self):
        first=self.complete();style=settings.load('visual-style');style['colours']['purple']='#73558A'
        path=self.base/'style.json';w.save(path,style)
        f=self.flow();f.configure('visual-style',path);second=f.run()
        self.assertEqual(second['stages']['normalize']['attempts'],1)
        self.assertEqual(second['stages']['compose']['attempts'],1)
        self.assertNotEqual(first['artifact_sha256'],second['artifact_sha256'])

    def test_data_revision_requires_editorial_reverification(self):
        self.numbers();f=self.flow();f.put('editorial',FIXTURES/'editorial.json')
        source=self.base/'source.json';w.save(source,{'kind':'fixture','name':'Revised fictional source','adjusted':True})
        f.put('equity-source',source);result=f.run()
        self.assertIn('editorial (refresh against revised metrics)',result['missing_inputs'])
        self.assertEqual(result['stages']['compose']['attempts'],0)
        f.put('editorial',FIXTURES/'editorial.json')
        self.assertNotIn('editorial (refresh against revised metrics)',f.status()['missing_inputs'])

    def test_modified_input_and_plan_are_rejected(self):
        f=self.flow();f.put('equities',FIXTURES/'equity-returns.csv');f.path('equities').write_text('modified')
        with self.assertRaises(ValueError):f.run()
        path=self.run_dir/'plan.json';doc=json.loads(path.read_text());doc['report_date']='2026-10-29';w.save(path,doc)
        with self.assertRaises(ValueError):self.flow()

    def test_qa_receipt_is_bound_to_current_artifact(self):
        result=self.complete();f=self.flow()
        with self.assertRaises(ValueError):f.record('delivery',self.evidence(result,True))
        receipt=self.evidence(result);doc=json.loads(receipt.read_text());doc['artifact_sha256']='wrong';w.save(receipt,doc)
        with self.assertRaises(ValueError):f.record('review',receipt)
        result=f.record('review',self.evidence(result))
        self.assertEqual(result['stages']['review']['status'],'complete')
        delivered=f.record('delivery',self.evidence(result,True))
        self.assertEqual(delivered['next_step'],'complete')
        again=self.flow().status();self.assertEqual(again['elapsed_wall_seconds'],delivered['elapsed_wall_seconds'])
        f.run(rerender=True)
        self.assertNotEqual(f.status()['stages']['review']['status'],'complete')
        self.assertNotEqual(f.status()['stages']['delivery']['status'],'complete')

    def test_renderer_failure_retries_only_render(self):
        self.numbers();f=self.flow();f.put('editorial',FIXTURES/'editorial.json')
        with patch.object(w.subprocess,'run',return_value=type('Result',(),{'returncode':1,'stderr':'renderer failure'})()):
            with self.assertRaises(ValueError):f.run()
        self.assertEqual(f.state['stages']['render']['status'],'failed')
        result=self.flow().run()
        self.assertEqual(result['stages']['normalize']['attempts'],1)
        self.assertEqual(result['stages']['compose']['attempts'],1)
        self.assertEqual(result['stages']['render']['attempts'],2)

    def test_configuration_changes_bounds_and_legend_together(self):
        config=settings.load('risk-context');config['vix_bounds']=[12,18,25]
        self.assertEqual(risk_context.risk_badge('vix',{'level':19},config)['label'],'ELEVATED')
        self.assertIn('18–<25 elevated',risk_context.reference_legend(config))
        config['vix_bounds']=[20,15,30]
        with self.assertRaises(ValueError):settings.validate('risk-context',config)

    def test_noop_put_preserves_cache_and_raw_history(self):
        self.numbers();f=self.flow();count=len(f.state['events'])
        f.put('equities',FIXTURES/'equity-returns.csv')
        self.assertEqual(len(f.state['events']),count)
        self.assertEqual(f.state['stages']['normalize']['status'],'complete')

    def test_cli_pause_exit_code_and_json_status(self):
        proc=subprocess.run([sys.executable,str(ROOT/'scripts/workflow.py'),'run','--run-dir',str(self.run_dir)],text=True,capture_output=True)
        self.assertEqual(proc.returncode,3)
        self.assertEqual(json.loads(proc.stdout)['stages']['collection']['status'],'waiting')

    def test_output_tampering_is_reported_and_rebuilt(self):
        result=self.complete();Path(result['image']).write_bytes(b'not a PNG')
        f=self.flow();self.assertEqual(f.status()['stages']['render']['status'],'pending')
        repaired=f.run()
        self.assertEqual(repaired['artifact_sha256'],result['artifact_sha256'])
        self.assertEqual(repaired['stages']['render']['attempts'],2)


if __name__=='__main__':unittest.main()
