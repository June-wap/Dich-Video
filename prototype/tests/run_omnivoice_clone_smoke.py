"""CP0.2B real local cloning with one reusable prompt and two VI requests."""
import os, sys, json, socket
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'prototype'))
from providers.omnivoice import OmniVoiceProvider

def main():
    print("Importing CUDA runtime", flush=True)
    import torch
    import soundfile as sf
    import numpy as np
    p=OmniVoiceProvider()
    report={'status':'FAIL','torch':torch.__version__,'gpu':torch.cuda.get_device_name(0),
            'reference_container':'MP4/M4A AAC with .mp3 extension (ffprobe verified)',
            'runs':[]}
    try:
        with patch.object(socket.socket,'connect',side_effect=OSError('Offline test')):
            print("Loading model", flush=True)
            p.load()
            print("Preparing profile", flush=True)
            with patch.object(p._model,'create_voice_clone_prompt',wraps=p._model.create_voice_clone_prompt) as create:
                profile=p.create_voice_profile(ROOT/'external/OmniVoice/ref_vi.mp3',
                    'Xin chào mọi người, hôm nay chúng ta sẽ cùng nhau thử nghiệm một hệ thống giọng nói mới.')
                print('Profile ready', flush=True)
                report['reference_duration']=profile.reference_duration
                for i,text in enumerate(['Xin chào, đây là bài kiểm tra nhân bản giọng nói tiếng Việt.',
                                         'Đây là câu thứ hai sử dụng lại hồ sơ giọng nói đã tạo.']):
                    result=p.synthesize_cloned(text,'vi',profile,
                        ROOT/'prototype/outputs'/f'cp02b_vi_clone_{i+1}.wav')
                    report['runs'].append(asdict(result))
                    assert result.status=='PASS',result.error
                    audio,sr=sf.read(result.wav_path)
                    assert sr==24000 and audio.ndim==1 and np.isfinite(audio).all() and np.max(np.abs(audio))>0
                    print(f'VI clone {i+1}: PASS, {result.duration:.2f}s',flush=True)
                report['prompt_creation_count']=create.call_count
                assert create.call_count==1
                report['model_load_count']=p.health_check()['load_count']
                assert report['model_load_count']==1
                report['status']='PASS'
    except Exception as exc:
        report['error_code'] = getattr(exc, 'code', 'SMOKE_FAILED')
        print('Clone smoke failed: ' + report['error_code'], flush=True)
    finally:
        p.unload()
        report['unloaded']=not p.is_loaded()
        (ROOT/'reports/cp02b_cloning_smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if report['status'] != 'PASS':
        raise SystemExit(1)
if __name__=='__main__':main()
