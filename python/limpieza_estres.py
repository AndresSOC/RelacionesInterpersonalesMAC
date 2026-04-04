import pandas as pd
import re


df = pd.read_csv(r"C:\Users\artur\RelacionesInterpersonalesMAC\documents\data\EstresAcademico.csv")
 

df = df.drop(index=0).reset_index(drop=True)

# Renombrar columnas que nos sirven
nuevos_nombres = {
    df.columns[1]: 'numero_cuenta',
    df.columns[2]: 'nivel_estres',
    df.columns[5]: 'horas_sueno',
    df.columns[10]: 'horas_relajacion',
    df.columns[11]: 'organizacion_tiempo',
    df.columns[13]: 'apoyo_profesores',
    df.columns[14]: 'dias_recreacion'
}
df = df.rename(columns=nuevos_nombres)

# Limpiar num
def limpiar_numero(valor):
    if pd.isna(valor): return None
    valor = str(valor).lower().strip()
    # Diccionario para números escritos
    texto_a_num = {'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10}
    if valor in texto_a_num: return float(texto_a_num[valor])
    # Extraer el primer número que encuentre (regex)
    match = re.search(r'\d+', valor)
    return float(match.group()) if match else None

#  limpieza columnas seleccionadas
cols_interes = ['nivel_estres', 'horas_sueno', 'horas_relajacion', 'organizacion_tiempo', 'apoyo_profesores', 'dias_recreacion']
for col in cols_interes:
    df[col] = df[col].apply(limpiar_numero)

# Seleccionar solo las variables para el análisis de Relaciones Personales
df_limpio = df[['numero_cuenta'] + cols_interes].copy()

# Eliminar filas con valores nulos en las variables críticas
df_limpio = df_limpio.dropna()

# Guardar el archivo limpio
df_limpio.to_csv('estres_relaciones_limpio.csv', index=False)

print("¡Limpieza completada con éxito!")
print(df_limpio.head())