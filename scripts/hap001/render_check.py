import subprocess, os, json
ROOT = '/workspace/devPPL/.worktrees/t_361bfeec'
png = os.path.join(ROOT, 'scripts/hap001/demo_render.png')
url = 'http://127.0.0.1:8901/scripts/hap001/demo.html'
tmp_png = '/tmp/hap001_render.png'
r = subprocess.run(['/usr/bin/chromium-browser', '--headless', '--disable-gpu',
                    '--no-sandbox', '--screenshot=' + tmp_png, '--window-size=1400,900',
                    '--virtual-time-budget=8000', url],
                   capture_output=True, text=True, timeout=180)
print('rc', r.returncode, 'tmp_png', os.path.exists(tmp_png),
      os.path.getsize(tmp_png) if os.path.exists(tmp_png) else 0)
print('stderr_tail', r.stderr[-300:])
import shutil
if os.path.exists(tmp_png):
    shutil.copy(tmp_png, png)
print('png', os.path.exists(png), os.path.getsize(png) if os.path.exists(png) else 0)
r2 = subprocess.run(['/usr/bin/chromium-browser', '--headless', '--disable-gpu',
                     '--no-sandbox', '--dump-dom', '--virtual-time-budget=8000', url],
                    capture_output=True, text=True, timeout=180)
dom = r2.stdout
print('dom_len', len(dom))
data = json.load(open(os.path.join(ROOT, 'data/pilot/scores/estates.json'), encoding='utf-8'))
print('missing', [e['display_name'] for e in data['estates'] if e['display_name'] not in dom])
open(os.path.join(ROOT, 'scripts/hap001/demo_dom.html'), 'w', encoding='utf-8').write(dom)
