"""Builds the sound (audio.py -> mix.wav) if needed and joins it with <outdir>/video.mp4.
usage: python make_final.py [outdir] [final_name.mp4]"""
import subprocess, os, sys, time
from ff import ffmpeg_exe

ff = ffmpeg_exe()
outdir = sys.argv[1] if len(sys.argv) > 1 else "out"
name = sys.argv[2] if len(sys.argv) > 2 else "final_2k_24fps.mp4"
if not os.path.exists("mix.wav"):
    print("1/2 building sound (ambient + SFX)... (~30 s)", flush=True)
    t = time.time()
    subprocess.run([sys.executable, "vzfast.py", "audio.py"], check=True)
    print(f"    sound ready in {time.time() - t:.0f}s", flush=True)
else:
    print("1/2 using existing mix.wav (delete it to rebuild the sound)", flush=True)
print("2/2 joining video + sound...", flush=True)
subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-stats", "-y", "-i", os.path.join(outdir, "video.mp4"),
                "-i", "mix.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                "-movflags", "+faststart", name], check=True)
print("done ->", name)
