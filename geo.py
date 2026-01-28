from __future__ import annotations

import math
from typing import Iterable


def ecef_to_lla_radians(ecef: Iterable[float]) -> tuple[float, float, float]:
    x, y, z = _coerce_ecef(ecef)
    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e2 = 1.0 - (b * b) / (a * a)
    ep2 = (a * a - b * b) / (b * b)

    p = math.hypot(x, y)
    lon = 0.0 if p == 0.0 else math.atan2(y, x)
    theta = math.atan2(z * a, p * b)
    sin_theta = math.sin(theta)
    cos_theta = math.cos(theta)

    lat = math.atan2(
        z + ep2 * b * sin_theta**3,
        p - e2 * a * cos_theta**3,
    )
    sin_lat = math.sin(lat)
    n = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    alt = p / math.cos(lat) - n

    return lat, lon, alt


def ecef_to_lla_degrees(ecef: Iterable[float]) -> tuple[float, float, float]:
    lat, lon, alt = ecef_to_lla_radians(ecef)
    return math.degrees(lat), math.degrees(lon), alt


def lla_degrees_to_ecef(lla: Iterable[float]) -> tuple[float, float, float]:
    lat_deg, lon_deg, alt = _coerce_lla(lla)
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)

    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    sin_lon = math.sin(lon)
    cos_lon = math.cos(lon)

    n = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    x = (n + alt) * cos_lat * cos_lon
    y = (n + alt) * cos_lat * sin_lon
    z = (n * (1.0 - e2) + alt) * sin_lat
    return x, y, z


def _coerce_ecef(ecef: Iterable[float]) -> tuple[float, float, float]:
    values = [float(v) for v in ecef]
    if len(values) != 3:
        raise ValueError("ECEF coordinate must contain 3 values")
    return values[0], values[1], values[2]


def _coerce_lla(lla: Iterable[float]) -> tuple[float, float, float]:
    values = [float(v) for v in lla]
    if len(values) != 3:
        raise ValueError("LLA coordinate must contain 3 values")
    return values[0], values[1], values[2]
