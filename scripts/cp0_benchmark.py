"""Local-only Piper POC. Measures engineering output, not listening quality."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import socket
import sys
import threading
import time
import traceback
import wave

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'reports/evidence/cp0'
TEXTS = {
    'vi': 'Xin chào. Đây là bản kiểm thử tổng hợp giọng nói tiếng Việt trên máy tính cá nhân.',
    'en': 'Hello. This is a local speech synthesis test on a personal computer.',
    'zh': '你好。这是在个人电脑上进行的本地语音合成测试。',
    'ja': 'こんにちは。これはパソコンで行う音声合成のテストです。',
    'es': 'Hola. Esta es una prueba de síntesis de voz local en un ordenador personal.',
    'pt': 'Olá. Este é um teste de síntese de voz local em um computador pessoal.',
    'it': 'Ciao. Questa è una prova di sintesi vocale locale su un computer personale.',
    'fr': 'Bonjour. Ceci est un test de synthèse vocale locale sur un ordinateur personnel.',
    'hi': 'नमस्ते। यह व्यक्तिगत कंप्यूटर पर स्थानीय वाक् संश्लेषण का परीक्षण है।',
}

def inspect_wav(path):
    import numpy as np
    with wave.open(str(path), 'rb') as stream:
        channels, width, rate, frames = stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()
        raw = stream.readframes(frames)
    if width != 2 or frames <= 0 or rate <= 0 or len(raw) != frames * channels * width:
        raise ValueError('Invalid/empty/truncated PCM16 WAV')
    data = np.frombuffer(raw, dtype='<i2').astype(np.float64) / 32768
    rms = math.sqrt(float(np.mean(data * data)))
    if rms == 0 or not np.all(np.isfinite(data)):
        raise ValueError('Silent/nonfinite output')
    return {'duration_s': frames / rate, 'sample_rate': rate, 'channels': channels,
            'size_bytes': Path(path).stat().st_size, 'rms': rms,
            'peak': float(np.max(np.abs(data))), 'clipping_fraction': float(np.mean(np.abs(data) >= 0.999)),
            'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}

def verify_artifacts(manifest):
    for artifact in manifest['artifacts']:
        path = (ROOT / artifact['path']).resolve()
        if not path.is_relative_to((ROOT / '.cp0').resolve()):
            raise ValueError('Artifact escapes CP0 directory')
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact['sha256']:
            raise ValueError('Artifact SHA256 mismatch')

def deny_network():
    def deny(*args, **kwargs):
        raise PermissionError('CP0: Python network denied during inference')
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.create_connection = deny
    socket.getaddrinfo = deny
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--long', action='store_true')
    parser.add_argument('--evidence-dir', default='reports/evidence/cp0')
    args = parser.parse_args()
    evidence = ROOT / args.evidence_dir
    deny_network()
    result = {'model_id': args.model, 'python_network_guard': True,
              'os_firewall_verified': False, 'subjective_quality': 'NOT VERIFIED',
              'gpu_inference': 'NOT VERIFIED', 'runs': []}
    out = ROOT / '.cp0/audio' / args.model
    out.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    monitor = None
    try:
        import psutil
        proc = psutil.Process()
        rss = []
        def sample():
            while not stop.is_set():
                rss.append(proc.memory_info().rss)
                stop.wait(0.02)
        monitor = threading.Thread(target=sample, daemon=True)
        monitor.start()
        started = time.perf_counter()
        from piper import PiperVoice, SynthesisConfig
        import onnxruntime as ort
        result['runtime'] = {n: importlib.metadata.version(n) for n in ['piper-tts', 'onnxruntime', 'numpy']}
        result['available_ort_providers'] = ort.get_available_providers()
        manifest = json.loads((evidence / f'{args.model}_artifacts.json').read_text())
        if manifest['status'] != 'DOWNLOADED_NOT_PRODUCTION_APPROVED':
            raise RuntimeError('Model download incomplete: ' + manifest.get('error', 'unknown'))
        verify_artifacts(manifest)
        result['revision'] = manifest['revision']
        model_path = ROOT / '.cp0/models/piper' / args.model / (args.model + '.onnx')
        load_start = time.perf_counter()
        voice = PiperVoice.load(str(model_path), use_cuda=False)
        result['model_load_s'] = time.perf_counter() - load_start
        result['import_verify_load_s'] = time.perf_counter() - started
        result['actual_session_providers'] = voice.session.get_providers()
        text = TEXTS[args.model[:2]]
        for index in range(3):
            target = out / f'short_{index}.wav'
            begin = time.perf_counter()
            with wave.open(str(target), 'wb') as stream:
                stream.setparams((1, 2, voice.config.sample_rate, 0, 'NONE', 'not compressed'))
                voice.synthesize_wav(text, stream, syn_config=SynthesisConfig(speaker_id=0))
            elapsed = time.perf_counter() - begin
            info = inspect_wav(target)
            info.update(kind='first' if index == 0 else 'warm', generation_and_write_s=elapsed,
                        rtf=elapsed / info['duration_s'], path=target.relative_to(ROOT).as_posix(),
                        input_sha256=hashlib.sha256(text.encode()).hexdigest())
            result['runs'].append(info)
        if args.long:
            # A simple POC loop, not the production chunker/job architecture.
            sentence = TEXTS['vi']
            count = math.ceil(10000 / len(sentence))
            begin = time.perf_counter()
            duration = 0.0
            for index in range(count):
                target = out / f'long_{index:03}.wav'
                with wave.open(str(target), 'wb') as stream:
                    voice.synthesize_wav(sentence, stream)
                duration += inspect_wav(target)['duration_s']
            result['long_test'] = {'characters': len(sentence)*count, 'segments': count,
                                   'elapsed_s': time.perf_counter()-begin, 'duration_s': duration,
                                   'coverage': 'repeated synthetic sentence; no natural long-form listening evaluation'}
        result['status'] = 'SYNTHESIS_AND_PCM_VALIDATED'
    except Exception as exc:
        result.update(status='FAILED', error=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc())
    finally:
        stop.set()
        if monitor is not None:
            monitor.join(timeout=2)
        if 'rss' in locals():
            result['peak_sampled_rss_bytes'] = max(rss, default=0)
            result['windows_peak_working_set_bytes'] = proc.memory_info().peak_wset
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / f'{args.model}_benchmark.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result['status'] == 'SYNTHESIS_AND_PCM_VALIDATED' else 1

if __name__ == '__main__':
    sys.exit(main())
