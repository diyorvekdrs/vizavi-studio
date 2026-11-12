"""Connect Vizavi Studio to the Claude desktop app: adds (or removes) the "vizavi-studio" entry in the app's
claude_desktop_config.json, keeping everything else in that file exactly as it was (a copy is kept as .bak).
The Claude app reads the file when it starts, so it has to be restarted once afterwards."""
import json, os, shutil, sys
from pathlib import Path

NAME = "vizavi-studio"
APP = Path(__file__).resolve().parent.parent


def config_paths():
    """where the Claude app keeps its config: %APPDATA%\\Claude (also the Store version's private copy, if it has one)"""
    out = []
    if os.environ.get("VZ_CLAUDE_CONFIG"):                     # tests
        return [Path(os.environ["VZ_CLAUDE_CONFIG"])]
    if os.name == "nt":
        ad = os.environ.get("APPDATA")
        if ad:
            out.append(Path(ad) / "Claude" / "claude_desktop_config.json")
        la = os.environ.get("LOCALAPPDATA")
        if la:
            for pk in sorted((Path(la) / "Packages").glob("Claude_*")):
                f = pk / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json"
                if f.exists():
                    out.append(f)
    else:
        home = Path.home()
        out.append(home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
                   if sys.platform == "darwin" else home / ".config" / "Claude" / "claude_desktop_config.json")
    return out


def python_exe():
    """python.exe (not pythonw.exe): the connector talks to the Claude app over its standard input/output"""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        exe = exe.with_name("python.exe")
    return str(exe)


def entry():
    return {"command": python_exe(), "args": [str(APP / "studio" / "mcp_server.py")]}


def _read(f):
    if not f.exists():
        return {}
    data = json.loads(f.read_text(encoding="utf-8-sig") or "{}")
    if not isinstance(data, dict):
        raise ValueError("the Claude app's config is not a JSON object")
    return data


def _write(f, data):
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists():
        shutil.copy2(f, f.with_suffix(".json.bak"))
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)


def status():
    """{'connected': bool, 'current': bool (points at this install), 'path': str, 'problem': str}"""
    paths = config_paths()
    for f in paths:
        try:
            e = (_read(f).get("mcpServers") or {}).get(NAME)
        except (OSError, ValueError) as ex:
            return {"connected": False, "current": False, "path": str(f), "problem": f"Can't read {f}: {ex}"}
        if e:
            cur = e.get("command") == python_exe() and list(e.get("args") or []) == entry()["args"]
            return {"connected": True, "current": cur, "path": str(f), "problem": ""}
    return {"connected": False, "current": False, "path": str(paths[0]) if paths else "", "problem": ""}


def connect():
    paths = config_paths()
    if not paths:
        raise RuntimeError("The Claude desktop app's settings folder was not found.")
    done = []
    for f in paths:
        data = _read(f)                        # a damaged file raises: we never overwrite what we can't read
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
        servers[NAME] = entry()
        data["mcpServers"] = servers
        _write(f, data)
        done.append(str(f))
    return done


def disconnect():
    done = []
    for f in config_paths():
        try:
            data = _read(f)
        except (OSError, ValueError):
            continue
        if NAME in (data.get("mcpServers") or {}):
            del data["mcpServers"][NAME]
            _write(f, data)
            done.append(str(f))
    return done
