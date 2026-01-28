from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class DaeQcResult:
    size_bytes: int
    geometry_count: int
    node_count: int
    triangles_count: int
    bbox_min: tuple[float, float, float] | None
    bbox_max: tuple[float, float, float] | None
    positions_count: int


def qc_dae(dae_path: Path) -> DaeQcResult:
    if not dae_path.exists():
        raise FileNotFoundError(f"DAE not found: {dae_path}")

    size_bytes = dae_path.stat().st_size
    tree = ET.parse(dae_path)
    root = tree.getroot()

    namespace = _detect_namespace(root.tag)
    ns = {"c": namespace} if namespace else {}

    geometry_count = len(root.findall(".//c:library_geometries/c:geometry", ns))
    node_count = len(root.findall(".//c:library_visual_scenes//c:node", ns))

    triangles_count = 0
    for tri in root.findall(".//c:triangles", ns):
        count_attr = tri.get("count")
        if count_attr and count_attr.isdigit():
            triangles_count += int(count_attr)

    bbox_min, bbox_max, positions_count = _compute_bbox(root, ns)

    return DaeQcResult(
        size_bytes=size_bytes,
        geometry_count=geometry_count,
        node_count=node_count,
        triangles_count=triangles_count,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        positions_count=positions_count,
    )


def log_qc(result: DaeQcResult) -> None:
    logging.info("DAE QC: size=%d bytes", result.size_bytes)
    logging.info("DAE QC: geometries=%d nodes=%d triangles=%d", result.geometry_count, result.node_count, result.triangles_count)
    if result.bbox_min and result.bbox_max:
        logging.info(
            "DAE QC: bbox min=(%.3f, %.3f, %.3f) max=(%.3f, %.3f, %.3f) positions=%d",
            result.bbox_min[0],
            result.bbox_min[1],
            result.bbox_min[2],
            result.bbox_max[0],
            result.bbox_max[1],
            result.bbox_max[2],
            result.positions_count,
        )
    else:
        logging.info("DAE QC: bbox unavailable (no position arrays found)")


def _detect_namespace(tag: str) -> str | None:
    if tag.startswith("{") and "}" in tag:
        return tag[1 : tag.index("}")]
    return None


def _compute_bbox(root: ET.Element, ns: dict[str, str]) -> tuple[tuple[float, float, float] | None, tuple[float, float, float] | None, int]:
    accessors = _collect_accessors(root, ns)
    bbox_min: list[float] | None = None
    bbox_max: list[float] | None = None
    positions_count = 0

    for float_array in root.findall(".//c:float_array", ns):
        array_id = float_array.get("id", "")
        if "positions" not in array_id.lower():
            continue
        raw_text = (float_array.text or "").strip()
        if not raw_text:
            continue
        floats = _parse_floats(raw_text)
        if not floats:
            continue
        stride = accessors.get(array_id, 3)
        if stride < 3:
            continue
        for i in range(0, len(floats) - 2, stride):
            x, y, z = floats[i], floats[i + 1], floats[i + 2]
            positions_count += 1
            if bbox_min is None:
                bbox_min = [x, y, z]
                bbox_max = [x, y, z]
            else:
                bbox_min[0] = min(bbox_min[0], x)
                bbox_min[1] = min(bbox_min[1], y)
                bbox_min[2] = min(bbox_min[2], z)
                bbox_max[0] = max(bbox_max[0], x)
                bbox_max[1] = max(bbox_max[1], y)
                bbox_max[2] = max(bbox_max[2], z)

    if bbox_min is None or bbox_max is None:
        return None, None, positions_count
    return (bbox_min[0], bbox_min[1], bbox_min[2]), (bbox_max[0], bbox_max[1], bbox_max[2]), positions_count


def _collect_accessors(root: ET.Element, ns: dict[str, str]) -> dict[str, int]:
    accessors: dict[str, int] = {}
    for accessor in root.findall(".//c:accessor", ns):
        source = accessor.get("source", "")
        if not source.startswith("#"):
            continue
        source_id = source[1:]
        stride_text = accessor.get("stride", "3")
        try:
            stride = int(stride_text)
        except ValueError:
            stride = 3
        accessors[source_id] = stride
    return accessors


def _parse_floats(text: str) -> list[float]:
    values: list[float] = []
    for token in text.split():
        try:
            values.append(float(token))
        except ValueError:
            continue
    return values
