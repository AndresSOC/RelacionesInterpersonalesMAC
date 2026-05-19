import requests
import time
import math
import pandas as pd
from sqlalchemy import create_engine, text
from config import API_KEY, URL_NEARBY, DATABASE_URL

# Coordenadas iniciales (Cruce Perisur / Cuicuilco)
latitud = 19.3048
longitud = -99.1895

# Los 29 giros comerciales para facilitar la clusterización
categorias_negocio = [
    # Comida y Bebida
    'restaurant', 'cafe', 'bar', 'bakery',
    'supermarket', 'convenience_store', 'liquor_store',
    # Comercio (Retail)
    'clothing_store', 'shoe_store', 'electronics_store',
    'shopping_mall', 'department_store', 'hardware_store', 'book_store',
    # Cuidado Personal y Salud
    'gym', 'pharmacy', 'beauty_salon', 'spa',
    # Entretenimiento y Ocio
    'movie_theater', 'night_club', 'bowling_alley', 'park',
    # Servicios y Anclas
    'bank', 'atm', 'school', 'university',
    'laundry', 'car_repair', 'parking'
]

meta_datos = 10
todos_los_lugares = []
circulos_explorados = 0

# Variables trigonométricas para la espiral
lat_centro = latitud
lng_centro = longitud
angulo = 0.0
paso_apertura = 0.004

# Filtro en tiempo real para evitar duplicados (el identificador único de Google)
ids_vistos = set()

print(f"Iniciando extracción en espiral. Meta: {meta_datos} lugares únicos...\n")

while len(todos_los_lugares) < meta_datos:
    circulos_explorados += 1
    print(f"Explorando círculo #{circulos_explorados} | Lat: {latitud:.4f}, Lng: {longitud:.4f}")

    # Iteramos sobre nuestra lista de categorías en este mismo círculo
    for categoria in categorias_negocio:

        # Freno de seguridad por si alcanzamos la meta en medio de las categorías
        if len(todos_los_lugares) >= meta_datos:
            break

        parametros = {
            'location': f"{latitud},{longitud}",
            'radius': 1000,
            'type': categoria,
            'key': API_KEY
        }

        respuesta = requests.get(URL_NEARBY, params=parametros)

        if respuesta.status_code == 200:
            datos = respuesta.json()
            lugares_obtenidos = datos.get('results', [])

            # Filtramos antes de guardar
            for lugar in lugares_obtenidos:
                id_unico = lugar.get('place_id')
                if id_unico not in ids_vistos:
                    ids_vistos.add(id_unico)
                    # Le inyectamos la categoría que buscamos para tenerla clara en el CSV
                    lugar['categoria_buscada'] = categoria
                    todos_los_lugares.append(lugar)

            # Paginador para esta categoría específica
            while 'next_page_token' in datos and len(todos_los_lugares) < meta_datos:
                time.sleep(2)
                parametros_pagina = {
                    'pagetoken': datos['next_page_token'],
                    'key': API_KEY
                }
                respuesta = requests.get(URL_NEARBY, params=parametros_pagina)
                datos = respuesta.json()
                lugares_obtenidos = datos.get('results', [])

                for lugar in lugares_obtenidos:
                    id_unico = lugar.get('place_id')
                    if id_unico not in ids_vistos:
                        ids_vistos.add(id_unico)
                        lugar['categoria_buscada'] = categoria
                        todos_los_lugares.append(lugar)

    # Matemáticas para mover el centro del círculo en forma de espiral al terminar las categorías
    angulo += 1.0
    radio_espiral = paso_apertura * angulo
    latitud = lat_centro + (radio_espiral * math.cos(angulo))
    longitud = lng_centro + (radio_espiral * math.sin(angulo))

    print(f"   -> Llevamos {len(todos_los_lugares)} lugares ÚNICOS recolectados.\n")

print(f"¡Extracción terminada! Total recolectado: {len(todos_los_lugares)}")


# Convertimos la lista en DataFrame
df_lugares = pd.DataFrame(todos_los_lugares)

# Renombramos 'name' de la API a 'business_name' del esquema SQL
if 'name' in df_lugares.columns:
    df_lugares.rename(columns={'name': 'business_name'}, inplace=True)

# Convertimos 'types' de lista Python a string separado por comas
if 'types' in df_lugares.columns:
    df_lugares['types'] = df_lugares['types'].apply(
        lambda x: ', '.join(x) if isinstance(x, list) else str(x) if x is not None else None
    )

# Separamos las coordenadas
# Usamos funciones lambda para entrar al diccionario y extraer solo los números
df_lugares['latitud'] = df_lugares['geometry'].apply(lambda x: x.get('location', {}).get('lat') if isinstance(x, dict) else None)
df_lugares['longitud'] = df_lugares['geometry'].apply(lambda x: x.get('location', {}).get('lng') if isinstance(x, dict) else None)


# Definimos las columnas útiles (cambiamos 'geometry' por nuestras dos columnas nuevas)
columnas_utiles = [
    'place_id',
    'business_name',
    'categoria_buscada',
    'types',
    'rating',
    'user_ratings_total',
    'price_level',
    'vicinity',
    'latitud',           # <-- ¡Nueva y limpia!
    'longitud',          # <-- ¡Nueva y limpia!
    'business_status'
]

# Filtramos la tabla
columnas_existentes = [col for col in columnas_utiles if col in df_lugares.columns]
df_limpio = df_lugares[columnas_existentes]

print(f"Tabla lista y limpia con {len(df_limpio)} lugares.")

# 4. Insertamos en PostgreSQL
engine = create_engine(DATABASE_URL)

with open('../database/init.sql', 'r') as f:
    init_sql = f.read()
with engine.connect() as conn:
    conn.execute(text(init_sql))
    conn.commit()

df_limpio.to_sql('mapsapi', engine, if_exists='append', index=False)

print(f"¡{len(df_limpio)} registros insertados en la tabla 'mapsapi' de PostgreSQL!")
df_limpio.head(3)