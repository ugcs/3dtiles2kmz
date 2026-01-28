from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PackageResult:
    output_path: Path
    input_count: int


def package_kmz(
    output_path: Path,
    doc_kml_path: Path,
    model_dae_path: Path,
) -> PackageResult:
    if not doc_kml_path.exists():
        raise FileNotFoundError(f"Missing doc.kml: {doc_kml_path}")
    if not model_dae_path.exists():
        raise FileNotFoundError(f"Missing model.dae: {model_dae_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".kmz.tmp")

    fixed_time = (1980, 1, 1, 0, 0, 0)
    entries = [("doc.kml", doc_kml_path), ("model.dae", model_dae_path)]

    with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, source in sorted(entries, key=lambda item: item[0]):
            _write_entry(zf, arcname, source, fixed_time)

    shutil.move(temp_path, output_path)
    return PackageResult(output_path=output_path, input_count=len(entries))


def _write_entry(
    zf: zipfile.ZipFile,
    arcname: str,
    source: Path,
    fixed_time: tuple[int, int, int, int, int, int],
) -> None:
    info = zipfile.ZipInfo(arcname, date_time=fixed_time)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    with source.open("rb") as handle:
        data = handle.read()
    zf.writestr(info, data)
