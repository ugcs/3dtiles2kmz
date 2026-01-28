from __future__ import annotations

import json
import logging
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from geo import ecef_to_lla_radians


@dataclass(frozen=True)
class ExportResult:
    output_path: Path
    manifest_path: Path
    tile_count: int


def export_collada(
    manifest: dict[str, Any],
    cache_dir: Path,
    temp_dir: Path,
) -> ExportResult:
    tiles = manifest.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        raise ValueError("Manifest contains no tiles to export")

    origin = manifest.get("origin")
    if not isinstance(origin, dict):
        raise ValueError("Manifest missing origin")
    origin_ecef = origin.get("ecef")
    if not isinstance(origin_ecef, list) or len(origin_ecef) != 3:
        raise ValueError("Manifest origin missing ECEF coordinates")

    export_dir = cache_dir / "dae"
    export_dir.mkdir(parents=True, exist_ok=True)
    export_manifest_path = temp_dir / "export_manifest.json"

    local_tiles = _build_local_tiles(tiles, origin_ecef)
    export_manifest = {"tiles": local_tiles}
    export_manifest_path.write_text(
        json.dumps(export_manifest, indent=2),
        encoding="utf-8",
    )

    output_path = export_dir / "model.dae"
    _run_blender(export_manifest_path, output_path)

    if not output_path.exists():
        raise RuntimeError("Blender did not produce model.dae")

    return ExportResult(
        output_path=output_path,
        manifest_path=export_manifest_path,
        tile_count=len(local_tiles),
    )


def _build_local_tiles(tiles: list[dict[str, Any]], origin_ecef: list[float]) -> list[dict[str, Any]]:
    origin_vec = np.array(origin_ecef, dtype=float)
    ecef_to_enu = _ecef_to_enu_matrix(origin_vec)
    local_tiles: list[dict[str, Any]] = []

    for tile in tiles:
        glb_path = Path(_require_str(tile, "glb_path"))
        transform_ecef = tile.get("transform_ecef")
        if not isinstance(transform_ecef, list) or len(transform_ecef) != 16:
            raise ValueError("Manifest tile missing transform_ecef")
        if not glb_path.exists():
            raise ValueError(f"Missing glb file: {glb_path}")

        tile_matrix = _matrix_from_column_major(transform_ecef)
        local_matrix = ecef_to_enu @ tile_matrix
        local_tiles.append(
            {
                "tile_id": _require_str(tile, "tile_id"),
                "glb_path": str(glb_path),
                "transform_enu": _matrix_to_column_major(local_matrix),
            }
        )

    return local_tiles


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Manifest tile missing '{key}'")
    return value


def _matrix_from_column_major(values: list[float]) -> np.ndarray:
    return np.array(values, dtype=float).reshape((4, 4), order="F")


def _matrix_to_column_major(matrix: np.ndarray) -> list[float]:
    return [float(value) for value in matrix.reshape(16, order="F")]


def _ecef_to_enu_matrix(origin_ecef: np.ndarray) -> np.ndarray:
    lat, lon, _ = ecef_to_lla_radians(origin_ecef)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    sin_lon = math.sin(lon)
    cos_lon = math.cos(lon)

    rotation = np.array(
        [
            [-sin_lon, cos_lon, 0.0],
            [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
            [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat],
        ],
        dtype=float,
    )
    translation = -rotation @ origin_ecef

    matrix = np.identity(4, dtype=float)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation
    return matrix


def _run_blender(manifest_path: Path, output_path: Path) -> None:
    script_path = Path(__file__).resolve().parent / "blender_exporter.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Missing Blender exporter script: {script_path}")

    command = [
        "blender",
        "--background",
        "--python",
        str(script_path),
        "--",
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
    ]
    logging.info("Running Blender export...")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Unknown failure"
        raise RuntimeError(f"Blender export failed ({result.returncode}): {message}")
    if not output_path.exists():
        message = result.stderr.strip() or result.stdout.strip() or "No output from Blender"
        raise RuntimeError(f"Blender export produced no file: {message}")
