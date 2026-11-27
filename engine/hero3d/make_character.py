"""Vendored từ repo BaoPV-DEV/Skills (ai-video-production-pipeline/scripts/hero3d). AI Workflow gọi qua engine/char3d.py."""
"""Character action: validate a character spec, render its turnaround sheet for review, then its animation sprites.

    python make_character.py check   videos/<slug>/cast/<id>.json
    python make_character.py sheet   videos/<slug>/cast/<id>.json [--fast]      -> <out>/<id>/sheet.png
    python make_character.py sprites videos/<slug>/cast/<id>.json [--only idle:back:golden,...] [--fast]
    python make_character.py presets                                            # list ready-made specs

Needs Blender's Python (`pip install bpy` in a venv, or a `blender` binary) and the MPFB data folder.
Found via --bpy / $CHAR_BPY / /opt/bpyenv/bin/python / `blender`, and --data / $MPFB_DATA / render_profile.json.
Default output: videos/_shared/cast_sprites/ (next to the project folder), so every video can reuse a character.
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent.parent
PRESETS = HERE.parent.parent / "library" / "cast3d"  # AI Workflow: mẫu nhân vật 3D
BUILDER = HERE / "build_character.py"

ENUMS = {
    "hair.style": ["none", "bald", "buzz", "short", "messy", "bob", "long", "wavy", "curly", "afro", "ponytail", "bun"],
    "top.length": ["crop", "waist", "hip", "thigh", "knee", "calf"],
    "top.sleeves": ["none", "cap", "short", "elbow", "3q", "long"],
    "top.collar": ["crew", "high", "v", "none"],
    "bottom.type": ["pants", "jeans", "cropped", "capri", "shorts", "short_shorts", "leggings", "skirt"],
    "shoes.type": ["boots", "ankle_boots", "hiking", "sneakers", "shoes", "sandals", "barefoot", "none"],
    "extras.type": ["backpack", "glasses", "beanie", "cap", "scarf"],
    "material": ["pvc", "rubber", "cotton", "denim", "wool", "knit", "leather", "nylon", "canvas", "silk", "suede", "plastic", "metal"],
    "anim": ["idle", "walk", "run", "arms_up", "push", "fall", "wave", "point", "look_up", "crouch", "celebrate", "talk"],
    "view": ["back", "back34", "side", "side_l", "front34", "front", "front34_l", "low_back"],
    "light": ["studio", "day", "overcast", "golden", "neon", "water", "night", "interior", "fire"],
}


def check(spec):
    errs, warn = [], []
    if not spec.get("id") or not str(spec["id"]).replace("_", "").isalnum():
        errs.append("id: required, letters/digits/underscore only")
    b = spec.get("body", {})
    for k in ("gender", "muscle", "weight", "height", "proportions", "age"):
        if k in b and not 0 <= float(b[k]) <= 1:
            errs.append(f"body.{k}: must be 0..1")
    if "age_years" in b and not 1 <= float(b["age_years"]) <= 90:
        errs.append("body.age_years: 1..90")
    if float(b.get("age_years", 25)) < 18:
        warn.append("minor character: keep wardrobe, poses and story age-appropriate")

    def en(path, val):
        if val is not None and val not in ENUMS[path]:
            errs.append(f"{path}: '{val}' not in {ENUMS[path]}")
    en("hair.style", spec.get("hair", {}).get("style"))
    o = spec.get("outfit", {})
    t = o.get("top") or {}
    en("top.length", t.get("length")); en("top.sleeves", t.get("sleeves")); en("top.collar", t.get("collar"))
    for part in (t, o.get("bottom") or {}, o.get("shoes") or {}):
        en("material", part.get("material"))
    en("bottom.type", (o.get("bottom") or {}).get("type")); en("shoes.type", (o.get("shoes") or {}).get("type"))
    for e in o.get("extras", []):
        en("extras.type", e.get("type"))
    lights = set(ENUMS["light"]) | set(spec.get("lights", {}))
    for r in spec.get("renders", []):
        en("anim", r[0])
        if len(r) > 1:
            en("view", r[1])
        if len(r) > 2 and r[2] not in lights:
            errs.append(f"light '{r[2]}' not built in and not defined in spec.lights")
    if not spec.get("renders"):
        warn.append("renders: empty — list the [anim, view, light] sets the storyboard needs")
    return errs, warn


def find_bpy(arg):
    for c in (arg, os.environ.get("CHAR_BPY"), "/opt/bpyenv/bin/python", sys.executable):
        if c and Path(c).exists():
            r = subprocess.run([c, "-c", "import bpy"], capture_output=True)
            if r.returncode == 0:
                return [c]
    if shutil.which("blender"):
        return [shutil.which("blender"), "-b", "--python-exit-code", "1", "-P"]
    sys.exit("No Blender Python found: pip install bpy (in a Python 3.11/3.13 venv) or install Blender, then pass --bpy")


def find_data(arg):
    prof = SKILL / "render_profile.json"
    cands = [arg, os.environ.get("MPFB_DATA")]
    if prof.exists():
        cands.append(json.loads(prof.read_text()).get("mpfb_data"))
    cands += ["/tmp/mpfb2/src/mpfb/data", str(Path.home() / "mpfb2/src/mpfb/data")]
    for c in cands:
        if c and (Path(c) / "3dobjs" / "base.obj").exists():
            return c
    sys.exit("MPFB data not found: git clone --depth 1 https://github.com/makehumancommunity/mpfb2 and pass "
             "--data mpfb2/src/mpfb/data (or set MPFB_DATA)")


def default_out(spec_path):
    p = Path(spec_path).resolve()
    for parent in p.parents:
        if parent.name == "videos":
            return parent / "_shared" / "cast_sprites"
    return Path.cwd() / "cast_sprites"


def run_builder(a, extra):
    cmd = find_bpy(a.bpy)
    args = ["--char", str(Path(a.spec).resolve()), "--data", find_data(a.data), "--out", str(a.out)] + extra
    if a.fast:
        args.append("--fast")
    if a.device:
        args += ["--device", a.device]
    full = cmd + [str(BUILDER)] + (["--"] if "blender" in cmd[0] else []) + args
    print("$", " ".join(full), flush=True)
    r = subprocess.run(full)
    if r.returncode:
        sys.exit(r.returncode)


def make_sheet(folder, spec):
    from PIL import Image, ImageDraw, ImageFont
    views = [v for v in ("front", "front34", "side", "back", "face", "head_back") if (folder / f"{v}.png").exists()]
    ims = [Image.open(folder / f"{v}.png").convert("RGBA") for v in views]
    h = 720
    ims = [im.resize((int(im.width * h / im.height), h), Image.LANCZOS) for im in ims]
    W = sum(im.width for im in ims) + 20 * (len(ims) + 1)
    sheet = Image.new("RGB", (W, h + 150), (56, 58, 64))
    d = ImageDraw.Draw(sheet)
    font_p = HERE / "Inter-ExtraBold.otf"
    try:
        f1 = ImageFont.truetype(str(font_p), 40); f2 = ImageFont.truetype(str(font_p), 22)
    except Exception:
        f1 = f2 = ImageFont.load_default()
    x = 20
    for v, im in zip(views, ims):
        sheet.paste(im, (x, 130), im)
        d.text((x + 8, 100), v.upper(), font=f2, fill=(200, 205, 215))
        x += im.width + 20
    o = spec.get("outfit", {})
    desc = " · ".join(filter(None, [spec.get("hair", {}).get("style"), (o.get("top") or {}).get("type"),
                                    (o.get("bottom") or {}).get("type"), (o.get("shoes") or {}).get("type")] +
                      [e.get("type") for e in o.get("extras", [])]))
    meta = json.loads((folder / "meta.json").read_text()) if (folder / "meta.json").exists() else {}
    d.text((20, 18), f"{spec.get('name', spec['id'])}  ({spec['id']})", font=f1, fill=(255, 255, 255))
    d.text((20, 66), f"{desc}   ·   height {meta.get('height_m', 0):.2f} m", font=f2, fill=(255, 214, 90))
    out = folder.parent / "sheet.png"
    sheet.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "sheet", "sprites", "presets"])
    ap.add_argument("spec", nargs="?")
    ap.add_argument("--out", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--fast", action="store_true", help="draft: fewer hairs, no motion blur (for quick looks)")
    ap.add_argument("--samples", type=int, default=0)
    ap.add_argument("--res", type=int, default=0)
    ap.add_argument("--device", default="")
    ap.add_argument("--bpy", default="")
    ap.add_argument("--data", default="")
    a = ap.parse_args()
    if a.cmd == "presets":
        for p in sorted(PRESETS.glob("*.json")):
            s = json.loads(p.read_text())
            print(f"{p.name:22s} {s.get('name', s['id'])}: {s.get('role', '')}")
        return
    if not a.spec:
        sys.exit("spec path required")
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    errs, warn = check(spec)
    for w in warn:
        print("WARN ", w)
    for e in errs:
        print("ERROR", e)
    if errs:
        sys.exit(1)
    if a.cmd == "check":
        print("OK", spec["id"]); return
    a.out = Path(a.out) if a.out else default_out(a.spec)
    extra = []
    if a.samples:
        extra += ["--samples", str(a.samples)]
    if a.res:
        extra += ["--res", str(a.res)]
    if a.cmd == "sheet":
        run_builder(a, extra + ["--sheet"] + ([] if a.res else ["--res", "720"]))
        print("sheet:", make_sheet(a.out / spec["id"] / "_sheet", spec))
    else:
        if a.only:
            extra += ["--only", a.only]
        run_builder(a, extra)
        print("sprites:", a.out / spec["id"])


if __name__ == "__main__":
    main()
