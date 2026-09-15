"""Real offline acceptance tests; preserves CP0 evidence and reports actual audio only."""
import json, sys, time, traceback, socket
from pathlib import Path
from dataclasses import asdict
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'prototype'))
import app
import numpy as np
import soundfile as sf
import psutil
from core.text_utils import TEST_SENTENCES, VI_TEST_CASES, CONVERSATION_TEST
from core.audio_utils import merge_segments, export_mp3, write_wav


def validate(path):
    data, sr = sf.read(path)
    assert data.size and np.isfinite(data).all() and np.max(np.abs(data)) > 0
    return {'duration': len(data)/sr, 'sample_rate': sr, 'rms': float(np.sqrt(np.mean(data**2)))}


def main():
    report = ROOT / 'reports'
    report.mkdir(exist_ok=True)
    run = {'environment': app.get_hardware_info(), 'runtimes': app.get_runtime_versions(),
           'languages': [], 'vietnamese': [], 'conversation': {}, 'cloning': [], 'errors': []}
    def save():
        (report/'prototype_results.json').write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding='utf-8')
    def record(result):
        row = asdict(result)
        row['ram_mb'] = round(psutil.Process().memory_info().rss/1024**2, 1)
        row['vram_mb'] = None
        if result.status == 'PASS':
            try:
                row['audio_validation'] = validate(result.wav_path)
                row['mp3_status'] = 'PASS' if result.mp3_path and validate(result.mp3_path) else 'FAIL'
            except Exception:
                row['status'] = 'FAIL'; row['error'] = traceback.format_exc()
        print(row['language'], row['voice'], row['status'], row.get('error'), flush=True)
        return row
    # Prevent outbound inference/downloads; local UI is tested separately.
    original_connect = socket.socket.connect
    def offline(*args, **kwargs):
        raise OSError('Offline acceptance test: outbound sockets disabled')
    socket.socket.connect = offline
    try:
        for lang in app.manager.get_languages():
            for voice in app.manager.get_voices(lang):
                run['languages'].append(record(app.manager.synthesize(TEST_SENTENCES[lang], lang, voice.id)))
                save()
        for case, text in VI_TEST_CASES.items():
            row = record(app.manager.synthesize(text, 'vi', 'vi_vais1000'))
            row['case'] = case
            run['vietnamese'].append(row); save()
        turns=[]; paths=[]; pauses=[250,500,750,250]
        for i, t in enumerate(CONVERSATION_TEST):
            voice='vieneu:Trúc Ly' if i%2==0 else 'vieneu:Minh Đức'
            row=record(app.manager.synthesize(t['text'], 'vi', voice))
            row.update(speaker=t['speaker'], pause_ms=pauses[i]);turns.append(row)
            if row['status']=='PASS':paths.append(row['wav_path'])
        conv={'turns':turns,'status':'FAIL'}
        if len(paths)==4:
            out=app.manager.output_dir/'acceptance_conversation.wav'
            merge_segments(paths,out,pauses_ms=pauses)
            mp3=export_mp3(out);check=validate(out)
            expected=sum(validate(p)['duration'] for p in paths)+sum(pauses)/1000
            assert abs(check['duration']-expected)<0.01
            merged,sr=sf.read(out);offset=0
            for path,pause in zip(paths,pauses):
                segment, rate=sf.read(path);assert rate==sr
                np.testing.assert_allclose(merged[offset:offset+len(segment)], segment, atol=1/32768)
                offset+=len(segment);n=round(sr*pause/1000)
                assert np.max(np.abs(merged[offset:offset+n]))==0
                offset+=n
            conv.update(status='PASS',wav_path=str(out),mp3_path=str(mp3),validation=check,
                        order_and_pauses='PASS',mp3_status='PASS' if validate(mp3) else 'FAIL')
        run['conversation']=conv;save()
        # Reuse legally scoped synthetic CP0 fixture; never a private person's recording.
        source=ROOT/'.cp0/audio/vieneu_cloning_poc/ref_30s.wav'
        samples,sr=sf.read(source)
        for seconds in (5,10,30):
            ref=app.manager.temp_dir/f'synthetic_reference_{seconds}s.wav'
            write_wav(ref,np.tile(samples, int(np.ceil(seconds*sr/len(samples))))[:seconds*sr],sr)
            profile=app.manager.prepare_clone_profile(ref)
            result=app.manager.synthesize_clone(
                'Xin chào, đây là bài kiểm tra chức năng nhân bản giọng nói chạy hoàn toàn trên máy tính.',
                ref, profile=profile)
            row=record(result);row.update(reference_seconds=validate(ref)['duration'],
                reference_origin='Repeated/cropped existing synthetic CP0 fixture; duration stress test, not human similarity validation',
                pronunciation='NOT_TESTED',naturalness='NOT_TESTED',similarity='NOT_TESTED',stability='NOT_TESTED')
            run['cloning'].append(row);save()
    except Exception:
        run['errors'].append(traceback.format_exc());raise
    finally:
        socket.socket.connect=original_connect
        run['models']=app.manager.get_all_health();save()

if __name__=='__main__':main()
