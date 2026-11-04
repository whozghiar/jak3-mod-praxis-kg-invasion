#!/usr/bin/env python3
"""
Build the Praxis KG Invasion mod's custom models from the user's own extracted Jak 2 and Jak 3 rips.

    python scripts/praxis_kg_invasion/make_models.py            # writes the models, prints a summary
    python scripts/praxis_kg_invasion/make_models.py --check    # only checks the sources and outputs

Inputs (written by `task extract` with `rip_levels` on, for Jak 2 and for Jak 3):
    decompiler_out/jak2/levels/forresca/crimson-guard-lod0.glb        Jak 2 Krimzon Guard
    decompiler_out/jak2/levels/forresca/crimson-guard-hover-lod0.glb  Jak 2 jetpack guard (red)
    decompiler_out/jak3/levels/ctypesa/crimson-guard-lod0.glb         Jak 3 Freedom League guard

Outputs, each written twice with the same content:
    custom_assets/jak3/models/custom_levels/<name>.glb   read by `build-actor` (art group <name>-ag)
    custom_assets/jak3/models/<level>/<name>-lod0.glb    baked into <level>.fr3 by `task extract`, so
                                                         the merc renderer has the mesh build-actor's
                                                         dummy merc-ctrl names (<name>-lod0); <level>
                                                         is ctypesa (guards) or ctypesc (jetpack)

  pki-kg-red       The Jak 2 guard's mesh and red textures, skinned to the Jak 3 guard's skeleton
                   (the same 38 joints plus back/right_wrist/left_wrist, identical bind poses), with
                   the Jak 3 guard's 52 animations after two padding clips, so every clip sits at
                   the index the Jak 3 `crimson-guard` code uses (idle 4 ... shield-sidle 55). The
                   rip carries every mesh segment (dark guard armor, rifle, other weapon) with no
                   segment flag, and a build-actor model draws all its primitives, so each weapon
                   gets its own model: this one keeps the rifle, the normal armor and the body.
  pki-kg-red-gl    The same with the guards' other weapon (grenade launcher, tazer: mask bit 4).
  pki-kg-yellow    Jak 2's dark guard: the yellow armor instead of part of the normal one, rifle.
  pki-kg-yellow-gl The same with the other weapon.
  pki-hover-red    The Jak 2 jetpack guard as ripped (34 joints, its 17 clips), drawn on the stock KG
                   flying-turret code: its clips are reordered so the three that code plays sit at
                   its indices (2 idle, 3 hover = fly-forward, 4 fire = shoot0), see HOVER_ORDER.

The primitive lists are those of Haven City: New Dawn's level port, checked in game there.
Every path is relative to the jak-project root. Needs numpy.
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DECOMP = ROOT / "decompiler_out"
J2_GUARD = DECOMP / "jak2/levels/forresca/crimson-guard-lod0.glb"
J2_HOVER = DECOMP / "jak2/levels/forresca/crimson-guard-hover-lod0.glb"
J3_GUARD = DECOMP / "jak3/levels/ctypesa/crimson-guard-lod0.glb"
OUT_ACTOR = ROOT / "custom_assets/jak3/models/custom_levels"
# Each model goes to the level whose processes draw it: art groups are looked up in the drawing
# process's own level. Guards are traffic units of CTYPESA, flying turrets of CTYPESC.
OUT_LEVEL = {"pki-kg-red": ROOT / "custom_assets/jak3/models/ctypesa",
             "pki-kg-red-gl": ROOT / "custom_assets/jak3/models/ctypesa",
             "pki-kg-yellow": ROOT / "custom_assets/jak3/models/ctypesa",
             "pki-kg-yellow-gl": ROOT / "custom_assets/jak3/models/ctypesa",
             "pki-hover-red": ROOT / "custom_assets/jak3/models/ctypesc"}

# Primitives of the Jak 2 guard rip kept for each model, by index in the rip's mesh: the dark guard
# armor (0-3, darkguard-* textures), the rifle (4-12, bound to joint `gun`), the shorter grenade
# launcher / tazer (13-17, the only one with cguardgame-guntube), the normal armor (18-24, of which
# the dark guard keeps 18-20) and the body (25-36).
GUARD_KEEP = {"pki-kg-red": list(range(4, 13)) + list(range(18, 37)),
              "pki-kg-red-gl": list(range(13, 37)),
              "pki-kg-yellow": list(range(0, 13)) + [18, 19, 20] + list(range(25, 37)),
              "pki-kg-yellow-gl": list(range(0, 4)) + list(range(13, 21)) + list(range(25, 37))}
RED_GUARD_PADDING = 2

# Clip order of the jetpack guard (art-group index = 2 + position). praxis-kg-invasion.gc names them.
HOVER_ORDER = ["idle", "fly-forward", "shoot0", "fly-right", "fly-left", "fly-back", "knocked0",
               "knocked0-recover", "knocked1", "knocked1-recover", "death-right", "death-left",
               "death-left-fall", "death-right-fall", "death-instant", "death-land", "explode-idle"]

COMPONENT = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class Glb:
    """A parsed .glb: its JSON and binary chunk, with typed accessor reads."""

    def __init__(self, path: Path):
        data = path.read_bytes()
        json_len = struct.unpack_from("<I", data, 12)[0]
        self.json = json.loads(data[20:20 + json_len])
        off = 20 + json_len
        bin_len = struct.unpack_from("<I", data, off)[0]
        self.bin = data[off + 8:off + 8 + bin_len]
        self.path = path

    def accessor(self, index: int) -> np.ndarray:
        acc = self.json["accessors"][index]
        view = self.json["bufferViews"][acc["bufferView"]]
        dtype = COMPONENT[acc["componentType"]]
        width = WIDTH[acc["type"]]
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        stride = view.get("byteStride", 0)
        item = np.dtype(dtype).itemsize * width
        if stride and stride != item:
            raw = np.frombuffer(self.bin, dtype=np.uint8, count=stride * acc["count"], offset=start)
            raw = raw.reshape(acc["count"], stride)[:, :item].copy()
            return raw.view(dtype).reshape(acc["count"], width)
        return np.frombuffer(self.bin, dtype=dtype, count=acc["count"] * width,
                             offset=start).reshape(acc["count"], width).copy()

    def view_bytes(self, index: int) -> bytes:
        view = self.json["bufferViews"][index]
        start = view.get("byteOffset", 0)
        return self.bin[start:start + view["byteLength"]]

    def joint_names(self) -> list[str]:
        skin = self.json["skins"][0]
        return [self.json["nodes"][i]["name"] for i in skin["joints"]]


class Writer:
    """Collects glTF objects and one binary buffer, then writes a .glb."""

    def __init__(self):
        self.json = {"asset": {"version": "2.0", "generator": "praxis_kg_invasion make_models.py"},
                     "scene": 0, "scenes": [{"nodes": []}], "nodes": [], "meshes": [],
                     "materials": [], "textures": [], "images": [], "samplers": [],
                     "accessors": [], "bufferViews": [], "skins": [], "animations": []}
        self.bin = bytearray()

    def view(self, data: bytes, target: int | None = None) -> int:
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            view["target"] = target
        self.bin.extend(data)
        self.json["bufferViews"].append(view)
        return len(self.json["bufferViews"]) - 1

    def accessor(self, array: np.ndarray, kind: str, component: int, target: int | None = None,
                 minmax: bool = False) -> int:
        array = np.ascontiguousarray(array, dtype=COMPONENT[component])
        acc = {"bufferView": self.view(array.tobytes(), target), "componentType": component,
               "count": int(array.shape[0]), "type": kind}
        if minmax:
            acc["min"] = [float(x) for x in array.reshape(array.shape[0], -1).min(axis=0)]
            acc["max"] = [float(x) for x in array.reshape(array.shape[0], -1).max(axis=0)]
        self.json["accessors"].append(acc)
        return len(self.json["accessors"]) - 1

    def copy_accessor(self, src: Glb, index: int, target: int | None = None) -> int:
        acc = src.json["accessors"][index]
        return self.accessor(src.accessor(index), acc["type"], acc["componentType"], target,
                             "min" in acc)

    def save(self, path: Path):
        for key in [k for k, v in self.json.items() if v == []]:
            del self.json[key]
        self.json["buffers"] = [{"byteLength": len(self.bin)}]
        js = json.dumps(self.json, separators=(",", ":")).encode()
        js += b" " * (-len(js) % 4)
        self.bin.extend(b"\0" * (-len(self.bin) % 4))
        out = bytearray(struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(self.bin)))
        out += struct.pack("<II", len(js), 0x4E4F534A) + js
        out += struct.pack("<II", len(self.bin), 0x004E4942) + self.bin
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(out))


def image_bytes(src: Glb, image: dict) -> tuple[bytes, str]:
    """Pixels of an image of `src`, embedded (bufferView) or as a data URI."""
    if "bufferView" in image:
        return src.view_bytes(image["bufferView"]), image.get("mimeType", "image/png")
    uri = image["uri"]
    head, payload = uri.split(",", 1)
    return base64.b64decode(payload), head[5:].split(";")[0]


def copy_skeleton(out: Writer, src: Glb) -> tuple[int, dict[int, int]]:
    """Copy every node of `src` (meshes detached), its skin and its scene roots.
    Returns the index of the node that carried the skinned mesh and the node index map."""
    node_map = {i: i for i in range(len(src.json["nodes"]))}
    mesh_node = None
    for i, node in enumerate(src.json["nodes"]):
        node = dict(node)
        if "mesh" in node:
            mesh_node = i
            node.pop("mesh")
            node.pop("skin", None)
        out.json["nodes"].append(node)
    skin = dict(src.json["skins"][0])
    skin["inverseBindMatrices"] = out.copy_accessor(src, skin["inverseBindMatrices"])
    out.json["skins"].append(skin)
    out.json["scenes"][0]["nodes"] = list(src.json["scenes"][src.json.get("scene", 0)]["nodes"])
    if mesh_node is None:
        sys.exit(f"{src.path}: no skinned mesh node")
    return mesh_node, node_map


def copy_mesh(out: Writer, src: Glb, mesh_node: int, keep: list[int] | None,
              joint_remap: np.ndarray | None, textures_from: dict[str, tuple[bytes, str]] | None):
    """Copy the skinned mesh of `src` onto node `mesh_node` of `out`.

    keep          primitive indices to keep (None: all)
    joint_remap   JOINTS_0 value map from `src`'s skin to `out`'s (None: unchanged)
    textures_from image name -> pixels replacing `src`'s image of that name"""
    mesh = src.json["meshes"][0]
    prims = mesh["primitives"] if keep is None else [mesh["primitives"][i] for i in keep]
    attr_map: dict[tuple[str, int], int] = {}
    image_map: dict[int, int] = {}
    texture_map: dict[int, int] = {}
    material_map: dict[int, int] = {}
    sampler_map: dict[int, int] = {}

    def image(index: int) -> int:
        if index not in image_map:
            img = src.json["images"][index]
            data, mime = image_bytes(src, img)
            if textures_from and img.get("name") in textures_from:
                data, mime = textures_from[img["name"]]
            out.json["images"].append({"name": img.get("name", f"image{index}"), "mimeType": mime,
                                       "bufferView": out.view(data)})
            image_map[index] = len(out.json["images"]) - 1
        return image_map[index]

    def texture(index: int) -> int:
        if index not in texture_map:
            tex = dict(src.json["textures"][index])
            if "source" in tex:
                tex["source"] = image(tex["source"])
            if "sampler" in tex:
                s = tex["sampler"]
                if s not in sampler_map:
                    out.json["samplers"].append(dict(src.json["samplers"][s]))
                    sampler_map[s] = len(out.json["samplers"]) - 1
                tex["sampler"] = sampler_map[s]
            out.json["textures"].append(tex)
            texture_map[index] = len(out.json["textures"]) - 1
        return texture_map[index]

    def remap_textures(obj):
        # in a material, every dict holding "index" is a texture reference
        if isinstance(obj, dict):
            return {k: texture(v) if k == "index" and isinstance(v, int) else remap_textures(v)
                    for k, v in obj.items()}
        if isinstance(obj, list):
            return [remap_textures(x) for x in obj]
        return obj

    def material(index: int) -> int:
        if index not in material_map:
            out.json["materials"].append(remap_textures(src.json["materials"][index]))
            material_map[index] = len(out.json["materials"]) - 1
        return material_map[index]

    # The rips' vertex attributes cover every merc model of the level (the Jak 2 drillmtn hover
    # guard uses 2447 of 107332 vertices; the others are bound to other skeletons): keep the
    # vertices this mesh's indices reach, renumbered in order.
    if len({json.dumps(p["attributes"], sort_keys=True) for p in prims}) != 1:
        sys.exit(f"{src.path}: primitives do not share their vertex attributes")
    used = np.unique(np.concatenate([src.accessor(p["indices"]).ravel() for p in prims]))
    renumber = np.full(int(used.max()) + 1, -1, dtype=np.int64)
    renumber[used] = np.arange(len(used))

    new_prims = []
    for prim in prims:
        attrs = {}
        for name, acc in prim["attributes"].items():
            key = (name, acc)
            if key not in attr_map:
                info = src.json["accessors"][acc]
                data = src.accessor(acc)[used]
                if name == "JOINTS_0" and joint_remap is not None:
                    data = joint_remap[data.astype(np.int64)]
                if name == "JOINTS_0" and data.max() >= len(out.json["skins"][0]["joints"]):
                    sys.exit(f"{src.path}: a kept vertex is bound to a joint outside the skin")
                attr_map[key] = out.accessor(data, info["type"], info["componentType"], 34962,
                                             name == "POSITION")
            attrs[name] = attr_map[key]
        indices = renumber[src.accessor(prim["indices"]).ravel()]
        new = {"attributes": attrs,
               "indices": out.accessor(indices.reshape(-1, 1), "SCALAR", 5125, 34963),
               "mode": prim.get("mode", 4)}
        if "material" in prim:
            new["material"] = material(prim["material"])
        new_prims.append(new)
    out.json["meshes"].append({"name": mesh.get("name", "mesh"), "primitives": new_prims})
    node = out.json["nodes"][mesh_node]
    node["mesh"] = len(out.json["meshes"]) - 1
    node["skin"] = 0


def copy_animations(out: Writer, src: Glb, node_map: dict[int, int], padding: int,
                    names: list[str] | None = None, prefix: str = ""):
    """Copy every clip of `src`, after `padding` copies of its first clip; with `names`, in that
    order (prefix + name), failing when one is missing."""
    anims = src.json.get("animations", [])
    if names:
        by_name = {a.get("name"): a for a in anims}
        missing = [n for n in names if prefix + n not in by_name]
        if missing or len(names) != len(anims):
            sys.exit(f"{src.path}: clips {missing} missing, or clips not in HOVER_ORDER")
        anims = [by_name[prefix + n] for n in names]
    order = [anims[0]] * padding + anims
    acc_map: dict[int, int] = {}
    for i, anim in enumerate(order):
        samplers = []
        for s in anim["samplers"]:
            for key in ("input", "output"):
                if s[key] not in acc_map:
                    acc_map[s[key]] = out.copy_accessor(src, s[key])
            samplers.append({"input": acc_map[s["input"]], "output": acc_map[s["output"]],
                             "interpolation": s.get("interpolation", "LINEAR")})
        channels = [{"sampler": c["sampler"],
                     "target": {"node": node_map[c["target"]["node"]], "path": c["target"]["path"]}}
                    for c in anim["channels"]]
        name = anim.get("name", f"clip{i}") if i >= padding else f"pki-padding-{i}"
        out.json["animations"].append({"name": name, "samplers": samplers, "channels": channels})


def red_guard(j2: Glb, j3: Glb, name: str) -> Writer:
    names2, names3 = j2.joint_names(), j3.joint_names()
    missing = [n for n in names2 if n not in names3]
    if missing:
        sys.exit(f"Jak 2 guard joints missing from the Jak 3 skeleton: {missing}")
    remap = np.array([names3.index(n) for n in names2], dtype=np.int64)
    ibm2 = j2.accessor(j2.json["skins"][0]["inverseBindMatrices"])
    ibm3 = j3.accessor(j3.json["skins"][0]["inverseBindMatrices"])
    worst = float(np.abs(ibm2 - ibm3[remap]).max())
    if worst > 1e-3:
        sys.exit(f"bind poses differ between the two guard skeletons (max {worst})")
    out = Writer()
    mesh_node, node_map = copy_skeleton(out, j3)
    copy_mesh(out, j2, mesh_node, GUARD_KEEP[name], remap, None)
    copy_animations(out, j3, node_map, RED_GUARD_PADDING)
    out.json["meshes"][0]["name"] = f"{name}-lod0"
    return out


def hover(j2h: Glb, name: str) -> Writer:
    out = Writer()
    mesh_node, node_map = copy_skeleton(out, j2h)
    copy_mesh(out, j2h, mesh_node, None, None, None)
    copy_animations(out, j2h, node_map, 0, HOVER_ORDER, "crimson-guard-hover-")
    out.json["meshes"][0]["name"] = f"{name}-lod0"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--check", action="store_true", help="check sources and outputs only")
    args = parser.parse_args()
    for src in (J2_GUARD, J2_HOVER, J3_GUARD):
        if not src.exists():
            sys.exit(f"missing {src.relative_to(ROOT)}: extract that game with rip_levels on")
    outputs = list(OUT_LEVEL)
    if args.check:
        bad = [n for n in outputs if not (OUT_ACTOR / f"{n}.glb").exists()
               or not (OUT_LEVEL[n] / f"{n}-lod0.glb").exists()]
        print("missing: " + ", ".join(bad) if bad else "all models present")
        return 1 if bad else 0
    j2, j2h, j3 = Glb(J2_GUARD), Glb(J2_HOVER), Glb(J3_GUARD)
    models = {name: red_guard(j2, j3, name) for name in GUARD_KEEP}
    models["pki-hover-red"] = hover(j2h, "pki-hover-red")
    for name, model in models.items():
        model.save(OUT_ACTOR / f"{name}.glb")
        model.save(OUT_LEVEL[name] / f"{name}-lod0.glb")
        anims = len(model.json.get("animations", []))
        prims = len(model.json["meshes"][0]["primitives"])
        print(f"{name}: {prims} primitives, {anims} clips, {len(model.bin) // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
