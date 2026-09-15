import sys, unittest, tempfile, subprocess, json, logging
from pathlib import Path
from types import SimpleNamespace
from dataclasses import asdict
from unittest.mock import Mock, patch
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from providers.omnivoice import OmniVoiceProvider, OmniVoiceError

class CloneTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'ref.wav'
        sf.write(self.path, np.sin(np.arange(24000)*.03)*.2,24000)
        self.text='Exact private reference transcript.'
        self.prompt=SimpleNamespace(ref_text=self.text,ref_audio_tokens=np.ones((8,20)))
        self.model=Mock(sampling_rate=24000)
        self.model.create_voice_clone_prompt.return_value=self.prompt
        self.model.generate.return_value=[np.ones(12000,dtype=np.float32)*.1]
        self.p=OmniVoiceProvider()
        self.loader=patch.object(self.p,'_load_model',return_value=self.model).start()
        self.addCleanup(patch.stopall)
    def profile(self): return self.p.create_voice_profile(self.path,self.text)
    def test_missing_and_corrupt_audio(self):
        corrupt=Path(self.tmp.name)/'bad.mp3';corrupt.write_text('not audio')
        for path in [self.path.with_name('missing.wav'),corrupt]:
            with self.assertRaisesRegex(OmniVoiceError,'INVALID_REFERENCE_AUDIO'):self.p.create_voice_profile(path,self.text)
        self.loader.assert_not_called()
    def test_empty_transcript(self):
        for text in ['', ' ', None]:
            with self.assertRaisesRegex(OmniVoiceError,'INVALID_REFERENCE_TRANSCRIPT'):self.p.create_voice_profile(self.path,text)
        self.loader.assert_not_called()
    def test_profile_reuse_and_normalized_output(self):
        profile=self.profile()
        self.path.unlink()  # generation must not re-read reference
        for language in self.p.LANGUAGES:
            result=self.p.synthesize_cloned('Xin chào',language,profile)
            self.assertEqual(result.status,'PASS');self.assertEqual(result.language,language)
            self.assertEqual(result.provider_id,'omnivoice');self.assertEqual(result.sample_rate,24000)
            self.assertEqual(result.duration,.5);self.assertEqual(result.audio.ndim,1)
            self.assertIs(self.model.generate.call_args.kwargs['voice_clone_prompt'],self.prompt)
            self.assertEqual(self.model.generate.call_args.kwargs['language'],language)
            self.assertNotIn(self.text,json.dumps(asdict(result)))
        self.model.create_voice_clone_prompt.assert_called_once()
        self.assertEqual(self.model.create_voice_clone_prompt.call_args.kwargs['ref_text'],self.text)
        self.assertFalse(self.model.create_voice_clone_prompt.call_args.kwargs['preprocess_prompt'])
        self.assertNotIn(self.text,repr(profile));self.assertNotIn(self.text,json.dumps(asdict(profile)))
    def test_invalid_inputs(self):
        profile=self.profile()
        for text,lang,code in [('', 'vi','INVALID_TEXT'),('x','bad','LANGUAGE_NOT_SUPPORTED')]:
            self.assertIn(code,self.p.synthesize_cloned(text,lang,profile).error)
        self.model.generate.assert_not_called()
    def test_foreign_and_unloaded_profiles(self):
        profile=self.profile()
        self.assertIn('INVALID_VOICE_PROFILE',OmniVoiceProvider().synthesize_cloned('x','vi',profile).error)
        self.p.unload()
        self.assertIn('INVALID_VOICE_PROFILE',self.p.synthesize_cloned('x','vi',profile).error)
        self.assertIn('INVALID_VOICE_PROFILE',self.p.synthesize_cloned('x','vi',None).error)
    def test_prompt_error_is_redacted(self):
        self.model.create_voice_clone_prompt.side_effect=RuntimeError(self.text)
        with self.assertRaises(OmniVoiceError) as cm:self.profile()
        self.assertIn('VOICE_PROFILE_FAILED',str(cm.exception));self.assertNotIn(self.text,str(cm.exception))
    def test_invalid_prompt(self):
        self.model.create_voice_clone_prompt.return_value=None
        with self.assertRaisesRegex(OmniVoiceError,'VOICE_PROFILE_FAILED'):self.profile()
    def test_generation_error_and_logs_are_redacted(self):
        profile=self.profile()
        def fail(**kwargs):
            logging.getLogger('omnivoice.models.omnivoice').warning(self.text)
            raise RuntimeError(self.text)
        self.model.generate.side_effect=fail
        with self.assertNoLogs('omnivoice.models.omnivoice',level='DEBUG'):
            result=self.p.synthesize_cloned('private target','vi',profile)
        self.assertIn('GENERATION_FAILED',result.error);self.assertNotIn(self.text,result.error)
    def test_aac_in_mp3_filename(self):
        disguised=Path(self.tmp.name)/'reference.mp3'
        subprocess.run(['ffmpeg','-v','error','-i',str(self.path),'-c:a','aac','-f','ipod',str(disguised)],check=True,capture_output=True)
        profile=self.p.create_voice_profile(disguised,self.text)
        self.assertGreater(profile.reference_duration,.9)
    def test_synthesize_cloned_num_step_defaults_and_override(self):
        profile = self.profile()
        self.p.synthesize_cloned('Xin chào', 'vi', profile)
        self.assertEqual(self.model.generate.call_args.kwargs['num_step'], 24)
        self.p.synthesize_cloned('Xin chào', 'vi', profile, num_step=16)
        self.assertEqual(self.model.generate.call_args.kwargs['num_step'], 16)

if __name__=='__main__':unittest.main()
