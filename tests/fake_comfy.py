"""Fake ComfyUI for testing the bridge without a GPU: same endpoints, "generation" = colour inversion."""

import io
import json
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageOps

UPLOADS: dict[str, bytes] = {}
OUTPUTS: dict[str, bytes] = {}
HISTORY: dict[str, dict] = {}
GRAPHS: list[dict] = []


def generate(graph: dict, pid: str) -> dict:
    nodes = {k: v for k, v in graph.items()}
    loads = [n for n in nodes.values() if n["class_type"] == "LoadImage"]
    batch = 1
    for n in nodes.values():
        for key in ("batch_size", "amount"):
            if key in n["inputs"]:
                batch = n["inputs"][key]
    if loads:
        src = Image.open(io.BytesIO(UPLOADS[loads[0]["inputs"]["image"]])).convert("RGB")
    else:
        lat = next(n for n in nodes.values() if n["class_type"] == "EmptyLatentImage")["inputs"]
        src = Image.new("RGB", (lat["width"], lat["height"]), (30, 160, 90))
    out_id = next(k for k, n in nodes.items() if n["class_type"] in ("SaveImage", "PreviewImage"))
    images = []
    for i in range(batch):
        im = ImageOps.invert(src) if i % 2 == 0 else ImageOps.grayscale(src).convert("RGB")
        name = f"fake_{pid}_{i}.png"
        b = io.BytesIO()
        im.save(b, "PNG")
        OUTPUTS[name] = b.getvalue()
        images.append({"filename": name, "subfolder": "", "type": "temp"})
    return {"outputs": {out_id: {"images": images}}, "status": {"status_str": "success", "completed": True, "messages": []}}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/system_stats":
            return self._send({"system": {"comfyui_version": "fake"}, "devices": [{"name": "cpu"}]})
        if u.path.startswith("/object_info/"):
            node = u.path.rsplit("/", 1)[1]
            if node == "CheckpointLoaderSimple":
                return self._send({node: {"input": {"required": {"ckpt_name": [["fake_sdxl.safetensors"], {}]}}}})
            if node == "KSampler":
                return self._send({node: {"input": {"required": {"sampler_name": [["euler", "dpmpp_2m"], {}],
                                                                  "scheduler": [["normal", "karras"], {}]}}}})
            return self._send({})
        if u.path.startswith("/history/"):
            pid = u.path.rsplit("/", 1)[1]
            return self._send({pid: HISTORY[pid]} if pid in HISTORY else {})
        if u.path == "/view":
            q = parse_qs(u.query)
            return self._send(OUTPUTS[q["filename"][0]], ctype="image/png")
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        if self.path == "/upload/image":
            ctype = self.headers["Content-Type"]
            boundary = ctype.split("boundary=")[1].encode()
            fields, filedata, filename = {}, None, None
            for part in body.split(b"--" + boundary):
                if b"\r\n\r\n" not in part:
                    continue
                head, data = part.split(b"\r\n\r\n", 1)
                data = data[:-2]
                head = head.decode()
                name = head.split('name="')[1].split('"')[0]
                if 'filename="' in head:
                    filename, filedata = head.split('filename="')[1].split('"')[0], data
                else:
                    fields[name] = data.decode()
            key = f"{fields.get('subfolder')}/{filename}" if fields.get("subfolder") else filename
            UPLOADS[key] = filedata
            return self._send({"name": filename, "subfolder": fields.get("subfolder", ""), "type": "input"})
        if self.path == "/prompt":
            j = json.loads(body)
            g = j["prompt"]
            GRAPHS.append(g)
            for nid, node in g.items():
                for k, v in node["inputs"].items():
                    if isinstance(v, list) and v and isinstance(v[0], str) and v[0] not in g:
                        return self._send({"error": {"message": "bad link"}, "node_errors": {nid: {"class_type": node["class_type"], "errors": [{"message": f"missing node {v[0]}", "details": k}]}}}, 400)
                    if v is None:
                        return self._send({"error": {"message": f"{nid}.{k} is None"}, "node_errors": {}}, 400)
            pid = uuid.uuid4().hex
            HISTORY[pid] = generate(g, pid)
            with open("/tmp/fake_comfy_last_graph.json", "w") as f:
                json.dump(g, f, indent=1)
            return self._send({"prompt_id": pid, "number": 1, "node_errors": {}})
        if self.path in ("/interrupt", "/queue"):
            return self._send({})
        self._send({"error": "not found"}, 404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8189
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
