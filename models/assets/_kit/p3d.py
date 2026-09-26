"""MLOD writer for the radio pipeline: the P3D source format Object Builder edits and
binarize turns into the ODOL the game loads.

Written 2026-09-26 to replace a module the contributor kept in a private copy of the
dayz-modding skill (scripts/p3d.py) and never handed over; radiokit.py is the only user,
and this file offers exactly what it calls plus a reader for round-trip checks.

The layout (community wiki, "P3D File Format - MLOD"; every number little-endian):

    "MLOD"  u32 version=257  u32 lod_count
    per LOD:
        "P3DM"  u32 major=28  u32 minor=256
        u32 n_points  u32 n_normals  u32 n_faces  u32 flags=0
        points:  n_points  x (f32 x, f32 y, f32 z, u32 point_flags)
        normals: n_normals x (f32 x, f32 y, f32 z)
        faces:   n_faces   x (u32 n_verts, 4 x (u32 point, u32 normal, f32 u, f32 v),
                              u32 face_flags, asciiz texture, asciiz material)
        "TAGG"
        taggs:   (u8 active=1, asciiz name, u32 size, bytes data) ...
                 the last one is "#EndOfFile#" with size 0
        f32 resolution

Model space is the engine's (x right, y up, z forward); the caller converts from Blender.
Named selections are taggs whose name is the selection and whose data is one byte per
point followed by one byte per face, 1 = selected. Two taggs have a fixed shape and get
helpers here: "#Property#" (two 64-byte fields, name and value) and "#Mass#" (one f32 per
point of the geometry LOD). "#SharpEdges#" is pairs of u32 point indices, packed by the
caller.
"""
import struct

MLOD_VERSION = 257
P3DM_MAJOR = 28
P3DM_MINOR = 256

# Special LOD resolutions, as Object Builder names them. A resolution below 10000 is a
# visual LOD ("1.000", "2.000", ...); 10000..10999 are shadow volumes.
GEOMETRY = 1.0e13
LANDCONTACT = 2.0e13
ROADWAY = 3.0e13
PATHS = 4.0e13
HITPOINTS = 5.0e13
MEMORY = 1.0e15
VIEW_GEOMETRY = 6.0e15
FIRE_GEOMETRY = 7.0e15
VIEW_CARGO_GEOMETRY = 8.0e15
VIEW_CARGO_FIRE_GEOMETRY = 9.0e15
VIEW_COMMANDER = 1.0e16
VIEW_PILOT = 1.1e16
VIEW_GUNNER = 1.2e16

_SPECIAL = {
    GEOMETRY: "Geometry",
    LANDCONTACT: "LandContact",
    ROADWAY: "Roadway",
    PATHS: "Paths",
    HITPOINTS: "Hit-points",
    MEMORY: "Memory",
    VIEW_GEOMETRY: "View Geometry",
    FIRE_GEOMETRY: "Fire Geometry",
    VIEW_CARGO_GEOMETRY: "View - Cargo Geometry",
    VIEW_CARGO_FIRE_GEOMETRY: "View - Cargo Fire Geometry",
    VIEW_COMMANDER: "View - Commander",
    VIEW_PILOT: "View - Pilot",
    VIEW_GUNNER: "View - Gunner",
}

PROPERTY_FIELD = 64


def lod_name(resolution):
    """What Object Builder would call a LOD of this resolution."""
    r = float(resolution)
    for value, name in _SPECIAL.items():
        if r == value:
            return name
    if 10000.0 <= r < 11000.0:
        return "ShadowVolume %d" % int(r - 10000.0)
    return "%.3f" % r


class Face(object):
    """One face: 3 or 4 vertices of (point index, normal index, u, v), flags, and the
    texture and material paths as the engine will look them up (prefix included)."""

    __slots__ = ("verts", "flags", "texture", "material")

    def __init__(self, verts, flags=0, texture="", material=""):
        verts = [tuple(v) for v in verts]
        if not 3 <= len(verts) <= 4:
            raise ValueError("a face has 3 or 4 vertices, not %d" % len(verts))
        for v in verts:
            if len(v) != 4:
                raise ValueError("a vertex is (point, normal, u, v), got %r" % (v,))
        self.verts = verts
        self.flags = int(flags)
        self.texture = texture or ""
        self.material = material or ""

    def pack(self):
        out = [struct.pack("<I", len(self.verts))]
        for i in range(4):
            if i < len(self.verts):
                p, n, u, v = self.verts[i]
                out.append(struct.pack("<IIff", int(p), int(n), float(u), float(v)))
            else:
                out.append(struct.pack("<IIff", 0, 0, 0.0, 0.0))
        out.append(struct.pack("<I", self.flags))
        out.append(_asciiz(self.texture))
        out.append(_asciiz(self.material))
        return b"".join(out)


class Lod(object):
    """One LOD. `points` are (x, y, z) or (x, y, z, flags); `normals` are (x, y, z);
    `taggs` are (name, data) pairs, written in order, before "#EndOfFile#"."""

    def __init__(self, points, normals, faces, taggs, resolution):
        self.points = [_point(p) for p in points]
        self.normals = [(float(n[0]), float(n[1]), float(n[2])) for n in normals]
        self.faces = list(faces)
        self.taggs = [(str(name), bytes(data)) for name, data in taggs]
        self.resolution = float(resolution)

    @property
    def name(self):
        return lod_name(self.resolution)

    def bbox(self):
        """((x0, y0, z0), (x1, y1, z1)) over the points; zeros for an empty LOD."""
        if not self.points:
            return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        zs = [p[2] for p in self.points]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def check(self):
        """Every index a face uses must exist, or Object Builder shows garbage and binarize
        may crash rather than complain."""
        np_, nn = len(self.points), len(self.normals)
        for fi, f in enumerate(self.faces):
            for p, n, _u, _v in f.verts:
                if not 0 <= p < np_:
                    raise ValueError("LOD %s face %d: point %d of %d" % (self.name, fi, p, np_))
                if not 0 <= n < nn:
                    raise ValueError("LOD %s face %d: normal %d of %d" % (self.name, fi, n, nn))
        for name, data in self.taggs:
            if name == "#Mass#" and len(data) != 4 * np_:
                raise ValueError("LOD %s: #Mass# has %d bytes for %d points" % (self.name, len(data), np_))
            if name == "#Property#" and len(data) != 2 * PROPERTY_FIELD:
                raise ValueError("LOD %s: #Property# has %d bytes, not %d" % (self.name, len(data), 2 * PROPERTY_FIELD))

    def pack(self):
        self.check()
        out = [b"P3DM", struct.pack("<IIIIII", P3DM_MAJOR, P3DM_MINOR,
                                      len(self.points), len(self.normals), len(self.faces), 0)]
        for x, y, z, fl in self.points:
            out.append(struct.pack("<fffI", x, y, z, fl))
        for x, y, z in self.normals:
            out.append(struct.pack("<fff", x, y, z))
        for f in self.faces:
            out.append(f.pack())
        out.append(b"TAGG")
        for name, data in self.taggs:
            out.append(b"\x01" + _asciiz(name) + struct.pack("<I", len(data)) + data)
        out.append(b"\x01" + _asciiz("#EndOfFile#") + struct.pack("<I", 0))
        out.append(struct.pack("<f", self.resolution))
        return b"".join(out)


def property_tagg(name, value):
    """A "#Property#" tagg: `name` and `value` in 64-byte zero-padded fields."""
    return ("#Property#", _fixed(name) + _fixed(str(value)))


def mass_tagg(mass, n_points):
    """A "#Mass#" tagg spreading `mass` (kg) evenly over the LOD's points; binarize sums
    the per-point values back into the model's mass."""
    n = int(n_points)
    if n <= 0:
        raise ValueError("#Mass# needs at least one point")
    each = float(mass) / n
    return ("#Mass#", struct.pack("<%df" % n, *([each] * n)))


def selection_tagg(name, n_points, n_faces, points=(), faces=()):
    """A named selection over the given point and face indices."""
    data = bytearray(n_points + n_faces)
    for i in points:
        data[i] = 1
    for i in faces:
        data[n_points + i] = 1
    return (name, bytes(data))


def sharp_edges_tagg(pairs):
    """A "#SharpEdges#" tagg from (point, point) pairs."""
    flat = [int(i) for pair in pairs for i in pair]
    return ("#SharpEdges#", struct.pack("<%dI" % len(flat), *flat))


def pack(lods):
    lods = list(lods)
    out = [b"MLOD", struct.pack("<II", MLOD_VERSION, len(lods))]
    for lod in lods:
        out.append(lod.pack())
    return b"".join(out)


def write(path, lods):
    """Write the MLOD; returns the number of bytes written."""
    data = pack(lods)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def read(path):
    """Read an MLOD back into Lod objects -- the round-trip check for write(), and enough
    of a reader to inspect what an export contains."""
    with open(path, "rb") as f:
        data = f.read()
    return unpack(data)


def unpack(data):
    if data[:4] != b"MLOD":
        raise ValueError("not an MLOD: starts with %r" % data[:4])
    version, count = struct.unpack_from("<II", data, 4)
    if version != MLOD_VERSION:
        raise ValueError("MLOD version %d, expected %d" % (version, MLOD_VERSION))
    pos = 12
    lods = []
    for _ in range(count):
        if data[pos:pos + 4] != b"P3DM":
            raise ValueError("LOD at %d does not start with P3DM" % pos)
        major, minor, n_points, n_normals, n_faces, _flags = struct.unpack_from("<IIIIII", data, pos + 4)
        if (major, minor) != (P3DM_MAJOR, P3DM_MINOR):
            raise ValueError("P3DM version %d.%d, expected %d.%d" % (major, minor, P3DM_MAJOR, P3DM_MINOR))
        pos += 28
        points = []
        for _ in range(n_points):
            points.append(struct.unpack_from("<fffI", data, pos))
            pos += 16
        normals = []
        for _ in range(n_normals):
            normals.append(struct.unpack_from("<fff", data, pos))
            pos += 12
        faces = []
        for _ in range(n_faces):
            (n_verts,) = struct.unpack_from("<I", data, pos)
            pos += 4
            verts = []
            for i in range(4):
                v = struct.unpack_from("<IIff", data, pos)
                pos += 16
                if i < n_verts:
                    verts.append(v)
            (flags,) = struct.unpack_from("<I", data, pos)
            pos += 4
            texture, pos = _read_asciiz(data, pos)
            material, pos = _read_asciiz(data, pos)
            faces.append(Face(verts, flags, texture, material))
        if data[pos:pos + 4] != b"TAGG":
            raise ValueError("LOD %d: TAGG expected at %d" % (len(lods), pos))
        pos += 4
        taggs = []
        while True:
            pos += 1  # active
            name, pos = _read_asciiz(data, pos)
            (size,) = struct.unpack_from("<I", data, pos)
            pos += 4
            payload = data[pos:pos + size]
            pos += size
            if name == "#EndOfFile#":
                break
            taggs.append((name, payload))
        (resolution,) = struct.unpack_from("<f", data, pos)
        pos += 4
        lods.append(Lod(points, normals, faces, taggs, resolution))
    return lods


def _point(p):
    if len(p) == 3:
        return (float(p[0]), float(p[1]), float(p[2]), 0)
    if len(p) == 4:
        return (float(p[0]), float(p[1]), float(p[2]), int(p[3]))
    raise ValueError("a point is (x, y, z) or (x, y, z, flags), got %r" % (p,))


def _asciiz(text):
    return text.encode("utf-8") + b"\x00"


def _fixed(text, size=PROPERTY_FIELD):
    raw = text.encode("utf-8")
    if len(raw) >= size:
        raise ValueError("%r does not fit a %d-byte field" % (text, size))
    return raw + b"\x00" * (size - len(raw))


def _read_asciiz(data, pos):
    end = data.index(b"\x00", pos)
    return data[pos:end].decode("utf-8", "replace"), end + 1
