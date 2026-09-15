"""Negative controls for CP0 measurements; these are not model-quality tests."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from cp0_benchmark import inspect_wav, verify_artifacts

class EvidenceTests(unittest.TestCase):
    def test_silence_is_not_successful_speech_evidence(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cp0') as directory:
            path = Path(directory)/'silent.wav'
            with wave.open(str(path),'wb') as stream:
                stream.setparams((1,2,22050,0,'NONE','not compressed'))
                stream.writeframes(b'\0\0'*22050)
            with self.assertRaises(ValueError):
                inspect_wav(path)

    def test_truncated_pcm_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cp0') as directory:
            path = Path(directory)/'truncated.wav'
            with wave.open(str(path),'wb') as stream:
                stream.setparams((1,2,22050,0,'NONE','not compressed'))
                stream.writeframes(b'\1\0'*22050)
            path.write_bytes(path.read_bytes()[:-100])
            with self.assertRaises(ValueError):
                inspect_wav(path)

    def test_wrong_artifact_hash_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cp0') as directory:
            path = Path(directory)/'artifact.bin'
            path.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                verify_artifacts({'artifacts':[{'path':path.relative_to(ROOT).as_posix(),'sha256':'0'*64}]})

    def test_artifact_escape_rejected(self):
        with self.assertRaises(ValueError):
            verify_artifacts({'artifacts':[{'path':'Rule/RULES.txt','sha256':'0'*64}]})

    def test_real_output_matches_recorded_hash(self):
        result = json.loads((ROOT/'reports/evidence/cp0/sherpa_vi_benchmark.json').read_text(encoding='utf-8'))
        self.assertEqual(result['status'],'SYNTHESIS_AND_PCM_VALIDATED')
        for run in result['runs']:
            self.assertEqual(inspect_wav(ROOT/run['path'])['sha256'],run['sha256'])

    def test_evidence_snapshots_match_receipts(self):
        for receipt in (ROOT/'reports/evidence/cp0').glob('sources*.json'):
            import hashlib
            for record in json.loads(receipt.read_text(encoding='utf-8')):
                if record['status']=='FETCHED':
                    actual=hashlib.sha256((ROOT/record['file']).read_bytes()).hexdigest()
                    self.assertEqual(actual,record['sha256'],record['id'])

if __name__ == '__main__':
    unittest.main()
