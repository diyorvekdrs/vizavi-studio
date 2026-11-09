"""Word-level transcription worker. Run as a subprocess by the app:
  python -m studio.transcribe <audio> <out.json> --lang uz --model large-v3 --device auto [--prompt file]
Backends tried in order: faster-whisper (CUDA, then CPU int8), openai-whisper.
Prints 'PROGRESS <0..1>' lines and 'LOG <text>' lines."""
import argparse, json, os, sys, threading, time, warnings
from pathlib import Path

# quiet, harmless library noise (symlink cache warning on Windows, HF token hint, progress bars)
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
warnings.filterwarnings("ignore")


def add_nvidia_dlls():
    """ctranslate2 (faster-whisper) needs cublas64_12.dll / cudnn DLLs; the app installs them with pip
    (nvidia-cublas-cu12, nvidia-cudnn-cu12) - make Windows find them."""
    if os.name != "nt":
        return
    import glob, site
    roots = list(site.getsitepackages()) + [site.getusersitepackages()]
    for r in roots:
        for b in glob.glob(os.path.join(r, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(b)
            except Exception:
                pass
            os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")


add_nvidia_dlls()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "claude" / "tools"))
import vz_analysis as va  # noqa: E402


def log(s):
    print("LOG " + s, flush=True)


def prog(x):
    print(f"PROGRESS {max(0.0, min(1.0, x)):.3f}", flush=True)


MODEL_GB = {"large-v3": 3.1, "large-v2": 3.1, "large-v1": 3.1, "large": 3.1, "large-v3-turbo": 1.6, "turbo": 1.6,
            "distil-large-v3": 1.5, "medium": 1.5, "small": 0.48, "base": 0.15, "tiny": 0.08}


def hf_cache():
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    return Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"


def ensure_model(name):
    """local path of the faster-whisper model; downloads it once with visible progress."""
    from faster_whisper.utils import download_model
    try:
        from faster_whisper.utils import _MODELS
        repo = _MODELS.get(name, name)
    except Exception:
        repo = name if "/" in name else f"Systran/faster-whisper-{name}"
    try:
        return download_model(name, local_files_only=True)
    except Exception:
        pass
    total = MODEL_GB.get(name, 0)
    folder = hf_cache() / ("models--" + repo.replace("/", "--"))
    log(f"Downloading the Whisper model '{name}' (~{total or '?'} GB, one time only). "
        f"This can take a while on a slow network…")
    done = threading.Event()

    def watch():
        last = -1
        while not done.wait(3):
            try:
                got = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 1e9
            except Exception:
                continue
            if abs(got - last) >= 0.02:
                last = got
                log(f"  downloaded {got:.2f}" + (f" / ~{total} GB" if total else " GB"))
                if total:
                    prog(0.4 * min(1.0, got / total))
    th = threading.Thread(target=watch, daemon=True)
    th.start()
    try:
        path = download_model(name)
    except Exception as e:
        raise RuntimeError(f"could not download the Whisper model from huggingface.co ({type(e).__name__}: "
                           f"{str(e)[:200]}). The network may block it (university/office firewall): try another "
                           f"network once, or set a smaller model in settings.json, e.g. \"whisper_model\": \"small\".")
    finally:
        done.set()
    log("Whisper model ready.")
    return path


def hotwords(script, limit=300):
    """the script's distinctive words (long / rare), so Whisper spells them right in every window."""
    import re
    if not script:
        return None
    seen, out = set(), []
    for w in sorted(re.findall(r"[\w'ʻʼ’‘-]+", script), key=lambda x: -len(x)):
        k = w.lower()
        if len(k) >= 6 and k not in seen:
            seen.add(k); out.append(w)
    s = " ".join(out)[:limit].rsplit(" ", 1)[0]
    return s or None


def cuda_devices():
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count()
    except Exception:
        return 0


def cuda_tries():
    """float16 needs ~5 GB VRAM for large-v3; small cards get int8_float16 (half the memory, same words).
    Each try also falls back if the card runs out of memory mid-way."""
    ct = os.environ.get("VZ_SPEECH_COMPUTE", "float16")
    t = [("cuda", ct)] + ([("cuda", "int8_float16")] if ct != "int8_float16" else [])
    return t + [("cpu", "int8")]


def run_faster(audio, dur, a, prompt):
    from faster_whisper import WhisperModel
    path = ensure_model(a.model)
    if a.device in ("auto", "cuda") and cuda_devices() > 0:
        tries = cuda_tries()
    else:
        if a.device != "cpu":
            log("No NVIDIA/CUDA GPU found → transcribing on the CPU (slower, same quality).")
        tries = [("cpu", "int8")]
    last = None
    for dev, ct in tries:
        try:
            log(f"faster-whisper: loading {a.model} on {dev}…")
            m = WhisperModel(path, device=dev, compute_type=ct, cpu_threads=max(1, (os.cpu_count() or 4) - 1))
            kw = dict(language=a.lang or None, word_timestamps=True, beam_size=5, initial_prompt=prompt,
                      condition_on_previous_text=False, vad_filter=False)
            hot = hotwords(a.full_script)
            try:   # hotwords reach EVERY 30 s window (the initial prompt only helps the first one)
                segs, info = m.transcribe(audio, hotwords=hot, **kw) if hot else m.transcribe(audio, **kw)
            except TypeError:   # older faster-whisper without hotwords
                segs, info = m.transcribe(audio, **kw)
            words, segments = [], []
            log("transcribing…")
            for s in segs:
                segments.append({"s": round(s.start, 3), "e": round(s.end, 3), "text": s.text.strip()})
                for w in s.words or []:
                    words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3),
                                  "p": round(w.probability, 3)})
                prog(0.4 + (0.2 if a.uz_model else 0.6) * s.end / max(dur, 1e-6))
            return words, segments, f"faster-whisper {a.model} ({dev} {ct})"
        except Exception as e:  # CUDA libs missing etc. -> next
            last = e
            log(f"faster-whisper on {dev} failed: {type(e).__name__}: {str(e)[:300]}")
    raise last


def ensure_ct2(model_id, models_dir):
    """converts a Hugging Face Whisper fine-tune (e.g. islomov/rubaistt_v2_medium) to CTranslate2 once."""
    out = Path(models_dir) / (model_id.replace("/", "__") + "-ct2")
    if (out / "model.bin").exists() and (out / "tokenizer.json").exists():
        return out
    log(f"Preparing the Uzbek model {model_id} (one time: download ~3 GB + convert, a few minutes)…")
    folder = hf_cache() / ("models--" + model_id.replace("/", "--"))
    done = threading.Event()

    def watch():
        last = -1
        while not done.wait(4):
            try:
                got = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 1e9
            except Exception:
                continue
            if abs(got - last) >= 0.05:
                last = got
                log(f"  Uzbek model downloaded {got:.2f} / ~3.1 GB")
    th = threading.Thread(target=watch, daemon=True); th.start()
    try:
        from ctranslate2.converters import TransformersConverter
        out.mkdir(parents=True, exist_ok=True)
        TransformersConverter(model_id, load_as_float16=True, low_cpu_mem_usage=True).convert(
            str(out), quantization="float16", force=True)
        from transformers import WhisperFeatureExtractor, WhisperTokenizerFast
        WhisperTokenizerFast.from_pretrained(model_id).save_pretrained(str(out))
        WhisperFeatureExtractor.from_pretrained(model_id).save_pretrained(str(out))
    finally:
        done.set()
    log("Uzbek model ready.")
    return out


def run_uzbek(audio, a):
    """text from the Uzbek-trained model (VAD chunks <= 25 s, no timestamp tokens needed)."""
    from faster_whisper import WhisperModel
    path = ensure_ct2(a.uz_model, a.models_dir)
    tries = cuda_tries() if a.device != "cpu" and cuda_devices() > 0 else [("cpu", "int8")]
    last = None
    for dev, ct in tries:
        try:
            log(f"Uzbek model: transcribing on {dev}…")
            m = WhisperModel(str(path), device=dev, compute_type=ct, cpu_threads=max(1, (os.cpu_count() or 4) - 1))
            segs, _ = m.transcribe(audio, language="uz", beam_size=5, without_timestamps=True,
                                   condition_on_previous_text=False, vad_filter=True,
                                   vad_parameters={"max_speech_duration_s": 25, "min_silence_duration_ms": 300})
            texts, segl = [], []
            for sg in segs:
                texts.append(sg.text.strip())
                segl.append({"s": round(sg.start, 2), "e": round(sg.end, 2), "text": sg.text.strip()})
                prog(0.6 + 0.35 * min(1.0, sg.end / max(len(audio) / 16000, 1e-6)))
            a.uz_segments = segl
            return " ".join(t for t in texts if t), f"{a.uz_model} ({dev})"
        except Exception as e:
            last = e
            log(f"Uzbek model on {dev} failed: {type(e).__name__}: {str(e)[:300]}")
    raise last


def run_openai(audio, dur, a, prompt):
    import whisper, torch
    dev = "cuda" if (a.device != "cpu" and torch.cuda.is_available()) else "cpu"
    log(f"openai-whisper: loading {a.model} on {dev} (first time downloads the model)...")
    m = whisper.load_model(a.model, device=dev)
    r = m.transcribe(audio, language=a.lang or None, word_timestamps=True, initial_prompt=prompt,
                     fp16=(dev == "cuda"), condition_on_previous_text=False, verbose=None)
    words, segments = [], []
    for s in r["segments"]:
        segments.append({"s": round(s["start"], 3), "e": round(s["end"], 3), "text": s["text"].strip()})
        for w in s.get("words", []):
            words.append({"w": w["word"].strip(), "s": round(w["start"], 3), "e": round(w["end"], 3),
                          "p": round(w.get("probability", 0), 3)})
    return words, segments, f"openai-whisper {a.model} ({dev})"


def run_fake(dur, prompt):
    """test hook only (VIZAVI_FAKE_TRANSCRIBE=1): spreads the script words evenly."""
    toks = (prompt or "test words only").split()
    step = (dur - 1.0) / max(1, len(toks))
    words = [{"w": t, "s": round(0.5 + k * step, 3), "e": round(0.5 + (k + 0.8) * step, 3), "p": 1.0}
             for k, t in enumerate(toks)]
    return words, [{"s": 0.5, "e": dur - 0.5, "text": " ".join(toks)}], "fake (test)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio"); ap.add_argument("out")
    ap.add_argument("--lang", default="uz"); ap.add_argument("--model", default="large-v3")
    ap.add_argument("--device", default="auto"); ap.add_argument("--prompt", default="")
    ap.add_argument("--uz-model", default=""); ap.add_argument("--models-dir", default="")
    a = ap.parse_args()
    t0 = time.time()
    audio = va.decode_audio(a.audio, 16000)
    dur = len(audio) / 16000
    log(f"audio: {dur:.2f}s")
    prompt, a.full_script = None, ""
    if a.prompt and Path(a.prompt).exists():
        a.full_script = Path(a.prompt).read_text(encoding="utf-8").strip()
        prompt = a.full_script[:700] or None
    if os.environ.get("VIZAVI_FAKE_TRANSCRIBE") == "1":
        words, segments, backend = run_fake(dur, prompt)
    else:
        errors = []
        for fn in (run_faster, run_openai):
            try:
                words, segments, backend = fn(audio, dur, a, prompt)
                break
            except ImportError as e:
                errors.append(f"{fn.__name__}: not installed ({e})")
            except Exception as e:
                errors.append(f"{fn.__name__}: {type(e).__name__}: {str(e)[:300]}")
        else:
            log("all transcription backends failed:\n  " + "\n  ".join(errors))
            sys.exit(2)
    words_large, uz_text, segments_large = words, "", list(segments)
    if a.uz_model and os.environ.get("VIZAVI_FAKE_TRANSCRIBE") != "1":
        try:
            uz_text, uz_backend = run_uzbek(audio, a)
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from studio.align import align
            better, rep = align(words_large, uz_text, trust_text=True)   # Uzbek model's words on large-v3's timing
            if better and len(better) >= 0.5 * max(1, rep["script_words"]):
                words = [dict(w, src="audio") for w in better]
                segments = [{"s": words[0]["s"], "e": words[-1]["e"], "text": uz_text}]
                backend = f"{uz_backend} words + {backend} timing"
                log(f"Uzbek model text used ({len(words)} words)")
            else:
                log("Uzbek model output did not line up with the audio – keeping large-v3")
        except Exception as e:
            log(f"Uzbek model unavailable ({type(e).__name__}: {str(e)[:200]}) – keeping large-v3 text")
    prog(1)
    Path(a.out).write_text(json.dumps({"backend": backend, "language": a.lang, "duration": round(dur, 3),
                                       "seconds": round(time.time() - t0, 1), "words": words,
                                       "words_large_v3": words_large, "uzbek_text": uz_text,
                                       "segments_large_v3": segments_large, "segments_uzbek": getattr(a, "uz_segments", []),
                                       "segments": segments}, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"done with {backend}: {len(words)} words in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
