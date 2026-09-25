"""Общий снимок: все шесть игровых моделей (LOD1 с запечёнными текстурами) в ряд.

    blender -b -P tools/render_lineup.py -- [out.jpg]

Берёт объект LOD1 и материалы превью из assets/<рация>/work/<рация>_game.blend (их пишет
radiokit.run), ставит рации по возрастанию дальности и рендерит в docs/screenshots.
"""
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "assets", "_kit"))
import radiokit as K  # noqa: E402

RADIOS = ["pmr_t388", "lxt", "uv5r", "uvs9", "xts", "prc152"]
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.join(ROOT, "docs", "screenshots", "lineup.jpg")

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

cam = K.studio(bg=(0.26, 0.27, 0.28))
# пол - ловец теней: без теней рации висят в пустоте, а видимый пол даёт кромку-горизонт
bpy.ops.mesh.primitive_plane_add(size=6.0, location=(x / 2, 0.0, 0.0))
bpy.context.active_object.is_shadow_catcher = True
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 2400, 1500
sc.cycles.samples = 128
# кадр ~0.8 м в ширину: ряд занимает его почти целиком, антенна PRC (0.45 м) влезает по высоте
mid = Vector(((x - 0.035) / 2, 0.0, 0.215))
K.aim(cam, yaw=-12, pitch=9, dist=1.9, target=mid)
cam.data.lens = 85
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 90
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("lineup:", OUT)
