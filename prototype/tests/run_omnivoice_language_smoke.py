"""Targeted CP0.2C smoke: EN normal + VI cloned; never reruns full benchmark."""
import os,sys,json,socket
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'prototype'))
from providers.omnivoice import OmniVoiceProvider

def main():
    p=OmniVoiceProvider()
    report={'status':'FAIL','scope':'EN normal and VI cloned only','runs':[]}
    try:
        with patch.object(socket.socket,'connect',side_effect=OSError('Offline smoke')):
            print('Loading model',flush=True)
            p.load()
            profile=p.create_voice_profile(ROOT/'prototype/outputs/cp02a_vi_1.wav',
                'Xin chào, đây là bài kiểm tra tiếng Việt bằng OmniVoice.')
            for lang,mode,text in [('en','normal','Hello, this is a short test.'),('vi','cloned','Xin chào, đây là bài kiểm tra.')]:
                output=ROOT/'prototype/outputs'/f'cp02c_{lang}_{mode}.wav'
                r=p.synthesize(text,lang,output_path=output) if mode=='normal' else p.synthesize_cloned(text,lang,profile,output)
                report['runs'].append(asdict(r))
                assert r.status=='PASS', 'Synthesis failed'
                d=r.metadata['diagnostics']
                assert d['language']==lang and d['dtype']=='float16'
                assert d['language_status']=='VERIFIED' and d['mode']==mode
                assert d['duration']>0 and d['audio_dtype']=='float32'
                print(f'{lang} {mode}: PASS',flush=True)
            report['status']='PASS'
    except Exception as exc:
        report['error_code']=getattr(exc,'code','SMOKE_FAILED')
        print(report['error_code'],flush=True)
    finally:
        p.unload()
        (ROOT/'reports/cp02c_smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if report['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
