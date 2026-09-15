import shutil
import cp0_download_piper as acquisition
from cp0_benchmark import ROOT

if __name__=='__main__':
    out=ROOT/'reports/evidence/cp0_1'
    out.mkdir(parents=True,exist_ok=True)
    for name in ['piper_voices.txt','piper_voices_metadata.txt']:
        shutil.copy2(ROOT/'reports/evidence/cp0'/name,out/name)
    acquisition.EVIDENCE=out
    result=acquisition.download('ja_JA-hi_fi_captain-medium')
    raise SystemExit(0 if result['status']=='DOWNLOADED_NOT_PRODUCTION_APPROVED' else 1)
