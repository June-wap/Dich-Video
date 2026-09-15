"""Reproducible CPU POC for the SHA256-pinned Sherpa VAIS1000 release."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import threading
import time
import wave

from cp0_benchmark import ROOT, EVIDENCE, TEXTS, deny_network, inspect_wav

def main():
    deny_network()
    import psutil
    import numpy as np
    started = time.perf_counter()
    import sherpa_onnx
    proc = psutil.Process()
    directory = ROOT / '.cp0/models/sherpa/vits-piper-vi_VN-vais1000-medium'
    output = ROOT / '.cp0/audio/kiểm thử tiếng Việt'
    output.mkdir(parents=True, exist_ok=True)
    report = {'provider': 'sherpa-onnx', 'runtime_version': importlib.metadata.version('sherpa-onnx'),
              'model_id': 'vits-piper-vi_VN-vais1000-medium', 'device': 'cpu', 'threads': 4,
              'network': 'Python socket guard + execution inside restricted sandbox; OS firewall test NOT VERIFIED',
              'subjective_quality': 'NOT VERIFIED', 'gpu': 'NOT VERIFIED', 'runs': []}
    stop = threading.Event()
    rss = []
    def sample():
        while not stop.is_set():
            rss.append(proc.memory_info().rss)
            stop.wait(0.02)
    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        archive = ROOT / '.cp0/downloads/vits-piper-vi_VN-vais1000-medium.tar.bz2'
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != 'fa1367710767d36ed5cf13b4a449e20c35ffd12791c2e47c2e64142bfa55551a':
            raise ValueError('Release archive SHA256 mismatch')
        report['release_archive_sha256'] = digest
        report['artifacts'] = [{'path': p.relative_to(ROOT).as_posix(), 'size_bytes': p.stat().st_size,
                                'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                               for p in sorted(directory.rglob('*')) if p.is_file()]
        config = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(directory/'vi_VN-vais1000-medium.onnx'),
                tokens=str(directory/'tokens.txt'), data_dir=str(directory/'espeak-ng-data')),
            num_threads=4, provider='cpu', debug=False))
        if not config.validate():
            raise ValueError('Sherpa configuration invalid')
        begin = time.perf_counter()
        tts = sherpa_onnx.OfflineTts(config)
        report['model_load_s'] = time.perf_counter() - begin
        report['import_verify_load_s'] = time.perf_counter() - started
        cases = [('cold_first', TEXTS['vi']), ('warm_1', TEXTS['vi']), ('warm_2', TEXTS['vi']),
                 ('raw_numbers', 'Ngày 11/09/2026, giá sản phẩm là 125.000 VNĐ, giảm 15 phần trăm.'),
                 ('spoken_numbers', 'Ngày mười một tháng chín năm hai nghìn không trăm hai mươi sáu, giá sản phẩm là một trăm hai mươi lăm nghìn đồng.'),
                 ('mixed', 'Xin chào, đây là phần mềm Local AI Voice Studio chạy trên Windows.')]
        for name, text in cases:
            begin = time.perf_counter()
            audio = tts.generate(text, sid=0, speed=1.0)
            synth_s = time.perf_counter()-begin
            values = np.asarray(audio.samples)
            if not np.all(np.isfinite(values)):
                raise ValueError('Nonfinite generated samples')
            path = output / (name+'.wav')
            pcm = (np.clip(values, -1, 1)*32767).astype('<i2')
            with wave.open(str(path), 'wb') as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(audio.sample_rate)
                stream.writeframes(pcm.tobytes())
            info = inspect_wav(path)
            info.update(case=name, text=text, synthesis_s=synth_s, rtf=synth_s/info['duration_s'],
                        path=path.relative_to(ROOT).as_posix())
            report['runs'].append(info)
            print(name, round(synth_s,3), 's / RTF', round(info['rtf'],3), flush=True)
        # Real model stability test using >10k characters in sequential small chunks.
        # This deliberately does not claim semantic long-form quality or production resume.
        count = 125
        begin = time.perf_counter()
        total_samples = 0
        long_path = output / 'long_repeated.wav'
        with wave.open(str(long_path), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(audio.sample_rate)
            for index in range(count):
                audio = tts.generate(TEXTS['vi'], sid=0, speed=1.0)
                values = np.asarray(audio.samples)
                if not values.size or not np.all(np.isfinite(values)) or np.max(np.abs(values)) == 0:
                    raise ValueError('Invalid long-test segment')
                stream.writeframes((np.clip(values,-1,1)*32767).astype('<i2').tobytes())
                total_samples += len(values)
                if (index+1) % 25 == 0:
                    print('long segments', index+1, '/', count, flush=True)
        report['long_test'] = {'characters': len(TEXTS['vi'])*count, 'segments': count,
                               'elapsed_s': time.perf_counter()-begin, 'duration_s': total_samples/audio.sample_rate,
                               'pcm_validation': inspect_wav(long_path),
                               'limitation': 'Repeated sentence; no natural long-form quality evaluation.'}
        report['status'] = 'SYNTHESIS_AND_PCM_VALIDATED'
    except Exception as exc:
        report.update(status='FAILED', error=f'{type(exc).__name__}: {exc}')
        print(report['error'], flush=True)
    finally:
        stop.set()
        thread.join(2)
        report['sampled_peak_rss_bytes'] = max(rss, default=0)
        report['windows_peak_working_set_bytes'] = proc.memory_info().peak_wset
        (EVIDENCE/'sherpa_vi_benchmark.json').write_text(json.dumps(report, indent=2, ensure_ascii=False),encoding='utf-8')
    return 0 if report['status'] == 'SYNTHESIS_AND_PCM_VALIDATED' else 1

if __name__ == '__main__':
    raise SystemExit(main())
