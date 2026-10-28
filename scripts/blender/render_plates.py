"""Render Persian plates on a procedural car in Blender, with exact plate and character boxes.

Runs inside Blender; scripts/blender_synth.py writes the jobs file and starts it:
  blender -b --factory-startup -P scripts/blender/render_plates.py -- --jobs jobs.json --out renders/

Each job is one image: a car (random shape and paint) with the plate on its bumper, the 8 symbols as
extruded 3D text (embossed like real plates), a random camera, daylight or night lighting, and dirt.
Boxes come from projecting the plate corners and every glyph's mesh vertices through the camera,
so nothing is labelled by hand. Writes <out>/<id>.jpg and one JSON line per image to <out>/labels.jsonl.
All scene randomness comes from random.Random(job["seed"]): a job renders the same scene every time.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

PLATE_W = 0.52            # metres; the templates are 600x132 px
K = PLATE_W / 600         # metres per template pixel
PLATE_H = 132 * K
EMBOSS = 0.0008           # how far the symbols stand out of the plate
PLATE_CORNERS = [(-PLATE_W / 2, PLATE_H / 2, 0), (PLATE_W / 2, PLATE_H / 2, 0), (PLATE_W / 2, -PLATE_H / 2, 0), (-PLATE_W / 2, -PLATE_H / 2, 0)]  # TL TR BR BL


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--res", type=int, nargs=2, default=[1280, 960])
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--device", choices=["GPU", "CPU"], default="GPU")
    ap.add_argument("--engine", choices=["cycles", "eevee"], default="cycles")
    return ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


# ---------- helpers ----------

def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def material(name, color, rough=0.5, metal=0.0, coat=0.0, emit=0.0):
    m = bpy.data.materials.new(name)
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    p.inputs["Coat Weight"].default_value = coat
    if emit:
        p.inputs["Emission Color"].default_value = (*color, 1)
        p.inputs["Emission Strength"].default_value = emit
    return m


def mix_rgb(nt, fac, a, b):
    """Mix two colours (sockets or RGB tuples) by a float socket; returns the result socket."""
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    nt.links.new(fac, mx.inputs[0])
    for sock, v in ((mx.inputs[6], a), (mx.inputs[7], b)):
        if isinstance(v, tuple):
            sock.default_value = (*v, 1)
        else:
            nt.links.new(v, sock)
    return mx.outputs[2]


def noise(nt, scale, detail=6.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    return n.outputs["Fac"]


def grime(nt, base, amount, scale, color=(0.18, 0.15, 0.11)):
    """Darken a colour socket with blotchy dirt; amount 0 = clean."""
    ramp = nt.nodes.new("ShaderNodeMapRange")
    nt.links.new(noise(nt, scale), ramp.inputs["Value"])
    ramp.inputs["From Min"].default_value = 0.45
    ramp.inputs["From Max"].default_value = 0.75
    ramp.inputs["To Max"].default_value = amount
    return mix_rgb(nt, ramp.outputs["Result"], base, color)


def box(name, dims, loc, mat, bevel=0.0, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * dims[0], v.co.y * dims[1], v.co.z * dims[2]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    ob.location, ob.rotation_euler = loc, rot
    me.materials.append(mat)
    if bevel:
        m = ob.modifiers.new("bevel", "BEVEL")
        m.width, m.segments = bevel, 5
        me.shade_smooth()
    return ob


def cylinder(name, r, depth, loc, mat):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=r, radius2=r, depth=depth)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = link(bpy.data.objects.new(name, me))
    ob.location, ob.rotation_euler = loc, (0, math.pi / 2, 0)
    return ob


def world_verts(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    pts = [ob.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return pts


def clear_scene():
    d = bpy.data
    d.batch_remove([*d.objects, *d.meshes, *d.curves, *d.materials, *d.lights, *d.cameras, *d.worlds])


# ---------- scene parts ----------

def car(rng, front):
    """A simple car seen from behind (or the front). Returns where the plate centre goes."""
    w, length = rng.uniform(1.65, 1.95), rng.uniform(3.8, 4.8)
    hue = rng.choice([(0.8, 0.8, 0.8), (0.02, 0.02, 0.02), (0.35, 0.35, 0.37), (0.5, 0.02, 0.02),
                      (0.02, 0.06, 0.25), (0.6, 0.55, 0.45), (0.9, 0.9, 0.88), (0.05, 0.15, 0.05)])
    paint = material("paint", tuple(min(1, c * rng.uniform(0.85, 1.15)) for c in hue), rng.uniform(0.15, 0.45), rng.uniform(0.3, 0.9), coat=1)
    nt = paint.node_tree
    p = nt.nodes["Principled BSDF"]
    nt.links.new(grime(nt, p.inputs["Base Color"].default_value[:3], rng.uniform(0, 0.5), 8), p.inputs["Base Color"])
    glass = material("glass", (0.01, 0.01, 0.012), 0.05, 0.0, coat=1)
    plastic = material("plastic", (0.03, 0.03, 0.03), 0.6)
    rubber = material("rubber", (0.015, 0.015, 0.015), 0.9)
    lamp = material("lamp", (1, 0.95, 0.85) if front else (0.8, 0.02, 0.01), 0.2, emit=rng.choice([0, 0, 2, 8]))

    body_z0, body_h = 0.3, rng.uniform(0.6, 0.8)
    box("body", (w, length, body_h), (0, length / 2, body_z0 + body_h / 2), paint, bevel=0.12)
    cabin_h = rng.uniform(0.4, 0.55)
    box("cabin", (w * 0.86, length * 0.5, cabin_h), (0, length * 0.55, body_z0 + body_h + cabin_h / 2 - 0.02), glass, bevel=0.1)
    bump_h = rng.uniform(0.22, 0.32)
    bump_z = body_z0 + rng.uniform(0.1, 0.2)
    box("bumper", (w * 1.01, 0.3, bump_h), (0, 0.05, bump_z), rng.choice([plastic, paint]), bevel=0.06)
    for sx in (-1, 1):
        box("lamp", (0.38, 0.06, 0.14), (sx * (w / 2 - 0.25), 0.0, body_z0 + body_h * 0.7), lamp, bevel=0.02)
        for y in (0.75, length - 0.85):
            cylinder("wheel", 0.32, 0.22, (sx * (w / 2 - 0.08), y, 0.32), rubber)
    return Vector((0, -0.1 - 0.012, bump_z + rng.uniform(-0.03, 0.03)))  # on the bumper face


def plate(job, font, rng, mount):
    """Plate with the template printed on it and the 8 symbols as extruded text. Returns (plate, glyphs)."""
    me = bpy.data.meshes.new("plate")
    me.from_pydata([(-PLATE_W / 2, -PLATE_H / 2, 0), (PLATE_W / 2, -PLATE_H / 2, 0), (PLATE_W / 2, PLATE_H / 2, 0), (-PLATE_W / 2, PLATE_H / 2, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    ob = link(bpy.data.objects.new("plate", me))
    ob.location = mount
    ob.rotation_euler = (math.pi / 2 + math.radians(rng.uniform(-6, 6)), 0, math.radians(rng.uniform(-2, 2)))
    ob.modifiers.new("thickness", "SOLIDIFY").thickness = 0.001

    m = bpy.data.materials.new("plate")
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(job["template"], check_existing=True)
    tex.interpolation = "Cubic"
    nt.links.new(grime(nt, tex.outputs["Color"], rng.uniform(0, 0.55), rng.uniform(15, 40)), p.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], p.inputs["Alpha"])
    p.inputs["Roughness"].default_value = rng.uniform(0.25, 0.6)
    p.inputs["Coat Weight"].default_value = rng.uniform(0, 0.6)  # reflective film
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = rng.uniform(0.02, 0.15)
    nt.links.new(noise(nt, 60, 10), bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    me.materials.append(m)
    holder = box("holder", (PLATE_W + 0.03, PLATE_H + 0.03, 0.01), (0, 0, -0.0065), material("holder", (0.02, 0.02, 0.02), 0.5), bevel=0.004)
    holder.parent = ob  # tilts with the plate, so it never cuts into it

    ink = material("ink", tuple(job["ink"]), rng.uniform(0.25, 0.5))
    glyphs = []
    for i, (glyph, (x, w, base_y, h)) in enumerate(zip(job["glyphs"], job["slots"])):
        traced = isinstance(glyph, dict)  # {"shape", "digit", "height" vs a digit} from scripts/glyphs.py, else font text
        if traced:
            cu = shape_curve(f"g{i}", json.loads(Path(glyph["shape"]).read_text()), h * K * glyph["height"])
            digit = glyph["digit"]
        else:
            cu = bpy.data.curves.new(f"g{i}", "FONT")
            cu.body, cu.font, cu.align_x = glyph, font, "CENTER"
            cu.size = h * K / font["digit_h"]
            digit = glyph.isdigit()
        cu.extrude, cu.bevel_depth, cu.bevel_resolution = EMBOSS / 2, 0.00025, 2
        cu.materials.append(ink)
        g = link(bpy.data.objects.new(f"g{i}", cu))
        g.parent = ob
        g.location = (0, 0, EMBOSS / 2)
        bpy.context.view_layer.update()
        xs = [v.x for v in local_verts(g)]
        ys = [v.y for v in local_verts(g)]
        gw, gh = max(xs) - min(xs), max(ys) - min(ys)
        # traced glyphs keep their real width; the font is condensed like the plate typeface. Wide letters squeeze into the slot.
        sx = min(1.0 if traced else 0.95, w * K / gw)
        sy = 1.0 if digit or traced else min(1.0, 1.1 * h * K / gh)
        g.scale = (sx, sy, 1)
        jx, jy = rng.uniform(-3, 3) * K, rng.uniform(-3, 3) * K
        # font glyphs sit on the baseline; traced ones have no baseline, so they are centred on the digit band
        y = PLATE_H / 2 - base_y * K if not traced else PLATE_H / 2 - (base_y - h / 2) * K - (min(ys) + max(ys)) / 2 * sy
        g.location = ((x + w / 2) * K - PLATE_W / 2 - (min(xs) + max(xs)) / 2 * sx + jx, y + jy, EMBOSS / 2)
        glyphs.append(g)
    return ob, glyphs


def shape_curve(name, polys, size):
    """Filled 2D curve from traced polygons (ink box height 1, y up); Blender fills it even-odd, so holes stay open."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions, cu.fill_mode = "2D", "BOTH"
    for poly in polys:
        sp = cu.splines.new("POLY")
        sp.points.add(len(poly) - 1)
        for pt, (x, y) in zip(sp.points, poly):
            pt.co = (x * size, y * size, 0, 1)
        sp.use_cyclic_u = True
    return cu


def local_verts(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    pts = [v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return pts


def surroundings(rng):
    asphalt = bpy.data.materials.new("asphalt")
    nt = asphalt.node_tree
    p = nt.nodes["Principled BSDF"]
    g = rng.uniform(0.04, 0.2)
    nt.links.new(mix_rgb(nt, noise(nt, 300, 8), (g, g, g), (g * 1.6, g * 1.6, g * 1.6)), p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rng.choice([0.85, 0.85, 0.3])  # sometimes wet
    box("ground", (80, 80, 0.02), (0, 20, -0.01), asphalt)
    for i in range(rng.randint(4, 12)):  # walls, buildings and parked boxes behind and beside the car
        c = rng.uniform(0.1, 0.8)
        col = (c * rng.uniform(0.8, 1.2), c, c * rng.uniform(0.8, 1.2))
        if rng.random() < 0.5:  # beside the car
            x, y = rng.choice([-1, 1]) * rng.uniform(2.5, 12), rng.uniform(-4, 30)
        else:                   # behind it
            x, y = rng.uniform(-15, 15), rng.uniform(7, 35)
        dims = (rng.uniform(1, 8), rng.uniform(1, 8), rng.uniform(1, 10))
        box(f"clutter{i}", dims, (x, y, dims[2] / 2), material(f"c{i}", tuple(min(1, v) for v in col), rng.uniform(0.3, 0.9)))


def lighting(rng):
    """Daylight (sky for ambient light plus a sun lamp for shadows), or night. Returns True at night."""
    world = bpy.data.worlds.new("world")
    bpy.context.scene.world = world
    nt = world.node_tree
    bg = nt.nodes["Background"]
    if rng.random() < 0.25:
        bg.inputs["Color"].default_value = (0.01, 0.012, 0.02, 1)
        bg.inputs["Strength"].default_value = rng.uniform(0.2, 1.0)
        return True
    elevation, rotation = math.radians(rng.uniform(8, 75)), math.radians(rng.uniform(0, 360))
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation, sky.sun_rotation, sky.sun_disc = elevation, rotation, False
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = rng.uniform(0.15, 0.5)
    if rng.random() < 0.75:  # otherwise overcast: sky light only
        sun = bpy.data.lights.new("sun", "SUN")
        sun.energy, sun.angle = rng.uniform(1.5, 5), math.radians(rng.uniform(0.5, 4))
        ob = link(bpy.data.objects.new("sun", sun))
        ob.rotation_euler = (math.pi / 2 - elevation, 0, rotation)
    return False


def night_lamps(rng, cam, mount):
    lamp = bpy.data.lights.new("headlight", "SPOT")
    lamp.energy, lamp.spot_size = rng.uniform(200, 1500), math.radians(50)
    ob = link(bpy.data.objects.new("headlight", lamp))
    ob.location = cam.location + Vector((rng.uniform(-0.6, 0.6), 0, rng.uniform(-0.6, 0)))
    ob.rotation_euler = (mount - ob.location).to_track_quat("-Z", "Y").to_euler()
    if rng.random() < 0.7:
        pl = bpy.data.lights.new("plate_lamp", "AREA")
        pl.energy, pl.size = rng.uniform(1, 6), 0.1
        ob = link(bpy.data.objects.new("plate_lamp", pl))
        ob.location = mount + Vector((0, -0.05, PLATE_H / 2 + 0.03))
        ob.rotation_euler = (math.radians(200), 0, 0)


def camera(rng, mount, res):
    """Random gate / street camera aimed near the plate; the plate must stay fully in frame."""
    cam = link(bpy.data.objects.new("cam", bpy.data.cameras.new("cam")))
    bpy.context.scene.camera = cam
    d = rng.uniform(1.8, 10)
    yaw, pitch = math.radians(rng.uniform(-40, 40)), math.radians(rng.uniform(0, 35))
    cam.location = mount + Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch))) * d
    cam.location.z = max(cam.location.z, 0.4)
    frac = rng.uniform(0.07, 0.5)                    # plate width as a fraction of the image width
    cam.data.sensor_width = 36
    cam.data.lens = max(12, frac * d * 36 / PLATE_W)
    aim = mount + Vector((rng.uniform(-1, 1), 0, rng.uniform(-0.6, 0.6))) * frac * d * 0.6
    cam.rotation_euler = (aim - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.rotation_euler.rotate_axis("Z", math.radians(rng.uniform(-5, 5)))
    if rng.random() < 0.3:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = d * rng.uniform(0.85, 1.15)
        cam.data.dof.aperture_fstop = rng.uniform(1.4, 5.6)
    return cam


def occluders(cam, pts):
    """Objects hit on the way from the camera to each point (stopping 2 cm short of it)."""
    dg = bpy.context.evaluated_depsgraph_get()
    hits = set()
    for p in pts:
        d = p - cam.location
        hit, _, _, _, ob, _ = bpy.context.scene.ray_cast(dg, cam.location, d.normalized(), distance=d.length - 0.02)
        if hit:
            hits.add(ob.original)
    return hits


def project(cam, pts, res):
    scene = bpy.context.scene
    out = []
    for p in pts:
        c = world_to_camera_view(scene, cam, p)
        out.append((c.x * res[0], (1 - c.y) * res[1], c.z))
    return out


def bbox(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]


# ---------- main ----------

def setup_render(a):
    scene = bpy.context.scene
    if a.engine == "eevee":  # rasterised: several times faster, softer shadows and reflections
        scene.render.engine = "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = a.samples
    else:
        scene.render.engine = "CYCLES"
    scene.cycles.samples = a.samples
    scene.cycles.use_denoising = True
    if a.device == "GPU" and a.engine == "cycles":
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = True
                scene.cycles.device = "GPU"
                break
    scene.render.resolution_x, scene.render.resolution_y = a.res
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 95
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0


def load_font(path):
    """Load the font once and measure the tallest digit at size 1, the unit every glyph is scaled from."""
    font = bpy.data.fonts.load(path, check_existing=True)
    hs = []
    for d in "۰۱۲۳۴۵۶۷۸۹":
        cu = bpy.data.curves.new("m", "FONT")
        cu.body, cu.font = d, font
        ob = link(bpy.data.objects.new("m", cu))
        bpy.context.view_layer.update()
        ys = [v.y for v in local_verts(ob)]
        hs.append(max(ys) - min(ys))
        bpy.data.objects.remove(ob)
        bpy.data.curves.remove(cu)
    font["digit_h"] = max(hs)
    return font


def main():
    a = args()
    jobs = json.loads(Path(a.jobs).read_text(encoding="utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)["id"] for line in (out / "labels.jsonl").open(encoding="utf-8")} if (out / "labels.jsonl").exists() else set()
    clear_scene()
    setup_render(a)
    fonts = {}
    for job in jobs:
        if job["id"] in done:  # resume an interrupted run
            continue
        rng = random.Random(job["seed"])
        clear_scene()
        if job["font"] not in fonts:
            fonts[job["font"]] = load_font(job["font"])
        front = rng.random() < 0.4
        mount = car(rng, front)
        pl, glyphs = plate(job, fonts[job["font"]], rng, mount)
        surroundings(rng)
        night = lighting(rng)
        res = a.res
        for _ in range(30):  # re-roll the camera until the whole plate is in frame and faces it
            for ob in [o for o in bpy.data.objects if o.type == "CAMERA"]:
                bpy.data.objects.remove(ob)
            cam = camera(rng, mount, res)
            bpy.context.view_layer.update()
            corners = project(cam, [pl.matrix_world @ Vector(c) for c in PLATE_CORNERS], res)
            if not all(2 < x < res[0] - 2 and 2 < y < res[1] - 2 and z > 0 for x, y, z in corners):
                continue
            blockers = occluders(cam, [pl.matrix_world @ Vector(c) for c in [(0, 0, 0), *PLATE_CORNERS]])
            walls = [b for b in blockers if b.name.startswith("clutter")]
            if len(walls) < len(blockers):  # the car itself hides the plate: new camera
                continue
            for ob in walls:
                bpy.data.objects.remove(ob)  # a wall in the way just goes
            break
        else:
            print(f"skip {job['id']}: no camera kept the plate in frame")
            continue
        if night:
            night_lamps(rng, cam, mount)
        bpy.context.view_layer.update()
        chars = [bbox(project(cam, world_verts(g), res)) for g in glyphs]
        name = f"{job['id']:06d}.jpg"
        bpy.context.scene.render.filepath = str(out / name)
        bpy.ops.render.render(write_still=True)
        row = {"id": job["id"], "image": name, "key": job["key"], "plate_type": job["plate_type"], "template": Path(job["template"]).stem,
               "w": res[0], "h": res[1], "plate": bbox(corners), "corners": [[round(x, 2), round(y, 2)] for x, y, _ in corners],
               "chars": chars, "classes": job["classes"], "night": night, "front": front}
        with open(out / "labels.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"rendered {name} {job['key']}")


main()
