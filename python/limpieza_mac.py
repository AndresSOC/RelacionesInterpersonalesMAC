import pandas as pd
import re

# Leer csv
ruta_archivo = '../documents/data/mac(Carrera4años).csv'
df = pd.read_csv(ruta_archivo)
df = df.drop(0).reset_index(drop=True)

# Renombrar las columnas
nuevos_nombres = [
    'fecha_registro', 'num_cuenta', 'edad', 'genero', 'generacion',
    'materias_dificiles', 'materias_adeudadas', 'trabajo_actual',
    'vive_lejos', 'otras_actividades', 'considera_cambio_carrera',
    'accesibilidad_profesores', 'preferencia_seriacion',
    'propuestas_titulacion', 'influencia_economica',
    'afectacion_pandemia', 'factor_paros'
]
df.columns = nuevos_nombres
df['num_cuenta'] = pd.to_numeric(df['num_cuenta'], errors='coerce').astype('Int64').astype(str)

# Bloque de limpieza
df['generacion'] = df['generacion'].astype(str).str[:4]

def clasificar_accesibilidad(texto):
    t = str(texto).lower().strip()
    if any(x in t for x in ['poco', 'estrictos', 'no destacan', 'no son muy flexibles', 'nada', 'muy poco']): return 0
    elif any(x in t for x in ['mucho', 'muy', 'bastante', 'lo suficiente']) and 'pero no todos' not in t and 'algunos' not in t: return 2
    else: return 1
df['accesibilidad_profesores'] = df['accesibilidad_profesores'].apply(clasificar_accesibilidad)

def contar_adeudos(texto):
    t = str(texto).lower().strip()
    if not t or t == 'nan' or (len(t) < 2 and not t.isdigit()): return 0
    if any(p in t for p in ['ningun', 'nada', '0', 'no debo', 'nignuna', 'limpio']): return 0
    if 'ecuaciones diferenciales las 2 \n3 optativas\noptimizacion' in t: return 6
    if t == '2': return 2
    return 1 + t.count(' y ') + t.count(',') + t.count('\n')
df['materias_adeudadas'] = df['materias_adeudadas'].apply(contar_adeudos)

def extraer_materias(texto):
    t = str(texto).lower()
    m = []
    if 'calculo' in t or 'cálculo' in t: m.append('Cálculo')
    if 'algebra' in t or 'álgebra' in t: m.append('Álgebra')
    if 'ed ' in t or 'ed2' in t or 'ecuaciones' in t: m.append('Ecuaciones Diferenciales')
    if 'programacion' in t or 'programación' in t: m.append('Programación')
    if 'optimiz' in t or 'opti' in t: m.append('Optimización')
    if 'estad' in t or 'estoc' in t: m.append('Estadística/Estocásticos')
    return ', '.join(m) if m else ('Ninguna' if 'ninguna' in t else 'Otras')
df['materias_dificiles'] = df['materias_dificiles'].apply(extraer_materias)

def limpiar_genero(g):
    g = str(g).lower().strip()
    if 'mujer' in g: return 2
    elif 'hombre' in g: return 1
    else: return 0
df['genero'] = df['genero'].apply(limpiar_genero)

# Seriacion o candado
def limpiar_seriacion(texto):
    t = str(texto).lower().strip()
    # Si menciona candado, lo tomamos como su preferencia principal
    if 'candado' in t:
        return 1
    # En cualquier otro caso (menciona seriación), lo ponemos como 0
    else:
        return 0

df['preferencia_seriacion'] = df['preferencia_seriacion'].apply(limpiar_seriacion)

#Hacer binarias las columnas de si y no
def a_binario(texto):
    t = str(texto).lower().strip()
    if any(x in t for x in ['no', 'negativo', 'actualmente no', 'ninguna', 'para nada']) and 'no mucho' not in t:
        if t.startswith('no') or 'diría que no' in t: return 0
    return 1
cols_bin = ['trabajo_actual', 'vive_lejos', 'otras_actividades', 'considera_cambio_carrera', 'influencia_economica', 'afectacion_pandemia', 'factor_paros']
for col in cols_bin: df[col] = df[col].apply(a_binario)

# Guardar la limpieza en otro csv
ruta_salida = '../documents/data/clean/limpieza-mac-carrera4.csv'
df.to_csv(ruta_salida, index=False)

print(f"¡Guardado con éxito en la ruta {ruta_salida}!")
print(df[['num_cuenta', 'materias_adeudadas', 'materias_dificiles', 'accesibilidad_profesores']].head(10))