"""Pinned source inspection for the concrete CP0 shortlist."""
import concurrent.futures
import json
from cp0_collect import fetch, OUT

def revision(name):
    return json.loads((OUT / (name + '.txt')).read_text(encoding='utf-8'))['sha']

nghi, vieneu, coqui = map(revision, ['nghi_repo', 'vieneu_repo', 'coqui_repo'])
sources = {
    'nghi_piper_source': f'https://raw.githubusercontent.com/nghimestudio/nghitts/{nghi}/src/lib/piper-tts.js',
    'nghi_lock': f'https://raw.githubusercontent.com/nghimestudio/nghitts/{nghi}/package-lock.json',
    'coqui_license': f'https://raw.githubusercontent.com/coqui-ai/TTS/{coqui}/LICENSE.txt',
    'vieneu_license': f'https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/{vieneu}/LICENSE',
    'vieneu_turbo_metadata': 'https://huggingface.co/api/models/pnnbao-ump/VieNeu-TTS-v3-Turbo',
    'vieneu_turbo_card': 'https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo/raw/main/README.md',
    'vieneu_nano_metadata': 'https://huggingface.co/api/models/pnnbao-ump/VieNeu-TTS-v3-Nano',
    'vieneu_nano_card': 'https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Nano/raw/main/README.md',
    'vieneu_pypi': 'https://pypi.org/pypi/vieneu/json',
    'moss_card': 'https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano/raw/main/README.md',
    'sea_g2p_pypi': 'https://pypi.org/pypi/sea-g2p/json',
    'piper_usage': 'https://raw.githubusercontent.com/OHF-Voice/piper1-gpl/v1.8.0/docs/API_PYTHON.md',
    'piper_license': 'https://raw.githubusercontent.com/OHF-Voice/piper1-gpl/v1.8.0/COPYING',
}
if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        records = list(pool.map(fetch, sources.items()))
    (OUT / 'sources_extra.json').write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding='utf-8')
