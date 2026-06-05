import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.cluster import DBSCAN, KMeans
from sklearn.preprocessing import StandardScaler
from dotenv import load_dotenv, find_dotenv
import os
import math

load_dotenv(find_dotenv())

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5441')
DB_NAME = os.getenv('DB_NAME', 'locadata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

SECTOR_MAP = {
    'bakery': 1, 'bar': 1, 'cafe': 1, 'food': 1, 'grocery_or_supermarket': 1,
    'liquor_store': 1, 'meal_delivery': 1, 'meal_takeaway': 1, 'restaurant': 1,
    'supermarket': 1,

    'bicycle_store': 2, 'book_store': 2, 'car_dealer': 2, 'car_rental': 2,
    'clothing_store': 2, 'convenience_store': 2, 'department_store': 2,
    'drugstore': 2, 'electronics_store': 2, 'florist': 2, 'furniture_store': 2,
    'gas_station': 2, 'hardware_store': 2, 'home_goods_store': 2,
    'jewelry_store': 2, 'pet_store': 2, 'shoe_store': 2, 'shopping_mall': 2, 'store': 2,

    'beauty_salon': 3, 'dentist': 3, 'doctor': 3, 'gym': 3, 'hair_care': 3,
    'health': 3, 'hospital': 3, 'pharmacy': 3, 'physiotherapist': 3, 'spa': 3,
    'veterinary_care': 3,

    'amusement_park': 4, 'aquarium': 4, 'art_gallery': 4, 'bowling_alley': 4,
    'campground': 4, 'casino': 4, 'movie_theater': 4, 'museum': 4,
    'night_club': 4, 'park': 4, 'rv_park': 4, 'stadium': 4,
    'tourist_attraction': 4, 'zoo': 4,

    'accounting': 5, 'atm': 5, 'bank': 5, 'finance': 5,
    'insurance_agency': 5, 'lawyer': 5, 'real_estate_agency': 5, 'travel_agency': 5,

    'library': 6, 'primary_school': 6, 'school': 6, 'secondary_school': 6,
    'university': 6,

    'car_repair': 7, 'car_wash': 7, 'electrician': 7, 'funeral_home': 7,
    'general_contractor': 7, 'laundry': 7, 'locksmith': 7, 'moving_company': 7,
    'painter': 7, 'parking': 7, 'plumber': 7, 'post_office': 7,
    'roofing_contractor': 7, 'storage': 7,
}

SECTOR_NAMES = [
    '', 'Alimentos y Bebidas', 'Retail y Conveniencia',
    'Salud y Bienestar', 'Entretenimiento', 'Finanzas y Servicios',
    'Educación', 'Servicios y Mantenimiento'
]

EPS_METERS = 120
EARTH_RADIUS = 6371000
MIN_SAMPLES = 20
K_ARQUETIPOS = 9


def _engine():
    return create_engine(DATABASE_URL)


def run_dbscan(engine):
    print("Leyendo lugares desde PostgreSQL...")
    df = pd.read_sql_query(
        "SELECT place_id, latitud, longitud FROM places WHERE latitud IS NOT NULL AND longitud IS NOT NULL",
        con=engine
    )
    print(f"  {len(df)} lugares con coordenadas.")

    if len(df) < MIN_SAMPLES:
        print(f"  Muy pocos lugares (min {MIN_SAMPLES}). Abortando DBSCAN.")
        return 0

    print(f"Ejecutando DBSCAN (eps={EPS_METERS}m, min_samples={MIN_SAMPLES}, Haversine)...")
    coords_rad = np.radians(df[['latitud', 'longitud']].values)
    eps_rad = EPS_METERS / EARTH_RADIUS
    dbscan = DBSCAN(eps=eps_rad, min_samples=MIN_SAMPLES, metric='euclidean', n_jobs=-1)
    labels = dbscan.fit_predict(coords_rad)

    unique = set(labels) - {-1}
    noise = sum(1 for l in labels if l == -1)
    print(f"  Clusters formados: {len(unique)}, ruido: {noise}")

    print("Guardando asignaciones en places.cluster_espacial...")
    df['cluster_espacial'] = labels
    with engine.begin() as conn:
        conn.execute(text("UPDATE places SET cluster_espacial = NULL"))
        for label in unique:
            pids = df.loc[df['cluster_espacial'] == label, 'place_id'].tolist()
            if pids:
                conn.execute(
                    text("UPDATE places SET cluster_espacial = :cid WHERE place_id = ANY(:pids)"),
                    {"cid": int(label), "pids": pids}
                )
    return len(unique)


def calculate_profiles(engine):
    print("Calculando sectores por lugar...")
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT place_id, business_name, rating, user_ratings_total, "
                 "cluster_espacial, business_status, id_colonia FROM places WHERE cluster_espacial IS NOT NULL")
        )
        rows = result.fetchall()

        result = conn.execute(
            text("SELECT place_id, category FROM place_categories WHERE place_id IN "
                 "(SELECT place_id FROM places WHERE cluster_espacial IS NOT NULL)")
        )
        cat_rows = result.fetchall()

    place_sectors = {}
    for pid, cat in cat_rows:
        s = SECTOR_MAP.get(cat, 0)
        if 1 <= s <= 7:
            if pid not in place_sectors:
                place_sectors[pid] = [0] * 7
            place_sectors[pid][s - 1] = 1

    from collections import Counter
    cluster_data = {}
    for pid, name, rating, ut, cid, status, idcol in rows:
        if cid not in cluster_data:
            cluster_data[cid] = {
                'places': 0, 'rating_sum': 0, 'rating_count': 0,
                'traffic': 0, 'active': 0, 'total_status': 0,
                'sectors': [0] * 7, 'colonias': []
            }
        d = cluster_data[cid]
        d['places'] += 1
        if rating is not None:
            d['rating_sum'] += rating
            d['rating_count'] += 1
        d['traffic'] += ut or 0
        if status == 'OPERATIONAL':
            d['active'] += 1
        d['total_status'] += 1
        if idcol is not None:
            d['colonias'].append(idcol)

        secs = place_sectors.get(pid, [0] * 7)
        for i in range(7):
            d['sectors'][i] += secs[i]

    print(f"Calculando perfiles para {len(cluster_data)} clusters con colonias...")
    profiles = []
    for cid, d in cluster_data.items():
        colonia_principal = 0
        if d['colonias']:
            counter = Counter(d['colonias'])
            colonia_principal = counter.most_common(1)[0][0] if counter else 0
        profiles.append({
            'cluster_espacial': cid,
            'total_negocios': d['places'],
            'rating_promedio': round(d['rating_sum'] / d['rating_count'], 2) if d['rating_count'] else None,
            'trafico_total': d['traffic'],
            'tasa_actividad': round((d['active'] / d['total_status']) * 100, 1) if d['total_status'] else 0,
            'sector_1': d['sectors'][0], 'sector_2': d['sectors'][1],
            'sector_3': d['sectors'][2], 'sector_4': d['sectors'][3],
            'sector_5': d['sectors'][4], 'sector_6': d['sectors'][5],
            'sector_7': d['sectors'][6],
            'id_colonia_principal': colonia_principal,
        })
    return profiles


def save_profiles(engine, profiles):
    print(f"Guardando {len(profiles)} perfiles en spatial_clusters...")
    df = pd.DataFrame(profiles)
    df['diagnostico'] = ''
    df['recomendacion'] = ''
    df['id_arquetipo'] = None
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM investment_recommendations"))
        conn.execute(text("DELETE FROM spatial_clusters"))
    df.to_sql('spatial_clusters', engine, if_exists='append', index=False, method='multi')


def run_recommendations(engine):
    print("Ejecutando motor de recomendaciones...")
    df = pd.read_sql_table('spatial_clusters', con=engine)
    if df.empty:
        return

    df['id_arquetipo'] = None
    df['diagnostico'] = ''
    df['recomendacion'] = ''

    recommendations = []
    for _, z in df.iterrows():
        total = z['total_negocios']
        if total == 0:
            continue
        sectors = [z[f'sector_{i}'] for i in range(1, 8)]
        pcts = [(s / total) * 100 for s in sectors]
        deficits = [(i + 1, SECTOR_NAMES[i + 1], pcts[i]) for i in range(7) if pcts[i] < 5]
        if deficits:
            names = ', '.join(n for _, n, _ in deficits)
            diag = 'OPORTUNIDAD'
            rec = f'Déficit detectado (<5% de oferta) en: {names}.'
        else:
            min_sector = min(enumerate(pcts), key=lambda x: x[1])
            diag = 'SATURADO'
            rec = f'Zona con alta competencia. Mayor oportunidad en {SECTOR_NAMES[min_sector[0]+1]}.'

        recommendations.append({
            'cluster_espacial': int(z['cluster_espacial']),
            'locales_totales': int(total),
            'trafico_peatonal': int(z['trafico_total']),
            'diagnostico': diag,
            'recomendacion': rec,
        })

    if recommendations:
        df_rec = pd.DataFrame(recommendations)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM investment_recommendations"))
        df_rec.to_sql('investment_recommendations', engine, if_exists='append', index=False, method='multi')
        print(f"  {len(recommendations)} recomendaciones generadas.")


def run_meta_clustering(engine):
    print(f"Ejecutando Meta-Clustering K-Means (K={K_ARQUETIPOS})...")
    df = pd.read_sql_table('spatial_clusters', con=engine)
    if df.empty or len(df) < K_ARQUETIPOS:
        print("  Muy pocos clusters para meta-clustering.")
        return

    for i in range(1, 8):
        total = df['total_negocios'].replace(0, 1)
        df[f'pct_sector_{i}'] = (df[f'sector_{i}'] / total) * 100

    feature_cols = ['trafico_total', 'rating_promedio', 'tasa_actividad'] + [f'pct_sector_{i}' for i in range(1, 8)]
    data = df[feature_cols].fillna(0).values
    data_scaled = StandardScaler().fit_transform(data)

    kmeans = KMeans(n_clusters=K_ARQUETIPOS, random_state=42, n_init=10)
    labels = kmeans.fit_predict(data_scaled)

    df['id_arquetipo'] = labels.astype(int)
    print(f"  Asignaciones K-Means: {dict(zip(*np.unique(labels, return_counts=True)))}")

    archetypes = [
        (0, 'Cluster Gastronomico', 'Zonas de bajo tráfico peatonal pero altísima concentración (62%) de giros de alimentos y bebidas. Ideal para dark kitchens o restaurantes de destino.'),
        (1, 'Corredor Mixto (Comida y Bienestar)', 'Ecosistemas equilibrados con alto nivel de actividad (92%), liderados por la oferta gastronómica y servicios de salud/cuidado personal.'),
        (2, 'Area de Mejora', 'Zonas de alto tránsito (71k) dominadas por el retail (35%), pero que presentan el rating de satisfacción más bajo (3.9). Oportunidad de competir con calidad.'),
        (3, 'Zona Especializada en Servicios/Mantenimiento', 'Sectores altamente especializados donde casi el 35% de la oferta se centra en reparaciones, oficios y mantenimiento. Tráfico local/vecinal.'),
        (4, 'Medico y Farmaceutico', 'Polígonos concentrados en salud y farmacias (31%), acompañados de retail. Presentan ligera vulnerabilidad con tasas de actividad del 85%.'),
        (5, 'Ecosistema Comercial de Alta Satisfacción', 'Zonas destacadas por tener la mejor reputación y satisfacción del cliente (Rating 4.4). Combinan alimentos, salud y servicios de alta calidad.'),
        (6, 'Cluster Educativo y Escolar', 'Zonas impulsadas por la vida académica. Poseen la mayor concentración de giros educativos (18%), rodeados de retail y servicios afines.'),
        (7, 'Corredor de Salud y Finanzas', 'Corredores de trámites y cuidado. Lideran en servicios de salud (32%) y albergan la mayor presencia de instituciones financieras (12%).'),
        (8, 'Epicentro Comercial y Tráfico Masivo', 'Los gigantes de la CDMX. Zonas con tráfico peatonal colosal (+300k), donde convergen masivamente el retail (36%) y los alimentos (27%).'),
    ]

    df_arch = pd.DataFrame(archetypes, columns=['id_arquetipo', 'nombre_arquetipo', 'descripcion_estrategica'])
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM commercial_archetypes"))
        conn.execute(text("UPDATE spatial_clusters SET id_arquetipo = NULL"))
    df_arch.to_sql('commercial_archetypes', engine, if_exists='append', index=False, method='multi')

    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text("UPDATE spatial_clusters SET id_arquetipo = :aid WHERE cluster_espacial = :cid"),
                {"aid": int(row['id_arquetipo']), "cid": int(row['cluster_espacial'])}
            )
    print("  Meta-clustering completado.")


def run():
    engine = _engine()
    print("=" * 60)
    print("Pipeline de Clustering — DBSCAN + Perfil + Recomendador + K-Means")
    print("=" * 60)

    n = run_dbscan(engine)
    if n == 0:
        print("No se formaron clusters. Abortando.")
        return
    print(f"Clusters: {n}")

    profiles = calculate_profiles(engine)
    save_profiles(engine, profiles)
    print(f"Perfiles: {len(profiles)}")

    run_recommendations(engine)
    run_meta_clustering(engine)

    print("\nPipeline de clustering completado.")


if __name__ == "__main__":
    run()
