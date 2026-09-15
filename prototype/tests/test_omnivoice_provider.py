import json
import sys
import unittest
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.base import ManagedTTSProvider, SynthResult
from providers.omnivoice import OmniVoiceError, OmniVoiceProvider
from core.tts_manager import TTSManager


class OmniVoiceTests(unittest.TestCase):
    def setUp(self):
        self.model = Mock(sampling_rate=24000)
        self.model.generate.return_value = [np.ones(12000, dtype=np.float32) * .1]
        self.provider = OmniVoiceProvider()
        self.loader = patch.object(self.provider, "_load_model", return_value=self.model).start()
        self.addCleanup(patch.stopall)

    def test_contract_and_capabilities(self):
        self.assertIsInstance(self.provider, ManagedTTSProvider)
        cap = self.provider.capabilities()
        self.assertEqual(cap['verified_languages'], ['vi','en','zh','ja','es','pt','it','fr','hi'])
        self.assertFalse(cap['cpu_verified'])
        self.assertFalse(cap['production_ready'])
        self.assertEqual((cap['sample_rate'], cap['channels']), (24000, 1))
        self.loader.assert_not_called()

    def test_load_once_repeated_requests_and_unload(self):
        self.assertFalse(self.provider.is_loaded())
        self.provider.load(); self.provider.load()
        for _ in range(2):
            self.assertEqual(self.provider.synthesize('Xin chào', 'vi').status, 'PASS')
        self.loader.assert_called_once()
        self.assertEqual(self.model.generate.call_count, 2)
        self.provider.unload(); self.provider.unload()
        self.assertFalse(self.provider.is_loaded())
        self.provider.load()
        self.assertEqual(self.loader.call_count, 2)

    def test_language_propagation(self):
        for language in self.provider.list_languages():
            result = self.provider.synthesize('short test', language)
            self.assertEqual(result.language, language)
            self.model.generate.assert_called_with(text='short test', language=language, num_step=16)

    def test_normalized_result_and_log_serialization(self):
        result = self.provider.synthesize('Xin chào', 'vi')
        self.assertIsInstance(result, SynthResult)
        self.assertEqual(result.provider_id, 'omnivoice')
        self.assertEqual(result.sample_rate, 24000)
        self.assertEqual(result.duration, .5)
        self.assertEqual(result.audio.shape, (12000,))
        self.assertEqual(result.audio.dtype, np.float32)
        self.assertGreaterEqual(result.generation_time, 0)
        self.assertEqual(result.metadata['load_count'], 1)
        self.assertNotIn('audio', json.loads(json.dumps(asdict(result))))

    def test_invalid_language_and_empty_text_do_not_load(self):
        for text, language, code in [('x','xx','LANGUAGE_NOT_SUPPORTED'), ('','vi','INVALID_TEXT'), ('  ','vi','INVALID_TEXT'), (None,'vi','INVALID_TEXT')]:
            result = self.provider.synthesize(text, language)
            self.assertEqual(result.status, 'FAIL')
            self.assertEqual(result.metadata['error_code'], code)
        self.loader.assert_not_called()

    def test_load_failure_and_retry(self):
        self.loader.side_effect = RuntimeError('weights unavailable')
        with self.assertRaisesRegex(OmniVoiceError, 'MODEL_LOAD_FAILED'):
            self.provider.load()
        self.assertFalse(self.provider.is_loaded())
        result = self.provider.synthesize('x', 'vi')
        self.assertIn('MODEL_LOAD_FAILED', result.error)
        self.loader.side_effect = None
        self.assertEqual(self.provider.synthesize('x', 'vi').status, 'PASS')

    def test_generation_failure_preserves_loaded_model(self):
        self.model.generate.side_effect = RuntimeError('GPU error')
        self.assertIn('GENERATION_FAILED', self.provider.synthesize('x','vi').error)
        self.assertTrue(self.provider.is_loaded())
        self.model.generate.side_effect = None
        self.assertEqual(self.provider.synthesize('x','vi').status, 'PASS')
        self.loader.assert_called_once()

    def test_native_sample_rate_required(self):
        self.model.sampling_rate = 48000
        self.assertIn('MODEL_LOAD_FAILED', self.provider.synthesize('x','vi').error)
        self.assertFalse(self.provider.is_loaded())

    def test_invalid_audio(self):
        for audio in [np.array([]), np.array([np.nan]), np.ones((2,10))]:
            self.model.generate.return_value = [audio]
            self.assertIn('GENERATION_FAILED', self.provider.synthesize('x','vi').error)

    def test_concurrent_requests_reuse_model(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.provider.synthesize('x','vi'), range(2)))
        self.assertTrue(all(r.status == 'PASS' for r in results))
        self.loader.assert_called_once()

    def test_existing_manager_routes_to_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = TTSManager(Path(directory))
            manager.register_provider(self.provider)
            with patch('core.tts_manager.export_mp3', return_value=None):
                result = manager.synthesize('Xin chào', 'vi', 'omnivoice_auto')
            self.assertEqual(result.status, 'PASS')
            self.assertEqual(result.provider_id, 'omnivoice')
            self.assertTrue(Path(result.wav_path).exists())

    def test_unload_releases_cuda_cache(self):
        from unittest.mock import MagicMock
        self.provider.load()
        runtime = MagicMock()
        self.provider._torch = runtime
        self.provider.unload()
        self.assertFalse(self.provider.is_loaded())
        runtime.cuda.empty_cache.assert_called_once()


if __name__ == '__main__':
    unittest.main()
