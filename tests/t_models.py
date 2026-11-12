import sys, os, types, tempfile, json
from pathlib import Path
APPDIR = os.environ.get("VZ_APP") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APPDIR); sys.path.insert(0, os.path.join(APPDIR, "claude", "tools"))
tmp = Path(tempfile.mkdtemp()); home = tmp / "home"; (home / ".cache" / "huggingface" / "hub").mkdir(parents=True)
os.environ["HOME"] = str(home); os.environ["USERPROFILE"] = str(home)
fails = []
def check(n, c, x=""):
    print(("ok   " if c else "FAIL ") + n, "" if c else x)
    if not c: fails.append(n)
# fake faster_whisper: the model "exists" only in the shared cache
calls = []
def download_model(name, output_dir=None, local_files_only=False, cache_dir=None):
    calls.append(cache_dir)
    if local_files_only and cache_dir and Path(cache_dir) == home / ".cache" / "huggingface" / "hub":
        return str(Path(cache_dir) / "models--Systran--faster-whisper-large-v3" / "snap")
    raise RuntimeError("not cached")
fw = types.ModuleType("faster_whisper"); fwu = types.ModuleType("faster_whisper.utils")
fwu.download_model = download_model; fwu._MODELS = {"large-v3": "Systran/faster-whisper-large-v3"}
sys.modules["faster_whisper"] = fw; sys.modules["faster_whisper.utils"] = fwu
os.environ["HF_HUB_CACHE"] = str(tmp / "appmodels")           # the installer's old setting
from studio import transcribe as T
p = T.ensure_model("large-v3")
check("model found in the shared cache, no download", "faster-whisper-large-v3" in p and len(calls) >= 2, (p, calls))
# ct2 fallback: the converted Uzbek model sits in the app's old models folder
old = T.APP_DIR / "models" / "islomov__rubaistt_v2_medium-ct2"
existed = old.exists()
if not existed:
    old.mkdir(parents=True); (old / "model.bin").write_text("x"); (old / "tokenizer.json").write_text("x")
got = T.ensure_ct2("islomov/rubaistt_v2_medium", tmp / "new_models")
check("converted Uzbek model reused from another folder", got == old, got)
if not existed:
    import shutil; shutil.rmtree(old)
# settings migration
from studio import core
core.SETTINGS = tmp / "settings.json"
core.SETTINGS.write_text(json.dumps({"projects_dir": str(tmp / "P"), "models_dir": str(core.APP / "models") + "\\"}))
check("installer's models_dir is reset to the shared cache", core.load_settings()["models_dir"] == "")
core.SETTINGS.write_text(json.dumps({"projects_dir": str(tmp / "P"), "models_dir": "D:\\my\\models"}))
check("a models_dir you chose yourself is kept", core.load_settings()["models_dir"] == "D:\\my\\models")
print("\nFAILS:", fails or "none")
