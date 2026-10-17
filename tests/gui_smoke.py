"""Window smoke test: headless PhotoCraft + fake ComfyUI, click "Generate", take a screenshot.

xvfb-run -s "-screen 0 1000x800x24" python tests/gui_smoke.py <photocraft-cli> <screenshot.png>
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy.gui import App  # noqa: E402
from pccomfy.photocraft import PhotoCraft  # noqa: E402

CLI, SHOT = sys.argv[1], sys.argv[2]
tmp = Path(tempfile.mkdtemp(prefix="pcc-gui-"))
xch, token = tmp / "x", tmp / "token"
xch.mkdir()
Image.new("RGB", (512, 384), (60, 120, 200)).save(xch / "t.png")
serve = subprocess.Popen([CLI, "serve", "--port", "7980", "--control-token-file", str(token),
                          "--automation-read-root", str(xch), "--automation-write-root", str(xch)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
fake = subprocess.Popen([sys.executable, str(ROOT / "tests" / "fake_comfy.py"), "8190"])
time.sleep(1.5)
try:
    ctl = PhotoCraft(port=7980, token_file=token, headless=True)
    ctl.open("t.png")
    ctl.execute("select.rect", {"x": 100, "y": 100, "width": 200, "height": 150, "ellipse": True})
    cfgmod.STATE_FILE = tmp / "state.json"
    cfg = cfgmod._merge(cfgmod.DEFAULTS, {
        "photocraft": {"port": 7980, "token_file": str(token), "exchange_dir": str(xch), "headless": True},
        "comfyui": {"url": "http://127.0.0.1:8190", "workflows_dir": str(tmp / "wf")}})
    app = App(cfg)
    app.t_prompt.insert("1.0", "ginger cat sleeping on a windowsill, soft light")

    def shot(name):
        app.root.update()
        x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
        w, h = app.root.winfo_width(), app.root.winfo_height()
        ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(name)

    app.root.after(1500, app.generate)
    app.root.after(5000, lambda: (shot(SHOT), print("status:", app.v_status.get()), print("conn:", app.v_conn.get())))
    app.root.after(5200, lambda: (app.v_mode.set("outpaint"), app._on_mode()))
    app.root.after(5800, lambda: shot(SHOT.replace(".png", "-outpaint.png")))
    app.root.after(6200, app.root.destroy)
    app.root.mainloop()
    print("layers:", [l["name"] for l in ctl.document()["layers"]])
finally:
    serve.terminate()
    fake.terminate()
