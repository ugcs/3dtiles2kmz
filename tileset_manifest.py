from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from geo import ecef_to_lla_degrees, lla_degrees_to_ecef

@dataclass(frozen=True)
class ManifestResult:
    manifest: dict[str, Any]
    manifest_path: Path
    tile_count: int
    root_ecef: list[float]


def build_manifest(
    tileset_path: Path,
    cache_dir: Path,
    temp_dir: Path,
) -> ManifestResult:
    tileset = _load_tileset(tileset_path)
    tileset_dir = tileset_path.parent
    glb_dir = cache_dir / "glb"
    glb_dir.mkdir(parents=True, exist_ok=True)

    tiles: list[dict[str, Any]] = []
    root_tile = tileset.get("root")
    if not isinstance(root_tile, dict):
        raise ValueError("tileset.json missing root tile")

    root_full = None
    walker = _TileWalker()
    for tile_id, tile, full_transform, tile_base_dir in walker.walk_tileset(
        root_tile,
        tileset_dir,
        np.identity(4, dtype=float),
    ):
        if root_full is None:
            root_full = full_transform
        if not _is_leaf_tile(tile):
            continue
        for uri in _extract_content_uris(tile):
            if _is_tileset_uri(uri):
                external_path = _resolve_content_path(tile_base_dir, uri)
                walker.queue_external_tileset(external_path, full_transform)
                continue
            if not _is_b3dm_uri(uri):
                continue
            b3dm_path = _resolve_content_path(tile_base_dir, uri)
            if not b3dm_path.exists():
                raise ValueError(f"Missing b3dm content: {b3dm_path}")
            tiles.append(
                {
                    "tile_id": tile_id,
                    "b3dm_path": str(b3dm_path),
                    "glb_path": str(glb_dir / f"{tile_id}.glb"),
                    "transform_ecef": _matrix_to_column_major(full_transform),
                    "boundingVolume": tile.get("boundingVolume"),
                }
            )

    if root_full is None:
        raise ValueError("No tiles found in tileset.json")

    origin_ecef, origin_lla, origin_strategy = _derive_origin(root_tile, root_full)
    manifest = {
        "tiles": tiles,
        "origin": {
            "strategy": origin_strategy,
            "ecef": origin_ecef,
            "lla": origin_lla,
        },
    }
    manifest_path = temp_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    return ManifestResult(
        manifest=manifest,
        manifest_path=manifest_path,
        tile_count=len(tiles),
        root_ecef=origin_ecef,
    )


def _load_tileset(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid tileset.json: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("tileset.json must contain a JSON object")
    return data


class _TileWalker:
    def __init__(self) -> None:
        self._counter = 0
        self._queued_tilesets: list[tuple[Path, np.ndarray]] = []
        self._visited_tilesets: set[Path] = set()

    def walk_tileset(
        self,
        root: dict[str, Any],
        base_dir: Path,
        parent_transform: np.ndarray,
    ) -> Iterable[tuple[str, dict[str, Any], np.ndarray, Path]]:
        stack: list[tuple[str, dict[str, Any], np.ndarray, Path]] = [
            ("tile_000000", root, parent_transform, base_dir)
        ]
        while stack:
            tile_id, tile, parent_transform, tile_base_dir = stack.pop()
            local_transform = _matrix_from_tile(tile.get("transform"))
            full_transform = parent_transform @ local_transform
            yield tile_id, tile, full_transform, tile_base_dir
            children = tile.get("children") or []
            if isinstance(children, list):
                for child in reversed(children):
                    if isinstance(child, dict):
                        self._counter += 1
                        stack.append(
                            (
                                f"tile_{self._counter:06d}",
                                child,
                                full_transform,
                                tile_base_dir,
                            )
                        )
            while self._queued_tilesets:
                tileset_path, tileset_parent_transform = self._queued_tilesets.pop()
                if tileset_path in self._visited_tilesets:
                    continue
                self._visited_tilesets.add(tileset_path)
                external_tileset = _load_tileset(tileset_path)
                external_root = external_tileset.get("root")
                if not isinstance(external_root, dict):
                    raise ValueError(f"External tileset missing root tile: {tileset_path}")
                external_dir = tileset_path.parent
                self._counter += 1
                stack.append(
                    (
                        f"tile_{self._counter:06d}",
                        external_root,
                        tileset_parent_transform,
                        external_dir,
                    )
                )

    def queue_external_tileset(self, tileset_path: Path, parent_transform: np.ndarray) -> None:
        if tileset_path.suffix.lower() != ".json":
            return
        self._queued_tilesets.append((tileset_path, parent_transform))


def _matrix_from_tile(transform: Any) -> np.ndarray:
    if not transform:
        return np.identity(4, dtype=float)
    if isinstance(transform, list) and len(transform) == 16:
        return np.array(transform, dtype=float).reshape((4, 4), order="F")
    raise ValueError("Tile transform must be a 16-number array")


def _matrix_to_column_major(matrix: np.ndarray) -> list[float]:
    return [float(value) for value in matrix.reshape(16, order="F")]


def _extract_translation(matrix: np.ndarray) -> list[float]:
    translation = matrix[:3, 3]
    return [float(value) for value in translation]


def _derive_origin(
    root_tile: dict[str, Any],
    root_full: np.ndarray,
) -> tuple[list[float], list[float], str]:
    bounding_volume = root_tile.get("boundingVolume")
    if isinstance(bounding_volume, dict):
        region = bounding_volume.get("region")
        if isinstance(region, list) and len(region) == 6:
            west, south, east, north, min_h, max_h = [float(v) for v in region]
            lat = math.degrees((south + north) * 0.5)
            lon = math.degrees((west + east) * 0.5)
            alt = min_h
            origin_lla = [lat, lon, alt]
            origin_ecef = list(lla_degrees_to_ecef(origin_lla))
            return origin_ecef, origin_lla, "region"
        sphere = bounding_volume.get("sphere")
        if isinstance(sphere, list) and len(sphere) == 4:
            center = np.array([float(sphere[0]), float(sphere[1]), float(sphere[2]), 1.0])
            ecef_center = root_full @ center
            origin_ecef = [float(ecef_center[0]), float(ecef_center[1]), float(ecef_center[2])]
            origin_lla = list(ecef_to_lla_degrees(origin_ecef))
            return origin_ecef, origin_lla, "sphere"
        box = bounding_volume.get("box")
        if isinstance(box, list) and len(box) == 12:
            center = np.array([float(box[0]), float(box[1]), float(box[2]), 1.0])
            ecef_center = root_full @ center
            origin_ecef = [float(ecef_center[0]), float(ecef_center[1]), float(ecef_center[2])]
            origin_lla = list(ecef_to_lla_degrees(origin_ecef))
            return origin_ecef, origin_lla, "box"

    origin_ecef = _extract_translation(root_full)
    origin_lla = list(ecef_to_lla_degrees(origin_ecef))
    return origin_ecef, origin_lla, "root"


def _extract_content_uris(tile: dict[str, Any]) -> list[str]:
    uris: list[str] = []
    content = tile.get("content")
    if isinstance(content, dict):
        uri = content.get("uri") or content.get("url")
        if isinstance(uri, str):
            uris.append(uri)
    contents = tile.get("contents")
    if isinstance(contents, list):
        for entry in contents:
            if not isinstance(entry, dict):
                continue
            uri = entry.get("uri") or entry.get("url")
            if isinstance(uri, str):
                uris.append(uri)
    return uris


def _is_leaf_tile(tile: dict[str, Any]) -> bool:
    children = tile.get("children")
    if children is None:
        return True
    if isinstance(children, list) and len(children) == 0:
        return True
    return False


def _is_b3dm_uri(uri: str) -> bool:
    normalized = _strip_query_fragment(uri).lower()
    return normalized.endswith(".b3dm")


def _is_tileset_uri(uri: str) -> bool:
    normalized = _strip_query_fragment(uri).lower()
    return normalized.endswith("tileset.json") or normalized.endswith(".json")


def _resolve_content_path(base_dir: Path, uri: str) -> Path:
    normalized = _strip_query_fragment(uri)
    return (base_dir / normalized).expanduser().resolve()


def _strip_query_fragment(uri: str) -> str:
    stripped = uri.split("?", 1)[0]
    return stripped.split("#", 1)[0]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
