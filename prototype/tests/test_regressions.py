import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from core.tts_manager import TTSManager
from core.audio_utils import write_wav, merge_segments
from providers.base import TTSProvider, VoiceInfo, SynthResult
class Provider(TTSProvider):
    def provider_name(self): return 'test'
    def list_languages(self): return ['vi']
    def list_voices(self, language): return [VoiceInfo('test','test','vi')] if language=='vi' else []
    def health_check(self): return {}
    def synthesize(self,text,language,voice,output_path,**options):
        write_wav(output_path,np.ones(100,dtype=np.float32)*0.1,1000)
        return SynthResult(wav_path=str(output_path))
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.m=TTSManager(Path(self.tmp.name));self.m.register_provider(Provider())
    def test_invalid_voice_language_text(self):
        for text,lang,voice,error in [('x','vi','bad','VOICE_NOT_FOUND'),('','vi','test','INVALID_TEXT'),('x','zz','test','LANGUAGE_NOT_SUPPORTED')]:
            self.assertIn(error,self.m.synthesize(text,lang,voice).error)
    def test_export_failure_retains_wav(self):
        with patch('core.tts_manager.export_mp3',return_value=None):
            result=self.m.synthesize('test','vi','test')
        self.assertEqual(result.status,'PASS');self.assertTrue(Path(result.wav_path).exists())
        self.assertIn('EXPORT_FAILED',result.export_error)
    def test_provider_exception_isolated(self):
        with patch.object(self.m._providers[0],'synthesize',side_effect=RuntimeError('broken')):
            self.assertEqual(self.m.synthesize('x','vi','test').status,'FAIL')
    def test_empty_audio_rejected(self):
        with self.assertRaises(ValueError):write_wav(Path(self.tmp.name)/'x.wav',np.array([]),22050)
    def test_invalid_pause_rejected(self):
        p=Path(self.tmp.name)/'x.wav';write_wav(p,np.ones(100),1000)
        with self.assertRaises(ValueError):merge_segments([p],p.with_name('y.wav'),pauses_ms=[float('nan')])
if __name__=='__main__':unittest.main()
