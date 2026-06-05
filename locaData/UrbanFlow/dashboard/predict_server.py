import json
import os
import sys
import numpy as np
import joblib
from flask import Flask, request, jsonify

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')

model = joblib.load(os.path.join(MODEL_DIR, 'best_model.pkl'))
scaler = joblib.load(os.path.join(MODEL_DIR, 'scaler.pkl'))
train_coords = np.load(os.path.join(MODEL_DIR, 'train_coords.npy'))

with open(os.path.join(MODEL_DIR, 'model_info.json')) as f:
    model_info = json.load(f)

colonia_df = None
colonias_json = os.path.join(MODEL_DIR, 'colonias_agg.json')
if os.path.exists(colonias_json):
    with open(colonias_json) as f:
        colonia_list = json.load(f)
    import pandas as pd
    colonia_df = pd.DataFrame(colonia_list).set_index('id_colonia')

feature_names = model_info['features']
simulator_cats = model_info['simulator_categories']
use_poly = os.path.exists(os.path.join(MODEL_DIR, 'poly.pkl'))
poly = joblib.load(os.path.join(MODEL_DIR, 'poly.pkl')) if use_poly else None

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

TOP20_CATS = ['establishment', 'point_of_interest', 'store', 'food', 'health',
              'restaurant', 'home_goods_store', 'lodging', 'finance', 'pharmacy',
              'school', 'grocery_or_supermarket', 'car_repair', 'place_of_worship',
              'convenience_store', 'transit_station', 'clothing_store', 'general_contractor',
              'doctor', 'church']

from scipy.spatial import KDTree
tree = KDTree(np.radians(train_coords))

app = Flask(__name__)

def build_features(lat, lon, category):
    sector = SECTOR_MAP.get(category, 0)

    point_rad = np.radians([[lat, lon]])
    distances, indices = tree.query(point_rad, k=100)
    nearby_500m = np.sum(distances[0] * 6371000 < 500)
    nearby_1km = np.sum(distances[0] * 6371000 < 1000)
    nearby_2km = np.sum(distances[0] * 6371000 < 2000)
    density_500m = nearby_500m / (np.pi * 0.25)
    density_1km = nearby_1km / (np.pi * 1.0)

    colonia_avg_rating = 4.17
    colonia_place_count = 1
    colonia_avg_traffic = 0
    if colonia_df is not None:
        nearby_idx = indices[0][0]
        nearby_lat, nearby_lon = train_coords[nearby_idx]
        min_dist = distances[0][0] * 6371000
        if min_dist < 1000:
            colonia_avg_rating = 4.17
            colonia_place_count = max(1, nearby_1km)

    features = [lat, lon, colonia_avg_rating, colonia_place_count,
                colonia_avg_traffic, nearby_500m, nearby_1km,
                nearby_2km, density_500m, density_1km]

    for s in range(1, 8):
        features.append(1.0 if sector == s else 0.0)

    for cat_name in TOP20_CATS:
        features.append(1.0 if category == cat_name else 0.0)

    return np.array(features).reshape(1, -1)

@app.route('/api/predict', methods=['POST'])
def predict():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    lat = data.get('lat')
    lon = data.get('lon')
    category = data.get('category')

    if not all([lat, lon, category]):
        return jsonify({'error': 'lat, lon, category required'}), 400

    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return jsonify({'error': 'lat, lon must be numbers'}), 400

    if category not in simulator_cats:
        return jsonify({'error': f'category not in list. Use: {simulator_cats[:10]}...'}), 400

    import math
    center_lat, center_lon = 19.3048, -99.1895
    dlat = math.radians(lat - center_lat)
    dlon = math.radians(lon - center_lon)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(center_lat)) * math.cos(math.radians(lat)) * math.sin(dlon/2)**2
    dist_m = 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    if dist_m > 20000:
        return jsonify({'error': f'Point {dist_m/1000:.1f}km from center. Max: 20km'}), 400

    X = build_features(lat, lon, category)
    X_scaled = scaler.transform(X)

    if use_poly and poly is not None:
        X_transformed = poly.transform(X_scaled)
    else:
        X_transformed = X_scaled

    composite_score = float(model.predict(X_transformed)[0])
    composite_score = max(0.5, min(composite_score, model_info['target_range']['max']))

    rmse = model_info['rmse']
    predicted_rating = min(5.0, max(1.0, composite_score / 3.5))
    predicted_traffic = int(np.exp(min(composite_score / max(predicted_rating, 0.5), 12)) - 1)

    if hasattr(model, 'feature_importances_'):
        contributions = get_rf_contributions(X, X_scaled, X_transformed, composite_score)
    else:
        contributions = get_ridge_contributions(X, X_transformed, composite_score)

    return jsonify({
        'composite_score': round(composite_score, 2),
        'predicted_rating': round(predicted_rating, 2),
        'predicted_traffic': predicted_traffic,
        'confidence_68_low': round(max(0.5, composite_score - rmse), 2),
        'confidence_68_high': round(composite_score + rmse, 2),
        'confidence_95_low': round(max(0.5, composite_score - rmse * 1.96), 2),
        'confidence_95_high': round(composite_score + rmse * 1.96, 2),
        'rmse': round(rmse, 2),
        'factors': contributions,
        'input': {'lat': lat, 'lon': lon, 'category': category},
    })

def get_rf_contributions(X, X_scaled, X_transformed, composite_score):
    contributions = []
    for i, name in enumerate(feature_names):
        val = X[0][i]
        contrib = float(model.feature_importances_[i]) * float(val) * 5.0
        if abs(contrib) > 0.01:
            contributions.append({
                'feature': name, 'value': round(float(val), 4),
                'contribution': round(contrib, 2)
            })
    contributions.sort(key=lambda x: abs(x['contribution']), reverse=True)
    return contributions[:8]

def get_ridge_contributions(X, X_transformed, composite_score):
    contributions = []
    poly_names = poly.get_feature_names_out(feature_names)
    for i, (name, val) in enumerate(zip(poly_names, X_transformed[0])):
        coef = float(model.coef_[i])
        contrib = coef * val
        if abs(contrib) > 0.05:
            contributions.append({
                'feature': name, 'value': round(float(val), 4),
                'contribution': round(contrib, 2)
            })
    contributions.sort(key=lambda x: abs(x['contribution']), reverse=True)
    return contributions[:8]

@app.route('/api/model-info', methods=['GET'])
def model_info_route():
    return jsonify(model_info)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'model': model_info['model']})

@app.route('/api/categories', methods=['GET'])
def categories():
    return jsonify(simulator_cats)

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    print(f"locadata Predict API ({model_info['model']}) en http://localhost:{port}")
    app.run(host='127.0.0.1', port=port, debug=False)
