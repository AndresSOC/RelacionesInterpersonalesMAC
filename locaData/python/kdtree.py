import math
import numpy as np
from typing import List, Optional
from scipy.spatial import cKDTree
from sqlalchemy import text
from coordinates import Cell

METROS_POR_GRADO_LAT = 111320.0


def _metros_por_grado_lon(lat: float) -> float:
    return METROS_POR_GRADO_LAT * math.cos(math.radians(lat))


def _project_to_meters(lat: float, lon: float, lat_ref: float, lon_ref: float):
    y = (lat - lat_ref) * METROS_POR_GRADO_LAT
    x = (lon - lon_ref) * _metros_por_grado_lon(lat_ref)
    return x, y


def _load_places_coords(engine):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT latitud, longitud FROM places"))
        return [(float(r[0]), float(r[1])) for r in result.fetchall() if r[0] is not None and r[1] is not None]


def _build_tree(places, lat_ref, lon_ref):
    coords = np.array([_project_to_meters(lat, lon, lat_ref, lon_ref) for lat, lon in places])
    return cKDTree(coords), coords


def _within_area(lat: float, lon: float, center_lat: float, center_lon: float, radius_km: float) -> bool:
    dlat = (lat - center_lat) * METROS_POR_GRADO_LAT
    dlon = (lon - center_lon) * _metros_por_grado_lon(center_lat)
    return math.sqrt(dlat ** 2 + dlon ** 2) <= radius_km * 1000


def filter_hex_cells_by_density(
    engine,
    hex_cells: List[Cell],
    density_threshold_m: float = 700
) -> List[Cell]:
    places = _load_places_coords(engine)
    if not places:
        return hex_cells

    lat_ref = sum(p[0] for p in places) / len(places)
    lon_ref = sum(p[1] for p in places) / len(places)

    tree, _ = _build_tree(places, lat_ref, lon_ref)

    cell_coords = np.array([
        _project_to_meters(c.lat, c.lon, lat_ref, lon_ref) for c in hex_cells
    ])
    distances, _ = tree.query(cell_coords)

    gap_cells = [
        hex_cells[i] for i, d in enumerate(distances) if d > density_threshold_m
    ]
    return gap_cells


def classify_cells(engine, hex_cells: List[Cell], density_tiers: list):
    places = _load_places_coords(engine)
    if not places:
        return [(c, density_tiers[-1]["max_pages"]) for c in hex_cells]

    lat_ref = sum(p[0] for p in places) / len(places)
    lon_ref = sum(p[1] for p in places) / len(places)

    tree, _ = _build_tree(places, lat_ref, lon_ref)
    cell_coords = np.array([
        _project_to_meters(c.lat, c.lon, lat_ref, lon_ref) for c in hex_cells
    ])
    distances, _ = tree.query(cell_coords)

    classified = []
    for i, cell in enumerate(hex_cells):
        max_pages = density_tiers[-1]["max_pages"]
        for tier in density_tiers:
            if distances[i] <= tier["max_dist_m"]:
                max_pages = tier["max_pages"]
                break
        classified.append((cell, max_pages))
    return classified


def detect_gap_patches(
    engine,
    center_lat: float,
    center_lon: float,
    radius_km: float,
    grid_step_m: float = 400,
    gap_min_m: float = 450,
    gap_max_m: float = 1200,
    patch_spacing_m: float = 800,
    max_patches: int = 60,
    search_radius_m: int = 500
) -> List[Cell]:
    places = _load_places_coords(engine)
    if not places:
        return []

    in_area = [(lat, lon) for lat, lon in places
               if _within_area(lat, lon, center_lat, center_lon, radius_km)]
    if not in_area:
        return []

    lat_ref = sum(p[0] for p in in_area) / len(in_area)
    lon_ref = sum(p[1] for p in in_area) / len(in_area)

    min_lat = min(p[0] for p in in_area)
    max_lat = max(p[0] for p in in_area)
    min_lon = min(p[1] for p in in_area)
    max_lon = max(p[1] for p in in_area)

    margin = 0.015
    min_lat = max(min_lat - margin, center_lat - radius_km / 111.32 - 0.02)
    max_lat = min(max_lat + margin, center_lat + radius_km / 111.32 + 0.02)
    min_lon = max(min_lon - margin, center_lon - radius_km / _metros_por_grado_lon(center_lat) - 0.02)
    max_lon = min(max_lon + margin, center_lon + radius_km / _metros_por_grado_lon(center_lat) + 0.02)

    paso_lat = grid_step_m / METROS_POR_GRADO_LAT
    paso_lon = grid_step_m / _metros_por_grado_lon(lat_ref)

    lats = np.arange(min_lat, max_lat, paso_lat)
    lons = np.arange(min_lon, max_lon, paso_lon)
    grid_points = [(lat, lon) for lat in lats for lon in lons]
    if not grid_points:
        return []

    tree, _ = _build_tree(in_area, lat_ref, lon_ref)

    grid_coords = np.array([
        _project_to_meters(lat, lon, lat_ref, lon_ref) for lat, lon in grid_points
    ])
    distances, _ = tree.query(grid_coords)

    mask = (distances > gap_min_m) & (distances < gap_max_m)
    candidates = sorted(
        [(distances[i], grid_points[i][0], grid_points[i][1]) for i in range(len(grid_points)) if mask[i]],
        key=lambda x: x[0],
        reverse=True
    )

    patches_final: List[dict] = []
    for dist_m, lat_c, lon_c in candidates:
        x_c, y_c = _project_to_meters(lat_c, lon_c, lat_ref, lon_ref)
        too_close = False
        for p in patches_final:
            d = math.sqrt((x_c - p["x"]) ** 2 + (y_c - p["y"]) ** 2)
            if d < patch_spacing_m:
                too_close = True
                break
        if not too_close:
            patches_final.append({"x": x_c, "y": y_c, "lat": lat_c, "lon": lon_c})
        if len(patches_final) == max_patches:
            break

    return [
        Cell(lat=round(p["lat"], 6), lon=round(p["lon"], 6), radius_m=search_radius_m)
        for p in patches_final
    ]
