"""Vizavi Studio - double-click to start. A small local engine starts and the app opens in its own
Edge/Chrome app window (nothing to install). Drop narration audio, assets or a zip from Claude on it
(or on the desktop shortcut, or right-click a file -> Send to -> Vizavi Studio)."""
import os, sys, traceback
from pathlib import Path

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))
os.chdir(APP)
try:   # native crashes (no Python traceback) are written here
    import faulthandler
    _fh = open(APP / "crash_native.log", "a", encoding="utf-8")
    _fh.write(f"\n--- start {__import__('time').strftime('%Y-%m-%d %H:%M:%S')} python {sys.version.split()[0]}\n"); _fh.flush()
    faulthandler.enable(_fh, all_threads=True)
except Exception:
    pass
try:
    from studio import server
    server.main(sys.argv[1:])
except Exception:
    msg = traceback.format_exc()
    (APP / "crash.log").write_text(msg, encoding="utf-8")
    try:
        import tkinter, tkinter.messagebox as mb
        tkinter.Tk().withdraw()
        mb.showerror("Vizavi Studio", msg[-1500:])
    except Exception:
        pass
