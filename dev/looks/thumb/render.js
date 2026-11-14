// node render.js stills <id> t1 t2 ...  |  node render.js clip <id> <out.mp4> [fps]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path'), fs = require('fs');
(async () => {
  const [mode, id, ...args] = process.argv.slice(2);
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
  page.on('pageerror', e => console.error('PAGEERR', id, e.message));
  await page.goto('file://' + path.join(__dirname, 'index.html'));
  const dur = await page.evaluate(i => window.load(i), id);
  const shot = () => page.locator('#c').screenshot({ type: 'jpeg', quality: 92 });
  if (mode === 'stills') {
    const dir = path.join(__dirname, 'out'); fs.mkdirSync(dir, { recursive: true });
    for (const a of args) { await page.evaluate(t => window.renderAt(t), +a); fs.writeFileSync(path.join(dir, `${id}_${(+a).toFixed(2)}.jpg`), await shot()); }
  } else {
    const out = args[0], fps = +(args[1] || 24), tmp = out.replace(/\.mp4$/, '.part.mp4');
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
      '-vf', 'scale=480:270:flags=lanczos', '-c:v', 'libx264', '-profile:v', 'main', '-preset', 'slow', '-crf', '25', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', tmp],
      { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let n = 0; n < Math.round(dur * fps); n++) {
      await page.evaluate(t => window.renderAt(t), n / fps);
      const b = await shot(); if (!ff.stdin.write(b)) await new Promise(r => ff.stdin.once('drain', r));
    }
    ff.stdin.end(); const code = await new Promise(r => ff.on('close', r));
    if (code === 0) fs.renameSync(tmp, out); else { console.error('ffmpeg failed'); process.exitCode = 1; }
  }
  await browser.close();
})();
