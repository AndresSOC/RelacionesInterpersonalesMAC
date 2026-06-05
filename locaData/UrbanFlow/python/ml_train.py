import numpy as np
import pandas as pd
import json
import os
import joblib
from scipy.spatial import KDTree
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5441')
DB_NAME = os.getenv('DB_NAME', 'locadata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

SECTOR_MAP = {
    'bakery': 1, 'bar': 1, 'cafe': 1, 'food': 1, 'grocery_or_supermarket': 1,
    'liquor_store': 1, 'meal_delivery': 1, 'meal_takeaway': 1, 'restaurant': 1, 'supermarket': 1,
    'bicycle_store': 2, 'book_store': 2, 'car_dealer': 2, 'car_rental': 2,
    'clothing_store': 2, 'convenience_store': 2, 'department_store': 2,
    'drugstore': 2, 'electronics_store': 2, 'florist': 2, 'furniture_store': 2,
    'gas_station': 2, 'hardware_store': 2, 'home_goods_store': 2,
    'jewelry_store': 2, 'pet_store': 2, 'shoe_store': 2, 'shopping_mall': 2, 'store': 2,
    'beauty_salon': 3, 'dentist': 3, 'doctor': 3, 'gym': 3, 'hair_care': 3,
    'health': 3, 'hospital': 3, 'pharmacy': 3, 'physiotherapist': 3, 'spa': 3, 'veterinary_care': 3,
    'amusement_park': 4, 'aquarium': 4, 'art_gallery': 4, 'bowling_alley': 4,
    'campground': 4, 'casino': 4, 'movie_theater': 4, 'museum': 4,
    'night_club': 4, 'park': 4, 'rv_park': 4, 'stadium': 4, 'tourist_attraction': 4, 'zoo': 4,
    'accounting': 5, 'atm': 5, 'bank': 5, 'finance': 5,
    'insurance_agency': 5, 'lawyer': 5, 'real_estate_agency': 5, 'travel_agency': 5,
    'library': 6, 'primary_school': 6, 'school': 6, 'secondary_school': 6, 'university': 6,
    'car_repair': 7, 'car_wash': 7, 'electrician': 7, 'funeral_home': 7,
    'general_contractor': 7, 'laundry': 7, 'locksmith': 7, 'moving_company': 7,
    'painter': 7, 'parking': 7, 'plumber': 7, 'post_office': 7,
    'roofing_contractor': 7, 'storage': 7,
}

SECTOR_NAMES = ['Desconocido', 'Alimentos y Bebidas', 'Retail y Conveniencia',
                'Salud y Bienestar', 'Entretenimiento', 'Finanzas y Servicios',
                'Educación', 'Servicios y Mantenimiento']

CATEGORIES_FOR_SIMULATOR = ['restaurant', 'cafe', 'bar', 'bakery', 'gym', 'pharmacy', 'beauty_salon',
    'spa', 'supermarket', 'convenience_store', 'clothing_store', 'electronics_store',
    'bank', 'school', 'parking', 'car_repair', 'laundry', 'doctor', 'dentist',
    'hospital', 'book_store', 'hardware_store', 'pet_store', 'park', 'movie_theater',
    'shopping_mall', 'liquor_store', 'lawyer', 'accounting', 'travel_agency']

engine = create_engine(DATABASE_URL)

print("=" * 60)
print("PIPELINE DE ENTRENAMIENTO + EVALUACIÓN")
print("=" * 60)

print("\n[1] Cargando datos desde PostgreSQL...")
with engine.connect() as conn:
    places = pd.read_sql_query("""
        SELECT p.place_id, p.latitud, p.longitud, p.rating, p.user_ratings_total,
               p.id_colonia, p.cluster_espacial
        FROM places p
        WHERE p.rating IS NOT NULL AND p.latitud IS NOT NULL AND p.longitud IS NOT NULL
    """, conn)
    cats = pd.read_sql_query("SELECT place_id, category FROM place_categories", conn)
    colonias_agg = pd.read_sql_query("""
        SELECT p.id_colonia,
               COUNT(*)::INT AS colonia_place_count,
               ROUND(AVG(p.rating)::numeric, 2) AS colonia_avg_rating,
               ROUND(AVG(p.user_ratings_total)::numeric, 0) AS colonia_avg_traffic
        FROM places p WHERE p.id_colonia IS NOT NULL AND p.rating IS NOT NULL
        GROUP BY p.id_colonia
    """, conn)

print(f"  {len(places)} lugares, {len(colonias_agg)} colonias")

print("\n[2] Feature engineering...")
df = places.copy()
df['rating'] = df['rating'].astype(float)
df['user_ratings_total'] = df['user_ratings_total'].fillna(0).astype(float)
df['composite_score'] = df['rating'] * np.log(df['user_ratings_total'] + 1)
df['log_traffic'] = np.log(df['user_ratings_total'] + 1)

df = df.join(colonias_agg.set_index('id_colonia'), on='id_colonia', how='left')
df['colonia_place_count'] = df['colonia_place_count'].fillna(1)
df['colonia_avg_rating'] = df['colonia_avg_rating'].fillna(df['rating'].mean())
df['colonia_avg_traffic'] = df['colonia_avg_traffic'].fillna(0)

coords = df[['latitud', 'longitud']].values
tree = KDTree(coords)
df['nearby_places_500m'] = tree.query_ball_point(coords, r=500/111320.0, return_length=True)
df['nearby_places_1km'] = tree.query_ball_point(coords, r=1000/111320.0, return_length=True)
df['nearby_places_2km'] = tree.query_ball_point(coords, r=2000/111320.0, return_length=True)
df['density_500m'] = df['nearby_places_500m'] / (np.pi * 0.25)
df['density_1km'] = df['nearby_places_1km'] / (np.pi * 1.0)

cat_place_to_sector = {}
for _, row in cats.iterrows():
    s = SECTOR_MAP.get(row['category'], 0)
    if 1 <= s <= 7 and row['place_id'] not in cat_place_to_sector:
        cat_place_to_sector[row['place_id']] = s

sector_map_df = pd.DataFrame(list(cat_place_to_sector.items()), columns=['place_id', 'primary_sector'])
df = df.merge(sector_map_df, on='place_id', how='left')
df['primary_sector'] = df['primary_sector'].fillna(0).astype(int)

top20_cats = cats['category'].value_counts().head(20).index.tolist()
cat_pivot = pd.crosstab(cats['place_id'], cats['category']).reindex(columns=top20_cats, fill_value=0)
cat_pivot = cat_pivot.add_prefix('cat_')
df = df.merge(cat_pivot, left_on='place_id', right_index=True, how='left')
for col in cat_pivot.columns:
    df[col] = df[col].fillna(0).astype(int)

sector_dummies = pd.get_dummies(df['primary_sector'], prefix='sector')
sector_dummies = sector_dummies.drop(columns=[c for c in sector_dummies.columns if c.endswith('_0')], errors='ignore')
df = pd.concat([df, sector_dummies], axis=1)

base_features = ['latitud', 'longitud', 'colonia_avg_rating', 'colonia_place_count',
                 'colonia_avg_traffic', 'nearby_places_500m', 'nearby_places_1km',
                 'nearby_places_2km', 'density_500m', 'density_1km']
sector_cols = [c for c in sector_dummies.columns.tolist()]
cat_cols = [c for c in cat_pivot.columns.tolist()]
feature_cols = base_features + sector_cols + cat_cols

print(f"  Features: {len(feature_cols)} ({len(base_features)} base + {len(sector_cols)} sectores + {len(cat_cols)} categorías)")

X = df[feature_cols].fillna(0).values
y_composite = df['composite_score'].values
y_log_traffic = df['log_traffic'].values
y_rating = df['rating'].values

X_train, X_test, yc_train, yc_test, yt_train, yt_test, yr_train, yr_test = train_test_split(
    X, y_composite, y_log_traffic, y_rating, test_size=0.2, random_state=42
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Save training coordinates for prediction KDTree
np.save(os.path.join(MODEL_DIR, 'train_coords.npy'), df[['latitud', 'longitud']].values)

print("\n[3] Baseline: predecir media de la colonia...")
df_full = df.copy()
baseline_pred = np.zeros(len(yc_test))
for i, idx in enumerate(range(len(yc_train), len(yc_train) + len(yc_test))):
    row = df_full.iloc[idx]
    cr = row['colonia_avg_rating'] if pd.notna(row['colonia_avg_rating']) else yc_train.mean()
    ct = row['colonia_avg_traffic'] if pd.notna(row['colonia_avg_traffic']) else 0
    baseline_pred[i] = cr * np.log(max(ct, 0) + 1)
baseline_rmse = np.sqrt(mean_squared_error(yc_test, baseline_pred))
baseline_mae = mean_absolute_error(yc_test, baseline_pred)
baseline_r2 = r2_score(yc_test, baseline_pred)
print(f"  Baseline R²={baseline_r2:.4f}  RMSE={baseline_rmse:.2f}  MAE={baseline_mae:.2f}")

print("\n[4] Ridge Regression + PolynomialFeatures...")
poly = PolynomialFeatures(degree=2, include_bias=False)
X_train_poly = poly.fit_transform(X_train_scaled)
X_test_poly = poly.transform(X_test_scaled)

ridge = Ridge(alpha=10.0)
ridge.fit(X_train_poly, yc_train)
ridge_pred = ridge.predict(X_test_poly)
ridge_r2 = r2_score(yc_test, ridge_pred)
ridge_rmse = np.sqrt(mean_squared_error(yc_test, ridge_pred))
ridge_mae = mean_absolute_error(yc_test, ridge_pred)
print(f"  Ridge    R²={ridge_r2:.4f}  RMSE={ridge_rmse:.2f}  MAE={ridge_mae:.2f}")

print("\n[5] Random Forest...")
rf = RandomForestRegressor(n_estimators=100, max_depth=12, min_samples_leaf=10,
                            random_state=42, n_jobs=-1, max_features='sqrt')
rf.fit(X_train_scaled, yc_train)
rf_pred = rf.predict(X_test_scaled)
rf_r2 = r2_score(yc_test, rf_pred)
rf_rmse = np.sqrt(mean_squared_error(yc_test, rf_pred))
rf_mae = mean_absolute_error(yc_test, rf_pred)
print(f"  RF       R²={rf_r2:.4f}  RMSE={rf_rmse:.2f}  MAE={rf_mae:.2f}")

print(f"\n  Mejora vs baseline: Ridge {((ridge_r2-baseline_r2)/abs(baseline_r2+0.001))*100:.0f}%, RF {((rf_r2-baseline_r2)/abs(baseline_r2+0.001))*100:.0f}%")

print("\n[6] Error por macrosector...")
df_test_sectors = df.iloc[len(yc_train):len(yc_train)+len(yc_test)]['primary_sector'].values
sector_errors = {}
for s in range(8):
    mask = (df_test_sectors == s) if s > 0 else np.ones(len(yc_test), dtype=bool)
    n = mask.sum()
    if n > 10:
            sector_errors[SECTOR_NAMES[s]] = {
                'count': int(n),
                'rf_rmse': round(np.sqrt(mean_squared_error(yc_test[mask], rf_pred[mask])), 2),
                'rf_mae': round(mean_absolute_error(yc_test[mask], rf_pred[mask]), 2),
                'baseline_rmse': round(np.sqrt(mean_squared_error(
                    yc_test[mask], baseline_pred[mask])), 2),
            }
for name, err in sorted(sector_errors.items(), key=lambda x: x[1]['rf_rmse']):
    print(f"  {name}: RMSE={err['rf_rmse']} (base={err['baseline_rmse']}) n={err['count']}")

print("\n[7] Feature importance (Random Forest)...")
rf_importance = sorted(zip(feature_cols, rf.feature_importances_), key=lambda x: x[1], reverse=True)
for name, imp in rf_importance[:12]:
    bar = '█' * int(imp * 100)
    print(f"  {name:35s} {imp:.4f} {bar}")

print(f"\n[8] Seleccionando mejor modelo: {'Random Forest' if rf_r2 > ridge_r2 else 'Ridge'}")
best_model = rf if rf_r2 > ridge_r2 else ridge
use_poly = rf_r2 <= ridge_r2
best_r2 = max(rf_r2, ridge_r2)
best_rmse = rf_rmse if rf_r2 > ridge_r2 else ridge_rmse
best_mae = rf_mae if rf_r2 > ridge_r2 else ridge_mae
best_method = 'RandomForest' if rf_r2 > ridge_r2 else 'Ridge+Poly'

print(f"\n[9] Guardando modelo ({best_method})...")
joblib.dump(best_model, os.path.join(MODEL_DIR, 'best_model.pkl'))
joblib.dump(scaler, os.path.join(MODEL_DIR, 'scaler.pkl'))
if use_poly:
    joblib.dump(poly, os.path.join(MODEL_DIR, 'poly.pkl'))

metadata = {
    'model': best_method,
    'r2': round(best_r2, 4),
    'rmse': round(best_rmse, 2),
    'mae': round(best_mae if best_method == 'RandomForest' else ridge_mae, 2),
    'baseline_r2': round(baseline_r2, 4),
    'baseline_rmse': round(baseline_rmse, 2),
    'baseline_mae': round(baseline_mae, 2),
    'ridge_r2': round(ridge_r2, 4),
    'rf_r2': round(rf_r2, 4),
    'target': 'composite_score',
    'target_formula': 'rating * log(user_ratings_total + 1)',
    'target_range': {'min': round(float(y_composite.min()), 2), 'max': round(float(y_composite.max()), 2)},
    'samples': len(df),
    'features': feature_cols,
    'feature_count': len(feature_cols),
    'simulator_categories': CATEGORIES_FOR_SIMULATOR,
    'sector_errors': sector_errors,
    'rf_top_features': [{'name': n, 'importance': round(i, 4)} for n, i in rf_importance[:15]],
    'confidence_68': round(best_rmse, 2),
    'confidence_95': round(best_rmse * 1.96, 2),
}

with open(os.path.join(MODEL_DIR, 'model_info.json'), 'w') as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

colonias_agg.to_json(os.path.join(MODEL_DIR, 'colonias_agg.json'), orient='records')

print(f"\n{'='*60}")
print("RESUMEN FINAL")
print(f"{'='*60}")
print(f"  Modelo:        {best_method}")
print(f"  R²:            {best_r2:.4f}")
print(f"  RMSE:          {best_rmse:.2f}")
print(f"  Baseline R²:   {baseline_r2:.4f}")
print(f"  Mejora:        {((best_r2-baseline_r2)/abs(baseline_r2+0.001))*100:.0f}% vs baseline")
print(f"  Intervalo 68%: ±{best_rmse:.1f}")
print(f"  Intervalo 95%: ±{best_rmse*1.96:.1f}")
print(f"\n  Modelo + métricas guardados en {MODEL_DIR}/")
