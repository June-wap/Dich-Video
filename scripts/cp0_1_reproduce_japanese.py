"""Reproduce the actual CP0 failure: model acquisition, not inference."""
import hashlib
import json
import time
import traceback
import urllib.request
from pathlib import Path
from cp0_benchmark import ROOT, TEXTS

if __name__=='__main__':
    out=ROOT/'reports/evidence/cp0_1'
    model='ja_JA-hi_fi_captain-medium'
    rev='1162a9173d0ce503555aed757976b7a9912eae4c'
    url=f'https://huggingface.co/rhasspy/piper-voices/resolve/{rev}/ja/ja_JA/hi_fi_captain/medium/{model}.onnx'
    record={'model_id':model,'model_revision':rev,'runtime':'piper-tts 1.8.0 (installed CP0 runtime)',
            'input':TEXTS['ja'],'url':url,'load_attempted':False,'synthesis_attempted':False,
            'cp0_failure':'HTTPS redirected model download timeout, before inference',
            'classification':'unknown','status':'NOT_VERIFIED'}
    started=time.perf_counter()
    try:
        with urllib.request.urlopen(url,timeout=15) as response:
            data=response.read()
        path=ROOT/'.cp0/models/piper'/model/(model+'.onnx')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
        record.update(status='VERIFIED',classification='download_recovered',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:
        record.update(status='FAILED',classification='transport',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    record['elapsed_s']=time.perf_counter()-started
    out.mkdir(parents=True,exist_ok=True)
    (out/'japanese_reproduction.json').write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
    print(record['status'],record['classification'],record.get('error','downloaded'))
