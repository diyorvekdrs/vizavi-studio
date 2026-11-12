import os, sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
KIT = APP / "kit"
CL = APP / "claude"
TOOLS = CL / "tools"
ENGINES = CL / "engines"
FONTS = CL / "fonts"
LIB = APP / "library"
SETTINGS = Path(os.environ["VZ_SETTINGS"]) if os.environ.get("VZ_SETTINGS") else APP / "settings.json"   # tests
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def is_inside(path, root):
    """True when `path` really lies inside `root` (symlinks and ../ resolved, case-insensitive on Windows).
    A plain startswith() on the text also accepts sibling folders such as Projects2 - this does not."""
    try:
        p = os.path.normcase(os.path.realpath(str(path)))
        r = os.path.normcase(os.path.realpath(str(root)))
        return os.path.commonpath([p, r]) == r
    except (ValueError, OSError):
        return False


def safe_member(name):
    """A zip member name as a clean relative posix path, or None when it could escape the target folder
    (absolute path, drive letter, '..', NTFS stream ':')."""
    n = str(name).replace("\\", "/")
    if not n or n.startswith("/") or (len(n) > 1 and n[1] == ":"):
        return None
    parts = [x for x in n.split("/") if x not in ("", ".")]
    if not parts or ".." in parts or any(":" in x for x in parts):
        return None
    return "/".join(parts)
