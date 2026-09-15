"""Read-only upstream evidence collection for CP0; no model execution."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports' / 'evidence' / 'cp0'
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = {
    'nghi_repo': 'https://api.github.com/repos/nghimestudio/nghitts/commits/main',
    'nghi_readme': 'https://raw.githubusercontent.com/nghimestudio/nghitts/main/README.md',
    'nghi_license': 'https://raw.githubusercontent.com/nghimestudio/nghitts/main/LICENSE',
    'nghi_packages': 'https://raw.githubusercontent.com/nghimestudio/nghitts/main/package.json',
    'piper_package': 'https://pypi.org/pypi/piper-tts/json',
    'piper_repo': 'https://api.github.com/repos/OHF-Voice/piper1-gpl/commits/main',
    'piper_voices_metadata': 'https://huggingface.co/api/models/rhasspy/piper-voices',
    'piper_voices': 'https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json',
    'vais_card': 'https://huggingface.co/rhasspy/piper-voices/raw/main/vi/vi_VN/vais1000/medium/MODEL_CARD',
    'vivos_card': 'https://huggingface.co/rhasspy/piper-voices/raw/main/vi/vi_VN/vivos/x_low/MODEL_CARD',
    'coqui_repo': 'https://api.github.com/repos/coqui-ai/TTS/commits/dev',
    'coqui_readme': 'https://raw.githubusercontent.com/coqui-ai/TTS/dev/README.md',
    'xtts_metadata': 'https://huggingface.co/api/models/coqui/XTTS-v2',
    'xtts_license': 'https://huggingface.co/coqui/XTTS-v2/raw/main/LICENSE.txt',
    'xtts_readme': 'https://huggingface.co/coqui/XTTS-v2/raw/main/README.md',
    'vieneu_repo': 'https://api.github.com/repos/pnnbao97/VieNeu-TTS/commits/main',
    'vieneu_readme': 'https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/main/README.md',
    'vieneu_package': 'https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/main/pyproject.toml',
    'vieneu_model': 'https://huggingface.co/api/models/pnnbao-ump/VieNeu-TTS',
    'vieneu_model_readme': 'https://huggingface.co/pnnbao-ump/VieNeu-TTS/raw/main/README.md',
    'kokoro_model': 'https://huggingface.co/api/models/hexgrad/Kokoro-82M',
    'kokoro_readme': 'https://huggingface.co/hexgrad/Kokoro-82M/raw/main/README.md',
}

def fetch(item):
    name, url = item
    record = {'id': name, 'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat()}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'LocalVoice-CP0-audit'})
        with urllib.request.urlopen(req, timeout=25) as response:
            body = response.read(5_000_000)
            record['resolved_url'] = response.url
        path = OUT / (name + '.txt')
        path.write_bytes(body)
        record.update(status='FETCHED', bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), file=path.relative_to(ROOT).as_posix())
    except Exception as exc:
        record.update(status='ERROR', error=f'{type(exc).__name__}: {exc}')
    print(name, record['status'], flush=True)
    return record

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(fetch, SOURCES.items()))
    (OUT / 'sources.json').write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding='utf-8')
