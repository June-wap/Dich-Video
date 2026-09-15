"""CP0.1 source/license investigation; no private input or model execution."""
import concurrent.futures
import json
import cp0_collect as collector
from cp0_benchmark import ROOT

collector.OUT = ROOT/'reports/evidence/cp0_1'
collector.OUT.mkdir(parents=True, exist_ok=True)
REV = '3206ed960e317e69bfe09f9d553aecbf1090f32e'
SOURCES = {
    'vieneu_tree': f'https://api.github.com/repos/pnnbao97/VieNeu-TTS/git/trees/{REV}?recursive=1',
    'vieneu_init': f'https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/{REV}/src/vieneu/__init__.py',
    'vieneu_onnx': f'https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/{REV}/src/vieneu/_v3_turbo_engine/inference_v3_turbo_onnx.py',
    'vieneu_package': f'https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/{REV}/pyproject.toml',
    'openjtalk_pypi': 'https://pypi.org/pypi/pyopenjtalk-plus/json',
    'openjtalk_repo': 'https://api.github.com/repos/tsukumijima/pyopenjtalk-plus/commits/master',
    'openjtalk_readme': 'https://raw.githubusercontent.com/tsukumijima/pyopenjtalk-plus/master/README.md',
    'openjtalk_license': 'https://raw.githubusercontent.com/tsukumijima/pyopenjtalk-plus/master/LICENSE.md',
    'openjtalk_voice_license': 'https://raw.githubusercontent.com/tsukumijima/pyopenjtalk-plus/master/pyopenjtalk/htsvoice/README.md',
    'sherpa_espeak_cmake': 'https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.12.26/cmake/espeak-ng.cmake',
    'sherpa_vits_impl': 'https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.12.26/sherpa-onnx/csrc/offline-tts-vits-impl.h',
    'sherpa_phonemizer': 'https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.12.26/sherpa-onnx/csrc/offline-tts-frontend.cc',
    'lessac_license': 'https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html',
    'mailabs_license': 'https://www.caito.de/2019/01/03/the-m-ailabs-speech-dataset/',
    'cc_by_4': 'https://creativecommons.org/licenses/by/4.0/legalcode.txt',
}
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(collector.fetch,SOURCES.items()))
    (collector.OUT/'sources.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
