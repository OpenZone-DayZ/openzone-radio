"""Lineup for the tutorial: the same six radios as in render_lineup.py, but on a transparent background.

    blender -b -P tools/render_tutorial_lineup.py -- [out_dir]

Writes into build/tutorial: lineup.png (RGBA, the shadow on the shadow catcher stays semi-transparent) and
lineup.json - where in the frame the bottom and top of each radio's body are, so that
tools/render_tutorial.py places the captions under them instead of them being picked by hand.
"""
import json
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "assets", "_kit"))
import radiokit as K  # noqa: E402

RADIOS = ["pmr_t388", "lxt", "uv5r", "uvs9", "xts", "prc152"]
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.join(ROOT, "build", "tutorial")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
x = 0.0
objs = []
for r in RADIOS:
    path = os.path.join(ROOT, "assets", r, "work", r + "_game.blend")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = ["LOD1"]
    ob = dst.objects[0]
    ob.name = "LOD1_" + r
    bpy.context.scene.collection.objects.link(ob)
    xs = [v.co.x for v in ob.data.vertices]
    w = max(xs) - min(xs)
    x += w / 2
    ob.location = (x, 0.0, 0.0)
    x += w / 2 + 0.035
    objs.append(ob)

cam = K.studio()
bpy.ops.mesh.primitive_plane_add(size=6.0, location=(x / 2, 0.0, 0.0))
bpy.context.active_object.is_shadow_catcher = True
sc = bpy.context.scene
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y = 2400, 1500
sc.cycles.samples = 128
mid = Vector(((x - 0.035) / 2, 0.0, 0.215))
K.aim(cam, yaw=-12, pitch=9, dist=1.9, target=mid)
cam.data.lens = 85
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.render.filepath = os.path.join(OUT, "lineup.png")
bpy.ops.render.render(write_still=True)

# Bottom of the body - the middle of the lower front edge, top - the top of the body on the same axis, without the antenna:
# on every radio the antenna sticks up higher and to the side, and the caption is not tied to it.
W, H = sc.render.resolution_x, sc.render.resolution_y
marks = {}
for r, ob in zip(RADIOS, objs):
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    x0, x1 = min(v.x for v in vs), max(v.x for v in vs)
    y0 = min(v.y for v in vs)
    cx = (x0 + x1) / 2
    near = [v for v in vs if abs(v.x - cx) < (x1 - x0) * 0.2]
    ztop = sorted(v.z for v in near)[int(len(near) * 0.9)]

    def px(p):
        c = world_to_camera_view(sc, cam, p)
        return [round(c.x * W, 1), round((1 - c.y) * H, 1)]

    marks[r] = {"bottom": px(Vector((cx, y0, 0.0))), "top": px(Vector((cx, y0, ztop))),
                "left": px(Vector((x0, y0, 0.0))), "right": px(Vector((x1, y0, 0.0)))}

with open(os.path.join(OUT, "lineup.json"), "w", encoding="utf-8") as f:
    json.dump({"size": [W, H], "radios": marks}, f, indent=1)
print("tutorial lineup:", OUT)
