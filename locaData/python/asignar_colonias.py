import numpy as np
import pandas as pd
from scipy.spatial import KDTree
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv
import os

load_dotenv(find_dotenv())

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5441')
DB_NAME = os.getenv('DB_NAME', 'locadata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

BASE = os.path.join(os.path.dirname(__file__), '..', 'proyecto_final')

engine = create_engine(DATABASE_URL)

print("Cargando catálogo de colonias...")
df_colonias = pd.read_csv(os.path.join(BASE, 'Limpieza y EDA', 'cat_colonias.csv'))
df_colonias.to_sql('colonias_cdmx', engine, if_exists='replace', index=False, method='multi')
print(f"  {len(df_colonias)} colonias cargadas en colonias_cdmx.")

print("Cargando dataset de referencia con coordenadas + id_colonia...")
df_ref = pd.read_csv(os.path.join(BASE, 'Limpieza y EDA', 'dataset_cdmx_limpio.csv'))
df_ref = df_ref[['place_id', 'latitud', 'longitud', 'id_colonia']].dropna(subset=['latitud', 'longitud', 'id_colonia'])
df_ref['id_colonia'] = df_ref['id_colonia'].astype(int)
print(f"  {len(df_ref)} lugares de referencia.")

print("Leyendo places de la DB sin colonia asignada...")
with engine.connect() as conn:
    df_db = pd.read_sql_query(
        "SELECT place_id, latitud, longitud FROM places WHERE latitud IS NOT NULL AND longitud IS NOT NULL",
        conn
    )
print(f"  {len(df_db)} lugares en DB.")

print("Construyendo KDTree con coordenadas de referencia...")
coords_ref = np.radians(df_ref[['latitud', 'longitud']].values)
tree = KDTree(coords_ref)

print("Asignando colonia más cercana a cada lugar de la DB...")
coords_db = np.radians(df_db[['latitud', 'longitud']].values)
distances, indices = tree.query(coords_db, k=1)

df_db['id_colonia'] = df_ref.iloc[indices]['id_colonia'].values
df_db['distancia_km'] = distances * 6371
print(f"  Distancia promedio: {df_db['distancia_km'].mean():.2f} km")
print(f"  Distancia máxima: {df_db['distancia_km'].max():.2f} km")

print("Guardando asignaciones en la DB...")
batch_size = 500
with engine.begin() as conn:
    for i in range(0, len(df_db), batch_size):
        batch = df_db.iloc[i:i+batch_size]
        for _, row in batch.iterrows():
            conn.execute(
                text("UPDATE places SET id_colonia = :cid WHERE place_id = :pid"),
                {"cid": int(row['id_colonia']), "pid": row['place_id']}
            )

with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM places WHERE id_colonia IS NOT NULL"))
    assigned = result.fetchone()[0]
print(f"\nAsignación completada: {assigned} lugares con colonia asignada.")
