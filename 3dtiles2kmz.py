#!/usr/bin/env python3
"""CLI scaffolding for DJI Terra 3D Tiles -> Google Earth KMZ conversion."""
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Optional

from b3dm_to_glb import convert_manifest_tiles
from dae_qc import log_qc, qc_dae
from blender_export import export_collada
from kml_writer import write_kml
from kmz_packager import package_kmz
from tileset_manifest import build_manifest


class ExitCodes:
    SUCCESS = 0
    INVALID_INPUT = 2
    EXTERNAL_TOOL_FAILURE = 3
    PACKAGING_FAILURE = 4


@dataclass(frozen=True)
class AppPaths:
    input_dir: Path
    tileset_path: Path
    output_path: Path
    cache_dir: Path
    temp_dir: Optional[Path] = None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="tiles_to_kmz",
        description="Convert DJI Terra 3D Tiles to Google Earth KMZ (V1 scaffolding).",
    )
    parser.add_argument("--input", required=True, help="Tileset input directory")
    parser.add_argument("--output", required=True, help="Output .kmz file path")
    return parser.parse_args(argv)


def configure_logging() -> None:
    level = logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s",
    )


def resolve_paths(args: argparse.Namespace) -> AppPaths:
    input_dir = Path(args.input).expanduser().resolve()
    tileset_path = input_dir / "tileset.json"

    output_path = Path(args.output).expanduser().resolve()
    cache_dir = input_dir / ".tiles_to_kmz_cache"

    return AppPaths(
        input_dir=input_dir,
        tileset_path=tileset_path,
        output_path=output_path,
        cache_dir=cache_dir,
    )


def validate_args(args: argparse.Namespace, paths: AppPaths) -> None:
    if not paths.input_dir.exists() or not paths.input_dir.is_dir():
        raise ValueError(f"Input directory not found: {paths.input_dir}")

    if not paths.tileset_path.exists():
        raise ValueError(f"tileset.json not found: {paths.tileset_path}")

    if paths.output_path.suffix.lower() != ".kmz":
        raise ValueError("Output file must have a .kmz extension")

    output_parent = paths.output_path.parent
    output_parent.mkdir(parents=True, exist_ok=True)

def create_workspace(paths: AppPaths) -> AppPaths:
    paths.cache_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="run_", dir=str(paths.cache_dir)))
    return AppPaths(
        input_dir=paths.input_dir,
        tileset_path=paths.tileset_path,
        output_path=paths.output_path,
        cache_dir=paths.cache_dir,
        temp_dir=temp_dir,
    )


def log_scaffold_summary(paths: AppPaths) -> None:
    logging.info("Phase 1 scaffolding complete.")
    logging.info("Input dir: %s", paths.input_dir)
    logging.info("Tileset: %s", paths.tileset_path)
    logging.info("Output kmz: %s", paths.output_path)
    logging.info("Cache dir: %s", paths.cache_dir)
    logging.info("Temp dir: %s", paths.temp_dir)


def log_manifest_summary(tile_count: int, manifest_path: Path) -> None:
    logging.info("Phase 2 tileset parsing complete.")
    logging.info("Tiles discovered: %s", tile_count)
    logging.info("Manifest: %s", manifest_path)


def log_conversion_summary(converted: int, skipped: int) -> None:
    logging.info("Phase 3 b3dm -> glb conversion complete.")
    logging.info("Converted: %s", converted)
    logging.info("Skipped (cached): %s", skipped)


def log_blender_summary(output_path: Path, tile_count: int) -> None:
    logging.info("Phase 4 Blender export complete.")
    logging.info("Tiles exported: %s", tile_count)
    logging.info("DAE output: %s", output_path)


def log_kml_summary(
    kml_path: Path,
    latitude: float,
    longitude: float,
    altitude: float,
    origin_strategy: str,
) -> None:
    logging.info("Phase 5 georeferencing + KML complete.")
    logging.info("KML output: %s", kml_path)
    logging.info("Origin (lat, lon, alt): %.6f, %.6f, %.2f", latitude, longitude, altitude)
    logging.info("Origin strategy: %s", origin_strategy)


def log_packaging_summary(output_path: Path, input_count: int) -> None:
    logging.info("Phase 6 KMZ packaging complete.")
    logging.info("KMZ output: %s", output_path)
    logging.info("Inputs packaged: %s", input_count)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    configure_logging()

    try:
        paths = resolve_paths(args)
        validate_args(args, paths)
        paths = create_workspace(paths)
    except ValueError as exc:
        logging.error("%s", exc)
        return ExitCodes.INVALID_INPUT

    log_scaffold_summary(paths)
    try:
        manifest_result = build_manifest(
            tileset_path=paths.tileset_path,
            cache_dir=paths.cache_dir,
            temp_dir=paths.temp_dir or paths.cache_dir,
        )
    except ValueError as exc:
        logging.error("%s", exc)
        return ExitCodes.INVALID_INPUT

    log_manifest_summary(manifest_result.tile_count, manifest_result.manifest_path)

    try:
        summary = convert_manifest_tiles(manifest_result.manifest, paths.cache_dir)
    except ValueError as exc:
        logging.error("%s", exc)
        return ExitCodes.INVALID_INPUT
    except (RuntimeError, FileNotFoundError) as exc:
        logging.error("%s", exc)
        return ExitCodes.EXTERNAL_TOOL_FAILURE

    log_conversion_summary(summary.converted, summary.skipped)

    try:
        export_result = export_collada(
            manifest_result.manifest,
            paths.cache_dir,
            paths.temp_dir or paths.cache_dir,
        )
    except ValueError as exc:
        logging.error("%s", exc)
        return ExitCodes.INVALID_INPUT
    except (RuntimeError, FileNotFoundError) as exc:
        logging.error("%s", exc)
        return ExitCodes.EXTERNAL_TOOL_FAILURE

    log_blender_summary(export_result.output_path, export_result.tile_count)

    try:
        qc_result = qc_dae(export_result.output_path)
        log_qc(qc_result)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        logging.warning("DAE QC failed: %s", exc)

    try:
        kml_path = export_result.output_path.parent / "doc.kml"
        kml_result = write_kml(
            manifest_result.manifest,
            kml_path,
            model_href="model.dae",
        )
    except ValueError as exc:
        logging.error("%s", exc)
        return ExitCodes.INVALID_INPUT

    log_kml_summary(
        kml_result.output_path,
        kml_result.latitude,
        kml_result.longitude,
        kml_result.altitude,
        str(manifest_result.manifest.get("origin", {}).get("strategy", "unknown")),
    )

    try:
        package_result = package_kmz(
            paths.output_path,
            kml_result.output_path,
            export_result.output_path,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        logging.error("KMZ packaging failed: %s", exc)
        return ExitCodes.PACKAGING_FAILURE

    log_packaging_summary(package_result.output_path, package_result.input_count)

    if paths.temp_dir is not None:
        shutil.rmtree(paths.temp_dir)

    return ExitCodes.SUCCESS


if __name__ == "__main__":
    sys.exit(main())
