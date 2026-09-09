"""Acquire CC0 PBR surfaces from Poly Haven; the game only loads local files.
The API uses heterogeneous channel names. Resolve aliases explicitly and fail
rather than silently shipping an absent or incorrectly colored normal map.
"""
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image
import hashlib
import io
import json
import time

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "stone": "monastery_stone_floor",
    "brick": "castle_brick_01",
    "rock": "rock_boulder_dry",
    "wood": "dark_wooden_planks",
    "leather": "brown_leather",
}
ALIASES = {"diff": ("diff", "diffuse", "color", "albedo"),
           "nor_gl": ("nor_gl", "normalgl", "normal"),
           "rough": ("rough", "roughness")}

def fetch(url):
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={"User-Agent": "STORMCROWN CC0 asset build"}), timeout=90) as response:
                return response.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)

def choose(files, channel, resolution="2k"):
    keys = {key.lower(): key for key in files}
    key = next((keys[a] for a in ALIASES[channel] if a in keys), None)
    if key is None:
        raise RuntimeError(f"Missing {channel}; API offers {list(files)}")
    available = files[key]
    level = available.get(resolution) or available.get("1k")
    if not level:
        raise RuntimeError(f"No suitable resolution for {channel}")
    for ext in ("png", "jpg"):
        if ext in level:
            return level[ext]["url"]
    raise RuntimeError(f"No LDR source for {channel}")

def main():
    records = []
    target = ROOT / "assets" / "textures"
    target.mkdir(parents=True, exist_ok=True)
    for name, asset in SOURCES.items():
        files = json.loads(fetch(f"https://api.polyhaven.com/files/{asset}"))
        print(asset, list(files.keys()), flush=True)
        for channel in ("diff", "nor_gl", "rough"):
            url = choose(files, channel, "1k" if name == "leather" else "2k")
            raw = fetch(url)
            image = Image.open(io.BytesIO(raw)).convert("RGB")
            path = target / f"{name}_{channel}.webp"
            image.save(path, "WEBP", quality=95 if channel == "nor_gl" else 88, method=6)
            records.append({"path": str(path.relative_to(ROOT)), "source": url,
                "asset": f"https://polyhaven.com/a/{asset}", "license": "CC0-1.0",
                "width": image.width, "height": image.height,
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    files = json.loads(fetch("https://api.polyhaven.com/files/moonless_golf"))
    url = files["hdri"]["1k"]["hdr"]["url"]
    raw = fetch(url)
    path = ROOT / "assets" / "environment" / "night.hdr"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    records.append({"path": str(path.relative_to(ROOT)), "source": url,
        "asset": "https://polyhaven.com/a/moonless_golf", "license": "CC0-1.0",
        "sha256": hashlib.sha256(raw).hexdigest()})
    (ROOT / "assets" / "provenance.json").write_text(json.dumps(records, indent=2) + "\n")
    print(f"Prepared {len(records)} licensed assets", flush=True)

if __name__ == "__main__":
    main()
