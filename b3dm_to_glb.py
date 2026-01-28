from __future__ import annotations

import hashlib
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ConversionSummary:
    converted: int
    skipped: int


def convert_manifest_tiles(manifest: dict[str, Any], cache_dir: Path) -> ConversionSummary:
    tiles = manifest.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        raise ValueError("Manifest contains no tiles to convert")

    hash_dir = cache_dir / "hashes"
    hash_dir.mkdir(parents=True, exist_ok=True)

    converted = 0
    skipped = 0

    for tile in tiles:
        tile_id = _require_str(tile, "tile_id")
        b3dm_path = Path(_require_str(tile, "b3dm_path"))
        glb_path = Path(_require_str(tile, "glb_path"))
        hash_path = hash_dir / f"{tile_id}.sha256"

        if not b3dm_path.exists():
            raise ValueError(f"Missing b3dm content: {b3dm_path}")

        current_hash = _hash_file(b3dm_path)
        if _is_cache_valid(glb_path, hash_path, current_hash):
            skipped += 1
            continue

        glb_path.parent.mkdir(parents=True, exist_ok=True)
        _run_b3dm_to_glb(b3dm_path, glb_path)
        hash_path.write_text(current_hash, encoding="utf-8")
        converted += 1

    return ConversionSummary(converted=converted, skipped=skipped)


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Manifest tile missing '{key}'")
    return value


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_cache_valid(glb_path: Path, hash_path: Path, current_hash: str) -> bool:
    if not glb_path.exists() or not hash_path.exists():
        return False
    cached_hash = hash_path.read_text(encoding="utf-8").strip()
    return cached_hash == current_hash


def _run_b3dm_to_glb(b3dm_path: Path, glb_path: Path) -> None:
    command = [
        "npx",
        "3d-tiles-tools",
        "b3dmToGlb",
        "-i",
        str(b3dm_path),
        "-o",
        str(glb_path),
    ]
    logging.info("Converting %s -> %s", b3dm_path.name, glb_path.name)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Unknown failure"
        raise RuntimeError(f"b3dmToGlb failed ({result.returncode}): {message}")
