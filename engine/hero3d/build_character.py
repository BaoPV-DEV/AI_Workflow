"""Build a realistic 3D character from a character spec (cast/<id>.json) in Blender, using MakeHuman/MPFB CC0 data,
then render a turnaround sheet and/or animation sprites (transparent PNG sequences + meta.json) that
anim_kit.hero_sprite() composites into 2D scenes.

    python build_character.py --char cast/mia.json --data <mpfb2>/src/mpfb/data --out <sprites root> --sheet
    python build_character.py --char cast/mia.json --data ... --out ... [--only idle:back:golden,walk:side:day]
    blender -b -P build_character.py -- --char ... (same args)

Only DATA files are read from MPFB (base.obj, targets .gz, rig/weights .json, mask textures); none of its code runs.
Output layout: <out>/<id>/<anim>_<view>_<light>/0000.png… + meta.json, and <out>/<id>/_sheet/*.png.
Spec schema and presets: ../../references/character-spec.md and ../../assets/cast-presets/.
"""
import argparse, gzip, json, math, os, random, sys, time
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# ============================================================================ args
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--char", required=True, help="character spec JSON")
ap.add_argument("--data", required=True, help="MPFB data folder (…/mpfb2/src/mpfb/data)")
ap.add_argument("--out", required=True, help="sprite root; the character goes in <out>/<id>/")
ap.add_argument("--only", default="", help="anim:view[:light],… (default: the spec's 'renders')")
ap.add_argument("--sheet", action="store_true", help="render the turnaround sheet (front, 3/4, side, back, face) only")
ap.add_argument("--samples", type=int, default=0, help="Cycles samples (default: spec or 32)")
ap.add_argument("--res", type=int, default=0, help="sprite height px (default: spec or 960)")
ap.add_argument("--device", default="auto", help="auto|cpu|gpu")
ap.add_argument("--test", action="store_true", help="one frame per requested anim")
ap.add_argument("--fast", action="store_true", help="draft quality: fewer hairs, no motion blur, subdiv 1")
ap.add_argument("--save-blend", default="")
A = ap.parse_args(argv)

SPEC = json.loads(Path(A.char).read_text(encoding="utf-8"))
CID = SPEC["id"]
DATA = Path(A.data)
OUT = Path(A.out) / CID
OUT.mkdir(parents=True, exist_ok=True)
RNG = random.Random(SPEC.get("seed", 7))
SUBDIV = 1 if A.fast else int(SPEC.get("render", {}).get("subdiv", 2))
SCALE = 0.1  # MakeHuman decimetres -> metres


def col(c, default=(0.5, 0.5, 0.5)):
    """Colour from [r,g,b] (0-1 linear-ish) or '#rrggbb' (sRGB, converted to linear)."""
    if c is None:
        return default
    if isinstance(c, str):
        h = c.lstrip("#")
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb)
    return tuple(c[:3])


def to_bl(v):  # obj y-up, faces +z  ->  Blender z-up, faces -y
    return Vector((v[0] * SCALE, -v[2] * SCALE, v[1] * SCALE))


# ============================================================================ load base mesh (data only)
def load_obj(path):
    verts, uvs, faces, group = [], [], [], None
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("v "):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vt "):
                uvs.append([float(x) for x in line.split()[1:3]])
            elif line.startswith("g "):
                group = line.split()[1]
            elif line.startswith("f "):
                tok = [t.split("/") for t in line.split()[1:]]
                faces.append(([int(t[0]) - 1 for t in tok], [int(t[1]) - 1 if len(t) > 1 and t[1] else -1 for t in tok], group))
    return verts, uvs, faces


def load_target(path):
    out = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            p = line.split()
            if len(p) == 4 and not line.startswith("#"):
                out.append((int(p[0]), float(p[1]), float(p[2]), float(p[3])))
    return out


verts, uvs, faces = load_obj(DATA / "3dobjs" / "base.obj")
groups_meta = json.load(open(DATA / "mesh_metadata" / "basemesh_vertex_groups.json"))


# ---------------------------------------------------------------------------- MakeHuman macro modifiers
def _pair(x, lo, hi, names):
    """Split x in [lo, hi] into weights of two named poles."""
    k = max(0.0, min(1.0, (x - lo) / (hi - lo)))
    return {names[0]: 1 - k, names[1]: k}


def macro_weights(b):
    g = float(b.get("gender", 1.0))
    if "age_years" in b:
        y = float(b["age_years"])
        age = (y - 1) / 10 * 0.1875 if y < 11 else 0.1875 + (y - 11) / 14 * 0.3125 if y < 25 else 0.5 + (y - 25) / 65 * 0.5
    else:
        age = float(b.get("age", 0.5))
    age = max(0.0, min(1.0, age))
    mu, we = float(b.get("muscle", 0.5)), float(b.get("weight", 0.5))
    G = {"female": 1 - g, "male": g}
    if age < 0.1875:
        AG = _pair(age, 0, 0.1875, ("baby", "child"))
    elif age < 0.5:
        AG = _pair(age, 0.1875, 0.5, ("child", "young"))
    else:
        AG = _pair(age, 0.5, 1.0, ("young", "old"))
    MU = _pair(mu, 0, 0.5, ("minmuscle", "averagemuscle")) if mu < 0.5 else _pair(mu, 0.5, 1, ("averagemuscle", "maxmuscle"))
    WE = _pair(we, 0, 0.5, ("minweight", "averageweight")) if we < 0.5 else _pair(we, 0.5, 1, ("averageweight", "maxweight"))
    eth = b.get("ethnicity", {"african": 1 / 3, "asian": 1 / 3, "caucasian": 1 / 3})
    s = sum(eth.values()) or 1
    T = DATA / "targets" / "macrodetails"
    out = []
    for gk, gw in G.items():
        for ak, aw in AG.items():
            if gw * aw < 1e-4:
                continue
            for race, rw in eth.items():
                out.append((T / f"{race}-{gk}-{ak}.target.gz", gw * aw * rw / s))
            for mk, mw in MU.items():
                for wk, ww in WE.items():
                    base = gw * aw * mw * ww
                    if base < 1e-4:
                        continue
                    out.append((T / f"universal-{gk}-{ak}-{mk}-{wk}.target.gz", base))
                    h = float(b.get("height", 0.5))
                    if abs(h - 0.5) > 1e-3:
                        out.append((T / "height" / f"{gk}-{ak}-{mk}-{wk}-{'max' if h > 0.5 else 'min'}height.target.gz", base * abs(h - 0.5) * 2))
                    p = float(b.get("proportions", 0.5))
                    if abs(p - 0.5) > 1e-3:
                        out.append((T / "proportions" / f"{gk}-{ak}-{mk}-{wk}-{'ideal' if p > 0.5 else 'uncommon'}proportions.target.gz", base * abs(p - 0.5) * 2))
    return out


BODY = SPEC.get("body", {})
for path, w in macro_weights(BODY) + [(DATA / "targets" / t, w) for t, w in BODY.get("targets", {}).items()]:
    if w > 1e-4 and path.exists():
        for i, dx, dy, dz in load_target(path):
            verts[i][0] += dx * w; verts[i][1] += dy * w; verts[i][2] += dz * w

V = [to_bl(v) for v in verts]


def gidx(name):
    out = []
    for a, b in groups_meta[name]:
        out.extend(range(a, b + 1))
    return out


def cube_center(name):
    ids = gidx(name)
    return sum((V[i] for i in ids), Vector()) / len(ids)


ground_z = min(V[i].z for i in gidx("body"))
for v in V:
    v.z -= ground_z

# ============================================================================ scene + rig
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
rig_def = json.load(open(DATA / "rigs" / "standard" / "rig.default.json"))
W_JSON = json.load(open(DATA / "rigs" / "standard" / "weights.default.json"))["weights"]
VW = {}  # vertex -> {bone: weight}
for bone, lst in W_JSON.items():
    if bone in rig_def:
        for i, w in lst:
            VW.setdefault(i, {})[bone] = w


def dom(i):
    d = VW.get(i)
    return max(d, key=d.get) if d else ""


def joint_pos(spec):
    s = spec["strategy"]
    if s == "CUBE":
        return cube_center(spec["cube_name"])
    if s == "VERTEX":
        return V[spec["vertex_index"]].copy()
    if s == "MEAN":
        return sum((V[i] for i in spec["vertex_indices"]), Vector()) / len(spec["vertex_indices"])
    return Vector(spec["default_position"])


arm_data = bpy.data.armatures.new("Rig")
rig = bpy.data.objects.new("Rig", arm_data)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
eb = {}
for name, d in rig_def.items():
    b = arm_data.edit_bones.new(name)
    b.head = joint_pos(d["head"]); b.tail = joint_pos(d["tail"])
    if (b.tail - b.head).length < 1e-4:
        b.tail = b.head + Vector((0, 0, 0.01))
    b.roll = d.get("roll", 0.0)
    eb[name] = b
for name, d in rig_def.items():
    if d.get("parent"):
        eb[name].parent = eb[d["parent"]]
        eb[name].use_connect = bool(d.get("use_connect"))
bpy.ops.object.mode_set(mode="OBJECT")


def bone_head(n):
    return rig.matrix_world @ arm_data.bones[n].head_local


HIP_Z = bone_head("upperleg01.L").z
KNEE_Z = bone_head("lowerleg01.L").z
ANKLE_Z = bone_head("foot.L").z
NECK_Z = bone_head("neck01").z
HEAD_C = bone_head("head") + Vector((0, 0, 0.09))
EYE_L = cube_center("helper-l-eye"); EYE_R = cube_center("helper-r-eye")
EYE_C = (EYE_L + EYE_R) / 2
MOUTH = cube_center("joint-mouth")
HEAD_TOP = max(V[i].z for i in gidx("body"))
SPINE_Y = bone_head("spine01").y


def make_mesh(name, group, uv=False, keep=None):
    """Object from one base.obj group (optionally a vertex subset), with rig weights, parented to the rig."""
    fl = [(fv, ft) for fv, ft, g in faces if g == group and (keep is None or all(i in keep for i in fv))]
    used = sorted({i for fv, _ in fl for i in fv})
    remap = {o: n for n, o in enumerate(used)}
    me = bpy.data.meshes.new(name)
    me.from_pydata([V[i].copy() for i in used], [], [[remap[i] for i in fv] for fv, _ in fl])
    if uv and uvs:
        layer = me.uv_layers.new(name="UVMap")
        li = 0
        for fv, ft in fl:
            for t in ft:
                if t >= 0:
                    layer.data[li].uv = uvs[t]
                li += 1
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    groups = {}
    for o, n in remap.items():
        for bone, w in VW.get(o, {}).items():
            if bone not in groups:
                groups[bone] = ob.vertex_groups.new(name=bone)
            groups[bone].add([n], w, "REPLACE")
    ob.parent = rig
    ob["orig"] = used  # original vertex ids, used for masks
    return ob, remap


def bone_parent(ob, bone):
    """Rigidly attach to a bone, keeping the current (rest-pose) world transform."""
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    ob.parent = rig; ob.parent_type = "BONE"; ob.parent_bone = bone
    ob.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    ob.matrix_world = mw


def add_armature(ob):
    m = ob.modifiers.new("Armature", "ARMATURE"); m.object = rig
    return m


def add_subsurf(ob, levels=None):
    s = ob.modifiers.new("Subsurf", "SUBSURF"); s.levels = 0; s.render_levels = SUBDIV if levels is None else levels
    return s


body, BREMAP = make_mesh("Body", "body", uv=True)

# ============================================================================ materials
MATS = {  # roughness, coat, sheen, bump strength, bump scale, wrinkle depth (m)
    "pvc": (0.36, 0.55, 0.0, 0.22, 5.0, 0.008), "rubber": (0.28, 0.5, 0.0, 0.05, 30, 0.0),
    "cotton": (0.85, 0.0, 0.5, 0.10, 160, 0.006), "denim": (0.8, 0.0, 0.2, 0.25, 260, 0.005),
    "wool": (0.95, 0.0, 0.8, 0.35, 120, 0.004), "knit": (0.95, 0.0, 0.8, 0.5, 90, 0.003),
    "leather": (0.45, 0.25, 0.0, 0.08, 60, 0.003), "nylon": (0.45, 0.15, 0.2, 0.08, 40, 0.007),
    "canvas": (0.8, 0.0, 0.3, 0.2, 140, 0.005), "silk": (0.35, 0.0, 0.6, 0.02, 80, 0.006),
    "suede": (0.9, 0.0, 0.6, 0.1, 200, 0.002), "plastic": (0.35, 0.3, 0.0, 0.0, 10, 0.0),
    "metal": (0.3, 0.0, 0.0, 0.0, 10, 0.0),
}


def principled(name, base, kind="cotton", sss=0.0, emission=None):
    rough, coat, sheen, bump, bscale, _ = MATS.get(kind, MATS["cotton"])
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    bsdf.inputs["Roughness"].default_value = rough
    if kind == "metal":
        bsdf.inputs["Metallic"].default_value = 1.0
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.06
    if sheen and "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = sheen
        bsdf.inputs["Sheen Roughness"].default_value = 0.5
    if sss and "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = sss
        bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
        bsdf.inputs["Subsurface Scale"].default_value = 0.012
    if bump:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = bscale
        tex.inputs["Detail"].default_value = 4.0
        nt.links.new(tc.outputs["Object"], tex.inputs["Vector"])
        bmp = nt.nodes.new("ShaderNodeBump"); bmp.inputs["Strength"].default_value = bump
        bmp.inputs["Distance"].default_value = 0.02
        nt.links.new(tex.outputs["Fac"], bmp.inputs["Height"])
        nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    if emission and "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*emission[0], 1)
        bsdf.inputs["Emission Strength"].default_value = emission[1]
    return m


def mix_color_by(m, factor_socket, color):
    """Base colour = mix(current, color, factor)."""
    nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
    src = bsdf.inputs["Base Color"].links[0].from_socket if bsdf.inputs["Base Color"].is_linked else None
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    if src is not None:
        nt.links.new(src, mix.inputs["A"])
    else:
        mix.inputs["A"].default_value = bsdf.inputs["Base Color"].default_value[:]
    mix.inputs["B"].default_value = (*color, 1)
    nt.links.new(factor_socket, mix.inputs["Factor"]); nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    return mix


def zband(m, z0, z1, axis="Z"):
    """Shader socket = 1 where object-space axis is within [z0, z1]."""
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = z0
    lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = z1
    nt.links.new(sep.outputs[axis], gt.inputs[0]); nt.links.new(sep.outputs[axis], lt.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    nt.links.new(gt.outputs[0], mul.inputs[0]); nt.links.new(lt.outputs[0], mul.inputs[1])
    return mul.outputs[0]


def seams(m, lines, color):
    """Thin darker seam lines: (axis, value, half-width[, zmin, zmax]) in object space."""
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    acc = None
    for spec in lines:
        axis, val, hw = spec[:3]
        sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = val
        nt.links.new(sep.outputs[axis.upper()], sub.inputs[0])
        ab = nt.nodes.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"; nt.links.new(sub.outputs[0], ab.inputs[0])
        lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = hw
        nt.links.new(ab.outputs[0], lt.inputs[0])
        out = lt.outputs[0]
        if len(spec) > 3:
            mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
            nt.links.new(out, mul.inputs[0]); nt.links.new(zband(m, spec[3], spec[4]), mul.inputs[1]); out = mul.outputs[0]
        if acc is None:
            acc = out
        else:
            mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
            nt.links.new(acc, mx.inputs[0]); nt.links.new(out, mx.inputs[1]); acc = mx.outputs[0]
    if acc is not None:
        mix_color_by(m, acc, color)


# ---------------------------------------------------------------------------- skin (UV masks from MPFB textures)
SK = SPEC.get("skin", {})
SKIN = col(SK.get("tone"), (0.62, 0.40, 0.29))
M_SKIN = principled("Skin", SKIN, "cotton", sss=0.25)
M_SKIN.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.56
if "Sheen Weight" in M_SKIN.node_tree.nodes["Principled BSDF"].inputs:
    M_SKIN.node_tree.nodes["Principled BSDF"].inputs["Sheen Weight"].default_value = 0.0


def uv_mask(m, fname):
    p = DATA / "textures" / fname
    if not p.exists():
        return None
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(str(p))
    tex.image.colorspace_settings.name = "Non-Color"
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
    return tex.outputs["Color"]


def scaled(m, sock, k):
    nt = m.node_tree
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = k
    nt.links.new(sock, mul.inputs[0])
    return mul.outputs[0]


face_m = uv_mask(M_SKIN, "mpfb_face.jpg")
if face_m is not None:   # a touch of warmth across cheeks and nose
    mix_color_by(M_SKIN, scaled(M_SKIN, face_m, 0.25 * float(SK.get("blush", 0.6))),
                 tuple(c * k for c, k in zip(SKIN, (1.08, 0.82, 0.8))))
lips_m = uv_mask(M_SKIN, "mpfb_lips.jpg")
if lips_m is not None:
    mix_color_by(M_SKIN, scaled(M_SKIN, lips_m, 0.85), col(SK.get("lips"), tuple(c * k for c, k in zip(SKIN, (0.85, 0.52, 0.52)))))
lids_m = uv_mask(M_SKIN, "mpfb_eyelids.jpg")
if lids_m is not None:
    mix_color_by(M_SKIN, scaled(M_SKIN, lids_m, 0.18), tuple(c * 0.75 for c in SKIN))
# micro pores
nt = M_SKIN.node_tree
_v = nt.nodes.new("ShaderNodeTexVoronoi"); _v.inputs["Scale"].default_value = 900
_b = nt.nodes.new("ShaderNodeBump"); _b.inputs["Strength"].default_value = 0.08; _b.inputs["Distance"].default_value = 0.002
_tc = nt.nodes.new("ShaderNodeTexCoord"); nt.links.new(_tc.outputs["Object"], _v.inputs["Vector"])
nt.links.new(_v.outputs["Distance"], _b.inputs["Height"]); nt.links.new(_b.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])

# ============================================================================ hair-line / scalp
HAIR = SPEC.get("hair", {"style": "short"})
HSTYLE = HAIR.get("style", "short")
HCOL = col(HAIR.get("color"), (0.035, 0.022, 0.014))


def _interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            k = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + k * (ys[i] - ys[i - 1])
    return ys[-1]


HL = HAIR.get("hairline", 0.0)   # +up / -down shift of the whole hairline, metres


def is_scalp(p):
    depth = p.y - EYE_C.y                     # 0 at the eyes, + towards the back of the head
    thr = EYE_C.z + HL + _interp(depth, [0.0, 0.04, 0.08, 0.13, 0.2], [0.05, 0.036, 0.0, -0.07, -0.095])
    if abs(p.x) > 0.072 and 0.07 < depth < 0.125 and EYE_C.z - 0.06 < p.z < EYE_C.z:  # ears
        return False
    return p.z > thr and dom_pos_ok(p)


def dom_pos_ok(p):
    return p.z > NECK_Z - 0.02


scalp_ids = [BREMAP[i] for i in BREMAP if not dom(i).startswith(("upperarm", "shoulder", "clavicle", "spine")) and is_scalp(V[i])]
# hair-coloured scalp under the strands so thin spots don't show bare skin
if HSTYLE not in ("none", "bald"):
    me = body.data
    attr = me.color_attributes.new("scalp", "FLOAT_COLOR", "POINT")
    sset = set(scalp_ids)
    for v in me.vertices:
        attr.data[v.index].color = (1, 1, 1, 1) if v.index in sset else (0, 0, 0, 1)
    an = M_SKIN.node_tree.nodes.new("ShaderNodeVertexColor"); an.layer_name = "scalp"
    mix_color_by(M_SKIN, an.outputs["Color"], tuple(c * 0.85 for c in HCOL))

body.data.materials.append(M_SKIN)

# ============================================================================ eyes, lashes
EYE = SPEC.get("eyes", {})
M_EYE = principled("Eye", (0.82, 0.8, 0.78), "plastic")
M_EYE.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.05
nt = M_EYE.node_tree
_tc = nt.nodes.new("ShaderNodeTexCoord"); _sep = nt.nodes.new("ShaderNodeSeparateXYZ")
_nrm = nt.nodes.new("ShaderNodeVectorMath"); _nrm.operation = "NORMALIZE"
nt.links.new(_tc.outputs["Object"], _nrm.inputs[0]); nt.links.new(_nrm.outputs[0], _sep.inputs[0])
_neg = nt.nodes.new("ShaderNodeMath"); _neg.operation = "MULTIPLY"; _neg.inputs[1].default_value = -1
nt.links.new(_sep.outputs["Y"], _neg.inputs[0])            # 1 at the front of the eyeball (-y)
for thr, c in ((0.86, col(EYE.get("iris"), (0.12, 0.06, 0.03))), (0.965, (0.005, 0.005, 0.005))):
    g = nt.nodes.new("ShaderNodeMath"); g.operation = "GREATER_THAN"; g.inputs[1].default_value = thr
    nt.links.new(_neg.outputs[0], g.inputs[0]); mix_color_by(M_EYE, g.outputs[0], c)
for grp in ("helper-l-eye", "helper-r-eye"):
    eo, _ = make_mesh("Eye_" + grp[-5], grp)
    c = sum((v.co for v in eo.data.vertices), Vector()) / len(eo.data.vertices)
    for v in eo.data.vertices:
        v.co -= c
    eo.data.update(); eo.location = c
    eo.data.materials.append(M_EYE); add_armature(eo); add_subsurf(eo, 2)
M_LASH = principled("Lash", tuple(x * 0.5 for x in HCOL), "cotton")
for grp in ("helper-l-eyelashes-1", "helper-l-eyelashes-2", "helper-r-eyelashes-1", "helper-r-eyelashes-2"):
    if grp in groups_meta:
        lo, _ = make_mesh("Lash_" + grp, grp); lo.data.materials.append(M_LASH); add_armature(lo)

# ============================================================================ garments
OUTFIT = SPEC.get("outfit", {})
covered = set()   # original body vertex ids hidden under clothing
BODY_BVH = None


def body_bvh(exclude_arms=True):
    bm = bmesh.new()
    me = body.data
    keep = set()
    for o, n in BREMAP.items():
        b = dom(o)
        if exclude_arms and b.startswith(("upperarm", "lowerarm", "wrist", "finger", "metacarpal", "thumb")):
            continue
        keep.add(n)
    vmap = {}
    for v in me.vertices:
        if v.index in keep:
            vmap[v.index] = bm.verts.new(v.co)
    for p in me.polygons:
        if all(i in vmap for i in p.vertices):
            try:
                bm.faces.new([vmap[i] for i in p.vertices])
            except ValueError:
                pass
    bm.normal_update()
    t = BVHTree.FromBMesh(bm); bm.free()
    return t


def arm_t(p, side):
    """Position along the arm: 0 shoulder joint, 1 elbow, 2 wrist (rest pose)."""
    s = bone_head(f"upperarm01.{side}"); e = bone_head(f"lowerarm01.{side}"); w = bone_head(f"wrist.{side}")
    d1 = (e - s); t1 = (p - s).dot(d1) / d1.length_squared
    if t1 <= 1:
        return t1
    d2 = (w - e)
    return 1 + (p - e).dot(d2) / d2.length_squared


HEMS = {"crop": lambda: HIP_Z + 0.2, "waist": lambda: HIP_Z + 0.1, "hip": lambda: HIP_Z - 0.03,
        "thigh": lambda: HIP_Z - 0.22, "knee": lambda: KNEE_Z - 0.06, "calf": lambda: KNEE_Z - 0.2}
SLEEVES = {"none": -0.2, "cap": 0.12, "short": 0.45, "elbow": 1.05, "3q": 1.5, "long": 1.93}


def cloth_mod_stack(ob, kind, thickness=0.004):
    wr = MATS.get(kind, MATS["cotton"])[5]
    if wr > 0:   # rest-space wrinkles: stick to the cloth as it deforms
        tex = bpy.data.textures.new(ob.name + "_wr", "CLOUDS"); tex.noise_scale = 0.035; tex.noise_depth = 3
        d = ob.modifiers.new("Wrinkles", "DISPLACE"); d.texture = tex; d.strength = wr; d.mid_level = 0.5
        d.texture_coords = "LOCAL"
    add_armature(ob)
    if thickness:
        so = ob.modifiers.new("Thickness", "SOLIDIFY"); so.thickness = thickness; so.offset = 1
    add_subsurf(ob)


def skirt_tube(bm, z_top, z_bot, loose, bins=56, rings=14):
    """Open A-line tube wrapped around both legs (polar max radius per slab): long coats, dresses and skirts
    read as one piece of cloth instead of two trouser legs. Joined to the garment by the voxel remesh."""
    leg = [V[o] for o in BREMAP if dom(o).startswith(("upperleg", "lowerleg", "pelvis", "root", "spine01"))]
    cy = SPINE_Y
    ring_verts = []
    for r in range(rings + 1):
        z = z_top + (z_bot - z_top) * r / rings
        rad = [0.0] * bins
        for p in leg:
            if abs(p.z - z) < 0.035:
                a = math.atan2(p.y - cy, p.x); i = int((a + math.pi) / (2 * math.pi) * bins) % bins
                rad[i] = max(rad[i], math.hypot(p.x, p.y - cy))
        if max(rad) == 0:
            continue
        for _ in range(3):   # fill notches between the legs, then smooth
            rad = [max(rad[i], 0.5 * (rad[i - 2] + rad[(i + 2) % bins])) for i in range(bins)]
        rad = [(rad[i - 1] + 2 * rad[i] + rad[(i + 1) % bins]) / 4 for i in range(bins)]
        ring = []
        for i in range(bins):
            a = -math.pi + (i + 0.5) / bins * 2 * math.pi
            rr = rad[i] + loose
            ring.append(bm.verts.new((math.cos(a) * rr, cy + math.sin(a) * rr, z)))
        ring_verts.append(ring)
    for r0, r1 in zip(ring_verts, ring_verts[1:]):
        for i in range(bins):
            bm.faces.new((r0[i], r0[(i + 1) % bins], r1[(i + 1) % bins], r1[i]))
    bm.normal_update()


def snap_cut_edges(bm, lo, hi):
    """Straighten the ragged edge left by cutting a voxel-remeshed shell with a z plane."""
    for v in bm.verts:
        if v.is_boundary:
            if v.co.z < lo + 0.02:
                v.co.z = lo
            elif hi is not None and v.co.z > hi - 0.02:
                v.co.z = hi


def build_top(t):
    kind = t.get("material", "cotton")
    hem = HEMS.get(t.get("length", "hip"), HEMS["hip"])()
    sl = SLEEVES.get(t.get("sleeves", "long"), 1.93)
    hood = bool(t.get("hood", False))
    loose = float(t.get("looseness", 0.012))
    collar = t.get("collar", "crew")      # crew | high | v | none(open neck)
    long_hem = hem < HIP_Z - 0.06
    fuse = hem < HIP_Z + 0.05          # hem at/below the crotch: fuse the legs into one ring
    bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table()
    inv = {n: o for o, n in BREMAP.items()}
    keep, hide = set(), set()
    for v in bm.verts:
        o = inv[v.index]; b = dom(o); p = v.co
        if b.startswith(("finger", "metacarpal", "thumb", "wrist", "foot", "toe", "lowerleg")):
            continue
        if b.startswith(("upperarm", "lowerarm")) or b.startswith(("shoulder",)) and abs(p.x) > 0.17:
            side = b[-1]
            if arm_t(p, side) > sl:
                continue
        if b.startswith("upperleg") and (not fuse or (long_hem and p.z < HIP_Z - 0.04)):
            continue
        if b.startswith(("head", "neck", "jaw", "eye", "tongue", "special")) or p.z > NECK_Z - 0.01:
            if hood:
                depth = p.y - EYE_C.y
                face_open = depth < 0.045 and MOUTH.z - 0.06 < p.z < EYE_C.z + 0.08
                if face_open:
                    continue
            else:
                lim = {"high": NECK_Z + 0.06, "crew": NECK_Z - 0.035, "v": NECK_Z - 0.06, "none": NECK_Z - 0.05}[collar]
                front_drop = 0.06 if collar == "v" else 0.0
                if p.z > lim - (front_drop if p.y < SPINE_Y - 0.03 else 0):
                    continue
        if p.z < hem - (0.0 if long_hem else 0.05):
            continue
        keep.add(v.index)
        if not b.startswith(("head",) if hood else ("head", "neck")) and hem + 0.03 < p.z < NECK_Z - (0.0 if hood else 0.07) and not (b.startswith(("upperarm", "lowerarm")) and arm_t(p, b[-1]) > sl - 0.1):
            hide.add(o)
    covered.update(hide)
    for v in list(bm.verts):
        if v.index not in keep:
            bm.verts.remove(v)
    bm.normal_update()
    for v in bm.verts:
        k = loose + (0.026 * max(0.0, min(1.0, (HIP_Z + 0.12 - v.co.z) / 0.25)) if fuse else 0.0)
        if hood and v.co.z > NECK_Z - 0.02:
            dv = v.co - HEAD_C; n = dv.normalized()
            back = max(0.0, n.y); top = max(0.0, n.z)
            kk = 0.022 + 0.022 * back + 0.008 * top + 0.012 * max(0.0, -n.y)   # roomier at the face opening
            v.co += n * kk
            # peak: a gentle point at the top-back, not a helmet dome
            pk = math.exp(-((n - Vector((0, 0.55, 0.83)).normalized()).length ** 2) / 0.08)
            v.co += Vector((0, 0.6, 0.35)).normalized() * 0.014 * pk
            continue
        if v.co.z > NECK_Z - 0.05 and not hood:   # collars hug the neck: no dark gap
            k = min(k, 0.006)
        v.co += v.normal * k
    if long_hem:
        skirt_tube(bm, HIP_Z + 0.02, hem - 0.02, loose + 0.01)
    cm = bpy.data.meshes.new("Top"); bm.to_mesh(cm); bm.free()
    top = bpy.data.objects.new("Top", cm); scene.collection.objects.link(top)
    so = top.modifiers.new("Vol", "SOLIDIFY"); so.thickness = 0.03 if long_hem else 0.02; so.offset = -1; so.use_rim = True
    rm = top.modifiers.new("Remesh", "REMESH"); rm.mode = "VOXEL"; rm.voxel_size = 0.009
    with bpy.context.temp_override(object=top, active_object=top):
        bpy.ops.object.modifier_apply(modifier="Vol"); bpy.ops.object.modifier_apply(modifier="Remesh")
    bm = bmesh.new(); bm.from_mesh(top.data)
    flare = float(t.get("flare", 0.16))
    for v in bm.verts:
        if long_hem and v.co.z < HIP_Z:
            d = HIP_Z - v.co.z; r = Vector((v.co.x, (v.co.y - SPINE_Y) * 1.15, 0))
            if r.length > 1e-4:
                v.co += r.normalized() * d * flare
    top_cut = None if hood else {"high": NECK_Z + 0.07, "crew": NECK_Z - 0.02, "v": NECK_Z - 0.04, "none": NECK_Z - 0.035}[collar]
    for v in [v for v in bm.verts if v.co.z < hem or (top_cut and v.co.z > top_cut)]:
        bm.verts.remove(v)
    snap_cut_edges(bm, hem, top_cut)
    # hood face opening: roll the rim outward a little so it reads as fabric, not a shell
    bm.to_mesh(top.data); bm.free()
    sm = top.modifiers.new("Smooth", "CORRECTIVE_SMOOTH"); sm.iterations = 12; sm.use_only_smooth = True
    with bpy.context.temp_override(object=top, active_object=top):
        bpy.ops.object.modifier_apply(modifier="Smooth")
    for p in top.data.polygons:
        p.use_smooth = True
    m = principled("Top", col(t.get("color"), (0.3, 0.3, 0.32)), kind)
    seam_c = tuple(c * 0.55 for c in col(t.get("color"), (0.3, 0.3, 0.32)))
    lines = [("z", hem + 0.012, 0.004)]
    if t.get("seams", True):
        lines += [("z", NECK_Z - 0.17, 0.0028), ("x", 0.0, 0.0022, hem, NECK_Z - 0.05)]
        if hood:
            lines += [("x", 0.0, 0.0025, NECK_Z + 0.05, NECK_Z + 0.6)]
    if t.get("zip"):
        lines += [("x", 0.0, 0.004, hem, NECK_Z + 0.03)]
    seams(m, lines, seam_c)
    for band in t.get("stripes", []):   # e.g. reflective tape: {"z": 0.45, "w": 0.02, "color": "#dddddd"}
        mix_color_by(m, zband(m, band["z"] * HEAD_TOP - band.get("w", 0.02) / 2, band["z"] * HEAD_TOP + band.get("w", 0.02) / 2), col(band.get("color"), (0.9, 0.9, 0.9)))
    top.data.materials.append(m)
    dt = top.modifiers.new("W", "DATA_TRANSFER"); dt.object = body
    dt.use_vert_data = True; dt.data_types_verts = {"VGROUP_WEIGHTS"}; dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"; dt.layers_vgroup_select_dst = "NAME"
    with bpy.context.temp_override(object=top, active_object=top):
        bpy.ops.object.datalayout_transfer(modifier="W"); bpy.ops.object.modifier_apply(modifier="W")
    if long_hem:   # the skirt follows the pelvis more than each thigh, so it doesn't tear when legs move
        vg = {g.name: g for g in top.vertex_groups}
        if "spine01" in vg:
            for v in top.data.vertices:
                if v.co.z < HIP_Z:
                    f = min(1.0, (HIP_Z - v.co.z) / 0.35); total = 0
                    for g in v.groups:
                        if top.vertex_groups[g.group].name.startswith(("upperleg", "lowerleg")):
                            g.weight *= (1 - 0.65 * f)
                        total += g.weight
                    vg["spine01"].add([v.index], max(0.0, 1 - total) + 0.3 * f, "ADD")
    top.parent = rig
    cloth_mod_stack(top, kind, 0.004)
    return top


def body_part(name, keep_fn, inflate, mat, hide_margin=0.02, extra=None):
    keep = {o for o in BREMAP if keep_fn(o, V[o])}
    ob, remap = make_mesh(name, "body", uv=False, keep=keep)
    ob.parent = rig
    me = ob.data
    bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    for v in bm.verts:
        k = inflate(v.co) if callable(inflate) else inflate
        v.co += v.normal * k
    bm.to_mesh(me); bm.free()
    sm = ob.modifiers.new("Smooth", "CORRECTIVE_SMOOTH"); sm.iterations = 3; sm.use_only_smooth = True
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier="Smooth")
    me.materials.append(mat)
    if extra:
        extra(ob)
    covered.update(o for o in keep if hide_margin is None or keep_fn(o, V[o] + Vector((0, 0, hide_margin))) and keep_fn(o, V[o] - Vector((0, 0, hide_margin))))
    return ob


def build_bottom(b):
    kind = b.get("material", "denim" if b.get("type", "pants") == "jeans" else "cotton")
    typ = b.get("type", "pants")
    c = col(b.get("color"), (0.08, 0.09, 0.12))
    if typ == "skirt":   # a skirt is a long top without the torso: reuse the remesh path
        sk = dict(b); sk.setdefault("length", "knee")
        hem = HEMS.get(sk["length"], HEMS["knee"])()
        waist = HIP_Z + 0.12
        bmesh_keep = lambda o, p: dom(o).startswith(("upperleg", "pelvis", "spine01", "root", "lowerleg")) and hem - 0.05 < p.z < waist
        ob = body_part("Skirt", bmesh_keep, lambda p: 0.012 + 0.03 * max(0.0, min(1.0, (HIP_Z + 0.1 - p.z) / 0.25)), principled("Skirt", c, kind))
        so = ob.modifiers.new("Vol", "SOLIDIFY"); so.thickness = 0.02; so.offset = -1; so.use_rim = True
        rm = ob.modifiers.new("Remesh", "REMESH"); rm.mode = "VOXEL"; rm.voxel_size = 0.009
        for mname in ("Vol", "Remesh"):
            with bpy.context.temp_override(object=ob, active_object=ob):
                bpy.ops.object.modifier_apply(modifier=mname)
        bmm = bmesh.new(); bmm.from_mesh(ob.data)
        for v in bmm.verts:
            if v.co.z < HIP_Z:
                d = HIP_Z - v.co.z; r = Vector((v.co.x, (v.co.y - SPINE_Y), 0))
                if r.length > 1e-4:
                    v.co += r.normalized() * d * float(b.get("flare", 0.3))
        for v in [v for v in bmm.verts if v.co.z < hem]:
            bmm.verts.remove(v)
        snap_cut_edges(bmm, hem, None)
        bmm.to_mesh(ob.data); bmm.free()
        for g in list(ob.vertex_groups):
            ob.vertex_groups.remove(g)
        dt = ob.modifiers.new("W", "DATA_TRANSFER"); dt.object = body
        dt.use_vert_data = True; dt.data_types_verts = {"VGROUP_WEIGHTS"}; dt.vert_mapping = "POLYINTERP_NEAREST"
        dt.layers_vgroup_select_src = "ALL"; dt.layers_vgroup_select_dst = "NAME"
        with bpy.context.temp_override(object=ob, active_object=ob):
            bpy.ops.object.datalayout_transfer(modifier="W"); bpy.ops.object.modifier_apply(modifier="W")
        for p in ob.data.polygons:
            p.use_smooth = True
        cloth_mod_stack(ob, kind, 0.003)
        # legs keep skin (or tights) below
        return ob
    hem = {"pants": ANKLE_Z + 0.03, "jeans": ANKLE_Z + 0.03, "cropped": ANKLE_Z + 0.12, "capri": KNEE_Z - 0.14,
           "shorts": KNEE_Z + 0.1, "short_shorts": HIP_Z - 0.12, "leggings": ANKLE_Z + 0.02}.get(typ, ANKLE_Z + 0.03)
    waist = HIP_Z + 0.13
    loose = float(b.get("looseness", 0.004 if typ == "leggings" else 0.02))
    keep_fn = lambda o, p: hem < p.z < waist and (dom(o).startswith(("upperleg", "lowerleg", "pelvis", "root", "spine01"))
                                                  or (abs(p.x) < 0.1 and p.z < HIP_Z and not dom(o).startswith(("upperarm", "lowerarm", "wrist", "finger", "metacarpal"))))

    def flare(p):  # trousers widen a touch towards the hem and sit snug at the waist (under any top)
        if p.z > HIP_Z - 0.02:
            return 0.006 + (loose - 0.006) * max(0.0, (HIP_Z + 0.06 - p.z) / 0.08)
        return loose + (0.012 * max(0.0, (KNEE_Z - p.z) / max(0.01, KNEE_Z - hem)) if typ in ("pants", "jeans") else 0.0)

    m = principled("Bottom", c, kind)
    seams(m, [("z", hem + 0.01, 0.004), ("z", waist - 0.03, 0.0035)], tuple(x * 0.55 for x in c))
    ob = body_part("Bottom", keep_fn, flare, m)
    cloth_mod_stack(ob, kind, 0.003)
    return ob


def build_shoes(s):
    typ = s.get("type", "sneakers")
    if typ in ("barefoot", "none"):
        return None
    top_z = {"boots": ANKLE_Z + 0.26, "ankle_boots": ANKLE_Z + 0.08, "hiking": ANKLE_Z + 0.07,
             "sneakers": ANKLE_Z + 0.02, "shoes": ANKLE_Z - 0.01, "sandals": ANKLE_Z - 0.04}.get(typ, ANKLE_Z + 0.02)
    kind = s.get("material", "rubber" if typ == "boots" else "leather" if typ in ("shoes", "ankle_boots") else "canvas")
    c = col(s.get("color"), (0.03, 0.03, 0.035))
    m = principled("Shoes", c, kind)
    sole = col(s.get("sole"), (0.85, 0.85, 0.82) if typ == "sneakers" else (0.03, 0.025, 0.02))
    mix_color_by(m, zband(m, -1, 0.024), sole)
    if s.get("laces", typ in ("sneakers", "hiking")):
        mix_color_by(m, zband(m, ANKLE_Z - 0.035, ANKLE_Z - 0.03), tuple(x * 0.6 + 0.3 for x in c))
    keep_fn = lambda o, p: dom(o).startswith(("foot", "toe", "lowerleg")) and p.z < top_z
    ob = body_part("Shoes", keep_fn, lambda p: 0.016 if p.z < 0.03 else 0.012, m)
    add_armature(ob); so = ob.modifiers.new("Thickness", "SOLIDIFY"); so.thickness = 0.004; add_subsurf(ob)
    return ob


pieces = {}
if OUTFIT.get("bottom"):
    pieces["bottom"] = build_bottom(OUTFIT["bottom"])
if OUTFIT.get("top"):
    pieces["top"] = build_top(OUTFIT["top"])
pieces["shoes"] = build_shoes(OUTFIT.get("shoes", {"type": "sneakers"}))

# hide body under clothes (keeps poke-through away at extreme poses)
hide = body.vertex_groups.new(name="covered")
hide.add([BREMAP[o] for o in covered if o in BREMAP], 1.0, "REPLACE")
mk = body.modifiers.new("Covered", "MASK"); mk.vertex_group = "covered"; mk.invert_vertex_group = True
add_armature(body); add_subsurf(body)

# ============================================================================ hair (procedural strands as Curves)
def surface_sampler(ids):
    """Area-weighted random points on body faces whose verts are all in ids (rest pose)."""
    me = body.data; s = set(ids); tris = []
    for p in me.polygons:
        if all(i in s for i in p.vertices):
            vs = [me.vertices[i].co for i in p.vertices]
            for k in range(1, len(vs) - 1):
                a, b, c = vs[0], vs[k], vs[k + 1]
                tris.append((a.copy(), b.copy(), c.copy(), ((b - a).cross(c - a)).length / 2))
    tot = sum(t[3] for t in tris)
    cum, acc = [], 0
    for t in tris:
        acc += t[3]; cum.append(acc)
    import bisect

    def sample():
        r = RNG.random() * tot
        a, b, c, _ = tris[min(bisect.bisect_left(cum, r), len(tris) - 1)]
        u, v = RNG.random(), RNG.random()
        if u + v > 1:
            u, v = 1 - u, 1 - v
        p = a + (b - a) * u + (c - a) * v
        n = (b - a).cross(c - a).normalized()
        if n.dot(p - HEAD_C) < 0:
            n = -n
        return p, n
    return sample, tot


def build_hair():
    if HSTYLE in ("none", "bald"):
        return None
    bvh = body_bvh()
    sample, area = surface_sampler(scalp_ids)
    density = float(HAIR.get("density", 1.0))
    styles = {  # length m, segments, gravity, lift (volume), clump, curl amp, curl freq
        "buzz": (0.008, 3, 0.0, 0.002, 0.0, 0.0, 0), "short": (0.065, 7, 0.25, 0.012, 0.35, 0.0, 0),
        "messy": (0.075, 7, 0.15, 0.016, 0.5, 0.008, 3), "bob": (0.17, 10, 0.6, 0.014, 0.45, 0.0, 0),
        "long": (0.42, 14, 0.8, 0.012, 0.5, 0.0, 0), "wavy": (0.36, 16, 0.75, 0.016, 0.5, 0.012, 4),
        "curly": (0.10, 10, 0.05, 0.03, 0.6, 0.014, 6), "afro": (0.11, 9, -0.1, 0.05, 0.3, 0.01, 7),
        "ponytail": (0.26, 14, 0.85, 0.006, 0.55, 0.0, 0), "bun": (0.0, 10, 0.0, 0.006, 0.4, 0.0, 0),
    }
    L, K, grav, lift, clump, camp, cfreq = styles.get(HSTYLE, styles["short"])
    L *= float(HAIR.get("length", 1.0)) if "length" in HAIR and HAIR["length"] < 3 else 1.0
    n = int((24000 if HSTYLE not in ("buzz",) else 40000) * density * (0.35 if A.fast else 1.0))
    part_x = float(HAIR.get("part", 0.025))       # side-part x (m); 0 = middle
    jaw_z = MOUTH.z - 0.045
    tie = HEAD_C + Vector((0, 0.1, 0.0 if HSTYLE == "ponytail" else 0.06))
    strands = []
    clumps = [sample() for _ in range(max(20, n // 120))]

    def collide(p, off):
        loc, nrm, _, _ = bvh.find_nearest(p)
        if loc is None:
            return p, None
        d = (p - loc).dot(nrm)
        if d < off:
            p = p + nrm * (off - d)
        return p, nrm

    hooded = bool(OUTFIT.get("top", {}).get("hood")) or any(e.get("type") in ("beanie",) for e in OUTFIT.get("extras", []))
    for s in range(n):
        root, nrm = sample()
        if hooded and (root.y - EYE_C.y > 0.05 or abs(root.x) > 0.06):
            continue
        pts = [root.copy()]
        if HSTYLE in ("ponytail", "bun"):   # sleek: flow over the scalp to the tie point
            steps = 8
            for k in range(1, steps + 1):
                q = root.lerp(tie, k / steps)
                q, _ = collide(q, lift + 0.002 * k / steps)
                pts.append(q)
            if HSTYLE == "bun":
                c0 = tie + Vector((0, 0.03, 0.02)); a0 = RNG.random() * 6.283; r = 0.035 + RNG.random() * 0.012
                for k in range(K):
                    a = a0 + k * 0.6; z = (k / K - 0.5) * 0.05
                    pts.append(c0 + Vector((math.cos(a) * r, math.sin(a) * r * 0.8, z)))
            else:
                d = Vector((RNG.gauss(0, 0.25), 0.8, -0.4)).normalized(); p = tie.copy() + Vector((RNG.gauss(0, 0.014), RNG.gauss(0, 0.006), RNG.gauss(0, 0.014)))
                seg = L * (0.8 + 0.4 * RNG.random()) / K
                for k in range(K):
                    d = (d + Vector((0, 0, -grav * 0.35))).normalized(); p = p + d * seg
                    p, _ = collide(p, 0.012)
                    pts.append(p.copy())
            strands.append(pts)
            continue
        # comb direction: away from the part / crown, tangent to the scalp
        side = 1 if root.x > part_x else -1
        crown = HEAD_C + Vector((0, 0.05, 0.09))
        comb = (root - crown); comb.z = min(comb.z, 0) - 0.02
        if HSTYLE in ("short", "messy", "buzz"):
            comb = Vector((side * 0.6, 0.9, -0.3)) if root.y < HEAD_C.y else Vector((side * 0.3, 0.3, -1))
            if hooded:
                comb = Vector((side * 0.5, -0.4, -1.0))     # fringe falls forward out of the hood
        comb = (comb - nrm * comb.dot(nrm)).normalized()
        cl = clumps[s % len(clumps)][0]
        d = (nrm * (0.35 + lift * 10) + comb).normalized()
        p = root + nrm * 0.0015
        ln = L * (0.75 + 0.5 * RNG.random())
        seg = ln / K
        ph = RNG.random() * 6.283
        for k in range(K):
            f = (k + 1) / K
            d = (d + comb * 0.25 + Vector((0, 0, -grav * f))).normalized()
            p = p + d * seg
            if camp:
                p += Vector((math.cos(ph + f * cfreq * 6.283), math.sin(ph + f * cfreq * 6.283), 0)) * camp * f
            p, sn = collide(p, 0.002 + lift * min(1.0, f * 2.5))
            if sn is not None:
                d = (d - sn * min(0.0, d.dot(sn))).normalized()
            if clump:   # strands gather into locks towards the tips
                p += Vector((cl.x - root.x, cl.y - root.y, 0)) * clump * f * 0.12
            if HSTYLE == "bob" and p.z < jaw_z:
                p.z = jaw_z + (p.z - jaw_z) * 0.15
            pts.append(p.copy())
        strands.append(pts)
    return make_curves("Hair", strands, HCOL, root_r=0.00035, tip_r=0.00012)


def make_curves(name, strands, color, root_r=0.0003, tip_r=0.0001, parent_bone="head"):
    import numpy as np
    cv = bpy.data.hair_curves.new(name)
    cv.add_curves([len(s) for s in strands])
    pos = np.array([c for s in strands for p in s for c in p], dtype=np.float32)
    cv.attributes["position"].data.foreach_set("vector", pos)
    if "radius" not in cv.attributes:
        cv.attributes.new("radius", "FLOAT", "POINT")
    rad = []
    for s in strands:
        m_ = len(s) - 1 or 1
        rad += [root_r + (tip_r - root_r) * (i / m_) for i in range(len(s))]
    cv.attributes["radius"].data.foreach_set("value", np.array(rad, dtype=np.float32))
    ob = bpy.data.objects.new(name, cv); scene.collection.objects.link(ob)
    mat = bpy.data.materials.new(name + "Mat"); mat.use_nodes = True
    nt = mat.node_tree; out = nt.nodes["Material Output"]
    for nd in list(nt.nodes):
        if nd.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(nd)
    hb = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
    try:
        hb.parametrization = "COLOR"
    except Exception:
        pass
    hb.inputs["Color"].default_value = (*color, 1) if len(hb.inputs["Color"].default_value) == 4 else color
    if "Roughness" in hb.inputs:
        hb.inputs["Roughness"].default_value = 0.32
    if "Radial Roughness" in hb.inputs:
        hb.inputs["Radial Roughness"].default_value = 0.5
    if "Random Color" in hb.inputs:
        hb.inputs["Random Color"].default_value = 0.08
    nt.links.new(hb.outputs[0], out.inputs["Surface"])
    cv.materials.append(mat)
    bone_parent(ob, parent_bone)
    return ob


def build_brows():
    if not SPEC.get("brows", True):
        return None
    bvh = body_bvh()
    strands = []
    bc = col(SPEC.get("brow_color"), tuple(c * 0.8 for c in HCOL))
    for eye, sgn in ((EYE_L, 1), (EYE_R, -1)):
        for i in range(int(700 * (0.4 if A.fast else 1))):
            u = RNG.random()
            x = eye.x + sgn * (-0.017 + 0.038 * u)
            z = EYE_C.z + 0.021 + 0.007 * math.sin(u * 3.1) - 0.004 * u + RNG.gauss(0, 0.0018)
            o = Vector((x, EYE_C.y - 0.2, z))
            hit = bvh.ray_cast(o, Vector((0, 1, 0)))
            if hit[0] is None:
                continue
            p = hit[0]; n = hit[1]
            d = Vector((sgn * 1.0, 0, 0.35 - 0.6 * u)).normalized()
            pts = [p - n * 0.0005]
            for k in range(3):
                q = pts[-1] + (d * 0.0028 + n * 0.0006)
                pts.append(q)
            strands.append(pts)
    return make_curves("Brows", strands, bc, root_r=0.00018, tip_r=0.00006)


hair = build_hair()
brows = build_brows()


# ============================================================================ head-wear and accessories
def build_extras():
    out = []
    for ex in OUTFIT.get("extras", []):
        typ = ex.get("type")
        c = col(ex.get("color"), (0.1, 0.1, 0.1))
        if typ in ("beanie", "cap"):
            keep_fn = lambda o, p: dom(o).startswith(("head",)) and is_scalp(p) and p.z > EYE_C.z + (0.05 if typ == "beanie" else 0.065)
            m = principled(typ.title(), c, ex.get("material", "knit" if typ == "beanie" else "cotton"))
            ob = body_part(typ.title(), keep_fn, 0.028 if HSTYLE not in ("long", "wavy", "afro", "curly") else 0.04, m, hide_margin=None)
            covered.difference_update({o for o in covered if dom(o) == "head"})
            if typ == "beanie":
                mix_color_by(m, zband(m, -1, EYE_C.z + 0.085), tuple(x * 0.8 for x in c))   # folded cuff
            add_armature(ob); so = ob.modifiers.new("T", "SOLIDIFY"); so.thickness = 0.006; add_subsurf(ob)
            if typ == "cap":   # brim
                bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=0.006, location=(0, EYE_C.y - 0.06, EYE_C.z + 0.07))
                br = bpy.context.active_object; br.scale = (1.0, 0.75, 1); br.rotation_euler = (math.radians(-8), 0, 0)
                br.data.materials.append(m); bone_parent(br, "head"); out.append(br)
            out.append(ob)
        elif typ == "glasses":
            m = principled("Frames", c, "plastic")
            ml = principled("Lens", (0.9, 0.95, 1.0), "plastic"); ml.node_tree.nodes["Principled BSDF"].inputs["Transmission Weight"].default_value = 1.0
            for e in (EYE_L, EYE_R):
                bpy.ops.mesh.primitive_torus_add(major_radius=0.021, minor_radius=0.0018, location=(e.x, e.y - 0.022, e.z))
                r = bpy.context.active_object; r.rotation_euler = (math.radians(90), 0, 0); r.scale = (1.15, 0.85, 1)
                r.data.materials.append(m); bone_parent(r, "head"); out.append(r)
                bpy.ops.mesh.primitive_cylinder_add(radius=0.0012, depth=0.1, location=(e.x + (0.024 if e.x > 0 else -0.024), e.y + 0.03, e.z + 0.004))
                tm = bpy.context.active_object; tm.rotation_euler = (math.radians(90), 0, 0); tm.data.materials.append(m)
                bone_parent(tm, "head"); out.append(tm)
            bpy.ops.mesh.primitive_cylinder_add(radius=0.0015, depth=abs(EYE_L.x - EYE_R.x) - 0.045, location=(EYE_C.x, EYE_C.y - 0.024, EYE_C.z + 0.004))
            bg = bpy.context.active_object; bg.rotation_euler = (0, math.radians(90), 0); bg.data.materials.append(m)
            bone_parent(bg, "head"); out.append(bg)
        elif typ == "backpack":
            m = principled("Backpack", c, ex.get("material", "nylon"))
            seams(m, [("z", 0.0, 0.003)], tuple(x * 0.5 for x in c))
            z = bone_head("spine03").z
            back_y = max(V[i].y for i in gidx("body") if abs(V[i].z - z) < 0.04 and abs(V[i].x) < 0.08)
            sz = ex.get("size", 1.0)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, back_y + 0.075 * sz, z - 0.02))
            bp = bpy.context.active_object; bp.scale = (0.28 * sz, 0.17 * sz, 0.40 * sz)
            bv = bp.modifiers.new("B", "BEVEL"); bv.width = 0.065 * sz; bv.segments = 6
            add_subsurf(bp)
            bp.data.materials.append(m); bone_parent(bp, "spine03"); out.append(bp)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, back_y + 0.16 * sz, z - 0.08))
            pk = bpy.context.active_object; pk.scale = (0.22 * sz, 0.06 * sz, 0.18 * sz)
            bv = pk.modifiers.new("B", "BEVEL"); bv.width = 0.025 * sz; bv.segments = 4; add_subsurf(pk)
            pk.data.materials.append(m); bone_parent(pk, "spine03"); out.append(pk)
            bvh = body_bvh()
            for sx in (-1, 1):   # straps: back top -> over the shoulder -> down the chest -> under the arm
                def front(x, z, off):
                    hit = bvh.ray_cast(Vector((x, SPINE_Y - 1, z)), Vector((0, 1, 0)))
                    return (hit[0] - Vector((0, off, 0))) if hit[0] else Vector((x, SPINE_Y - 0.15, z))
                sh = bone_head("upperarm01." + ("L" if sx > 0 else "R"))
                pts = [Vector((sx * 0.08, back_y + 0.02, z + 0.16)), Vector((sx * 0.1, SPINE_Y + 0.01, NECK_Z - 0.025)),
                       front(sx * 0.105, NECK_Z - 0.09, 0.05), front(sx * 0.12, z - 0.06, 0.05),
                       Vector((sx * (abs(sh.x) - 0.03), SPINE_Y + 0.03, z - 0.13)), Vector((sx * 0.12, back_y + 0.03, z - 0.2))]
                cu = bpy.data.curves.new("Strap", "CURVE"); cu.dimensions = "3D"
                cu.bevel_depth = 0.009; cu.bevel_resolution = 2
                sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(pts) - 1)
                for pp, p in zip(sp.bezier_points, pts):
                    pp.co = p; pp.handle_left_type = pp.handle_right_type = "AUTO"
                so = bpy.data.objects.new("Strap", cu); scene.collection.objects.link(so); so.scale = (1, 1, 1)
                cu.materials.append(m); bone_parent(so, "spine03"); out.append(so)
        elif typ == "scarf":
            keep_fn = lambda o, p: dom(o).startswith("neck") and p.z < NECK_Z + 0.07
            m = principled("Scarf", c, "knit")
            ob = body_part("Scarf", keep_fn, 0.035, m, hide_margin=None)
            add_armature(ob); add_subsurf(ob); out.append(ob)
    return out


extras = build_extras()
if covered:
    hide.add([BREMAP[o] for o in covered if o in BREMAP], 1.0, "REPLACE")

# ============================================================================ poses
pose = rig.pose.bones


def reset_pose():
    for pb in pose:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)
    rig.location = (0, 0, 0)
    bpy.context.view_layer.update()


def rot(bone, axis, deg):
    """Rotate a pose bone around a WORLD axis ('X' right, 'Y' back, 'Z' up) through its head."""
    if bone not in pose or abs(deg) < 1e-6:
        return
    pb = pose[bone]
    ax = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]
    m = pb.matrix.copy(); h = m.translation.copy()
    pb.matrix = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-h) @ m
    bpy.context.view_layer.update()


def arms_down(k=1.0):
    rot("upperarm01.L", "Y", 30 * k); rot("upperarm01.R", "Y", -30 * k)
    rot("upperarm01.L", "X", -4 * k); rot("upperarm01.R", "X", -4 * k)
    rot("lowerarm01.L", "X", -8 * k); rot("lowerarm01.R", "X", -8 * k)


def fingers_relax(k=1.0):
    for s in ("L", "R"):
        for f in range(1, 6):
            for j in (1, 2, 3):
                b = f"finger{f}-{j}.{s}"
                if b in pose:
                    rot(b, "X", -(12 if f > 1 else 6) * k)


def sm(x):  # smoothstep
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)


def P_idle(f, n):
    ph = 2 * math.pi * f / n
    reset_pose(); arms_down(); fingers_relax()
    rot("spine03", "X", 1.5 * math.sin(ph)); rot("spine01", "Z", 1.2 * math.sin(ph * 0.5))
    rot("neck01", "X", 2 + 1.0 * math.sin(ph + 0.6)); rot("head", "Z", 2.5 * math.sin(ph * 0.5 + 1))
    rot("upperarm01.L", "X", 2 * math.sin(ph)); rot("upperarm01.R", "X", 2 * math.sin(ph + 0.4))
    rot("upperleg01.L", "Y", 1.0); rot("upperleg01.R", "Y", -1.5)


def P_walk(f, n, run=False):
    ph = 2 * math.pi * f / n; s = math.sin(ph)
    A_ = 1.45 if run else 1.0
    reset_pose(); arms_down(); fingers_relax(1.4 if run else 1)
    rot("upperleg01.L", "X", 26 * A_ * s); rot("upperleg01.R", "X", -26 * A_ * s)
    rot("lowerleg01.L", "X", -max(0, (40 + 40 * run) * math.sin(ph + 1.2))); rot("lowerleg01.R", "X", -max(0, (40 + 40 * run) * math.sin(ph + 1.2 + math.pi)))
    rot("foot.L", "X", 10 * math.sin(ph + 2.0)); rot("foot.R", "X", 10 * math.sin(ph + 2.0 + math.pi))
    rot("upperarm01.L", "X", -22 * A_ * s); rot("upperarm01.R", "X", 22 * A_ * s)
    rot("lowerarm01.L", "X", (15 + 55 * run) + 10 * max(0, -s)); rot("lowerarm01.R", "X", (15 + 55 * run) + 10 * max(0, s))
    rot("spine02", "Z", 5 * s); rot("spine04", "Z", -6 * s); rot("spine01", "X", 3 + 9 * run)
    rot("head", "X", -3 * run)
    rig.location = (0, 0, -(0.018 + 0.03 * run) * abs(math.cos(ph)) + (0.03 * run))


def P_run(f, n):
    P_walk(f, n, run=True)


def P_arms_up(f, n):
    k = sm(f / (n * 0.35)); jit = 0.0 if f < n * 0.35 else math.sin(2 * math.pi * f / (n * 0.3)) * 3
    reset_pose(); arms_down(1 - k); fingers_relax(1 - k)
    for s_, sg in (("L", 1), ("R", -1)):
        rot(f"upperarm01.{s_}", "X", (-150 + jit) * k); rot(f"upperarm01.{s_}", "Y", sg * 25 * k)
        rot(f"lowerarm01.{s_}", "X", -15 * k)
    rot("spine02", "X", -6 * k); rot("neck01", "X", -12 * k)


def P_push(f, n):
    ph = 2 * math.pi * f / n; push = 0.5 + 0.5 * math.sin(ph)
    reset_pose()
    for s_, sg in (("L", 1), ("R", -1)):
        rot(f"upperarm01.{s_}", "Y", sg * 10); rot(f"upperarm01.{s_}", "X", -(75 + 6 * push))
        rot(f"lowerarm01.{s_}", "X", -(25 - 15 * push))
    rot("spine01", "X", -(10 + 3 * push)); rot("spine03", "X", -4)
    rot("upperleg01.L", "X", -25); rot("lowerleg01.L", "X", 25)
    rot("upperleg01.R", "X", 22); rot("lowerleg01.R", "X", 8)


def P_fall(f, n):
    ph = 2 * math.pi * f / n
    reset_pose(); fingers_relax(0.5)
    for s_, sg in (("L", 1), ("R", -1)):
        rot(f"upperarm01.{s_}", "Y", -sg * (28 + 8 * math.sin(ph + (0 if sg > 0 else 1.3))))
        rot(f"lowerarm01.{s_}", "X", -20 - 10 * math.sin(ph * 2))
    rot("upperleg01.L", "X", -18 + 8 * math.sin(ph)); rot("lowerleg01.L", "X", 30)
    rot("upperleg01.R", "X", -6 - 8 * math.sin(ph)); rot("lowerleg01.R", "X", 18)
    rot("spine02", "X", 6); rot("neck01", "X", -8)


def P_wave(f, n):
    ph = 2 * math.pi * f / n
    reset_pose(); arms_down(); fingers_relax(0.3)
    rot("upperarm01.R", "Y", 30); rot("upperarm01.R", "X", -10); rot("upperarm01.R", "Y", -125)
    rot("lowerarm01.R", "Y", -(20 + 22 * math.sin(ph)))
    rot("spine02", "Y", 3); rot("head", "Z", -4)


def P_point(f, n):
    ph = 2 * math.pi * f / n; k = sm(f / (n * 0.3))
    reset_pose(); arms_down(); fingers_relax()
    rot("upperarm01.R", "Y", 30 * k); rot("upperarm01.R", "X", -85 * k); rot("upperarm01.R", "Z", 15 * k)
    rot("lowerarm01.R", "X", -5 * k)
    rot("spine02", "Z", 6 * k); rot("head", "Z", 8 * k); rot("spine03", "X", 1.2 * math.sin(ph))


def P_look_up(f, n):
    ph = 2 * math.pi * f / n; k = sm(f / (n * 0.4))
    reset_pose(); arms_down(); fingers_relax()
    rot("neck01", "X", -18 * k); rot("head", "X", -16 * k); rot("spine04", "X", -6 * k)
    rot("head", "Z", 4 * math.sin(ph))
    rot("upperarm01.L", "X", -6 * k); rot("upperarm01.R", "X", -6 * k)


def P_crouch(f, n):
    ph = 2 * math.pi * f / n
    reset_pose(); arms_down(); fingers_relax()
    for s_ in ("L", "R"):
        rot(f"upperleg01.{s_}", "X", -70); rot(f"lowerleg01.{s_}", "X", 110); rot(f"foot.{s_}", "X", -38)
        rot(f"upperarm01.{s_}", "X", -40); rot(f"lowerarm01.{s_}", "X", -40)
    rot("spine01", "X", -25); rot("neck01", "X", 12 + 2 * math.sin(ph))
    rig.location = (0, 0, -0.33)


def P_celebrate(f, n):
    ph = 2 * math.pi * f / n; up = max(0.0, math.sin(ph))
    reset_pose(); fingers_relax(0.6)
    for s_, sg in (("L", 1), ("R", -1)):
        rot(f"upperarm01.{s_}", "X", -(140 + 10 * up)); rot(f"upperarm01.{s_}", "Y", sg * 30)
        rot(f"lowerarm01.{s_}", "X", -25)
        rot(f"upperleg01.{s_}", "X", -12 * up); rot(f"lowerleg01.{s_}", "X", 24 * up)
    rot("neck01", "X", -10)
    rig.location = (0, 0, 0.12 * up)


def P_talk(f, n):
    ph = 2 * math.pi * f / n
    reset_pose(); arms_down(); fingers_relax(0.5)
    rot("upperarm01.R", "X", -25 - 10 * math.sin(ph)); rot("lowerarm01.R", "X", -60 - 15 * math.sin(ph * 2))
    rot("upperarm01.L", "X", -12 + 6 * math.sin(ph + 1)); rot("lowerarm01.L", "X", -40 + 10 * math.sin(ph * 2 + 1))
    rot("head", "X", 3 * math.sin(ph * 2)); rot("head", "Z", 4 * math.sin(ph))


ANIMS = {  # name: (pose fn, frames, loop, playback fps)
    "idle": (P_idle, 24, True, 12), "walk": (P_walk, 24, True, 24), "run": (P_run, 16, True, 24),
    "arms_up": (P_arms_up, 18, False, 24), "push": (P_push, 18, True, 14), "fall": (P_fall, 24, True, 12),
    "wave": (P_wave, 16, True, 16), "point": (P_point, 16, False, 16), "look_up": (P_look_up, 20, False, 14),
    "crouch": (P_crouch, 16, True, 10), "celebrate": (P_celebrate, 16, True, 16), "talk": (P_talk, 24, True, 12),
}
for k, nf in SPEC.get("frames", {}).items():
    if k in ANIMS:
        fn, _, lp, fps = ANIMS[k]; ANIMS[k] = (fn, int(nf), lp, fps)


def key_anim(name):
    """Bake the pose function into keyframes so Cycles can motion-blur between frames."""
    fn, n, loop, _ = ANIMS[name]
    rig.animation_data_clear()
    prev = {}
    total = n + 1
    for f in range(total):
        src = f % n if loop else min(f, n - 1)
        fn(src, n)
        for pb in pose:
            q = pb.rotation_quaternion.copy()
            if pb.name in prev and prev[pb.name].dot(q) < 0:
                q.negate(); pb.rotation_quaternion = q
            prev[pb.name] = q
            pb.keyframe_insert("rotation_quaternion", frame=f + 1)
            pb.keyframe_insert("location", frame=f + 1)
        rig.keyframe_insert("location", frame=f + 1)
    if rig.animation_data and rig.animation_data.action:
        act = rig.animation_data.action
        fcs = []
        try:
            fcs = list(act.fcurves)
        except Exception:
            for layer in getattr(act, "layers", []):
                for strip in layer.strips:
                    for cb in strip.channelbags:
                        fcs += list(cb.fcurves)
        for fc in fcs:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    return n


# ============================================================================ lights, camera, render
VIEWS = {  # camera direction (from target), elevation deg
    "back": (Vector((0, 1, 0)), 8), "back34": (Vector((0.7, 0.7, 0)).normalized(), 8),
    "side": (Vector((1, 0, 0)), 4), "side_l": (Vector((-1, 0, 0)), 4),
    "front34": (Vector((0.65, -0.75, 0)).normalized(), 6), "front": (Vector((0, -1, 0)), 5),
    "front34_l": (Vector((-0.65, -0.75, 0)).normalized(), 6), "low_back": (Vector((0, 1, 0)), -12),
}
LIGHTS = {  # key: (colour, W, camera-relative dir (right, toward camera, up)); rims behind; world colour
    "studio": dict(key=((1.0, 0.96, 0.9), 160, (-0.6, 0.8, 0.7)), rim_l=((0.85, 0.92, 1.0), 220), rim_r=((1.0, 0.95, 0.9), 160), world=(0.10, 0.10, 0.11)),
    "day": dict(key=((1.0, 0.95, 0.85), 180, (0.5, 0.6, 1.0)), rim_l=((0.8, 0.9, 1.0), 150), rim_r=((1.0, 0.95, 0.85), 120), world=(0.22, 0.27, 0.33)),
    "overcast": dict(key=((0.9, 0.93, 1.0), 90, (0.2, 0.7, 1.0)), rim_l=((0.8, 0.85, 0.9), 90), rim_r=((0.8, 0.85, 0.9), 90), world=(0.28, 0.3, 0.33)),
    "golden": dict(key=((1.0, 0.86, 0.62), 110, (-0.5, 0.8, 0.8)), rim_l=((1.0, 0.8, 0.45), 420), rim_r=((0.55, 1.0, 0.55), 120), world=(0.10, 0.13, 0.07)),
    "neon": dict(key=((0.8, 0.88, 1.0), 70, (0.4, 0.8, 0.9)), rim_l=((0.18, 0.9, 1.0), 380), rim_r=((1.0, 0.18, 0.53), 300), world=(0.015, 0.02, 0.04)),
    "water": dict(key=((0.75, 0.95, 1.0), 90, (0.2, 0.7, 1.0)), rim_l=((0.5, 0.95, 1.0), 320), rim_r=((0.6, 1.0, 0.9), 220), world=(0.03, 0.07, 0.09)),
    "night": dict(key=((0.6, 0.7, 1.0), 45, (0.3, 0.5, 1.0)), rim_l=((0.4, 0.55, 1.0), 260), rim_r=((1.0, 0.7, 0.4), 140), world=(0.01, 0.012, 0.025)),
    "interior": dict(key=((1.0, 0.85, 0.7), 120, (-0.4, 0.7, 0.8)), rim_l=((1.0, 0.8, 0.6), 160), rim_r=((0.7, 0.8, 1.0), 120), world=(0.08, 0.06, 0.05)),
    "fire": dict(key=((1.0, 0.55, 0.25), 140, (0.3, 0.8, 0.3)), rim_l=((1.0, 0.45, 0.15), 380), rim_r=((0.3, 0.4, 0.9), 120), world=(0.03, 0.015, 0.01)),
}
for k, L in SPEC.get("lights", {}).items():   # custom presets in the spec, same shape (colours may be hex)
    LIGHTS[k] = dict(key=(col(L["key"][0]), L["key"][1], tuple(L["key"][2])), rim_l=(col(L["rim_l"][0]), L["rim_l"][1]),
                     rim_r=(col(L["rim_r"][0]), L["rim_r"][1]), world=col(L.get("world"), (0.05, 0.05, 0.05)))

RSPEC = SPEC.get("render", {})
RES = A.res or int(RSPEC.get("res", 960))
SAMPLES = A.samples or int(RSPEC.get("samples", 32))


def setup_render(res_h, aspect=0.75):
    scene.render.engine = "CYCLES"
    cy = scene.cycles
    cy.samples = SAMPLES; cy.use_denoising = True
    cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.03
    cy.max_bounces = 4; cy.diffuse_bounces = 2; cy.glossy_bounces = 2; cy.transparent_max_bounces = 4
    try:
        cy.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    cy.device = "CPU"
    if A.device in ("auto", "gpu"):
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = backend; prefs.get_devices()
                devs = [d for d in prefs.devices if d.type != "CPU"]
                if devs:
                    for d in prefs.devices:
                        d.use = d.type != "CPU"
                    cy.device = "GPU"; print("Cycles GPU:", backend, [d.name for d in devs]); break
            except Exception:
                continue
    scene.render.film_transparent = True
    scene.render.use_persistent_data = True
    scene.render.use_motion_blur = not A.fast and bool(RSPEC.get("motion_blur", True))
    scene.render.motion_blur_shutter = 0.45
    scene.render.resolution_y = res_h; scene.render.resolution_x = int(res_h * aspect)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    try:
        scene.view_settings.look = "Medium High Contrast"
    except Exception:
        pass
    scene.render.fps = 24


def setup_world(color):
    w = bpy.data.worlds.get("W") or bpy.data.worlds.new("W"); w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (*color, 1)
    scene.world = w


def area_light(name, color, power, pos, target, size=1.2):
    ld = bpy.data.lights.get(name) or bpy.data.lights.new(name, "AREA")
    ld.color = color; ld.energy = power; ld.size = size
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, ld); scene.collection.objects.link(ob)
    ob.location = pos; ob.rotation_euler = (target - pos).to_track_quat("-Z", "Y").to_euler()


def measure_height():
    dg = bpy.context.evaluated_depsgraph_get(); top = 0.0
    for ob in scene.objects:
        if ob.type in ("MESH", "CURVES") and not ob.hide_render and ob.name != "Ground":
            ev = ob.evaluated_get(dg)
            for c in ev.bound_box:
                top = max(top, (ev.matrix_world @ Vector(c)).z)
    return top


reset_pose(); arms_down(); bpy.context.view_layer.update()
HEIGHT = measure_height()
ORTHO = max(1.0, HEIGHT * 1.42)
CENTER = Vector((0, SPINE_Y, HEIGHT * 0.52))


def setup_lights(preset, view_dir):
    L = LIGHTS.get(preset, LIGHTS["studio"]); setup_world(L["world"])
    up = Vector((0, 0, 1)); right = -view_dir.cross(up).normalized()
    kc, kp, (dx, dy, dz) = L["key"]
    kd = right * dx + view_dir * dy + up * dz
    area_light("Key", kc, kp * (HEIGHT / 1.84) ** 2, CENTER + kd.normalized() * 4 * HEIGHT / 1.84, CENTER, 3)
    s = HEIGHT / 1.84
    area_light("RimL", L["rim_l"][0], L["rim_l"][1] * s * s, CENTER - view_dir * 2.2 * s - right * 1.6 * s + up * 0.6 * s, CENTER, 1.0)
    area_light("RimR", L["rim_r"][0], L["rim_r"][1] * s * s, CENTER - view_dir * 2.2 * s + right * 1.6 * s + up * 0.4 * s, CENTER, 1.0)


def setup_camera(view, ortho=None, look=None):
    d, elev = VIEWS[view]
    cam = bpy.data.objects.get("Cam")
    if cam is None:
        cd = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cd); scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"; cam.data.ortho_scale = ortho or ORTHO
    look = look or Vector((0, SPINE_Y, ORTHO * 0.377))
    pos = look + Vector((d.x, d.y, math.tan(math.radians(elev)))).normalized() * 8
    cam.location = pos; cam.rotation_euler = (look - pos).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    return cam


def project(cam, p):
    from bpy_extras.object_utils import world_to_camera_view
    c = world_to_camera_view(scene, cam, p)
    return [c.x, 1 - c.y]


def shadow_catcher(on):
    pl = bpy.data.objects.get("Ground")
    if pl is None:
        bpy.ops.mesh.primitive_plane_add(size=8); pl = bpy.context.active_object; pl.name = "Ground"
        pl.is_shadow_catcher = True
    pl.hide_render = not on


def render_anim(name, view, light):
    fn, n, loop, afps = ANIMS[name]
    key_anim(name)
    cam = setup_camera(view); setup_lights(light, VIEWS[view][0]); shadow_catcher(name not in ("fall",))
    folder = OUT / f"{name}_{view}_{light}"; folder.mkdir(parents=True, exist_ok=True)
    meta = {"char": CID, "anim": name, "view": view, "light": light, "frames": n, "loop": loop, "fps": afps,
            "size": [scene.render.resolution_x, scene.render.resolution_y], "height_m": HEIGHT, "ortho": ORTHO,
            "feet": [], "hands": [], "head": []}
    for f in ([n // 3] if A.test else range(n)):
        scene.frame_set(f + 1)
        meta["hands"].append([project(cam, rig.matrix_world @ pose[b].tail) for b in ("lowerarm02.L", "lowerarm02.R") if b in pose])
        meta["feet"].append(project(cam, Vector((0, CENTER.y, 0))))
        meta["head"].append(project(cam, rig.matrix_world @ pose["head"].tail))
        scene.render.filepath = str(folder / f"{(0 if A.test else f):04d}.png")
        t0 = time.time(); bpy.ops.render.render(write_still=True)
        print(f"  {CID}/{folder.name}/{f:04d}.png  {time.time() - t0:.1f}s", flush=True)
    (folder / "meta.json").write_text(json.dumps(meta))


def render_sheet():
    folder = OUT / "_sheet"; folder.mkdir(parents=True, exist_ok=True)
    scene.render.use_motion_blur = False
    rig.animation_data_clear(); P_idle(0, 24); bpy.context.view_layer.update()
    shadow_catcher(True)
    for view in ("front", "front34", "side", "back"):
        cam = setup_camera(view); setup_lights("studio", VIEWS[view][0])
        scene.render.filepath = str(folder / f"{view}.png")
        t0 = time.time(); bpy.ops.render.render(write_still=True); print(f"  sheet {view} {time.time() - t0:.1f}s", flush=True)
    # face close-up
    shadow_catcher(False)
    head = rig.matrix_world @ pose["head"].head
    look = Vector((0, EYE_C.y, (EYE_C.z + head.z) / 2 + 0.02))
    cam = setup_camera("front34", ortho=0.42, look=look); setup_lights("studio", VIEWS["front34"][0])
    rx, ry = scene.render.resolution_x, scene.render.resolution_y
    scene.render.resolution_x = ry
    scene.render.filepath = str(folder / "face.png"); bpy.ops.render.render(write_still=True)
    cam = setup_camera("back34", ortho=0.42, look=look + Vector((0, 0.06, 0))); setup_lights("studio", VIEWS["back34"][0])
    scene.render.filepath = str(folder / "head_back.png"); bpy.ops.render.render(write_still=True)
    scene.render.resolution_x = rx
    (folder / "meta.json").write_text(json.dumps({"char": CID, "height_m": HEIGHT, "ortho": ORTHO}))


setup_render(RES)
if A.save_blend:
    bpy.ops.wm.save_as_mainfile(filepath=A.save_blend)
print(f"{CID}: height {HEIGHT:.2f} m, ortho {ORTHO:.2f} m, hair '{HSTYLE}', pieces {[k for k, v in pieces.items() if v]}", flush=True)
if A.sheet:
    render_sheet()
else:
    jobs = [s.split(":") for s in A.only.split(",") if s] or SPEC.get("renders") or [["idle", "back", "studio"]]
    for job in jobs:
        render_anim(job[0], job[1] if len(job) > 1 else "back", job[2] if len(job) > 2 else "studio")
print("done")
