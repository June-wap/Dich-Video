import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.languages import (VERIFIED_LANGUAGE_IDS, LANGUAGE_NAMES,
                            language_status, VERIFIED, EXPERIMENTAL_UPSTREAM, UNSUPPORTED)
from core.text_utils import LANGUAGE_NAMES as COMPAT_NAMES
from providers.omnivoice import OmniVoiceProvider, VoiceProfile


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.p = OmniVoiceProvider()
        self.model = Mock(sampling_rate=24000, dtype="torch.float16")
        self.model.generate.return_value = [np.ones(2400, dtype=np.float32)]
        self.loader = patch.object(self.p, '_load_model', return_value=self.model).start()
        self.addCleanup(patch.stopall)
        self.profile = VoiceProfile('test', 'omnivoice', 1)
        self.prompt = object()
        self.p._profiles['test'] = (self.profile, self.prompt)

    def test_canonical_metadata_and_capabilities(self):
        self.assertIs(COMPAT_NAMES, LANGUAGE_NAMES)
        self.assertEqual(VERIFIED_LANGUAGE_IDS, ('vi','en','zh','ja','es','pt','it','fr','hi'))
        cap = self.p.capabilities()
        self.assertEqual(cap['languages'], list(VERIFIED_LANGUAGE_IDS))
        self.assertEqual([m['id'] for m in cap['language_metadata']], cap['languages'])
        self.assertTrue(all(m['status'] == VERIFIED and not m['production_ready'] for m in cap['language_metadata']))
        self.assertIn('de', cap['experimental_upstream_languages'])
        self.assertNotIn('de', cap['verified_languages'])
        self.assertFalse(cap['experimental_languages_enabled'])
        self.assertEqual(cap['cloned_live_verified_languages'], ['vi'])

    def test_three_statuses(self):
        self.assertEqual(language_status('vi'), VERIFIED)
        self.assertEqual(language_status('de'), EXPERIMENTAL_UPSTREAM)
        self.assertEqual(language_status('not-a-language'), UNSUPPORTED)

    def test_all_nine_exact_propagation_both_modes(self):
        for lang in VERIFIED_LANGUAGE_IDS:
            for cloned in (False, True):
                r = (self.p.synthesize_cloned('test', lang, self.profile) if cloned
                     else self.p.synthesize('test', lang))
                self.assertEqual(r.status, 'PASS')
                self.assertEqual(r.language, lang)
                call = self.model.generate.call_args.kwargs
                self.assertEqual(call['language'], lang)
                if cloned:
                    self.assertIs(call['voice_clone_prompt'], self.prompt)
                else:
                    self.assertNotIn('voice_clone_prompt', call)
        self.loader.assert_called_once()
        self.model.create_voice_clone_prompt.assert_not_called()

    def test_no_aliases_or_silent_fallback(self):
        for lang in ('de', 'VI', ' vi', 'vi ', 'vi-VN', 'Vietnamese', '', None, [], {}, 5):
            for cloned in (False, True):
                r = (self.p.synthesize_cloned('test', lang, self.profile) if cloned
                     else self.p.synthesize('test', lang))
                self.assertEqual(r.status, 'FAIL')
                self.assertEqual(r.metadata['error_code'], 'LANGUAGE_NOT_SUPPORTED')
                self.assertIsNone(r.audio)
                self.assertEqual(r.metadata['diagnostics']['language_status'], language_status(lang))
        self.loader.assert_not_called()
        self.model.generate.assert_not_called()

    def test_matching_diagnostics_and_dtype_semantics(self):
        for r in (self.p.synthesize('test','en'), self.p.synthesize_cloned('test','en',self.profile)):
            d = r.metadata['diagnostics']
            self.assertEqual(d['provider'], r.provider_id)
            self.assertEqual(d['language'], 'en')
            self.assertEqual(d['device'], 'cuda:0')
            self.assertEqual(d['dtype'], 'float16')
            self.assertEqual(d['audio_dtype'], 'float32')
            self.assertEqual(d['generation_time'], r.generation_time)
            self.assertEqual(d['duration'], r.duration)
            self.assertAlmostEqual(d['rtf'], d['generation_time']/d['duration'])
            json.dumps(d)

    def test_validation_failure_does_not_invent_runtime_dtype(self):
        r = self.p.synthesize('test','unknown')
        self.assertIsNone(r.metadata['diagnostics']['dtype'])
        self.assertEqual(r.metadata['diagnostics']['generation_time'], 0)

    def test_baseline_evidence_matches_verified_set(self):
        root = Path(__file__).resolve().parents[2]
        data = json.loads((root/'external/OmniVoice/benchmark_results.json').read_text(encoding='utf-8'))
        self.assertEqual({r['language'] for r in data['tests'] if r['status']=='PASS'}, set(VERIFIED_LANGUAGE_IDS))


if __name__ == '__main__':
    unittest.main()
