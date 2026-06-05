import math
from typing import List, Dict
from dataclasses import dataclass

METROS_POR_GRADO_LAT = 111320.0


@dataclass
class Cell:
    lat: float
    lon: float
    radius_m: int


def _metros_por_grado_lon(lat: float) -> float:
    return METROS_POR_GRADO_LAT * math.cos(math.radians(lat))


def hex_grid(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    search_radius_m: int = 1000
) -> List[Cell]:
    cells: List[Cell] = []
    spacing_m = search_radius_m * math.sqrt(3)  # hexagonal tiling
    row_height_m = search_radius_m * 1.5

    metros_lat = spacing_m / METROS_POR_GRADO_LAT
    metros_lon_center = spacing_m / _metros_por_grado_lon(center_lat)

    max_steps = int((radius_km * 1000) / spacing_m) + 2

    for row in range(-max_steps, max_steps + 1):
        offset = (spacing_m / 2) if row % 2 != 0 else 0
        offset_lon = offset / _metros_por_grado_lon(center_lat)

        lat = center_lat + row * (row_height_m / METROS_POR_GRADO_LAT)
        if abs(lat - center_lat) * METROS_POR_GRADO_LAT > radius_km * 1000:
            continue

        metros_lon_current = spacing_m / _metros_por_grado_lon(lat)

        for col in range(-max_steps, max_steps + 1):
            lon = center_lon + col * metros_lon_current + offset_lon
            dist_m = _haversine(center_lat, center_lon, lat, lon)
            if dist_m <= radius_km * 1000:
                cells.append(Cell(lat=round(lat, 6), lon=round(lon, 6), radius_m=search_radius_m))

    return cells


def spiral(
    center_lat: float,
    center_lon: float,
    max_points: int,
    step_degrees: float = 0.004,
    search_radius_m: int = 1000
) -> List[Cell]:
    cells: List[Cell] = []
    angulo = 0.0
    for _ in range(max_points):
        radio = step_degrees * angulo
        lat = center_lat + radio * math.cos(angulo)
        lon = center_lon + radio * math.sin(angulo)
        cells.append(Cell(lat=round(lat, 6), lon=round(lon, 6), radius_m=search_radius_m))
        angulo += 1.0
    return cells


def helix(
    center_lat: float,
    center_lon: float,
    puntos_por_aspa: int = 18,
    distancia_entre_puntos: float = 800,
    search_radius_m: int = 1000
) -> List[Dict]:
    desfases = [
        ("Desfase 120°", (2 * math.pi) / 3),
        ("Desfase 240°", (4 * math.pi) / 3),
    ]
    results: List[Dict] = []
    idx = 1
    lat_base, lon_base = center_lat, center_lon
    m_por_g_lon = _metros_por_grado_lon(lat_base)

    for arm_label, radian_offset in desfases:
        for i in range(1, puntos_por_aspa + 1):
            r_m = math.sqrt(i) * distancia_entre_puntos
            angle = math.sqrt(i) * math.pi + radian_offset
            dy = r_m * math.sin(angle)
            dx = r_m * math.cos(angle)
            lat = lat_base + dy / METROS_POR_GRADO_LAT
            lon = lon_base + dx / m_por_g_lon
            results.append({
                "id_parche": idx,
                "brazo": arm_label,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "radius_m": search_radius_m
            })
            idx += 1
    return results


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
