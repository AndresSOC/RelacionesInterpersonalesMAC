import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

API_KEY = os.getenv('api_key')
URL_NEARBY = os.getenv('url_nearby')

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5441')
DB_NAME = os.getenv('DB_NAME', 'locadata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

AREA_CONFIG = {
    "center_lat": 19.3048,
    "center_lon": -99.1895,
    "radius_km": 5.0,
}

FETCHER_BASE = {
    "rate_limit_rps": 10,
    "page_delay_seconds": 2,
    "max_retries": 3,
    "retry_backoff_base": 2
}

PHASE1 = {
    "search_radius_m": 3000,
    "max_pages_per_cell": 1,
    "enabled": True
}

PHASE2 = {
    "search_radius_m": 1000,
    "density_tiers": [
        {"max_dist_m": 400,  "max_pages": 5,  "label": "denso (5 págs)"},
        {"max_dist_m": 700,  "max_pages": 3,  "label": "medio (3 págs)"},
        {"max_dist_m": 9999, "max_pages": 1,  "label": "bajo (1 pág)"},
    ],
    "density_skip_threshold_m": 0,
    "enabled": True
}

KDTREE_CONFIG = {
    "grid_step_m": 400,
    "gap_min_m": 450,
    "gap_max_m": 1200,
    "patch_spacing_m": 800,
    "max_patches": 60
}

PHASE3 = {
    "search_radius_m": 500,
    "max_pages_per_cell": 3,
    "enabled": True
}

META_PLACES = None
