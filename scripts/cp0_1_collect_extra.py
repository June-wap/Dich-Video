import concurrent.futures
import json
import cp0_collect as collector
from cp0_benchmark import ROOT
collector.OUT=ROOT/'reports/evidence/cp0_1'
REV='3206ed960e317e69bfe09f9d553aecbf1090f32e'
JP='9e4bf25324ac135dfc81ca64aed2fa6a48b83304'
SOURCES={
    'vieneu_onnx_lite': f'https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/{REV}/src/vieneu/_v3_turbo_engine/onnx_runtime_lite.py',
    'vieneu_factory': f'https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/{REV}/src/vieneu/factory.py',
    'vieneu_hub': f'https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/{REV}/src/vieneu/_v3_turbo_engine/hub_load_v3_turbo.py',
    'openjtalk_mei_license': f'https://raw.githubusercontent.com/tsukumijima/pyopenjtalk-plus/{JP}/pyopenjtalk/htsvoice/LICENSE_mei_normal.htsvoice',
    'openjtalk_init': f'https://raw.githubusercontent.com/tsukumijima/pyopenjtalk-plus/{JP}/pyopenjtalk/__init__.py',
    'openjtalk_tree': f'https://api.github.com/repos/tsukumijima/pyopenjtalk-plus/git/trees/{JP}?recursive=1',
    'sherpa_tree': 'https://api.github.com/repos/k2-fsa/sherpa-onnx/git/trees/v1.12.26?recursive=1',
    'sherpa_piper_lexicon': 'https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.12.26/sherpa-onnx/csrc/piper-phonemize-lexicon.cc',
    'sherpa_cmake': 'https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.12.26/sherpa-onnx/csrc/CMakeLists.txt',
}
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(collector.fetch,SOURCES.items()))
    (collector.OUT/'sources_extra.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
