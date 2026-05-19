import json
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from config import (
    API_KEY, URL_NEARBY, DATABASE_URL,
    AREA_CONFIG, FETCHER_BASE, META_PLACES,
    PHASE1, PHASE2, PHASE3, KDTREE_CONFIG
)
from coordinates import hex_grid
from fetcher import PlacesFetcher
from kdtree import classify_cells, detect_gap_patches

INIT_SQL_PATH = str(Path(__file__).resolve().parent.parent / "database" / "init.sql")


def _insert_places(engine, places: list, cell_id: int):
    if not places:
        return
    fetcher_obj = PlacesFetcher(API_KEY, URL_NEARBY)

    rows = [fetcher_obj.place_to_row(p, cell_id) for p in places]
    df = pd.DataFrame(rows)
    df = df.dropna(subset=["place_id"])
    df = df.where(pd.notnull(df), None)

    with engine.connect() as conn:
        for _, row in df.iterrows():
            row_dict = {k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()}
            if row_dict.get("raw_data") is not None and isinstance(row_dict["raw_data"], dict):
                row_dict["raw_data"] = json.dumps(row_dict["raw_data"])
            columns = ", ".join(row_dict.keys())
            placeholders = ", ".join(
                f"CAST(:{k} AS JSONB)" if k == "raw_data" else f":{k}"
                for k in row_dict.keys()
            )
            updates = ", ".join(
                f"{col} = EXCLUDED.{col}"
                for col in row_dict.keys()
                if col != "place_id"
            )
            sql = (
                f"INSERT INTO places ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT (place_id) DO UPDATE SET {updates}"
            )
            conn.execute(text(sql), row_dict)

        categories_data = []
        for p in places:
            pid = p.get("place_id")
            for cat in fetcher_obj.extract_categories(p):
                categories_data.append({"place_id": pid, "category": cat})

        if categories_data:
            for cat_row in categories_data:
                conn.execute(
                    text(
                        "INSERT INTO place_categories (place_id, category) "
                        "VALUES (:place_id, :category) ON CONFLICT DO NOTHING"
                    ),
                    cat_row
                )
        conn.commit()


def _init_schema(engine):
    with open(INIT_SQL_PATH, "r") as f:
        init_sql = f.read()
    with engine.connect() as conn:
        conn.execute(text(init_sql))
        conn.commit()
    print("Esquema de BD inicializado.")


def _create_session(engine, phase_name: str, total_cells: int) -> int:
    cfg = {
        "phase": phase_name,
        "area": AREA_CONFIG,
        "total_cells": total_cells
    }
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "INSERT INTO fetch_sessions (area_config, total_cells, status) "
                "VALUES (CAST(:cfg AS JSONB), :total, 'running') RETURNING id"
            ),
            {"cfg": json.dumps(cfg), "total": total_cells}
        )
        session_id = result.fetchone()[0]
        conn.commit()
    return session_id


def _insert_cells(engine, session_id: int, cells: list) -> int:
    count = 0
    with engine.connect() as conn:
        for item in cells:
            if isinstance(item, tuple):
                cell, max_pages = item
            else:
                cell = item
                max_pages = 3
            conn.execute(
                text(
                    "INSERT INTO coverage_cells (session_id, lat, lon, radius_m, max_pages, status) "
                    "VALUES (:sid, :lat, :lon, :radius, :mp, 'pending') "
                    "ON CONFLICT (lat, lon) DO NOTHING"
                ),
                {"sid": session_id, "lat": cell.lat, "lon": cell.lon,
                 "radius": cell.radius_m, "mp": max_pages}
            )
            count += 1
        conn.commit()
    return count


def _reset_stuck_cells(engine):
    with engine.connect() as conn:
        conn.execute(text(
            "UPDATE coverage_cells SET status = 'pending' WHERE status = 'fetching'"
        ))
        conn.commit()


def _get_pending_cells(engine) -> list:
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT id, lat, lon, radius_m, max_pages FROM coverage_cells "
                "WHERE status = 'pending' "
                "ORDER BY id"
            )
        )
        return [dict(row._mapping) for row in result]


def _fetch_cells(engine, pending_cells: list, session_id: int,
                 rate_limit_rps: int, max_pages: int, page_delay: int,
                 max_retries: int, backoff: int, emit=None) -> int:
    fetcher_cache = {}

    def _get_fetcher(mp: int):
        if mp not in fetcher_cache:
            fetcher_cache[mp] = PlacesFetcher(
                api_key=API_KEY,
                nearby_url=URL_NEARBY,
                rate_limit_rps=rate_limit_rps,
                max_pages_per_cell=mp,
                page_delay_seconds=page_delay,
                max_retries=max_retries,
                retry_backoff_base=backoff
            )
        return fetcher_cache[mp]

    total = 0
    for i, cell in enumerate(pending_cells, 1):
        cell_id = cell["id"]
        cell_max_pages = cell.get("max_pages", max_pages)
        lat, lon = float(cell["lat"]), float(cell["lon"])
        fetcher = _get_fetcher(cell_max_pages)

        with engine.connect() as conn:
            conn.execute(
                text("UPDATE coverage_cells SET status = 'fetching' WHERE id = :cid"),
                {"cid": cell_id}
            )
            conn.commit()

        print(f"  [{i}/{len(pending_cells)}] ({lat:.5f}, {lon:.5f}) págs={cell_max_pages} ...", end=" ")

        try:
            places = fetcher.fetch_cell(lat, lon, cell["radius_m"])
        except Exception as e:
            print(f"✗ {e}")
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "UPDATE coverage_cells SET status = 'failed', error_message = :err "
                        "WHERE id = :cid"
                    ),
                    {"cid": cell_id, "err": str(e)[:500]}
                )
                conn.commit()
            continue

        _insert_places(engine, places, cell_id)
        total += len(places)

        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE coverage_cells SET status = 'done', places_found = :pf, "
                    "api_calls = :ac, fetched_at = NOW() WHERE id = :cid"
                ),
                {"cid": cell_id, "pf": len(places), "ac": fetcher.stats["total_api_calls"]}
            )
            conn.commit()

        print(f"{len(places)} lugares")

        if emit:
            with create_engine(DATABASE_URL).connect() as conn:
                tp = conn.execute(text("SELECT COUNT(*) FROM places")).fetchone()[0]
                tc = conn.execute(
                    text("SELECT COUNT(*) FROM coverage_cells WHERE status = 'done'")
                ).fetchone()[0]
            emit("update", {"totalPlaces": tp, "totalCells": tc, "phase": "running"})

        if META_PLACES:
            with engine.connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM places")).fetchone()[0]
            if count >= META_PLACES:
                print(f"  Meta de {META_PLACES} lugares alcanzada.")
                break

    return total


def _finish_session(engine, session_id: int, places_fetched: int, cells_done: int):
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE fetch_sessions SET finished_at = NOW(), "
                "places_fetched = :pf, cells_completed = :cc, status = 'completed' "
                "WHERE id = :sid"
            ),
            {"sid": session_id, "pf": places_fetched, "cc": cells_done}
        )
        conn.commit()


def _print_phase(phase: str, places: int):
    with create_engine(DATABASE_URL).connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM places")).fetchone()[0]
    print(f"\n--- {phase} completada: {places} nuevos | Total BD: {total} ---")


def run(emit=None):
    print("=" * 60)
    print("Pipeline 3-Fases — Google Places API")
    print("=" * 60)
    print(f"Area: {AREA_CONFIG['radius_km']}km desde "
          f"({AREA_CONFIG['center_lat']}, {AREA_CONFIG['center_lon']})")
    print(f"Rate base: {FETCHER_BASE['rate_limit_rps']} req/s")
    print()

    engine = create_engine(DATABASE_URL)
    _init_schema(engine)
    _reset_stuck_cells(engine)

    center_lat = AREA_CONFIG["center_lat"]
    center_lon = AREA_CONFIG["center_lon"]
    radius_km = AREA_CONFIG["radius_km"]

    # ============================
    # FASE 1: Reconocimiento
    # ============================
    if PHASE1["enabled"]:
        print("─" * 40)
        print("FASE 1: Reconocimiento (radio grande, 1 página)")
        print("─" * 40)

        cells = hex_grid(center_lat, center_lon, radius_km, PHASE1["search_radius_m"])
        print(f"Grid generado: {len(cells)} celdas (radio {PHASE1['search_radius_m']}m).")

        sid = _create_session(engine, "phase1_recon", len(cells))
        processed = _insert_cells(engine, sid, cells)
        print(f"Celdas programadas: {processed}. Sesión #{sid}.")

        pending = _get_pending_cells(engine)
        print(f"Celdas pendientes: {len(pending)}.")

        if pending:
            fetched = _fetch_cells(
                engine, pending, sid,
                rate_limit_rps=FETCHER_BASE["rate_limit_rps"],
                max_pages=PHASE1["max_pages_per_cell"],
                page_delay=FETCHER_BASE["page_delay_seconds"],
                max_retries=FETCHER_BASE["max_retries"],
                backoff=FETCHER_BASE["retry_backoff_base"],
                emit=emit
            )
            done = sum(1 for c in pending if True)
            _finish_session(engine, sid, fetched, len(pending))
            _print_phase("Fase 1", fetched)

    # ============================
    # FASE 2: Cobertura densa inteligente
    # ============================
    if PHASE2["enabled"]:
        print("\n" + "─" * 40)
        print("FASE 2: Cobertura densa (density-aware páginas)")
        print("─" * 40)

        all_hex = hex_grid(center_lat, center_lon, radius_km, PHASE2["search_radius_m"])
        print(f"Hex grid completo: {len(all_hex)} celdas (radio {PHASE2['search_radius_m']}m).")

        classified = classify_cells(engine, all_hex, PHASE2["density_tiers"])
        skip = PHASE2.get("density_skip_threshold_m", 0)
        if skip > 0:
            classified = [(c, mp) for c, mp in classified
                          if mp > 1 or any(t["max_pages"] == 1 for t in PHASE2["density_tiers"])]

        tiers_count = {}
        for _, mp in classified:
            tiers_count[mp] = tiers_count.get(mp, 0) + 1
        for mp, cnt in sorted(tiers_count.items()):
            label = next((t["label"] for t in PHASE2["density_tiers"] if t["max_pages"] == mp), f"{mp} págs")
            print(f"  → {cnt} celdas clasificadas como: {label}")

        if not classified:
            print("Sin celdas para Fase 2.")
        else:
            sid = _create_session(engine, "phase2_dense", len(classified))
            processed = _insert_cells(engine, sid, classified)
            print(f"Celdas programadas: {processed}. Sesión #{sid}.")

            pending = _get_pending_cells(engine)
            print(f"Celdas pendientes: {len(pending)}.")

            if pending:
                fetched = _fetch_cells(
                    engine, pending, sid,
                    rate_limit_rps=FETCHER_BASE["rate_limit_rps"],
                    max_pages=PHASE2["density_tiers"][-1]["max_pages"],
                    page_delay=FETCHER_BASE["page_delay_seconds"],
                    max_retries=FETCHER_BASE["max_retries"],
                    backoff=FETCHER_BASE["retry_backoff_base"],
                    emit=emit
                )
                _finish_session(engine, sid, fetched, len(pending))
                _print_phase("Fase 2", fetched)

    # ============================
    # FASE 3: Parches quirúrgicos
    # ============================
    if PHASE3["enabled"]:
        print("\n" + "─" * 40)
        print("FASE 3: Parches quirúrgicos (KDTree 400m + supresión)")
        print("─" * 40)

        patches = detect_gap_patches(
            engine,
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=radius_km,
            grid_step_m=KDTREE_CONFIG["grid_step_m"],
            gap_min_m=KDTREE_CONFIG["gap_min_m"],
            gap_max_m=KDTREE_CONFIG["gap_max_m"],
            patch_spacing_m=KDTREE_CONFIG["patch_spacing_m"],
            max_patches=KDTREE_CONFIG["max_patches"],
            search_radius_m=PHASE3["search_radius_m"]
        )
        print(f"Parches estratégicos detectados: {len(patches)} "
              f"(radio {PHASE3['search_radius_m']}m).")

        if not patches:
            print("Sin huecos finos detectados. Fase 3 omitida.")
        else:
            sid = _create_session(engine, "phase3_patches", len(patches))
            processed = _insert_cells(engine, sid, patches)
            print(f"Parches programados: {processed}. Sesión #{sid}.")

            pending = _get_pending_cells(engine)
            print(f"Parches pendientes: {len(pending)}.")

            if pending:
                fetched = _fetch_cells(
                    engine, pending, sid,
                    rate_limit_rps=FETCHER_BASE["rate_limit_rps"],
                    max_pages=PHASE3["max_pages_per_cell"],
                    page_delay=FETCHER_BASE["page_delay_seconds"],
                    max_retries=FETCHER_BASE["max_retries"],
                    backoff=FETCHER_BASE["retry_backoff_base"],
                    emit=emit
                )
                _finish_session(engine, sid, fetched, len(pending))
                _print_phase("Fase 3", fetched)

    # Resumen final
    with engine.connect() as conn:
        total_places = conn.execute(text("SELECT COUNT(*) FROM places")).fetchone()[0]
        total_cells = conn.execute(
            text("SELECT COUNT(*) FROM coverage_cells WHERE status = 'done'")
        ).fetchone()[0]

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETADO")
    print("=" * 60)
    print(f"  Lugares totales en BD: {total_places}")
    print(f"  Celdas completadas:    {total_cells}")

    if emit:
        emit("done", {"totalPlaces": total_places, "totalCells": total_cells})


if __name__ == "__main__":
    run()
