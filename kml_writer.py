from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geo import ecef_to_lla_degrees


@dataclass(frozen=True)
class KmlResult:
    output_path: Path
    latitude: float
    longitude: float
    altitude: float


def write_kml(
    manifest: dict[str, Any],
    output_path: Path,
    model_href: str = "model.dae",
    altitude_mode: str = "clampToGround",
) -> KmlResult:
    origin = manifest.get("origin")
    if not isinstance(origin, dict):
        raise ValueError("Manifest missing origin")

    lat, lon, alt = _origin_lla(origin)
    heading = 0.0
    tilt = 0.0
    roll = 0.0

    if altitude_mode == "clampToGround":
        alt = 0.0

    output_path.write_text(
        _render_kml(
            latitude=lat,
            longitude=lon,
            altitude=alt,
            heading=heading,
            tilt=tilt,
            roll=roll,
            model_href=model_href,
            altitude_mode=altitude_mode,
        ),
        encoding="utf-8",
    )

    return KmlResult(
        output_path=output_path,
        latitude=lat,
        longitude=lon,
        altitude=alt,
    )


def _origin_lla(origin: dict[str, Any]) -> tuple[float, float, float]:
    lla = origin.get("lla")
    if isinstance(lla, list) and len(lla) == 3:
        lat, lon, alt = (float(lla[0]), float(lla[1]), float(lla[2]))
        return lat, lon, alt
    ecef = origin.get("ecef")
    if not isinstance(ecef, list) or len(ecef) != 3:
        raise ValueError("Manifest origin missing ECEF coordinates")
    return ecef_to_lla_degrees(ecef)


def _render_kml(
    latitude: float,
    longitude: float,
    altitude: float,
    heading: float,
    tilt: float,
    roll: float,
    model_href: str,
    altitude_mode: str,
) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<kml xmlns=\"http://www.opengis.net/kml/2.2\">\n"
        "  <Document>\n"
        "    <Placemark>\n"
        "      <name>Tileset Model</name>\n"
        "      <Model>\n"
        f"        <altitudeMode>{_escape(altitude_mode)}</altitudeMode>\n"
        "        <Location>\n"
        f"          <longitude>{_fmt(longitude)}</longitude>\n"
        f"          <latitude>{_fmt(latitude)}</latitude>\n"
        f"          <altitude>{_fmt(altitude)}</altitude>\n"
        "        </Location>\n"
        "        <Orientation>\n"
        f"          <heading>{_fmt(heading)}</heading>\n"
        f"          <tilt>{_fmt(tilt)}</tilt>\n"
        f"          <roll>{_fmt(roll)}</roll>\n"
        "        </Orientation>\n"
        "        <Scale>\n"
        "          <x>1</x>\n"
        "          <y>1</y>\n"
        "          <z>1</z>\n"
        "        </Scale>\n"
        "        <Link>\n"
        f"          <href>{_escape(model_href)}</href>\n"
        "        </Link>\n"
        "      </Model>\n"
        "    </Placemark>\n"
        "  </Document>\n"
        "</kml>\n"
    )


def _fmt(value: float) -> str:
    if math.isnan(value) or math.isinf(value):
        raise ValueError("KML value is not finite")
    return f"{value:.8f}"


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
