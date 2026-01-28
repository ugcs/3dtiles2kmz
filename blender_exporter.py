import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def main() -> None:
    args = _parse_args()
    manifest_path = Path(args["manifest"]).resolve()
    output_path = Path(args["output"]).resolve()

    _ensure_collada_exporter()

    if not manifest_path.exists():
        raise RuntimeError(f"Manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tiles = manifest.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        raise RuntimeError("Manifest contains no tiles")

    _clear_scene()

    correction = Matrix.Rotation(-math.pi / 2.0, 4, "X")
    for tile in tiles:
        glb_path = Path(tile.get("glb_path", "")).resolve()
        transform = tile.get("transform_enu")
        if not glb_path.exists():
            raise RuntimeError(f"Missing glb: {glb_path}")
        if not isinstance(transform, list) or len(transform) != 16:
            raise RuntimeError("Invalid transform_enu in manifest")

        imported_objects = _import_glb(glb_path)
        matrix = _matrix_from_column_major(transform)
        for obj in imported_objects:
            obj.matrix_world = correction @ matrix @ obj.matrix_world

    _apply_grounding_offset()
    bpy.ops.object.select_all(action="SELECT")
    if not _has_collada_exporter():
        raise RuntimeError(
            "Collada exporter not available in this Blender build. "
            "Install Blender 3.6/4.x with the io_scene_dae addon."
        )
    bpy.ops.wm.collada_export(
        filepath=str(output_path),
        check_existing=False,
        apply_modifiers=True,
    )


def _parse_args() -> dict[str, str]:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    args: dict[str, str] = {}
    current_key = None
    for token in argv:
        if token.startswith("--"):
            current_key = token[2:]
            args[current_key] = ""
        elif current_key:
            args[current_key] = token
            current_key = None
    if "manifest" not in args or "output" not in args:
        raise RuntimeError("Usage: --manifest <path> --output <path>")
    return args


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _import_glb(path: Path) -> list[bpy.types.Object]:
    bpy.ops.import_scene.gltf(filepath=str(path))
    return list(bpy.context.selected_objects)


def _matrix_from_column_major(values: list[float]) -> Matrix:
    rows = [
        [values[0], values[4], values[8], values[12]],
        [values[1], values[5], values[9], values[13]],
        [values[2], values[6], values[10], values[14]],
        [values[3], values[7], values[11], values[15]],
    ]
    return Matrix(rows)


def _apply_grounding_offset() -> None:
    min_z = _scene_min_z()
    if min_z is None:
        return
    if abs(min_z) < 1e-6:
        return
    translation = Matrix.Translation((0.0, 0.0, -min_z))
    for obj in bpy.context.scene.objects:
        if obj.type in {"MESH", "EMPTY", "CURVE", "SURFACE"}:
            obj.matrix_world = translation @ obj.matrix_world
    print(f"[export] Applied grounding offset: {-min_z:.4f}m")


def _scene_min_z() -> float | None:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    min_z = None
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        eval_obj = obj.evaluated_get(depsgraph)
        for corner in eval_obj.bound_box:
            world_corner = eval_obj.matrix_world @ Vector(corner)
            z = world_corner.z
            if min_z is None or z < min_z:
                min_z = z
    return min_z


def _ensure_collada_exporter() -> None:
    if _has_collada_exporter():
        return
    if "io_scene_dae" not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module="io_scene_dae")


def _has_collada_exporter() -> bool:
    return hasattr(bpy.ops.wm, "collada_export")


if __name__ == "__main__":
    main()
