"""The radio's face for the frequency window: a front orthographic render of the in-game model.

    blender -b -P tools/render_hud_faces.py -- [radio ...]

Takes LOD1 with baked textures from assets/<radio>/work/<radio>_game.blend, removes the range
tape (in the window it is drawn by a separate picture - its own per class) and renders the face into
the top-left corner of a transparent TEX_W x TEX_H canvas (powers of two - otherwise ImageToPAA
would refuse it). Scale and frame come from tools/hud_spec.py. Writes assets/<radio>/work/hud/face_raw.png;
next, tools/make_hud_layouts.py cleans the screen, converts it and builds the layout.
"""
import math
import os
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hud_spec as S  # noqa: E402

sys.path.insert(0, os.path.join(S.ROOT, "assets", "_kit"))
import radiokit as K  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
radios = argv or list(S.RADIOS)

for r in radios:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = os.path.join(S.ROOT, "assets", r, "work", r + "_game.blend")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = ["LOD1"]
    ob = dst.objects[0]
    bpy.context.scene.collection.objects.link(ob)

    # the range tape - the second section (radiokit.G_LABEL); in the window it is drawn by its own picture
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    tape = [f for f in bm.faces if f.material_index == K.G_LABEL]
    bmesh.ops.delete(bm, geom=tape, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()

    cam = K.studio(bg=(0.0, 0.0, 0.0))
    sc = bpy.context.scene
    sc.render.film_transparent = True
    sc.cycles.samples = 96
    sc.render.resolution_x, sc.render.resolution_y = S.TEX_W, S.TEX_H
    sc.render.resolution_percentage = 100

    x0, x1, z0, z1 = S.region(r)
    t = S.tex_ppmm(r)
    cw, ch = S.TEX_W / t / 1000.0, S.TEX_H / t / 1000.0      # canvas in meters
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(cw, ch)
    cam.location = (x0 + cw / 2, -1.0, z1 - ch / 2)           # the frame is pinned to the top-left corner
    cam.rotation_euler = (math.radians(90), 0.0, 0.0)
    cam.data.clip_end = 5.0

    out = os.path.join(S.ROOT, "assets", r, "work", "hud")
    os.makedirs(out, exist_ok=True)
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.filepath = os.path.join(out, "face_raw.png")
    bpy.ops.render.render(write_still=True)
    print("hud face:", r, "tex %.2f px/mm, deleted %d tape faces" % (t, len(tape)))
