"""Bilingual parity, stale-translation, layout and workflow regression checks."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import workflow as w
import localization as loc
import render_snapshot as render
import install_chinese_fonts as installer

FIX=ROOT/'tests/fixtures'
FONT_DIR=os.environ.get('MARKET_UPDATE_TEST_FONT_DIR')

class TranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan=w.data.make_plan('2026-10-31T08:00:00+08:00','2026-10-30',example=True)
        metrics=w.data.normalize(plan,w.data.rows_from_file(FIX/'equity-returns.csv'),w.data.rows_from_file(FIX/'treasuries.json'))
        cls.snapshot=w.data.compose(metrics,w.data.read_json(FIX/'editorial.json'))
        cls.translation=w.data.read_json(FIX/'translation-zh-Hans.json')

    def test_fixture_is_complete_and_identical_facts(self):
        before=copy.deepcopy(self.snapshot)
        mapping=loc.validate(self.snapshot,self.translation)
        self.assertEqual(self.snapshot,before)
        self.assertEqual(mapping['THE MORNING MARKET'],'美股晨报')
        self.assertEqual(set(self.translation['translations']),set(loc.display_strings(self.snapshot)))

    def test_stale_translation_rejected_after_source_change(self):
        snapshot=copy.deepcopy(self.snapshot);snapshot['headline']='Revised headline'
        with self.assertRaisesRegex(ValueError,'stale'):loc.validate(snapshot,self.translation)

    def test_missing_extra_and_blank_entries_rejected(self):
        for kind in ('missing','extra','blank'):
            doc=copy.deepcopy(self.translation);key=next(iter(doc['translations']))
            if kind=='missing':del doc['translations'][key]
            elif kind=='extra':doc['translations']['unexpected']='意外'
            else:doc['translations'][key]=''
            with self.subTest(kind=kind),self.assertRaises(ValueError):loc.validate(self.snapshot,doc)

    def test_changed_price_sign_citation_ticker_unit_rejected(self):
        for source,target in [('$93.00','$94.00'),('+7.00%','-7.00%'),('VIX [3]','VIX [1]'),('VIX [3]','DXY [3]'),('+2.0 bp','+2.0 pts')]:
            doc=copy.deepcopy(self.translation);doc['translations'][source]=target
            with self.subTest(source=source),self.assertRaises(ValueError):loc.validate(self.snapshot,doc)

    def test_locale_and_untranslated_prose_rejected(self):
        doc=copy.deepcopy(self.translation);doc['locale']='zh-Hant'
        with self.assertRaises(ValueError):loc.validate(self.snapshot,doc)
        doc=copy.deepcopy(self.translation);key=self.snapshot['headline'];doc['translations'][key]=key
        with self.assertRaises(ValueError):loc.validate(self.snapshot,doc)

    def test_date_format_conversion_preserves_instant(self):
        self.assertEqual(loc.tokens('02 Nov 2026\n23:00'),loc.tokens('2026-11-02\n23:00'))
        self.assertNotEqual(loc.tokens('02 Nov 2026\n23:00'),loc.tokens('2026-11-03\n23:00'))

    def test_font_download_checksum_failure_is_not_installed(self):
        from io import BytesIO
        with tempfile.TemporaryDirectory() as directory,patch.object(installer,'urlopen',return_value=BytesIO(b'wrong font')):
            with self.assertRaisesRegex(ValueError,'checksum'):installer.install(directory)
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_missing_font_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'Missing'):loc.chinese_fonts(directory)

    @unittest.skipUnless(FONT_DIR,'Set MARKET_UPDATE_TEST_FONT_DIR to the verified SC font cache')
    def test_cjk_wrap_keeps_punctuation_and_citations(self):
        fonts=loc.chinese_fonts(FONT_DIR)
        r=render.Renderer(fonts['regular'],fonts['bold'],render.resolve_font(None,'mono'),{'enabled':'测试'})
        lines=r.lines('市场变化与参与度值得关注，保留数字 SPY +1.00% [1]。',180)
        self.assertGreater(len(lines),1)
        self.assertTrue(all(r.width(line,27)<=180 for line in lines))
        self.assertFalse(any(line.startswith(('[1]','，','。')) for line in lines))
        lines=r.lines('示例数值 −$7.00 / +2.0 bp，保持正负号。',180)
        self.assertTrue(any('−$7.00' in line for line in lines))
        self.assertTrue(any('+2.0 bp' in line for line in lines))

@unittest.skipUnless(FONT_DIR,'Set MARKET_UPDATE_TEST_FONT_DIR for bilingual integration rendering')
class BilingualWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.directory=self.base/'run'
        w.initialize(self.directory,'2026-10-30','2026-10-31T08:00:00+08:00',True,languages='en,zh-Hans',chinese_font_dir=FONT_DIR)
        self.f=w.Workflow(self.directory)
        self.f.put('equities',FIX/'equity-returns.csv');self.f.put('treasuries',FIX/'treasuries.json');self.f.run()
        self.f.put('editorial',FIX/'editorial.json')
        self.waiting=self.f.run()

    def complete(self):
        self.f.put('translation-zh-Hans',FIX/'translation-zh-Hans.json');return self.f.run()

    def test_translation_pause_then_two_images_and_cache(self):
        self.assertIn('translation-zh-Hans',self.waiting['next_step'])
        result=self.complete();self.assertEqual(set(result['images']),{'en','zh-Hans'})
        self.assertTrue(all(Path(v['image']).is_file() and Path(v['preview']).is_file() for v in result['images'].values()))
        self.assertEqual(self.f.run()['stages'],result['stages'])
        style=w.load_settings('visual-style');style['colours']['purple']='#73558A'
        p=self.base/'style.json';w.save(p,style);self.f.configure('visual-style',p)
        again=self.f.run()
        self.assertEqual(again['stages']['compose']['attempts'],1)
        for lang in result['images']:self.assertNotEqual(result['images'][lang]['sha256'],again['images'][lang]['sha256'])

    def test_revised_editorial_requires_new_translation(self):
        self.complete();editorial=w.data.read_json(FIX/'editorial.json');editorial['headline']='Revised fictional headline'
        p=self.base/'revised.json';w.save(p,editorial);self.f.put('editorial',p)
        result=self.f.run();self.assertIn('translation-zh-Hans',result['next_step'])
        self.assertNotIn('images',result)
        with self.assertRaisesRegex(ValueError,'stale'):self.f.put('translation-zh-Hans',FIX/'translation-zh-Hans.json')

    def test_both_artifact_hashes_required_for_review_and_delivery(self):
        result=self.complete();p=self.base/'evidence.json'
        doc={'artifact_sha256':result['artifact_sha256'],'notes':'Automated fixture evidence, not human review','full_size_checked':True,'preview_checked':True,'facts_checked':True}
        w.save(p,doc)
        with self.assertRaisesRegex(ValueError,'both'):self.f.record('review',p)
        doc['artifacts_sha256']={k:v['sha256'] for k,v in result['images'].items()};w.save(p,doc)
        with self.assertRaisesRegex(ValueError,'Simplified'):self.f.record('review',p)
        doc['translation_checked']=True;w.save(p,doc);self.f.record('review',p)
        doc['reference']='fixture-only:english';w.save(p,doc)
        with self.assertRaisesRegex(ValueError,'each language'):self.f.record('delivery',p)
        doc['references']={'en':'fixture-only:english','zh-Hans':'fixture-only:chinese'};w.save(p,doc)
        self.assertEqual(self.f.record('delivery',p)['next_step'],'complete')

if __name__=='__main__':unittest.main()
