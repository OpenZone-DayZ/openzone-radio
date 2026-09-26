"""Minimal reader/writer for MLOD .p3d files (the editable, non-binarised form).

Object Builder is the only GUI that speaks this format, and it is crash-prone,
so being able to inspect and generate LODs from a script keeps the model
pipeline scriptable and reviewable.

Layout, which read()/write() must agree on exactly:

    "MLOD", int version, int lod_count
    per LOD:
        "P3DM", int major, int minor
        int n_points, int n_normals, int n_faces, int flags
        n_points  * (float x, y, z, int flags)
        n_normals * (float x, y, z)
        n_faces   * (int n_verts,
                     4 * (int point_idx, int normal_idx, float u, float v),
                     int flags, asciiz texture, asciiz material)
        "TAGG", then repeating (byte active, asciiz name, int size, size bytes)
        until the "#EndOfFile#" tagg, then float resolution
"""
import struct

# Resolutions above the visual range identify a LOD's role. Values from the
# Bohemia wiki's LOD resolutions table -- do not guess these, a wrong value
# silently turns a Geometry LOD into something the engine ignores.
GEOMETRY = 1.0e13
BUOYANCY = 2.0e13
PHYSX_OLD = 3.0e13
PHYSX = 4.0e13
MEMORY = 1.0e15
LAND_CONTACT = 2.0e15
ROADWAY = 3.0e15
PATHS = 4.0e15
HITPOINTS = 5.0e15
VIEW_GEOMETRY = 6.0e15
FIRE_GEOMETRY = 7.0e15
VIEW_CARGO_GEOMETRY = 8.0e15
VIEW_CARGO_FIRE_GEOMETRY = 9.0e15

SPECIAL_NAMES = {
    GEOMETRY: "Geometry",
    BUOYANCY: "Buoyancy",
    PHYSX_OLD: "PhysX (old)",
    PHYSX: "PhysX",
    MEMORY: "Memory",
    LAND_CONTACT: "LandContact",
    ROADWAY: "Roadway",
    PATHS: "Paths",
    HITPOINTS: "HitPoints",
    VIEW_GEOMETRY: "View Geometry",
    FIRE_GEOMETRY: "Fire Geometry",
    VIEW_CARGO_GEOMETRY: "View Cargo Geometry",
    VIEW_CARGO_FIRE_GEOMETRY: "View Cargo Fire Geometry",
}


def lod_name(resolution):
    for value, name in SPECIAL_NAMES.items():
        if abs(resolution - value) < abs(value) * 1e-6:
            return name
    if resolution >= 1e13:
        return "Special/unknown (%.4g)" % resolution
    return "Resolution %.3f" % resolution


class Face:
    def __init__(self, verts, flags=0, texture="", material=""):
        # verts: list of (point_idx, normal_idx, u, v); 3 or 4 entries
        self.verts = verts
        self.flags = flags
        self.texture = texture
        self.material = material


class Lod:
    def __init__(self, points, normals, faces, taggs, resolution,
                 major=28, minor=256, flags=0):
        self.points = points        # [(x, y, z, flags)]
        self.normals = normals      # [(x, y, z)]
        self.faces = faces          # [Face]
        self.taggs = taggs          # [(name, bytes)] excluding #EndOfFile#
        self.resolution = resolution
        self.major = major
        self.minor = minor
        self.flags = flags

    @property
    def name(self):
        return lod_name(self.resolution)

    def bbox(self):
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        zs = [p[2] for p in self.points]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _read_asciiz(buf, off):
    end = buf.index(b"\0", off)
    return buf[off:end].decode("ascii", "replace"), end + 1


def _write_asciiz(out, text):
    out += text.encode("ascii")
    out += b"\0"
    return out


def read(path):
    with open(path, "rb") as fh:
        buf = fh.read()

    if buf[:4] != b"MLOD":
        raise ValueError("%s is not MLOD (got %r) -- binarised ODOL files "
                         "cannot be edited" % (path, buf[:4]))

    version, lod_count = struct.unpack_from("<ii", buf, 4)
    off = 12
    lods = []

    for i in range(lod_count):
        if buf[off:off + 4] != b"P3DM":
            raise ValueError("LOD %d: expected P3DM at 0x%x, got %r"
                             % (i, off, buf[off:off + 4]))
        major, minor, n_points, n_normals, n_faces, flags = \
            struct.unpack_from("<6i", buf, off + 4)
        off += 28

        points = []
        for _ in range(n_points):
            x, y, z, pf = struct.unpack_from("<3fi", buf, off)
            points.append((x, y, z, pf))
            off += 16

        normals = []
        for _ in range(n_normals):
            normals.append(struct.unpack_from("<3f", buf, off))
            off += 12

        faces = []
        for _ in range(n_faces):
            n_verts = struct.unpack_from("<i", buf, off)[0]
            off += 4
            verts = []
            for v in range(4):
                pi, ni, u, uv_v = struct.unpack_from("<2i2f", buf, off)
                off += 16
                if v < n_verts:
                    verts.append((pi, ni, u, uv_v))
            face_flags = struct.unpack_from("<i", buf, off)[0]
            off += 4
            texture, off = _read_asciiz(buf, off)
            material, off = _read_asciiz(buf, off)
            faces.append(Face(verts, face_flags, texture, material))

        if buf[off:off + 4] != b"TAGG":
            raise ValueError("LOD %d: expected TAGG at 0x%x, got %r"
                             % (i, off, buf[off:off + 4]))
        off += 4

        taggs = []
        while True:
            off += 1  # 'active' byte, always 1 in practice
            name, off = _read_asciiz(buf, off)
            size = struct.unpack_from("<i", buf, off)[0]
            off += 4
            data = buf[off:off + size]
            off += size
            if name == "#EndOfFile#":
                break
            taggs.append((name, data))

        resolution = struct.unpack_from("<f", buf, off)[0]
        off += 4
        lods.append(Lod(points, normals, faces, taggs, resolution,
                        major, minor, flags))

    if off != len(buf):
        raise ValueError("parsed to %d but file is %d bytes -- layout mismatch"
                         % (off, len(buf)))
    return version, lods


def write(path, lods, version=257):
    out = bytearray()
    out += b"MLOD"
    out += struct.pack("<ii", version, len(lods))

    for lod in lods:
        out += b"P3DM"
        out += struct.pack("<6i", lod.major, lod.minor, len(lod.points),
                           len(lod.normals), len(lod.faces), lod.flags)

        for x, y, z, pf in lod.points:
            out += struct.pack("<3fi", x, y, z, pf)
        for n in lod.normals:
            out += struct.pack("<3f", *n)

        for face in lod.faces:
            out += struct.pack("<i", len(face.verts))
            # The vertex table is always four entries wide; a triangle simply
            # leaves the fourth zeroed.
            for v in range(4):
                if v < len(face.verts):
                    out += struct.pack("<2i2f", *face.verts[v])
                else:
                    out += struct.pack("<2i2f", 0, 0, 0.0, 0.0)
            out += struct.pack("<i", face.flags)
            out = _write_asciiz(out, face.texture)
            out = _write_asciiz(out, face.material)

        out += b"TAGG"
        for name, data in lod.taggs:
            out += b"\x01"
            out = _write_asciiz(out, name)
            out += struct.pack("<i", len(data))
            out += data
        out += b"\x01"
        out = _write_asciiz(out, "#EndOfFile#")
        out += struct.pack("<i", 0)

        out += struct.pack("<f", lod.resolution)

    with open(path, "wb") as fh:
        fh.write(bytes(out))
    return len(out)


def property_tagg(name, value):
    """A '#Property#' tagg: two fixed 64-byte null-padded strings."""
    if len(name) >= 64 or len(value) >= 64:
        raise ValueError("property name/value must be under 64 bytes")
    data = name.encode("ascii").ljust(64, b"\0")
    data += value.encode("ascii").ljust(64, b"\0")
    return ("#Property#", data)


def mass_tagg(total_mass, n_points):
    """A '#Mass#' tagg: one float per point, summing to total_mass."""
    per_point = float(total_mass) / n_points
    return ("#Mass#", struct.pack("<%df" % n_points, *([per_point] * n_points)))


def selection_tagg(name, n_points, n_faces):
    """A named selection covering the whole LOD.

    Layout is one byte per point followed by one byte per face, 1 meaning
    'in the selection' -- verified against the '#Selected#' tagg Object Builder
    writes, whose length is exactly n_points + n_faces with every byte set to 1.

    Geometry LODs need their convex sub-shapes named Component01, Component02
    and so on. Without them the engine loads the LOD but logs
    "No components in <model>:geometry" and the object ends up with no
    collision -- a failure that neither binarising nor Object Builder reports.
    """
    return (name, b"\x01" * (n_points + n_faces))


def box_lod(minimum, maximum, resolution, taggs=None):
    """Build a closed convex box LOD spanning the given bounds.

    Geometry LODs want convex shapes; reusing the detailed visual mesh (with
    its protruding hooks) would give the physics engine a concave soup.
    """
    x0, y0, z0 = minimum
    x1, y1, z1 = maximum
    points = [
        (x0, y0, z0, 0), (x1, y0, z0, 0), (x1, y1, z0, 0), (x0, y1, z0, 0),
        (x0, y0, z1, 0), (x1, y0, z1, 0), (x1, y1, z1, 0), (x0, y1, z1, 0),
    ]
    normals = [
        (0.0, 0.0, -1.0), (0.0, 0.0, 1.0),
        (0.0, -1.0, 0.0), (0.0, 1.0, 0.0),
        (-1.0, 0.0, 0.0), (1.0, 0.0, 0.0),
    ]
    # Corner order per face is wound counter-clockwise seen from outside.
    quads = [
        ([0, 3, 2, 1], 0), ([4, 5, 6, 7], 1),
        ([0, 1, 5, 4], 2), ([3, 7, 6, 2], 3),
        ([0, 4, 7, 3], 4), ([1, 2, 6, 5], 5),
    ]
    faces = [Face([(pi, ni, 0.0, 0.0) for pi in corners])
             for corners, ni in quads]
    return Lod(points, normals, faces, list(taggs or []), resolution)
