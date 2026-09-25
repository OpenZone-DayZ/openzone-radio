"""Common kit for radio models (Blender Python): parts, materials, LODs, unwrapping,
baking, textures, MLOD p3d.

Assembly coordinate system (Blender): X right, Y back (the radio's face looks toward -Y), Z up,
meters. The origin is the center of the case's bottom face; the case is centered along its depth.

The DayZ frame was taken from the vanilla WalkieTalkie.p3d (ODOL, 23.09): its Geometry - case
x -0.032..0.030, y 0..0.141, z -0.019..0.022, and antenna x -0.027..-0.010, y 0.140..0.257,
z 0.004..0.021. The antenna is on the left when viewed from the front (that's how its texture
is drawn), and left when viewed from -Z turns out to be -X - meaning the vanilla radio's face
looks toward -Z, with the origin at the bottom, +Y up. The PersonalRadio.anm grip and the
backpack strap's proxy slot are tuned to this frame, so our models are written in the same frame:
    DayZ (x, y, z) = Blender (x, z, y)       - Y/Z swapped, determinant -1, as it should be.

Each radio is its own build_<name>.py script with a build(m) function that builds parts
according to level m.q: q = 0 - detail model (bake source only), q = 1..4 - in-game LODs.
"""
import math
import os
import struct
import subprocess
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

KIT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(KIT, ".."))
MODELS = os.path.normpath(os.path.join(ASSETS, ".."))      # models/ - model sources
REPO = os.path.normpath(os.path.join(MODELS, ".."))        # root of the openzone-radio repository
# Models are part of the main mod: the folder and pbo prefix are OpenZone_Radio, with model\<radio> inside.
# PREFIX - what every path baked into the p3d and rvmat starts with.
MOD = "OpenZone_Radio"
PREFIX = MOD + "\\model"
PBO_ROOT = os.path.join(REPO, MOD, "model")
# Binarize root (build.project_root in the repository's dayz-mcp.toml): contains the OpenZone_Radio folder.
MODEL_ROOT = os.path.join(REPO, "build", "model-root")
VANILLA_DZ = r"D:\modding\PDrive\dz"
IMAGE_TO_PAA = r"E:\SteamLibrary\steamapps\common\DayZ Tools\Bin\ImageToPAA\ImageToPAA.exe"
PEN = r"dz\data\data\penetration"
sys.path.insert(0, r"C:\Users\Crystal\.claude\skills\dayz-modding\scripts")
import p3d  # noqa: E402

# face tags (the "part" layer): atlas priority and special sections
T_GEN, T_FRONT, T_BACK, T_HIDE, T_LCD, T_KEYS, T_LABEL, T_GLASS = range(8)
UV_WEIGHT = {T_GEN: 1.0, T_FRONT: 1.35, T_BACK: 0.75, T_HIDE: 0.4, T_LCD: 1.4, T_KEYS: 1.55,
             T_LABEL: 0.02, T_GLASS: 0.02}
# material slots of the in-game LODs
G_ATLAS, G_LABEL, G_GLASS = 0, 1, 2


# =============================================================================
# 2D profiles (a, b): for the Y axis this is (x, z), for the Z axis - (x, y), for the X axis - (y, z)
# =============================================================================
def arc(ca, cb, r, a0, a1, n):
    return [(ca + r * math.cos(a0 + (a1 - a0) * i / n), cb + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def circle(ca, cb, r, n, a0=0.0):
    return [(ca + r * math.cos(a0 + 2 * math.pi * i / n), cb + r * math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]


def rect(w, h, ca=0.0, cb=0.0):
    return [(ca + w / 2, cb - h / 2), (ca + w / 2, cb + h / 2), (ca - w / 2, cb + h / 2), (ca - w / 2, cb - h / 2)]


def rrect(w, h, r, ca=0.0, cb=0.0, seg=6):
    """Rounded rectangle, counter-clockwise; r can be a tuple (bottom-right, top-right, top-left, bottom-left)."""
    rs = r if isinstance(r, (tuple, list)) else (r, r, r, r)
    pts = []
    for (sa, sb, a0), rr in zip(((1, -1, -90), (1, 1, 0), (-1, 1, 90), (-1, -1, 180)), rs):
        if rr <= 1e-7 or seg <= 0:
            pts.append((ca + sa * w / 2, cb + sb * h / 2))
            continue
        pts += arc(ca + sa * (w / 2 - rr), cb + sb * (h / 2 - rr), rr, math.radians(a0), math.radians(a0 + 90), seg)
    return pts


def rounded_poly(pts, radii, seg=6):
    """Polygon with rounded vertices (radius 0 - sharp vertex)."""
    out = []
    n = len(pts)
    for i in range(n):
        p, a, b = Vector(pts[i]), Vector(pts[i - 1]), Vector(pts[(i + 1) % n])
        r = radii[i] if isinstance(radii, (list, tuple)) else radii
        if r <= 0 or seg <= 0:
            out.append(tuple(p))
            continue
        u1, u2 = (a - p).normalized(), (b - p).normalized()
        half = u1.angle(u2) / 2
        d = r / math.tan(half)
        c = p + (u1 + u2).normalized() * (r / math.sin(half))
        t1, t2 = p + u1 * d, p + u2 * d
        a1 = math.atan2(t1.y - c.y, t1.x - c.x)
        a2 = math.atan2(t2.y - c.y, t2.x - c.x)
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        out += [(c.x + r * math.cos(a1 + da * k / seg), c.y + r * math.sin(a1 + da * k / seg)) for k in range(seg + 1)]
    return out


def knurl(ca, cb, r_lo, r_hi, teeth, shape=(0.0, 0.12, 0.5, 0.62)):
    """Knurled profile: teeth with a flat top; shape - fractions of the step."""
    pts = []
    for t in range(teeth):
        a = 2 * math.pi * t / teeth
        s = 2 * math.pi / teeth
        for f, r in zip(shape, (r_lo, r_hi, r_hi, r_lo)):
            pts.append((ca + r * math.cos(a + f * s), cb + r * math.sin(a + f * s)))
    return pts


def densify(pts, step, closed=True):
    """Insert points on long contour edges (so the part can be bent)."""
    out = []
    n = len(pts)
    for i in range(n if closed else n - 1):
        a, b = Vector(pts[i]), Vector(pts[(i + 1) % n])
        k = max(1, int(math.ceil((b - a).length / step)))
        for j in range(k):
            p = a + (b - a) * (j / k)
            out.append((p.x, p.y))
    if not closed:
        out.append(tuple(pts[-1]))
    return out


def ccw(pts):
    """Counter-clockwise contour (for prism this matters only for consistency)."""
    s = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return pts if s > 0 else pts[::-1]


# =============================================================================
# BMesh
# =============================================================================
def _v(axis, a, b, t):
    if axis == "Y":
        return (a, t, b)
    if axis == "Z":
        return (a, b, t)
    return (t, a, b)  # X


def prism(pts, t0, t1, axis="Y"):
    """Prism: a 2D contour extruded along the axis from t0 to t1."""
    bm = bmesh.new()
    pts = ccw(pts)
    lo = [bm.verts.new(_v(axis, a, b, t0)) for a, b in pts]
    hi = [bm.verts.new(_v(axis, a, b, t1)) for a, b in pts]
    n = len(pts)
    bm.faces.new(lo[::-1])
    bm.faces.new(hi)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    fix_normals(bm)
    return bm


def ring_prism(outer, inner, t0, t1, axis="Y", closed=True):
    """Ring between two contours of equal length (a frame around a window)."""
    bm = bmesh.new()
    ol = [bm.verts.new(_v(axis, a, b, t0)) for a, b in outer]
    oh = [bm.verts.new(_v(axis, a, b, t1)) for a, b in outer]
    il = [bm.verts.new(_v(axis, a, b, t0)) for a, b in inner]
    ih = [bm.verts.new(_v(axis, a, b, t1)) for a, b in inner]
    n = len(outer)
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        bm.faces.new((ol[i], ol[j], il[j], il[i]))
        bm.faces.new((oh[i], ih[i], ih[j], oh[j]))
        bm.faces.new((ol[i], oh[i], oh[j], ol[j]))
        bm.faces.new((il[i], il[j], ih[j], ih[i]))
    if not closed:
        for k in (0, n - 1):
            bm.faces.new((ol[k], il[k], ih[k], oh[k]))
    fix_normals(bm)
    return bm


def lathe(profile, n, ca=0.0, cb=0.0, axis="Z", a0=0.0):
    """Solid of revolution around axis, passing through (ca, cb). profile: [(r, t)] along the
    axis; r = 0 gives a pole, otherwise the end cap is closed with an n-gon."""
    bm = bmesh.new()
    rings = []
    for r, t in profile:
        if r < 1e-7:
            rings.append([bm.verts.new(_v(axis, ca, cb, t))])
        else:
            rings.append([bm.verts.new(_v(axis, ca + r * math.cos(a0 + 2 * math.pi * i / n),
                                          cb + r * math.sin(a0 + 2 * math.pi * i / n), t)) for i in range(n)])
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 or len(b) == 1:
            pole, ring = (a[0], b) if len(a) == 1 else (b[0], a)
            for i in range(n):
                bm.faces.new((pole, ring[i], ring[(i + 1) % n]))
        else:
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((a[i], a[j], b[j], b[i]))
    for ring in (rings[0], rings[-1]):
        if len(ring) > 1:
            bm.faces.new(ring)
    fix_normals(bm)
    return bm


def cyl(ca, cb, r, t0, t1, n=24, axis="Y"):
    return prism(circle(ca, cb, r, n), t0, t1, axis)


def box(x0, x1, y0, y1, z0, z1):
    return prism(rect(x1 - x0, z1 - z0, (x0 + x1) / 2, (z0 + z1) / 2), y0, y1, "Y")


def fix_normals(bm):
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def bevel(bm, width, segments, angle=30.0, profile=0.5, only=None, clamp=True):
    """Bevel/round edges whose dihedral angle is greater than angle. only(edge) - a filter.

    clamp - Blender's clamp_overlap. It is cautious: on a contour of frequent short edges (the
    grip waves of the T-388, 1.3 mm pitch) it clamped a 4.5 mm bevel down to 2.9 mm across the
    whole part. Where the contour is smooth and overlaps are impossible, it is turned off."""
    if width <= 0 or segments <= 0:
        return bm
    bm.normal_update()
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(angle)
             and (only is None or only(e))]
    if edges:
        bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type="OFFSET", segments=segments, profile=profile,
                        affect="EDGES", clamp_overlap=clamp)
    fix_normals(bm)
    return bm


def transform(bm, mat):
    bmesh.ops.transform(bm, matrix=mat, verts=bm.verts[:])
    return bm


def move(bm, dx=0.0, dy=0.0, dz=0.0):
    return transform(bm, Matrix.Translation((dx, dy, dz)))


def rotate(bm, deg, axis, pivot=(0, 0, 0)):
    p = Vector(pivot)
    return transform(bm, Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-p))


def merge(*bms):
    out = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new("_m")
        b.to_mesh(me)
        b.free()
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
    return out


def _tmp_obj(bm, name="_tmp"):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def boolean(bm, others, op="DIFFERENCE"):
    """Boolean operation (EXACT) over a bmesh; others - list of bmesh, they get freed."""
    if not others:
        return bm
    ob = _tmp_obj(bm, "_bool")
    cut_obs = []
    for o in others:
        c = _tmp_obj(o, "_cutter")
        c.hide_render = True
        cut_obs.append(c)
        m = ob.modifiers.new("b", "BOOLEAN")
        m.operation = op
        m.solver = "EXACT"
        m.object = c
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    out = bmesh.new()
    out.from_mesh(me)
    bpy.data.meshes.remove(me)
    for o in [ob] + cut_obs:
        m = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.meshes.remove(m)
    fix_normals(out)
    return out


def flat_face(pts3d, facing):
    """A single flat face, oriented with its normal toward facing (Vector)."""
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(p) for p in pts3d])
    bm.normal_update()
    if f.normal.dot(Vector(facing)) < 0:
        bmesh.ops.reverse_faces(bm, faces=[f])
    return bm


# =============================================================================
# Materials (Cycles) - detail model only
# =============================================================================
def node_mat(name):
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) or nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
    out.name = "Material Output"
    if not out.inputs["Surface"].is_linked:
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m, nt, bsdf


def sock(coll_, ident):
    return next(s for s in coll_ if s.identifier == ident)


def _math(nt, op, a, b, clamp=True):
    mn = nt.nodes.new("ShaderNodeMath")
    mn.operation = op
    mn.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if isinstance(v, (int, float)):
            mn.inputs[i].default_value = float(v)
        elif v is not None:
            nt.links.new(v, mn.inputs[i])
    return mn.outputs["Value"]


def _mix_color(nt, fac, a, b):
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    for s, v in ((sock(mx.inputs, "Factor_Float"), fac), (sock(mx.inputs, "A_Color"), a), (sock(mx.inputs, "B_Color"), b)):
        if isinstance(v, (tuple, list)):
            s.default_value = (*v[:3], 1.0) if len(v) == 3 else tuple(v)
        elif isinstance(v, (int, float)):
            s.default_value = float(v)
        else:
            nt.links.new(v, s)
    return sock(mx.outputs, "Result_Color")


def _mix_float(nt, fac, a, b):
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "FLOAT"
    for s, v in ((sock(mx.inputs, "Factor_Float"), fac), (sock(mx.inputs, "A_Float"), a), (sock(mx.inputs, "B_Float"), b)):
        if isinstance(v, (int, float)):
            s.default_value = float(v)
        else:
            nt.links.new(v, s)
    return sock(mx.outputs, "Result_Float")


_images = {}


def load_image(path, noncolor=False):
    key = (path, noncolor)
    if key not in _images:
        img = bpy.data.images.load(path, check_existing=False)
        if noncolor:
            img.colorspace_settings.name = "Non-Color"
        _images[key] = img
    return _images[key]


# Print: an image projected onto faces that face a given direction.
# print_spec = dict(image=path, rect=(a0, a1, b0, b1), axis="-Y"|"+X"|"-X"|"+Z"|"+Y")
# rect - the image rectangle in model coordinates on the projection plane:
#   -Y (face): a = x,  b = z (viewed from the front: x to the right)
#   +Y (back): a = -x, b = z (viewed from the rear: -x to the right)
#   -X (left side): a = -y, b = z;  +X (right side): a = y, b = z
#   +Z (top):  a = x,  b = -y (viewed from above, the radio's front is at the bottom of the image)
PROJ = {
    "-Y": ((0, 1.0), (2, 1.0), Vector((0, -1, 0))),
    "+Y": ((0, -1.0), (2, 1.0), Vector((0, 1, 0))),
    "-X": ((1, -1.0), (2, 1.0), Vector((-1, 0, 0))),
    "+X": ((1, 1.0), (2, 1.0), Vector((1, 0, 0))),
    "+Z": ((0, 1.0), (1, -1.0), Vector((0, 0, 1))),
}


def _print_layer(nt, color, spec, tc, geo):
    (ia, sa), (ib, sb), facing = PROJ[spec["axis"]]
    a0, a1, b0, b1 = spec["rect"]
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    comps = [sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]]
    u = _math(nt, "MULTIPLY", comps[ia], sa, clamp=False)
    u = _math(nt, "SUBTRACT", u, a0, clamp=False)
    u = _math(nt, "DIVIDE", u, a1 - a0, clamp=False)
    v = _math(nt, "MULTIPLY", comps[ib], sb, clamp=False)
    v = _math(nt, "SUBTRACT", v, b0, clamp=False)
    v = _math(nt, "DIVIDE", v, b1 - b0, clamp=False)
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(u, comb.inputs["X"])
    nt.links.new(v, comb.inputs["Y"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = load_image(spec["image"])
    tex.extension = "CLIP"
    tex.interpolation = "Cubic"
    nt.links.new(comb.outputs["Vector"], tex.inputs["Vector"])
    # side mask: only faces that face the same direction as the projection
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = facing
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    side = _math(nt, "GREATER_THAN", dot.outputs["Value"], spec.get("min_dot", 0.6))
    if spec.get("depth"):     # print only on faces within the depth band (e.g. key caps)
        comp = comps[{"-Y": 1, "+Y": 1, "-X": 0, "+X": 0, "+Z": 2}[spec["axis"]]]
        d0, d1 = spec["depth"]
        lo = _math(nt, "GREATER_THAN", comp, d0)
        hi = _math(nt, "LESS_THAN", comp, d1)
        side = _math(nt, "MULTIPLY", side, _math(nt, "MULTIPLY", lo, hi))
    fac = _math(nt, "MULTIPLY", tex.outputs["Alpha"], side)
    if "strength" in spec:
        fac = _math(nt, "MULTIPLY", fac, spec["strength"])
    return _mix_color(nt, fac, color, tex.outputs["Color"]), fac


def mat_worn(name, base, rough=(0.45, 0.65), metallic=0.0, dust=(0.16, 0.15, 0.13), edge_col=None,
             dust_amount=0.35, edge_amount=1.0, prints=(), soft_edges=0.0006, noise_bump=0.0, image=None,
             grime=None):
    """Worn material: roughness variation, worn light edges, print, dust in recesses.

    soft_edges - radius of the Bevel node wired into the normal: when baking normals, sharp
    edges of the detail model (including from boolean cuts) come out softly rounded.
    image - (path, rect, axis): base color from an image instead of flat (LCD display, nameplate).
    grime - (color, amount, scale): patches of ingrained dirt via noise over everything (dirty radios)."""
    m, nt, b = node_mat(name)
    N = nt.nodes
    tc = N.new("ShaderNodeTexCoord")
    geo = N.new("ShaderNodeNewGeometry")
    edge_col = edge_col or tuple(min(1.0, c * 3.2 + 0.05) for c in base)

    def noise(scale, detail, rough_=0.55):
        n = N.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough_
        nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
        return n.outputs["Fac"]

    # base color: flat or from an image
    color = (*base, 1.0)
    if image:
        color, _ = _print_layer(nt, color, dict(image=image[0], rect=image[1], axis=image[2], min_dot=-2.0), tc, geo)

    # worn edges: the Bevel node's normal diverges from the real one
    bev = N.new("ShaderNodeBevel")
    bev.inputs["Radius"].default_value = 0.0009
    dot = N.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(bev.outputs["Normal"], dot.inputs[0])
    nt.links.new(geo.outputs["Normal"], dot.inputs[1])
    edge = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, dot.outputs["Value"]), 30.0)
    edge = _math(nt, "MULTIPLY", edge, noise(260.0, 4.0))
    edge_m = _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", edge, 0.20), edge_amount)
    color = _mix_color(nt, edge_m, color, edge_col)

    for spec in prints:
        color, _ = _print_layer(nt, color, spec, tc, geo)

    # dust: cavities (AO) + upward-facing faces
    ao = N.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 0.004
    ao.only_local = True
    cav = _math(nt, "SUBTRACT", 1.0, ao.outputs["AO"])
    sep = N.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], sep.inputs[0])
    up = _math(nt, "MULTIPLY", sep.outputs["Z"], 0.35)
    dmask = _math(nt, "MAXIMUM", _math(nt, "MULTIPLY", cav, 1.6), up)
    dust_f = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", dmask, noise(55.0, 5.0)), 0.9 * dust_amount)
    color = _mix_color(nt, dust_f, color, dust)
    if grime:
        g_col, g_amt, g_scale = grime
        gr = N.new("ShaderNodeMapRange")
        gr.inputs["From Min"].default_value = 0.48
        gr.inputs["From Max"].default_value = 0.72
        gr.inputs["To Min"].default_value = 0.0
        gr.inputs["To Max"].default_value = g_amt
        nt.links.new(noise(g_scale, 8.0, 0.62), gr.inputs["Value"])
        color = _mix_color(nt, gr.outputs["Result"], color, g_col)
        dust_f = _math(nt, "MAXIMUM", dust_f, gr.outputs["Result"])
    nt.links.new(color, b.inputs["Base Color"])

    r = N.new("ShaderNodeMapRange")
    r.inputs["From Min"].default_value = 0.3
    r.inputs["From Max"].default_value = 0.7
    r.inputs["To Min"].default_value = rough[0]
    r.inputs["To Max"].default_value = rough[1]
    nt.links.new(noise(120.0, 6.0), r.inputs["Value"])
    rr = _mix_float(nt, dust_f, r.outputs["Result"], 0.92)
    rr = _mix_float(nt, edge_m, rr, min(1.0, rough[1] + 0.1) if metallic < 0.5 else max(0.1, rough[0] - 0.15))
    nt.links.new(rr, b.inputs["Roughness"])
    b.inputs["Metallic"].default_value = metallic

    nrm = None
    if soft_edges > 0:
        sb = N.new("ShaderNodeBevel")
        sb.samples = 8
        sb.inputs["Radius"].default_value = soft_edges
        nrm = sb.outputs["Normal"]
    if noise_bump > 0:
        bump = N.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = noise_bump
        bump.inputs["Distance"].default_value = 0.0002
        nt.links.new(noise(900.0, 3.0, 0.7), bump.inputs["Height"])
        if nrm is not None:
            nt.links.new(nrm, bump.inputs["Normal"])
        nrm = bump.outputs["Normal"]
    if nrm is not None:
        nt.links.new(nrm, b.inputs["Normal"])
    return m


def mat_simple(name, color, rough, metallic=0.0, emission=None):
    m, nt, b = node_mat(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if emission:
        b.inputs["Emission Color"].default_value = (*emission[0], 1)
        b.inputs["Emission Strength"].default_value = emission[1]
    return m


def mat_image(name, path, rough=0.5, metallic=0.0):
    """Material with an image mapped by UV (sticker/strap: it has its own 0..1 unwrap)."""
    m, nt, b = node_mat(name)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = load_image(path)
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    return m


# =============================================================================
# Model: parts by level
# =============================================================================
class LodMesh:
    def __init__(self):
        self.bm = bmesh.new()
        self.tag = self.bm.faces.layers.int.new("part")

    def add(self, part, tag, gmat, auto_tag):
        part.normal_update()
        tags = []
        for f in part.faces:
            t = tag
            if auto_tag and tag == T_GEN:
                n = f.normal
                t = T_FRONT if n.y < -0.7 else T_BACK if n.y > 0.7 else T_HIDE if n.z < -0.7 else T_GEN
            tags.append(t)
        me = bpy.data.meshes.new("_tmp")
        part.to_mesh(me)
        part.free()
        n0 = len(self.bm.faces)
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        self.bm.faces.ensure_lookup_table()
        for f, t in zip(self.bm.faces[n0:], tags):
            f[self.tag] = t
            f.material_index = gmat

    def finish(self, name, collection, sharp_deg=35.0):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
        for e in bm.edges:
            e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(0.0) < math.radians(sharp_deg)
        for f in bm.faces:
            f.smooth = True
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for mn in ("M_GameAtlas", "M_GameLabel", "M_GameGlass"):
            me.materials.append(bpy.data.materials.get(mn) or bpy.data.materials.new(mn))
        ob = bpy.data.objects.new(name, me)
        collection.objects.link(ob)
        return ob


class Model:
    """Collector of parts for one level. q = 0 - detail model (objects with Cycles materials),
    q = 1..4 - in-game LOD (a single mesh with face tags)."""

    def __init__(self, q, mats=None, collection=None):
        self.q = q
        self.hi = q == 0
        self.M = mats or {}
        self.col = collection
        self.lod = None if self.hi else LodMesh()
        self.objects = []

    def s(self, *v):
        """Value by level: v[0] detail, v[1] LOD1, ... (the last one carries on further)."""
        return v[min(self.q, len(v) - 1)]

    def upto(self, q_max):
        """Does the part exist at this level? (0 - detail model only)."""
        return self.q <= q_max

    def add(self, bm, mat="body", tag=T_GEN, name="part", bevel_=None, cuts=None, gmat=G_ATLAS, bake=True,
            auto_tag=True, smooth_deg=40.0, bevel_angle=30.0, label=False):
        """bevel_ = (width, (segments per level)), e.g. (0.001, (3, 1, 0)) - a 3-segment round
        on the detail model, a chamfer on LOD1, no bevel further on. cuts - list of bmesh to
        subtract (built by the caller already for this level)."""
        if bevel_:
            w, segs = bevel_
            sg = segs[min(self.q, len(segs) - 1)]
            if sg > 0:
                bevel(bm, w, sg, angle=bevel_angle)
        if cuts:
            bm = boolean(bm, list(cuts))
        if self.hi:
            for e in bm.edges:
                e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(0.0) < math.radians(smooth_deg)
            for f in bm.faces:
                f.smooth = True
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            bm.free()
            me.materials.append(self.M[mat])
            ob = bpy.data.objects.new(name, me)
            self.col.objects.link(ob)
            ob["bake"] = bool(bake)
            if label:
                ob["label"] = True
            self.objects.append(ob)
            return ob
        self.lod.add(bm, tag, gmat, auto_tag)
        return None


# =============================================================================
# Studio and preview
# =============================================================================
def studio(bg=(0.30, 0.30, 0.31)):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    use_gpu()
    sc.cycles.samples = 96
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1200, 1200
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = world
    if hasattr(world, "use_nodes"):
        world.use_nodes = True
    wn = world.node_tree.nodes
    for n in list(wn):
        if n.type not in ("BACKGROUND", "OUTPUT_WORLD"):
            wn.remove(n)
    bgn = next(n for n in wn if n.type == "BACKGROUND")
    bgn.inputs["Color"].default_value = (0.5, 0.5, 0.52, 1)
    bgn.inputs["Strength"].default_value = 0.30
    cam_bg = wn.new("ShaderNodeBackground")
    cam_bg.inputs["Color"].default_value = (*bg, 1)
    lp = wn.new("ShaderNodeLightPath")
    mix = wn.new("ShaderNodeMixShader")
    wout = next(n for n in wn if n.type == "OUTPUT_WORLD")
    world.node_tree.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    world.node_tree.links.new(bgn.outputs["Background"], mix.inputs[1])
    world.node_tree.links.new(cam_bg.outputs["Background"], mix.inputs[2])
    world.node_tree.links.new(mix.outputs["Shader"], wout.inputs["Surface"])

    c = bpy.data.collections.get("Studio") or bpy.data.collections.new("Studio")
    if c.name not in sc.collection.children:
        sc.collection.children.link(c)
    for ob in list(c.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    def area(name, loc, size, power, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.shape = "DISK"
        ld.size = size
        ld.energy = power
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        ob.rotation_euler = (Vector((0, 0, 0.08)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        c.objects.link(ob)

    area("Key", (-0.55, -0.75, 0.55), 0.5, 32, (1.0, 0.96, 0.9))
    area("Fill", (0.8, -0.6, 0.15), 0.9, 10, (0.9, 0.95, 1.0))
    area("Rim", (0.3, 0.55, 0.6), 0.4, 22)
    cam_d = bpy.data.cameras.new("Camera")
    cam_d.lens = 85
    cam = bpy.data.objects.new("Camera", cam_d)
    c.objects.link(cam)
    sc.camera = cam
    return cam


def aim(cam, yaw, pitch, dist, target):
    """yaw - azimuth (degrees, 0 - front, negative - left), pitch - elevation."""
    t = Vector(target)
    y, p = math.radians(yaw), math.radians(pitch)
    cam.location = t + Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p))) * dist
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()


def render(path, cam, yaw, pitch, dist, target, show=None, samples=96, res=1200):
    sc = bpy.context.scene
    aim(cam, yaw, pitch, dist, target)
    sc.cycles.samples = samples
    sc.render.resolution_x = sc.render.resolution_y = res
    hidden = []
    if show is not None:
        for ob in sc.objects:
            if ob.type == "MESH":
                vis = ob in show
                if ob.hide_render == vis:
                    hidden.append((ob, ob.hide_render))
                    ob.hide_render = not vis
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for ob, h in hidden:
        ob.hide_render = h
    print("render:", path)


# =============================================================================
# Unwrap
# =============================================================================
def select_only(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def _uv_area(f, uvl):
    pts = [l[uvl].uv for l in f.loops]
    s = 0.0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        s += a.x * b.y - b.x * a.y
    return abs(s) / 2


def unwrap(ob, weights=None, angle=55.0, margin=0.004):
    """Smart UV separately for each tag, then texel density by tag weight, then packing.

    First each face group is unwrapped separately (islands don't mix tags), then its islands
    are scaled so that UV area per square meter is the same for all groups, multiplied by
    weight^2 - face and keys bigger, back and bottom smaller, strap and glass almost nothing
    (they have their own texture). pack_islands scales everything equally, the ratio is kept."""
    weights = weights or UV_WEIGHT
    select_only(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(ob.data)
    tag = bm.faces.layers.int["part"]
    tags = sorted({f[tag] for f in bm.faces})
    for t in tags:
        for f in bm.faces:
            f.select = f[tag] == t
        bmesh.update_edit_mesh(ob.data)
        bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=0.0, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
        bm = bmesh.from_edit_mesh(ob.data)
        tag = bm.faces.layers.int["part"]
    uvl = bm.loops.layers.uv.active
    groups = {}
    for f in bm.faces:
        groups.setdefault(f[tag], []).append(f)
    for t, faces in groups.items():
        a3 = sum(f.calc_area() for f in faces)
        auv = sum(_uv_area(f, uvl) for f in faces)
        if a3 <= 0 or auv <= 0:
            continue
        k = math.sqrt(weights.get(t, 1.0) ** 2 * a3 / auv)
        for f in faces:
            for l in f.loops:
                l[uvl].uv = l[uvl].uv * k
    for f in bm.faces:
        f.select = True
    bmesh.update_edit_mesh(ob.data)
    # CONVEX, not CONCAVE: by default the packer drops small islands into the "holes" of big
    # ones (into the keypad recess inside the face island). A far LOD, whose face is one big
    # face with no recess, interpolates UV across that hole and shows other islands as streaks.
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=margin, shape_method="CONVEX")
    except TypeError:
        bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")


def transfer_uv(dst, src):
    """Give far LODs the UV from LOD1 (one atlas). The nearest point is searched only among
    LOD1 faces with the same tag and the same dominant normal axis, and UV is taken
    barycentrically (skill: transferring by nearest face without this stretches the face
    across other islands)."""
    from mathutils.bvhtree import BVHTree
    from mathutils.geometry import barycentric_transform

    def bucket(n):
        i = max(range(3), key=lambda k: abs(n[k]))
        return i * 2 + (n[i] > 0)

    sm = src.data
    sm.calc_loop_triangles()
    s_part = sm.attributes["part"].data
    s_uv = sm.uv_layers["UVMap"].data
    groups = {}
    for t in sm.loop_triangles:
        key = (s_part[t.polygon_index].value, bucket(t.normal))
        g = groups.setdefault(key, ([], [], []))
        base = len(g[0])
        for li in t.loops:
            g[0].append(sm.vertices[sm.loops[li].vertex_index].co.copy())
            g[2].append(s_uv[li].uv.copy())
        g[1].append((base, base + 1, base + 2))
    trees = {k: (BVHTree.FromPolygons(v, f), v, uvs) for k, (v, f, uvs) in groups.items()}
    by_part = {}
    for (part, _b), tr in trees.items():
        by_part.setdefault(part, []).append(tr)

    # The far LOD is triangulated first, and each of ITS triangles takes, as a whole, the affine
    # unwrap of one LOD1 triangle - the one closest to its own center (a triangle's center is
    # always on the surface, never in a hole). Searching per vertex separately gave the corner
    # vertex of a big face the bevel's island, and the triangle got stretched in streaks across
    # half the atlas.
    bm = bmesh.new()
    bm.from_mesh(dst.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(dst.data)
    bm.free()
    dm = dst.data
    d_uv = (dm.uv_layers.get("UVMap") or dm.uv_layers.new(name="UVMap")).data
    d_part = dm.attributes["part"].data
    misses = 0
    for poly in dm.polygons:
        key = (d_part[poly.index].value, bucket(poly.normal))
        if key in trees:
            cands = [trees[key]]
        else:
            misses += 1
            cands = by_part.get(key[0], list(trees.values()))
        centre = poly.center
        best = None
        for tree, verts, uvs in cands:
            hit = tree.find_nearest(centre)
            if hit[0] is not None and (best is None or hit[3] < best[0][3]):
                best = (hit, verts, uvs)
        (_pt, _n, ti, _d), verts, uvs = best
        a, b_, c = verts[ti * 3], verts[ti * 3 + 1], verts[ti * 3 + 2]
        ua, ub, uc = (Vector((u.x, u.y, 0.0)) for u in (uvs[ti * 3], uvs[ti * 3 + 1], uvs[ti * 3 + 2]))
        for li in poly.loop_indices:
            co = dm.vertices[dm.loops[li].vertex_index].co
            w = barycentric_transform(co, a, b_, c, ua, ub, uc)
            d_uv[li].uv = (w.x, w.y)
    print("  UV %s <- %s: %d faces without a same-orientation match" % (dst.name, src.name, misses))


# =============================================================================
# Baking
# =============================================================================
def use_gpu():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("CUDA", "OPTIX"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(d.type == dev for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev
                bpy.context.scene.cycles.device = "GPU"
                return dev
        except TypeError:
            continue
    return "CPU"


def pixels(img):
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)[..., :3]


def bake_maps(lod1, high, size, bake_dir, cage=0.0025, ray=0.006, passes_only=None):
    os.makedirs(bake_dir, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    print("bake device:", use_gpu())

    tgt = lod1.copy()
    tgt.data = lod1.data.copy()
    tgt.name = "_BakeTarget"
    lod1.users_collection[0].objects.link(tgt)
    bm = bmesh.new()
    bm.from_mesh(tgt.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != G_ATLAS], context="FACES")
    bm.to_mesh(tgt.data)
    bm.free()
    tgt.data.materials.clear()
    mat = bpy.data.materials.new("M_BakeTarget")
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    mat.node_tree.nodes.active = node
    tgt.data.materials.append(mat)

    mats = {s.material for o in high for s in o.material_slots if s.material}

    def principled(m):
        return next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)

    def emission_mat(name, value):
        """Material made of a single emission: the metal and coverage passes don't depend on
        wear, whereas the full material with Bevel/AO nodes casts its own rays on every sample
        (metal took 6.5 min)."""
        em = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        if hasattr(em, "use_nodes"):
            em.use_nodes = True
        nt = em.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = (value, value, value, 1.0)
        e.inputs["Strength"].default_value = 1.0
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(e.outputs["Emission"], o.inputs["Surface"])
        return em

    def swap(mapping):
        saved = {o.name: [s.material for s in o.material_slots] for o in high}
        for o in high:
            for s in o.material_slots:
                s.material = mapping(s.material)
        return saved

    def restore(saved):
        for o in high:
            for s, mt in zip(o.material_slots, saved[o.name]):
                s.material = mt

    def select_for_bake():
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in high:
            o.select_set(True)
        tgt.select_set(True)
        bpy.context.view_layer.objects.active = tgt

    sc.world.light_settings.distance = 0.012
    # AO doesn't need materials, and worn materials' own Bevel and AO nodes cast rays on every
    # sample: with them the AO pass at 4096 took more than ten minutes. For the duration of the
    # pass - a plain diffuse material.
    plain = bpy.data.materials.get("_BakePlain") or bpy.data.materials.new("_BakePlain")
    metal_of = {m.name: emission_mat("_BakeMetal_" + m.name, principled(m).inputs["Metallic"].default_value
                                     if principled(m) else 0.0) for m in mats}
    white = emission_mat("_BakeCover", 1.0)
    passes = [("normal", "NORMAL", set(), 8, True), ("ao", "AO", set(), 96, True),
              ("albedo", "DIFFUSE", {"COLOR"}, 16, False), ("rough", "ROUGHNESS", set(), 8, True),
              ("metal", "EMIT", set(), 1, True), ("cover", "EMIT", set(), 1, True)]
    out = {}
    for name, typ, filt, spp, noncolor in passes:
        path = os.path.join(bake_dir, name + ".npy")
        if passes_only is not None and name not in passes_only and os.path.exists(path):
            out[name] = np.load(path)
            continue
        img = bpy.data.images.new("bake_" + name, size, size, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color" if noncolor else "Linear Rec.709"
        node.image = img
        sc.cycles.samples = spp
        select_for_bake()
        kw = dict(type=typ, use_selected_to_active=True, cage_extrusion=cage, max_ray_distance=ray,
                  margin=24, margin_type="EXTEND", use_clear=True, target="IMAGE_TEXTURES")
        if filt:
            kw["pass_filter"] = filt
        if typ == "NORMAL":
            kw.update(normal_space="TANGENT", normal_r="POS_X", normal_g="NEG_Y", normal_b="POS_Z")  # DirectX
        saved, metallic = None, {}
        if name == "ao":
            saved = swap(lambda m: plain)
        elif name == "metal":
            saved = swap(lambda m: metal_of[m.name])
        elif name == "cover":
            saved = swap(lambda m: white)
        elif name == "albedo":
            # Metal has no diffuse part in Cycles: a chrome plate baked out black. The metal's
            # color is needed in _co as-is - _smdi gives it the shine - so metallic is removed
            # for the duration of the pass.
            for m in mats:
                b = principled(m)
                if b and b.inputs["Metallic"].default_value > 0:
                    metallic[m.name] = b.inputs["Metallic"].default_value
                    b.inputs["Metallic"].default_value = 0.0
        bpy.ops.object.bake(**kw)
        if saved:
            restore(saved)
        for mname, v in metallic.items():
            principled(bpy.data.materials[mname]).inputs["Metallic"].default_value = v
        out[name] = pixels(img)
        np.save(path, out[name])
        print("baked", name)
    bpy.data.objects.remove(tgt, do_unlink=True)
    return out


def pushpull(img, mask):
    """Fill invalid texels with the neighborhood average (a "push-pull" pyramid).

    Outside the islands and their 24-pixel padding a black void remains, and a far LOD, whose
    big face interpolates UV across the gap between islands, would show it as a black patch.
    The fill averages valid texels across pyramid levels and substitutes the average wherever
    there is no data of its own."""
    h, w = mask.shape
    levels = []
    c = img * mask[..., None]
    wt = mask.astype(np.float32)
    while min(c.shape[:2]) > 1:
        levels.append((c, wt))
        hh, ww = c.shape[:2]
        c = c.reshape(hh // 2, 2, ww // 2, 2, -1).sum(axis=(1, 3))
        wt = wt.reshape(hh // 2, 2, ww // 2, 2).sum(axis=(1, 3))
    col = c / np.maximum(wt, 1e-8)[..., None]
    for c_l, w_l in reversed(levels):
        up = np.repeat(np.repeat(col, 2, axis=0), 2, axis=1)
        col = np.where((w_l > 0)[..., None], c_l / np.maximum(w_l, 1e-8)[..., None], up)
    return np.where(mask[..., None], img, col)


def fill_empty(b):
    """Fill in everything the bake didn't reach (per the coverage map): normals - flat,
    everything else - the average of the neighbors."""
    if "cover" not in b:
        return b
    mask = b["cover"][..., 0] > 0.5
    out = dict(b)
    for k in ("ao", "albedo", "rough", "metal"):
        out[k] = pushpull(b[k], mask)
    flat = np.zeros_like(b["normal"])
    flat[..., 0], flat[..., 1], flat[..., 2] = 0.5, 0.5, 1.0
    out["normal"] = np.where(mask[..., None], b["normal"], flat)
    print("filled %.1f%% empty texels" % (100.0 * (1.0 - mask.mean())))
    return out


# =============================================================================
# Textures
# =============================================================================
def down2(a):
    h, w = a.shape[:2]
    return a.reshape(h // 2, 2, w // 2, 2, -1).mean(axis=(1, 3))


def to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def save_png(path, rgb):
    """RGB 0..1, rows bottom-to-top (Blender buffer) -> 8-bit PNG with no conversions."""
    h, w = rgb.shape[:2]
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=False)
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = np.clip(rgb, 0, 1)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def make_textures(b, out_dir, stem, ao_min=0.5, out_size=2048):
    os.makedirs(out_dir, exist_ok=True)
    alb, ao, rough, metal, nrm = (b[n] for n in ("albedo", "ao", "rough", "metal", "normal"))
    while alb.shape[0] > out_size:
        alb, ao, rough, metal, nrm = (down2(x) for x in (alb, ao, rough, metal, nrm))
    shade = ao_min + (1 - ao_min) * ao[..., :1]
    save_png(os.path.join(out_dir, stem + "_co.png"), to_srgb(alb * shade))
    # Normals - half the resolution of color (1024 for a 2048 atlas), like _smdi: no visible
    # difference on the radio in hand, and the map weighs four times less (3.3 -> 0.85 MB; the
    # owner's decision, 25.09). Vectors are renormalized after downscaling - averaging shortens them.
    n = down2(nrm) * 2 - 1
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    save_png(os.path.join(out_dir, stem + "_nohq.png"), n * 0.5 + 0.5)
    r, m = rough[..., 0], metal[..., 0]
    gloss = 1.0 - r
    smdi = np.zeros(r.shape + (3,), np.float32)
    smdi[..., 0] = 1.0
    smdi[..., 1] = np.clip(0.03 + 0.22 * gloss ** 2 + 0.60 * m, 0, 1)
    smdi[..., 2] = np.clip(0.15 + 0.60 * gloss + 0.1 * m, 0, 1)
    save_png(os.path.join(out_dir, stem + "_smdi.png"), down2(smdi))
    print("textures:", out_dir)


def to_paa(src_png, dst_paa):
    os.makedirs(os.path.dirname(dst_paa), exist_ok=True)
    r = subprocess.run([IMAGE_TO_PAA, src_png, dst_paa], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dst_paa):
        raise RuntimeError("ImageToPAA failed for %s: %s %s" % (src_png, r.stdout, r.stderr))
    print("paa:", dst_paa, os.path.getsize(dst_paa))


# =============================================================================
# rvmat and model.cfg
# =============================================================================
def _stage(i, tex):
    return ("class Stage%d\n{\n\ttexture = \"%s\";\n\tuvSource = \"tex\";\n\tclass uvTransform\n\t{\n"
            "\t\taside[] = {1.0,0.0,0.0};\n\t\tup[] = {0.0,1.0,0.0};\n\t\tdir[] = {0.0,0.0,0.0};\n"
            "\t\tpos[] = {0.0,0.0,0.0};\n\t};\n};\n" % (i, tex))


def write_rvmat(path, nohq, smdi, mc="#(argb,8,8,3)color(0,0,0,0,MC)", specular=0.75, power=100.0,
                fresnel="#(ai,64,64,1)fresnel(1,1.05)", ambient=0.75):
    """Super, like the vanilla walkietalkie.rvmat (ambient/diffuse 0.75, specular 0.745/100). No //-comments:
    the Bohemia parser rejects them (skill: models.md)."""
    s = ("ambient[] = {%.2f,%.2f,%.2f,1.0};\ndiffuse[] = {%.2f,%.2f,%.2f,1.0};\nforcedDiffuse[] = {0.0,0.0,0.0,0.0};\n"
         "emmisive[] = {0.0,0.0,0.0,1.0};\nspecular[] = {%.3f,%.3f,%.3f,1.0};\nspecularPower = %.1f;\n"
         "PixelShaderID = \"Super\";\nVertexShaderID = \"Super\";\n"
         % (ambient, ambient, ambient, ambient, ambient, ambient, specular, specular, specular, power))
    s += _stage(1, nohq) + _stage(2, "#(argb,8,8,3)color(0.5,0.5,0.5,1,DT)") + _stage(3, mc)
    s += _stage(4, "#(argb,8,8,3)color(1,1,1,1,AS)") + _stage(5, smdi)
    s += "class Stage6\n{\n\ttexture = \"%s\";\n\tuvSource = \"none\";\n};\n" % fresnel
    s += _stage(7, "dz\\data\\data\\env_land_co.paa")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\r\n") as fh:
        fh.write(s)
    print("rvmat:", path)


def write_model_cfg(path, classes):
    """classes: {p3d name: [sections]}. Class name = p3d file name without the extension."""
    s = ("// Model configuration: one CfgModels class per p3d (name = file name). A model with no\n"
         "// class of its own silently falls back to Default. sections[] lists the hidden\n"
         "// selections config.cpp may retexture - here the range label on the case.\n\n"
         "class CfgSkeletons\n{\n\tclass Default\n\t{\n\t\tisDiscrete = 1;\n\t\tskeletonInherit = \"\";\n"
         "\t\tskeletonBones[] = {};\n\t};\n};\n\nclass CfgModels\n{\n\tclass Default\n\t{\n"
         "\t\tsectionsInherit = \"\";\n\t\tsections[] = {};\n\t\tskeletonName = \"\";\n\t};\n")
    for name, secs in classes.items():
        s += "\tclass %s: Default\n\t{\n\t\tsections[] = {%s};\n\t};\n" % (name, ",".join('"%s"' % x for x in secs))
    s += "};\n"
    with open(path, "w", newline="\r\n") as fh:
        fh.write(s)


# =============================================================================
# p3d
# =============================================================================
def conv(v):
    """Blender -> DayZ: (x, z, y). Face -Y -> -Z, like the vanilla radio."""
    return (v[0], v[2], v[1])


def conv_dir(v):
    return (v[0], v[2], v[1])


def visual_lod(ob, resolution, tex, label=None):
    """tex: {slot: (texture, rvmat)}; label: dict(origin, u, v) - frame of the strap's flat unwrap."""
    me = ob.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    uv = me.uv_layers["UVMap"].data
    pts = [conv(v.co) + (0,) for v in me.vertices]
    normals, faces, label_faces = [], [], []
    for poly in me.polygons:
        verts = []
        slot = poly.material_index
        for li in poly.loop_indices:
            normals.append(conv_dir(me.corner_normals[li].vector))
            u, v = uv[li].uv
            if slot == G_LABEL and label:
                co = me.vertices[me.loops[li].vertex_index].co - Vector(label["origin"])
                lu, lv = Vector(label["u"]), Vector(label["v"])
                u, v = co.dot(lu) / lu.length_squared, co.dot(lv) / lv.length_squared
            verts.append((me.loops[li].vertex_index, len(normals) - 1, float(u), 1.0 - float(v)))
        t, rv = tex[slot]
        if slot == G_LABEL:
            label_faces.append(len(faces))
        faces.append(p3d.Face(verts, 0, t, rv))
    sharp = [i for e in me.edges if e.use_edge_sharp for i in e.vertices]
    taggs = [("#SharpEdges#", struct.pack("<%dI" % len(sharp), *sharp))] if sharp else []
    if label_faces:
        b = bytearray(len(pts) + len(faces))
        for fi in label_faces:
            b[len(pts) + fi] = 1
            for (pi, _n, _u, _v) in faces[fi].verts:
                b[pi] = 1
        taggs.append(("label", bytes(b)))
    taggs.append(p3d.property_tagg("lodnoshadow", "1"))
    bpy.data.meshes.remove(me)
    secs = len({(f.texture, f.material) for f in faces})
    print("  LOD %.0f: %d tris, %d points, %d sections" % (resolution, len(faces), len(pts), secs))
    return p3d.Lod(pts, normals, faces, taggs, resolution)


def hull(points):
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    r = bmesh.ops.convex_hull(bm, input=bm.verts[:])
    dead = {g for g in list(r.get("geom_interior", [])) + list(r.get("geom_unused", [])) if isinstance(g, bmesh.types.BMVert)}
    if dead:
        bmesh.ops.delete(bm, geom=list(dead), context="VERTS")
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.verts.index_update()
    bm.normal_update()
    pts = [tuple(v.co) for v in bm.verts]
    tris = [[v.index for v in f.verts] for f in bm.faces]
    vn = [tuple(v.normal) for v in bm.verts]
    bm.free()
    return pts, tris, vn


def geometry_lod(resolution, comps, mass=None, props=()):
    """comps: [(points in Blender space, penetration rvmat or "")] - one convex hull per component."""
    pts, normals, faces, spans = [], [], [], []
    for comp_pts, mat in comps:
        hp, tris, vn = hull(comp_pts)
        p0, f0 = len(pts), len(faces)
        pts += [conv(p) + (0,) for p in hp]
        normals += [conv_dir(n) for n in vn]
        for t in tris:
            faces.append(p3d.Face([(p0 + i, p0 + i, 0.0, 0.0) for i in t], 0, "", mat))
        spans.append((p0, len(pts), f0, len(faces)))
    taggs = []
    for k, (p0, p1, f0, f1) in enumerate(spans):
        b = bytearray(len(pts) + len(faces))
        for i in range(p0, p1):
            b[i] = 1
        for i in range(f0, f1):
            b[len(pts) + i] = 1
        taggs.append(("Component%02d" % (k + 1), bytes(b)))
    if mass:
        taggs.append(p3d.mass_tagg(mass, len(pts)))
    for name, value in props:
        taggs.append(p3d.property_tagg(name, value))
    return p3d.Lod(pts, normals, faces, taggs, resolution)


def memory_lod(points):
    names = list(points)
    pts = [tuple(points[n]) + (0,) for n in names]
    taggs = []
    for i, n in enumerate(names):
        b = bytearray(len(pts))
        b[i] = 1
        taggs.append((n, bytes(b)))
    return p3d.Lod(pts, [], [], taggs, p3d.MEMORY)


def mesh_points(ob):
    return [tuple(v.co) for v in ob.data.vertices]


def prepare_model_root(name):
    """Model build root (build.project_root): its own folder with the MLOD and a copy of
    model.cfg, the mod data and vanilla dz - via junctions (skill: models.md, 'Building models
    with dayz-mcp asset_build')."""
    import _winapi
    import shutil
    src = os.path.join(MODEL_ROOT, MOD, "model", name)
    os.makedirs(src, exist_ok=True)
    for link, target in ((os.path.join(src, "data"), os.path.join(PBO_ROOT, name, "data")),
                         (os.path.join(MODEL_ROOT, "dz"), VANILLA_DZ)):
        if not os.path.exists(link):
            os.makedirs(target, exist_ok=True)
            _winapi.CreateJunction(target, link)
    shutil.copy2(os.path.join(PBO_ROOT, name, "model.cfg"), os.path.join(src, "model.cfg"))
    return src


# =============================================================================
# Run: one radio from parts to p3d
# =============================================================================
def set_planar_uv(ob, frame):
    """Flat 0..1 unwrap by the strap frame (origin, u, v) - for the detail model preview."""
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    o, u, v = Vector(frame["origin"]), Vector(frame["u"]), Vector(frame["v"])
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co - o
            uv.data[li].uv = (co.dot(u) / u.length_squared, co.dot(v) / v.length_squared)


def game_preview_material(stem, tex_dir):
    """Preview material for the in-game model, built from the finished _co/_nohq/_smdi (normals DirectX -> OpenGL)."""
    m, nt, b = node_mat("M_Preview_" + stem)
    N = nt.nodes
    co = N.new("ShaderNodeTexImage")
    co.image = bpy.data.images.load(os.path.join(tex_dir, stem + "_co.png"))
    nt.links.new(co.outputs["Color"], b.inputs["Base Color"])
    nh = N.new("ShaderNodeTexImage")
    nh.image = bpy.data.images.load(os.path.join(tex_dir, stem + "_nohq.png"))
    nh.image.colorspace_settings.name = "Non-Color"
    sep = N.new("ShaderNodeSeparateColor")
    nt.links.new(nh.outputs["Color"], sep.inputs["Color"])
    inv = _math(nt, "SUBTRACT", 1.0, sep.outputs["Green"])
    comb = N.new("ShaderNodeCombineColor")
    nt.links.new(sep.outputs["Red"], comb.inputs["Red"])
    nt.links.new(inv, comb.inputs["Green"])
    nt.links.new(sep.outputs["Blue"], comb.inputs["Blue"])
    nm = N.new("ShaderNodeNormalMap")
    nt.links.new(comb.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    sm = N.new("ShaderNodeTexImage")
    sm.image = bpy.data.images.load(os.path.join(tex_dir, stem + "_smdi.png"))
    sm.image.colorspace_settings.name = "Non-Color"
    sep2 = N.new("ShaderNodeSeparateColor")
    nt.links.new(sm.outputs["Color"], sep2.inputs["Color"])
    g = _math(nt, "DIVIDE", _math(nt, "SUBTRACT", sep2.outputs["Blue"], 0.15), 0.6)
    nt.links.new(_math(nt, "SUBTRACT", 1.0, g), b.inputs["Roughness"])
    return m


def run(spec):
    """spec: name, stem, build(m), materials() -> {name: material}, label (dict origin/u/v, classes,
    default), collision(lods) -> (geom comps, view comps, fire comps), mass, previews [(name, yaw, pitch,
    dist, target)], bake=dict(cage, ray, size), sharp_deg, body_top."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    skip_bake = "--skip-bake" in argv
    high_only = "--high-only" in argv
    no_prev = "--no-previews" in argv
    passes = set(argv[argv.index("--passes") + 1].split(",")) if "--passes" in argv else None

    name, stem = spec["name"], spec["stem"]
    asset = os.path.join(ASSETS, name)
    work = os.path.join(asset, "work")
    renders = os.path.join(work, "renders")
    tex_src = os.path.join(asset, "textures")
    game_tex = os.path.join(work, "game_textures")
    pbo_dir = os.path.join(PBO_ROOT, name)
    data = os.path.join(pbo_dir, "data")
    os.makedirs(renders, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    high_col = bpy.data.collections.new("High")
    sc.collection.children.link(high_col)
    mats = spec["materials"]()
    m0 = Model(0, mats, high_col)
    spec["build"](m0)
    lab = spec.get("label")
    if lab:
        for ob in m0.objects:
            if ob.get("label"):
                set_planar_uv(ob, lab)
    tris = 0
    for ob in m0.objects:
        ob.data.calc_loop_triangles()
        tris += len(ob.data.loop_triangles)
    print("HIGH: %d objects, %d tris" % (len(m0.objects), tris))

    cam = studio()
    if not no_prev and "--no-high-previews" not in argv:
        for pname, yaw, pitch, dist, target in spec["previews"]:
            render(os.path.join(renders, "high_%s.png" % pname), cam, yaw, pitch, dist, target, show=m0.objects)
    if high_only:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(work, name + "_high.blend"))
        return

    lod_col = bpy.data.collections.new("GameLODs")
    sc.collection.children.link(lod_col)
    lods = []
    for q in (1, 2, 3, 4):
        mq = Model(q)
        spec["build"](mq)
        lods.append(mq.lod.finish("LOD%d" % q, lod_col, spec.get("sharp_deg", 35.0)))
    unwrap(lods[0])
    for ob in lods[1:]:
        transfer_uv(ob, lods[0])

    bake_dir = os.path.join(work, "bake")
    high = [o for o in m0.objects if o.get("bake", True)]
    bk = spec.get("bake", {})
    size = bk.get("size", 4096)
    if skip_bake:
        b = {n: np.load(os.path.join(bake_dir, n + ".npy"))
             for n in ("normal", "ao", "albedo", "rough", "metal", "cover")
             if os.path.exists(os.path.join(bake_dir, n + ".npy"))}
    else:
        b = bake_maps(lods[0], high, size, bake_dir, bk.get("cage", 0.0025), bk.get("ray", 0.006), passes)
    b = fill_empty(b)
    make_textures(b, game_tex, stem, ao_min=bk.get("ao_min", 0.5), out_size=bk.get("out", 2048))
    for suf in ("co", "nohq", "smdi"):
        to_paa(os.path.join(game_tex, "%s_%s.png" % (stem, suf)), os.path.join(data, "%s_%s.paa" % (stem, suf)))
    rel = PREFIX + "\\" + name + "\\data\\"
    write_rvmat(os.path.join(data, stem + ".rvmat"), rel + stem + "_nohq.paa", rel + stem + "_smdi.paa")
    write_rvmat(os.path.join(data, stem + "_damage.rvmat"), rel + stem + "_nohq.paa", rel + stem + "_smdi.paa",
                mc="dz\\weapons\\data\\weapons_damage_generic_mc.paa")
    write_rvmat(os.path.join(data, stem + "_destruct.rvmat"), rel + stem + "_nohq.paa", rel + stem + "_smdi.paa",
                mc="dz\\weapons\\data\\weapons_destruct_generic_mc.paa")
    tex = {G_ATLAS: (rel + stem + "_co.paa", rel + stem + ".rvmat")}
    sections = []
    if lab:
        for cls in lab["classes"]:
            to_paa(os.path.join(tex_src, "label_%s.png" % cls), os.path.join(data, "%s_label_%s_co.paa" % (stem, cls)))
        write_rvmat(os.path.join(data, stem + "_label.rvmat"), "#(argb,8,8,3)color(0.5,0.5,1,1,NOHQ)",
                    "#(argb,8,8,3)color(1,0.05,0.25,1,SMDI)", specular=0.2, power=30.0)
        tex[G_LABEL] = (rel + "%s_label_%s_co.paa" % (stem, lab["default"]), rel + stem + "_label.rvmat")
        sections.append("label")
    write_model_cfg(os.path.join(pbo_dir, "model.cfg"), {stem: sections})

    p3d_lods = [visual_lod(ob, float(i + 1), tex, lab) for i, ob in enumerate(lods)]
    geom, view, fire = spec["collision"](lods)
    p3d_lods.append(geometry_lod(p3d.GEOMETRY, geom, mass=spec.get("mass", 0.25), props=(("autocenter", "0"),)))
    p3d_lods.append(geometry_lod(p3d.VIEW_GEOMETRY, view))
    p3d_lods.append(geometry_lod(p3d.FIRE_GEOMETRY, fire))
    (bx0, by0, bz0), (bx1, by1, bz1) = p3d_lods[0].bbox()
    cx, cy, cz = (bx0 + bx1) / 2, (by0 + by1) / 2, (bz0 + bz1) / 2
    r = 0.5 * math.sqrt((bx1 - bx0) ** 2 + (by1 - by0) ** 2 + (bz1 - bz0) ** 2)
    body_top = spec.get("body_top", by1)
    # invView - preview CAMERA (skill: models.md): front-left, like the vanilla radio, whose
    # overall envelope (it includes memory points) extends to x -0.11 and z -0.27 - camera
    # in front of the face (-Z)
    p3d_lods.append(memory_lod({
        "invView": (cx - 0.10, body_top * 0.55, bz0 - 0.26),
        "boundingbox_min": (bx0, by0, bz0),
        "boundingbox_max": (bx1, by1, bz1),
        "ce_center": (cx, cy, cz),
        "ce_radius": (cx + r, cy, cz),
        "throwingimpulseposition": (cx, body_top * 0.5, cz),
    }))
    # Grip shift: the hand grip and the strap slot are anchored to the model's origin, so the
    # only way to shift the radio in the hand is to shift the whole model relative to the origin
    # (+ toward the antenna). Only the p3d is shifted: the Blender scene stays as it is, otherwise
    # the frequency window images would go out of sync (render_hud_faces captures LOD1 from
    # _game.blend). The strap shifts together with the hand.
    shift = spec.get("grip_shift", 0.0)
    if shift:
        for lod in p3d_lods:
            lod.points = [(x, y + shift, z, fl) for x, y, z, fl in lod.points]
        print("grip_shift %.3f m applied to all LODs" % shift)
    src = prepare_model_root(name)
    path = os.path.join(src, stem + ".p3d")
    n = p3d.write(path, p3d_lods)
    print("WROTE %s (%d bytes, %d LODs), bbox x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f"
          % (path, n, len(p3d_lods), bx0, bx1, by0, by1, bz0, bz1))
    for l in p3d_lods:
        print("   %-18s pts=%5d faces=%5d" % (l.name, len(l.points), len(l.faces)))

    if not no_prev:
        pm = game_preview_material(stem, game_tex)
        lab_m = mat_image("M_PrevLabel", os.path.join(tex_src, "label_%s.png" % lab["default"])) if lab else pm
        for ob in lods:
            # slots are replaced in place: materials.clear() would reset the material indices on
            # the faces, and the strap in the preview would pick up the atlas (a black patch)
            ob.data.materials[G_ATLAS] = pm
            ob.data.materials[G_LABEL] = lab_m
            ob.data.materials[G_GLASS] = pm
            if lab:
                uvl = ob.data.uv_layers["UVMap"].data
                o, u, v = Vector(lab["origin"]), Vector(lab["u"]), Vector(lab["v"])
                for poly in ob.data.polygons:
                    if poly.material_index == G_LABEL:
                        for li in poly.loop_indices:
                            co = ob.data.vertices[ob.data.loops[li].vertex_index].co - o
                            uvl[li].uv = (co.dot(u) / u.length_squared, co.dot(v) / v.length_squared)
        for pname, yaw, pitch, dist, target in spec["previews"]:
            render(os.path.join(renders, "game_%s.png" % pname), cam, yaw, pitch, dist, target, show=[lods[0]])
        pname, yaw, pitch, dist, target = spec["previews"][0]
        for i, ob in enumerate(lods[1:], 2):
            render(os.path.join(renders, "game_lod%d.png" % i), cam, yaw, pitch, dist, target, show=[ob], samples=48,
                   res=600)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(work, name + "_game.blend"))
