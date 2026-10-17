"""End-to-end test: PhotoCraft + fake ComfyUI + bridge.

python tests/e2e_headless.py /path/to/photocraft-cli            # headless (photocraft-cli serve)
python tests/e2e_headless.py /path/to/photocraft --desktop      # the real app with --control
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pccomfy.bridge import Bridge, Request  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402
from pccomfy.photocraft import PhotoCraft  # noqa: E402
from pccomfy.workflows import GenParams  # noqa: E402

CLI = sys.argv[1]
DESKTOP = "--desktop" in sys.argv
PORT = 7982 if DESKTOP else 7979
tmp = Path(tempfile.mkdtemp(prefix="pcc-e2e-"))
xch = tmp / "exchange"
xch.mkdir()
token = tmp / "token"
out = Path(os.environ.get("E2E_OUT", tmp / "out"))
out.mkdir(parents=True, exist_ok=True)

img = Image.new("RGB", (640, 400), (40, 90, 160))
d = ImageDraw.Draw(img)
d.rectangle([80, 60, 560, 340], fill=(220, 180, 60))
d.ellipse([250, 130, 390, 270], fill=(200, 40, 40))
img.save(xch / "test.png")

args = ["--control", str(PORT)] if DESKTOP else ["serve", "--port", str(PORT)]
serve = subprocess.Popen([CLI, *args, "--control-token-file", str(token),
                          "--automation-read-root", str(xch), "--automation-write-root", str(xch)],
                         stdout=subprocess.DEVNULL, stderr=open(tmp / "photocraft.log", "w"))
fake = subprocess.Popen([sys.executable, str(ROOT / "tests" / "fake_comfy.py"), "8189"])
for _ in range(240):  # the desktop app takes longer to start
    time.sleep(0.5)
    if token.exists():
        try:
            PhotoCraft(port=PORT, token_file=token, headless=not DESKTOP).ping()
            break
        except Exception:
            pass
try:
    ctl = PhotoCraft(port=PORT, token_file=token, headless=not DESKTOP)
    bridge = Bridge(PhotoCraft(port=PORT, token_file=token, headless=not DESKTOP), ComfyUI("http://127.0.0.1:8189"), xch)
    log = lambda f, m: print(f"  {f:5.2f} {m}")  # noqa: E731

    def snapshot(name):
        if DESKTOP:
            ctl.call("ui.screenshot", {"path": f"{name}-ui.png"})
            Image.open(xch / f"{name}-ui.png").save(out / f"{name}-ui.png")
            os.remove(xch / f"{name}-ui.png")
        ctl.save(f"{name}.png")
        Image.open(xch / f"{name}.png").save(out / f"{name}.png")
        layers = ctl.document()["layers"]
        print("  layers:", [(l["name"], l.get("visible"), l.get("hasMask")) for l in layers])
        return layers

    ctl.open("test.png")

    print("1) inpaint without a selection → expected error")
    try:
        bridge.run(Request("inpaint", GenParams(prompt="cat", checkpoint="fake_sdxl.safetensors")), log)
        raise SystemExit("FAIL: expected an exception")
    except Exception as e:
        print("  OK:", e)

    print("2) inpaint with an elliptical selection, 2 variants")
    ctl.execute("select.rect", {"x": 240, "y": 120, "width": 160, "height": 160, "ellipse": True, "feather": 6})
    res = bridge.run(Request("inpaint", GenParams(prompt="cat", checkpoint="fake_sdxl.safetensors"), variants=2), log)
    print("  result:", res)
    layers = snapshot("after_inpaint")
    assert len(layers) == 3 and layers[0]["hasMask"] and layers[0]["name"].endswith("#1") and layers[0]["visible"] and not layers[1]["visible"], layers
    assert ctl.document()["hasSelection"], "the selection should be restored"
    assert sorted(os.listdir(xch)) == ["after_inpaint.png", "test.png"], os.listdir(xch)

    print("3) img2img without a selection (whole image)")
    ctl.execute("select.deselect")
    res = bridge.run(Request("img2img", GenParams(prompt="painting", checkpoint="fake_sdxl.safetensors", denoise=0.5)), log)
    layers = snapshot("after_img2img")
    assert len(layers) == 4 and not layers[0]["hasMask"]

    print("4) txt2img in a rectangular selection")
    ctl.execute("select.rect", {"x": 20, "y": 20, "width": 200, "height": 120})
    res = bridge.run(Request("txt2img", GenParams(prompt="forest", checkpoint="fake_sdxl.safetensors")), log)
    print("  result:", res)
    snapshot("after_txt2img")

    print("5) outpaint: +200 px right, +100 px top")
    for l in ctl.document()["layers"][:-1]:
        ctl.execute("layer.delete", {"layer": l["id"]})
    res = bridge.run(Request("outpaint", GenParams(prompt="more landscape", checkpoint="fake_sdxl.safetensors"),
                             outpaint=(0, 100, 200, 0), overlap=32), log)
    print("  result:", res)
    doc = ctl.document()
    assert (doc["width"], doc["height"]) == (840, 500), (doc["width"], doc["height"])
    snapshot("after_outpaint")
    print("\nALL OK →", out)
finally:
    serve.terminate()
    fake.terminate()
