import pandas as pd
from sqlalchemy import create_engine
from config import DATABASE_URL
import math
import pandas as pd
import matplotlib.pyplot as plt

# 1. Conectar a la base de datos PostgreSQL
engine = create_engine(DATABASE_URL)

# 2. Leer los datos desde la tabla mapsapi
print("📡 Conectando a la base de datos...")
df_completo = pd.read_sql_table('mapsapi', con=engine)
print(f"✅ Se cargaron {len(df_completo)} registros de la base de datos.\n")

# 3. Filtramos: Solo negocios con más de 50 reseñas (para asegurar que haya texto jugoso)
df_populares = df_completo[df_completo['user_ratings_total'] >= 50].copy()

# 4. Ordenamos de mayor a menor por número de reseñas y tomamos el Top 2000
df_top = df_populares.sort_values(by='user_ratings_total', ascending=False).head(2000)

print(f"📉 De {len(df_completo)} negocios, nos quedamos con una élite de {len(df_top)} lugares para analizar sus reseñas.")


# Centro
lat_centro = 19.304941
lon_centro = -99.191105

# Helices
distancia_entre_puntos = 800
puntos_por_aspa = 18

METROS_POR_GRADO_LAT = 111320
METROS_POR_GRADO_LON = 111320 * math.cos(math.radians(lat_centro))

nuevas_coordenadas = []
print("Calculando hélice expandida.")

# Algoritmo
desfases = [
    (120, (2 * math.pi) / 3),
    (240, (4 * math.pi) / 3)
]

id_global = 1

for grados, radianes_desfase in desfases:
    for i in range(1, puntos_por_aspa + 1):
        radio_metros = math.sqrt(i) * distancia_entre_puntos
        angulo_original = math.sqrt(i) * math.pi
        angulo_desfasado = angulo_original + radianes_desfase

        desplazamiento_y = radio_metros * math.sin(angulo_desfasado)
        desplazamiento_x = radio_metros * math.cos(angulo_desfasado)

        nueva_lat = lat_centro + (desplazamiento_y / METROS_POR_GRADO_LAT)
        nueva_lon = lon_centro + (desplazamiento_x / METROS_POR_GRADO_LON)

        nuevas_coordenadas.append({
            'id_parche': id_global,
            'brazo': f'Desfase {grados}°',
            'lat_parche': round(nueva_lat, 6),
            'lon_parche': round(nueva_lon, 6)
        })
        id_global += 1

df_parches = pd.DataFrame(nuevas_coordenadas)

# Visual
plt.figure(figsize=(9, 9))
plt.scatter(lon_centro, lat_centro, color='red', marker='*', s=300, label='Origen (Perisur)')

brazo_120 = df_parches[df_parches['brazo'] == 'Desfase 120°']
brazo_240 = df_parches[df_parches['brazo'] == 'Desfase 240°']

plt.scatter(brazo_120['lon_parche'], brazo_120['lat_parche'], color='#00CED1', s=100, label='Brazo Izquierdo (120°)')
plt.scatter(brazo_240['lon_parche'], brazo_240['lat_parche'], color='#FF8C00', s=100, label='Brazo Derecho (240°)')

plt.title('Simulador de Coordenadas: Hélice Expandida (32 Parches)', fontsize=14, fontweight='bold')
plt.xlabel('Longitud')
plt.ylabel('Latitud')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.6)
plt.show()