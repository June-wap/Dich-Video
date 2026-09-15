import concurrent.futures
import json
from cp0_collect import fetch, OUT
from cp0_download_piper import IDS

revision = json.loads((OUT/'piper_voices_metadata.txt').read_text())['sha']
voices = json.loads((OUT/'piper_voices.txt').read_text())
sources = {}
for model in IDS:
    card = next(p for p in voices[model]['files'] if p.endswith('MODEL_CARD'))
    sources[model+'_MODEL_CARD'] = f'https://huggingface.co/rhasspy/piper-voices/raw/{revision}/{card}'
sources.update({
    'sherpa_license': 'https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.12.26/LICENSE',
    'sherpa_pypi': 'https://pypi.org/pypi/sherpa-onnx/1.12.26/json',
    'espeak_license': 'https://raw.githubusercontent.com/espeak-ng/espeak-ng/master/COPYING',
    'onnxruntime_license': 'https://raw.githubusercontent.com/microsoft/onnxruntime/v1.30.0/LICENSE',
    'vieneu_dataset_10k': 'https://huggingface.co/api/datasets/pnnbao-ump/VieNeu-TTS-10k-ENVI',
    'vieneu_dataset_1000': 'https://huggingface.co/api/datasets/pnnbao-ump/VieNeu-TTS-1000h',
    'kokoro_voices': 'https://huggingface.co/hexgrad/Kokoro-82M/raw/f3ff3571791e39611d31c381e3a41a3af07b4987/VOICES.md',
})
for name, model in [('vieneu_turbo', 'pnnbao-ump/VieNeu-TTS-v3-Turbo'), ('vieneu_nano', 'pnnbao-ump/VieNeu-TTS-v3-Nano'), ('xtts', 'coqui/XTTS-v2')]:
    rev = json.loads((OUT/(name+'_metadata.txt')).read_text())['sha']
    sources[name+'_tree'] = f'https://huggingface.co/api/models/{model}/tree/{rev}?recursive=true&expand=false'

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(fetch, sources.items()))
    (OUT/'sources_final.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
