import pandas as pd
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

engine = create_engine(DATABASE_URL)

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'UrbanFlow', 'Reviews', 'reviews_sentiment_only.csv')

print(f"Cargando reseñas desde {CSV_PATH}...")
df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')

print(f"  {len(df)} reseñas, {df['place_id'].nunique()} lugares distintos")

bool_cols = ['has_emoji']
for col in bool_cols:
    if col in df.columns:
        df[col] = df[col].astype(bool)

with engine.begin() as conn:
    conn.execute(text("DELETE FROM reviews"))

batch_size = 2000
total = len(df)
for i in range(0, total, batch_size):
    batch = df.iloc[i:i+batch_size]
    batch.to_sql('reviews', engine, if_exists='append', index=False, method='multi')
    pct = min(100, (i + batch_size) / total * 100)
    print(f"  {i+len(batch)}/{total} ({pct:.0f}%)")

with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM reviews"))
    count = result.fetchone()[0]
    result = conn.execute(text("SELECT sentiment_label, COUNT(*) FROM reviews GROUP BY sentiment_label ORDER BY COUNT(*) DESC"))
    dist = result.fetchall()

print(f"\nCarga completada: {count} reseñas")
print("Distribución de sentimiento:")
for label, cnt in dist:
    print(f"  {label}: {cnt} ({cnt/count*100:.1f}%)")
