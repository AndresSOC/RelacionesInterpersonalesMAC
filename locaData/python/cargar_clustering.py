import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5441')
DB_NAME = os.getenv('DB_NAME', 'locadata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

BASE = os.path.join(os.path.dirname(__file__), '..', 'proyecto_final')

with engine.begin() as conn:
    conn.execute(text("TRUNCATE TABLE macro_sectors, commercial_archetypes, investment_recommendations, spatial_clusters RESTART IDENTITY CASCADE"))

df_macro = pd.read_csv(os.path.join(BASE, 'cat_macrosectores.csv'))
df_macro.to_sql('macro_sectors', engine, if_exists='append', index=False, method='multi')
print(f"macro_sectors: {len(df_macro)} filas")

df_arq = pd.read_csv(os.path.join(BASE, 'cat_arquetipos_mc.csv'))
df_arq = df_arq.rename(columns={
    'Nombre_Arquetipo': 'nombre_arquetipo',
    'Descripcion_Estrategica': 'descripcion_estrategica'
})
df_arq.to_sql('commercial_archetypes', engine, if_exists='append', index=False, method='multi')
print(f"commercial_archetypes: {len(df_arq)} filas")

df_meta = pd.read_csv(os.path.join(BASE, 'meta_clustering_cdmx.csv'))
cols_cluster = [
    'cluster_espacial', 'total_negocios', 'rating_promedio', 'trafico_total',
    'tasa_actividad', 'sector_1', 'sector_2', 'sector_3', 'sector_4',
    'sector_5', 'sector_6', 'sector_7', 'id_colonia_principal',
    'Diagnóstico', 'Recomendación', 'id_arquetipo'
]
df_clusters = df_meta[cols_cluster].rename(columns={
    'Diagnóstico': 'diagnostico',
    'Recomendación': 'recomendacion'
})
df_clusters['id_colonia_principal'] = df_clusters['id_colonia_principal'].fillna(0).astype(int)
df_clusters['diagnostico'] = df_clusters['diagnostico'].fillna('')
df_clusters['recomendacion'] = df_clusters['recomendacion'].fillna('')
df_clusters.to_sql('spatial_clusters', engine, if_exists='append', index=False, method='multi')
print(f"spatial_clusters: {len(df_clusters)} filas")

df_rec = pd.read_csv(os.path.join(BASE, 'Clustering', 'recomendaciones_inversion_cdmx.csv'))
df_rec = df_rec.rename(columns={
    'Cluster': 'cluster_espacial',
    'Locales_Totales': 'locales_totales',
    'Tráfico_Peatonal': 'trafico_peatonal',
    'Diagnóstico': 'diagnostico',
    'Recomendación': 'recomendacion'
})
df_rec = df_rec[['cluster_espacial', 'locales_totales', 'trafico_peatonal', 'diagnostico', 'recomendacion']]
df_rec.to_sql('investment_recommendations', engine, if_exists='append', index=False, method='multi')
print(f"investment_recommendations: {len(df_rec)} filas")

with engine.connect() as conn:
    r = conn.execute(text("SELECT COUNT(*) FROM spatial_clusters")).fetchone()
    print(f"\nVerificacion: spatial_clusters = {r[0]}")
    r = conn.execute(text("SELECT COUNT(*) FROM commercial_archetypes")).fetchone()
    print(f"commercial_archetypes = {r[0]}")
    r = conn.execute(text("SELECT COUNT(*) FROM investment_recommendations")).fetchone()
    print(f"investment_recommendations = {r[0]}")
    r = conn.execute(text("SELECT COUNT(*) FROM macro_sectors")).fetchone()
    print(f"macro_sectors = {r[0]}")
    r = conn.execute(text("SELECT nombre_arquetipo FROM commercial_archetypes ORDER BY id_arquetipo")).fetchall()
    print("\nArquetipos:")
    for row in r:
        print(f"  {row[0]}")

print("\nCarga completada.")
