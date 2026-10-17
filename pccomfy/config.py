"""Configuration: ~/.config/pccomfy/config.toml (every field optional)."""

from __future__ import annotations

import copy
import json
import os
import tomllib
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "pccomfy"
CONFIG_FILE = CONFIG_DIR / "config.toml"
STATE_FILE = CONFIG_DIR / "state.json"

DEFAULTS = {
    "photocraft": {
        "host": "127.0.0.1",
        "port": 7878,
        "token_file": str(CONFIG_DIR / "photocraft.token"),
        "exchange_dir": "~/.cache/pccomfy/exchange",
        "headless": False,
    },
    "comfyui": {
        "url": "http://127.0.0.1:8188",
        "workflows_dir": str(CONFIG_DIR / "workflows"),
    },
    "defaults": {
        "checkpoint": "",
        "negative": "",
        "steps": 25,
        "cfg": 6.0,
        "sampler": "dpmpp_2m",
        "scheduler": "karras",
        "denoise": 0.6,
        "base_res": 1024,
        "context": 0.4,
        "mask_grow": 8,
        "mask_blur": 8,
        "overlap": 48,
        "variants": 1,
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(path: str | Path | None = None) -> dict:
    p = Path(path).expanduser() if path else CONFIG_FILE
    cfg = DEFAULTS
    if p.exists():
        with open(p, "rb") as f:
            cfg = _merge(DEFAULTS, tomllib.load(f))
    return cfg


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    except OSError:
        pass
