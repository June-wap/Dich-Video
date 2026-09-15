"""CP0.1 VieNeu v3 Turbo Voice Cloning POC."""
import hashlib, importlib.metadata, json, os, socket, sys, time, wave
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cp0/audio/vieneu_cloning_poc"
EV = ROOT / "reports/evidence/cp0_1"
OUT.mkdir(parents=True, exist_ok=True)


def sf(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def iw(p):
    with wave.open(str(p), "rb") as w:
        n, r = w.getnframes(), w.getframerate()
    return {"dur": round(n / r, 3), "rate": r, "bytes": Path(p).stat().st_size}


def ww(p, s, sr):
    c = (np.clip(s, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(c.tobytes())


def phase1_init(R):
    """Init VieNeu engine."""
    print("[1] Init VieNeu v3 Turbo...")
    t0 = time.perf_counter()
    from vieneu import Vieneu
    eng = Vieneu(mode="v3turbo")
    R["load_s"] = round(time.perf_counter() - t0, 3)
    R["sr"] = eng.sample_rate
    print(f"  Loaded in {R['load_s']}s, SR={eng.sample_rate}")
    return eng


def phase2_preset(eng, R):
    """Generate preset voice baseline."""
    print("[2] Preset baseline...")
    txt = "Xin chào, đây là hệ thống chuyển văn bản thành giọng nói."
    t1 = time.perf_counter()
    w0 = eng.infer(text=txt)
    gs = time.perf_counter() - t1
    p0 = OUT / "preset.wav"
    ww(p0, w0, eng.sample_rate)
    i0 = iw(p0)
    R["preset"] = {
        "txt": txt, "gen_s": round(gs, 3), "dur": i0["dur"],
        "rtf": round(gs / i0["dur"], 4),
        "rms": round(float(np.sqrt(np.mean(w0 ** 2))), 4),
        "sha": sf(p0), "path": str(p0.relative_to(ROOT)), "ok": True,
    }
    print(f"  preset {i0['dur']}s rtf={R['preset']['rtf']}")



def phase3_refs(eng, R):
    """Generate reference audio segments."""
    print("[3] Ref audio...")
    refs = {
        "5s": "Trí tuệ nhân tạo đang thay đổi thế giới xung quanh chúng ta.",
        "10s": "Công nghệ giọng nói ngày càng phát triển. Điều này mở ra nhiều ứng dụng hữu ích.",
        "30s": ("Trong những năm gần đây công nghệ AI tiến bộ vượt bậc. "
                "Hệ thống tạo giọng nói tự nhiên. "
                "Công nghệ nhân bản giọng nói mô phỏng đặc điểm giọng nói "
                "từ đoạn ghi âm ngắn. Ứng dụng trong giáo dục và giải trí."),
    }
    rw = {}
    for l, t in refs.items():
        try:
            w = eng.infer(text=t)
            p = OUT / f"ref_{l}.wav"
            ww(p, w, eng.sample_rate)
            rw[l] = p
            print(f"  ref {l}: {iw(p)['dur']}s")
        except Exception as e:
            R["errors"].append(f"ref {l}:{e}")
    return rw


def phase4_clone(eng, rw, R):
    """Voice cloning with each reference."""
    print("[4] Clone tests...")
    ct = "Chào mừng bạn đến với phần mềm giọng nói thông minh."
    ct2 = "Hôm nay thời tiết đẹp, chúng ta đi dạo công viên."
    for l, rp in rw.items():
        print(f"  clone {l}...")
        try:
            tr = time.perf_counter()
            spk, rc = eng.encode_reference(str(rp))
            rt = time.perf_counter() - tr
            tg = time.perf_counter()
            wc = eng.infer(text=ct, ref_audio=str(rp))
            gs = time.perf_counter() - tg
            cp = OUT / f"clone_{l}.wav"
            ww(cp, wc, eng.sample_rate)
            ic = iw(cp)
            tg2 = time.perf_counter()
            wc2 = eng.infer(text=ct2, ref_audio=str(rp))
            gs2 = time.perf_counter() - tg2
            cp2 = OUT / f"clone_{l}_b.wav"
            ww(cp2, wc2, eng.sample_rate)
            ic2 = iw(cp2)
            run = {
                "ref": l, "ref_dur": iw(rp)["dur"], "ref_sha": sf(rp),
                "prep_s": round(rt, 3),
                "spk_shape": list(spk.shape) if spk is not None else None,
                "rc_shape": list(rc.shape) if rc is not None else None,
                "g1": {"txt": ct, "gen_s": round(gs, 3), "dur": ic["dur"],
                       "rtf": round(gs / ic["dur"], 4), "sha": sf(cp),
                       "rms": round(float(np.sqrt(np.mean(wc ** 2))), 4)},
                "g2": {"txt": ct2, "gen_s": round(gs2, 3), "dur": ic2["dur"],
                       "rtf": round(gs2 / ic2["dur"], 4), "sha": sf(cp2)},
                "status": "PASS",
            }
            R["cloning_tests"].append(run)
            print(f"    OK g1={ic['dur']}s g2={ic2['dur']}s")
        except Exception as e:
            import traceback
            R["cloning_tests"].append({
                "ref": l, "status": "FAILED",
                "error": str(e), "tb": traceback.format_exc(),
            })
            R["errors"].append(f"clone {l}:{e}")
            print(f"    FAIL:{e}")


def phase5_offline(eng, rw, R):
    """Offline test — block network and regenerate."""
    print("[5] Offline test...")
    _ri = socket.socket.__init__
    def _g(self, *a, **kw):
        raise OSError("blocked")
    socket.socket.__init__ = _g
    try:
        if rw.get("10s"):
            to = time.perf_counter()
            wo = eng.infer(text="Kiểm tra ngoại tuyến.", ref_audio=str(rw["10s"]))
            go = time.perf_counter() - to
            op = OUT / "offline.wav"
            ww(op, wo, eng.sample_rate)
            io = iw(op)
            R["offline"] = {"status": "PASS", "gen_s": round(go, 3),
                            "dur": io["dur"], "sha": sf(op)}
            print(f"  PASS {io['dur']}s")
        else:
            R["offline"] = {"status": "SKIPPED", "reason": "no 10s ref"}
    except Exception as e:
        R["offline"] = {"status": "FAILED", "error": str(e)}
        print(f"  FAIL:{e}")
    finally:
        socket.socket.__init__ = _ri


def main():
    import psutil
    proc = psutil.Process()
    R = {
        "task": "cp0_1_vieneu_cloning", "provider": "VieNeu v3 Turbo ONNX",
        "version": importlib.metadata.version("vieneu"), "device": "cpu",
        "runs": [], "errors": [], "cloning_tests": [],
    }
    try:
        eng = phase1_init(R)
    except Exception as e:
        R["errors"].append(str(e))
        R["status"] = "FAILED"
        with open(EV / "vieneu_cloning_poc.json", "w") as f:
            json.dump(R, f, indent=2, ensure_ascii=False)
        print(json.dumps(R, indent=2, ensure_ascii=False))
        sys.exit(1)
    try:
        phase2_preset(eng, R)
    except Exception as e:
        R["errors"].append(f"preset:{e}")
        R["preset"] = {"ok": False, "err": str(e)}
    rw = phase3_refs(eng, R)
    phase4_clone(eng, rw, R)
    phase5_offline(eng, rw, R)
    R["rss"] = proc.memory_info().rss
    pc = sum(1 for t in R["cloning_tests"] if t.get("status") == "PASS")
    R["status"] = "PASS" if pc >= 2 else ("PARTIAL" if pc >= 1 else "FAILED")
    with open(EV / "vieneu_cloning_poc.json", "w") as f:
        json.dump(R, f, indent=2, ensure_ascii=False)
    print(json.dumps(R, indent=2, ensure_ascii=False))
    sys.exit(0 if R["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()

