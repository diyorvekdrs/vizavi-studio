"""Publish a new Vizavi Studio version for everyone who uses it (maintainer only - run dev/Publish update.cmd).

  py dev/publish_update.py [patch|minor|major|X.Y.Z] --notes "what's new"

1. writes the new version into studio/version.py and the file list into app/release.json
2. commits everything the repository tracks (.gitignore decides – settings, projects, models and your own
   library never leave this PC), tags it vX.Y.Z and pushes to GitHub
3. builds the release zip (Install Vizavi Studio.cmd + READ ME + app/) with its SHA-256 and publishes it as a
   GitHub release. Every friend's app sees it within a few hours (or right away with Settings → Check now)."""
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # C:\Vizavi Studio (the repository)
APP = ROOT / "app"
VFILE = APP / "studio" / "version.py"


def run(*cmd, capture=False):
    print("  $ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=capture)
    if r.returncode != 0:
        sys.exit(f"\nStopped: {' '.join(cmd[:2])} failed.\n{(r.stderr or '') if capture else ''}")
    return (r.stdout or "").strip() if capture else ""


def release_body(notes, repo):
    """the release page text: what's new first (the app's "What's new" shows it too), then how to get it"""
    lines = [l.strip() for l in re.split(r"(?<=[.!])\s+(?=[A-Z])|;\s+|\n", notes) if l.strip()]
    whats_new = "\n".join(f"- {l}" for l in lines) if len(lines) > 1 else notes
    return (f"## What's new\n\n{whats_new}\n\n---\n\n"
            "**Already using Vizavi Studio?** The app shows *Update available* at the top – click **Update now**.\n\n"
            f"**New here?** Download [Vizavi-Studio-Installer.cmd](https://github.com/{repo}/releases/latest/download/"
            "Vizavi-Studio-Installer.cmd) and double-click it. "
            f"[Install guide](https://github.com/{repo}#-install)")


def bump(cur, how):
    if re.fullmatch(r"\d+\.\d+\.\d+", how):
        return how
    a, b, c = (int(x) for x in cur.split("."))
    return {"major": f"{a + 1}.0.0", "minor": f"{a}.{b + 1}.0"}.get(how, f"{a}.{b}.{c + 1}")


def main():
    try:
        sys.stdout.reconfigure(errors="replace")       # a Windows console can't show every character
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("how", nargs="?", default="patch")
    ap.add_argument("--notes", default="")
    ap.add_argument("--dry", action="store_true", help="build the zip but don't commit, push or publish")
    a = ap.parse_args()
    src = VFILE.read_text(encoding="utf-8")
    cur = re.search(r'VERSION = "([^"]+)"', src)[1]
    repo = re.search(r'UPDATE_REPO = "([^"]+)"', src)[1]
    new = bump(cur, a.how)
    tags = run("git", "tag", "--list", capture=True).split()
    if f"v{new}" in tags:
        sys.exit(f"v{new} was already published. Use a higher number.")
    print(f"\nPublishing Vizavi Studio {cur} -> {new} to github.com/{repo}\n")
    VFILE.write_text(src.replace(f'VERSION = "{cur}"', f'VERSION = "{new}"'), encoding="utf-8")
    run("git", "add", "-A")
    files = [f[4:] for f in run("git", "ls-files", "--cached", "app", capture=True).splitlines()
             if f.startswith("app/") and f != "app/release.json"]
    (APP / "release.json").write_text(json.dumps({"version": new, "files": sorted(files + ["release.json"])},
                                                 indent=0), encoding="utf-8")
    run("git", "add", "-A")
    leaked = [f for f in run("git", "diff", "--cached", "--name-only", capture=True).splitlines()
              if re.search(r"settings\.json|/Projects/|\.venv|/models/|\.session_token|\.ui_profile", f)]
    if leaked:
        VFILE.write_text(src, encoding="utf-8")
        sys.exit("Stopped – these private files would be published: " + ", ".join(leaked))
    notes = a.notes.strip() or f"Vizavi Studio {new}"
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    zname = f"vizavi-studio-{new}.zip"
    if a.dry:
        staged = run("git", "diff", "--cached", "--name-only", capture=True).splitlines()
        print(f"Dry run – {len(files) + 1} files would be in the release; changed since the last one:")
        print("\n".join("   " + f for f in staged) or "   (nothing)")
        VFILE.write_text(src, encoding="utf-8")
        run("git", "reset", "-q")
        return
    run("git", "commit", "-m", f"Vizavi Studio {new}\n\n{notes}")
    run("git", "tag", f"v{new}")
    run("git", "push", "origin", "HEAD", "--tags")
    run("git", "archive", "--format=zip", "-o", str(dist / zname), f"v{new}")
    stable = dist / "Vizavi-Studio-Setup.zip"          # same file under a fixed name: the README's download button
    stable.write_bytes((dist / zname).read_bytes())
    h = hashlib.sha256((dist / zname).read_bytes()).hexdigest()
    (dist / "SHA256SUMS.txt").write_text(f"{h}  {zname}\n{h}  {stable.name}\n", encoding="utf-8")
    quick = ROOT / "Vizavi-Studio-Installer.cmd"      # the one-small-file installer (always fetches the newest)
    run("gh", "release", "create", f"v{new}", str(dist / zname), str(stable), str(dist / "SHA256SUMS.txt"),
        *([str(quick)] if quick.exists() else []),
        "--repo", repo, "--title", f"Vizavi Studio {new}", "--notes", release_body(notes, repo))
    print(f"\nDone. Vizavi Studio {new} is published: https://github.com/{repo}/releases/tag/v{new}")
    print("Friends' apps show 'Update available' (at their next start, or Settings -> Check now).")


if __name__ == "__main__":
    main()
