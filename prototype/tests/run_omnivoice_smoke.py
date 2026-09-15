"""Real CP0.2A CUDA smoke. Run with external/OmniVoice/.venv312 Python."""
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

# Set offline mode before importing the runtime or Hugging Face.
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'prototype'))
from providers.omnivoice import OmniVoiceProvider


def main():
    import torch
    import numpy as np
    import soundfile as sf
    provider = OmniVoiceProvider()
    evidence = {'status': 'FAIL', 'python': sys.version, 'torch': torch.__version__,
                'gpu': torch.cuda.get_device_name(0),
                'capabilities': provider.capabilities(), 'runs': []}
    try:
        provider.load()
        assert provider.is_loaded()
        for index, text in enumerate(['Xin chào, đây là bài kiểm tra tiếng Việt bằng OmniVoice.',
                                      'Đây là yêu cầu thứ hai, sử dụng lại mô hình đã tải.']):
            path = ROOT / 'prototype' / 'outputs' / f'cp02a_vi_{index+1}.wav'
            result = provider.synthesize(text, 'vi', output_path=path)
            evidence['runs'].append(asdict(result))
            assert result.status == 'PASS', result.error
            samples, rate = sf.read(path)
            assert rate == 24000 and samples.ndim == 1 and np.max(np.abs(samples)) > 0
            assert result.metadata['load_count'] == 1
            assert result.metadata['model_reused']
            print(f'VI request {index+1}: PASS, {result.duration:.2f}s audio', flush=True)
        evidence['loaded_health'] = provider.health_check()
        provider.unload()
        assert not provider.is_loaded()
        evidence['unload'] = 'PASS'
        evidence['status'] = 'PASS'
    finally:
        provider.unload()
        path = ROOT / 'reports' / 'cp02a_omnivoice_smoke.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
