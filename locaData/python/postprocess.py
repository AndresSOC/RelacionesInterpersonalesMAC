import math
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
from config import DATABASE_URL, AREA_CONFIG
from coordinates import helix

TOP_N = 2000
MIN_REVIEWS = 50


def _load_data(engine):
    print("Cargando datos desde PostgreSQL...")
    query = text(
        "SELECT p.*, pc.category "
        "FROM places p "
        "LEFT JOIN place_categories pc ON p.place_id = pc.place_id"
    )
    df = pd.read_sql_query(query, con=engine)
    print(f"  {len(df)} registros cargados (con categorías expandidas).")
    return df


def _stats(engine, df: pd.DataFrame):
    print("\n--- Estadísticas generales ---")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM fetch_sessions")).fetchone()
        print(f"  Sesiones de extracción: {result[0]}")

        result = conn.execute(
            text("SELECT COUNT(*), SUM(places_found) FROM coverage_cells WHERE status = 'done'")
        ).fetchone()
        print(f"  Celdas completadas: {result[0]}, lugares encontrados: {result[1] or 0}")

    unique_places = df["place_id"].nunique()
    print(f"  Lugares únicos: {unique_places}")
    print(f"  Rating promedio: {df['rating'].mean():.2f}" if df["rating"].notna().any() else "  Rating promedio: n/d")
    print(f"  Reseñas promedio: {df['user_ratings_total'].mean():.0f}" if df["user_ratings_total"].notna().any() else "  Reseñas promedio: n/d")

    if "category" in df.columns:
        top_cats = df["category"].value_counts().head(10)
        print("\n  Top 10 categorías:")
        for cat, count in top_cats.items():
            print(f"    {cat}: {count}")


def _filter_elite(df: pd.DataFrame, min_reviews: int, top_n: int) -> pd.DataFrame:
    df_unique = df.drop_duplicates(subset="place_id")
    popular = df_unique[df_unique["user_ratings_total"] >= min_reviews].copy()
    elite = popular.sort_values("user_ratings_total", ascending=False).head(top_n)
    print(f"\n  De {len(df_unique)} lugares únicos → élite de {len(elite)} (≥{min_reviews} reseñas, top {top_n}).")
    return elite


def _generate_helix(elite_df: pd.DataFrame, center_lat: float, center_lon: float):
    n = len(elite_df)
    puntos_por_aspa = max(8, int(math.sqrt(n / 2)))
    coords = helix(center_lat, center_lon, puntos_por_aspa=puntos_por_aspa, distancia_entre_puntos=800)
    print(f"  Hélice generada: {len(coords)} puntos (2 brazos × {puntos_por_aspa}) para {n} lugares élite.")
    return pd.DataFrame(coords), coords


def _plot(elite_df: pd.DataFrame, helix_df: pd.DataFrame, center_lat: float, center_lon: float):
    _, ax = plt.subplots(figsize=(10, 10))

    ax.scatter(center_lon, center_lat, color="red", marker="*", s=300, label="Centro", zorder=5)
    ax.scatter(
        elite_df["longitud"], elite_df["latitud"],
        c=elite_df["user_ratings_total"], cmap="plasma",
        s=30, alpha=0.7, label=f"Élite ({len(elite_df)} lugares)"
    )

    brazo_120 = helix_df[helix_df["brazo"] == helix_df["brazo"].unique()[0]]
    brazo_240 = helix_df[helix_df["brazo"] == helix_df["brazo"].unique()[1]] if len(helix_df["brazo"].unique()) > 1 else helix_df

    ax.scatter(brazo_120["lon"], brazo_120["lat"], color="#00CED1", s=60, label=brazo_120["brazo"].iloc[0])
    if len(helix_df["brazo"].unique()) > 1:
        ax.scatter(brazo_240["lon"], brazo_240["lat"], color="#FF8C00", s=60, label=brazo_240["brazo"].iloc[0])

    ax.set_title("Mapa de Lugares Élite + Hélice de Expansión", fontsize=14, fontweight="bold")
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.show()


def run():
    engine = create_engine(DATABASE_URL)
    df = _load_data(engine)
    _stats(engine, df)

    elite = _filter_elite(df, MIN_REVIEWS, TOP_N)
    center_lat = AREA_CONFIG["center_lat"]
    center_lon = AREA_CONFIG["center_lon"]

    helix_df, _ = _generate_helix(elite, center_lat, center_lon)
    _plot(elite, helix_df, center_lat, center_lon)

    return elite, helix_df


if __name__ == "__main__":
    run()
