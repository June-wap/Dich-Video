"""Explicit, pinned CP0 model acquisition; never called by inference."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'reports/evidence/cp0'
IDS = ['vi_VN-vais1000-medium', 'en_US-lessac-medium', 'zh_CN-huayan-medium',
       'ja_JA-hi_fi_captain-medium', 'es_ES-davefx-medium', 'pt_BR-faber-medium',
       'it_IT-riccardo-x_low', 'fr_FR-siwis-medium', 'hi_IN-pratham-medium']

def download(model_id):
    catalog = json.loads((EVIDENCE / 'piper_voices.txt').read_text(encoding='utf-8'))
    revision = json.loads((EVIDENCE / 'piper_voices_metadata.txt').read_text(encoding='utf-8'))['sha']
    result = {'model_id': model_id, 'repository': 'rhasspy/piper-voices', 'revision': revision, 'artifacts': []}
    directory = ROOT / '.cp0/models/piper' / model_id
    directory.mkdir(parents=True, exist_ok=True)
    try:
        for remote, expected in catalog[model_id]['files'].items():
            # Catalogue paths are untrusted. Only take a validated leaf filename.
            filename = remote.rsplit('/', 1)[-1]
            if filename in ('', '.', '..') or '\\' in filename or ':' in filename:
                raise ValueError('Unsafe artifact name')
            target = directory / filename
            url = f'https://huggingface.co/rhasspy/piper-voices/resolve/{revision}/{remote}'
            if not target.exists():
                request = urllib.request.Request(url, headers={'User-Agent': 'LocalVoice-CP0'})
                temporary = target.with_suffix(target.suffix + '.part')
                with urllib.request.urlopen(request, timeout=60) as response, temporary.open('wb') as dest:
                    while chunk := response.read(1024 * 1024):
                        dest.write(chunk)
                temporary.replace(target)
            data = target.read_bytes()
            actual_md5 = hashlib.md5(data).hexdigest()
            if len(data) != expected['size_bytes'] or actual_md5 != expected['md5_digest']:
                raise ValueError(f'Catalogue integrity mismatch: {filename}')
            artifact = {'path': target.relative_to(ROOT).as_posix(), 'url': url, 'size_bytes': len(data),
                        'sha256': hashlib.sha256(data).hexdigest(), 'catalog_md5_match': True}
            result['artifacts'].append(artifact)
            if filename == 'MODEL_CARD':
                (EVIDENCE / f'{model_id}_MODEL_CARD.txt').write_bytes(data)
            print(model_id, filename, len(data), flush=True)
        result['status'] = 'DOWNLOADED_NOT_PRODUCTION_APPROVED'
    except Exception as exc:
        result.update(status='ERROR', error=f'{type(exc).__name__}: {exc}')
        print(model_id, result['error'], flush=True)
    (EVIDENCE / f'{model_id}_artifacts.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(download, IDS if args.all else IDS[:1]))
