import pandas as pd

url = "C:\proyectoF\RelacionesInterpersonalesMAC\documents\data\interesesPersonales (DifusionCiencia).csv"

df = pd.read_csv(url)



# =========================
# 2. Exploración básica
# =========================
print("Dimensiones:", df.shape)
print("\nColumnas:", df.columns)
print("\nNulos por columna:\n", df.isnull().sum())

# =========================
# 3. Limpieza de columnas (nombres)
# =========================
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

# =========================
# 4. Eliminar duplicados
# =========================
df = df.drop_duplicates()

# =========================
# 5. Manejo de valores nulos
# =========================
# eliminar filas completamente vacías
df = df.dropna(how='all')

# rellenar valores numéricos con media
for col in df.select_dtypes(include=['float64', 'int64']).columns:
    df[col] = df[col].fillna(df[col].mean())

# rellenar texto con "desconocido"
for col in df.select_dtypes(include=['object']).columns:
    df[col] = df[col].fillna("desconocido")

# =========================
# 6. Limpieza de texto
# =========================
for col in df.select_dtypes(include=['object']).columns:
    df[col] = df[col].str.strip().str.lower()


# =========================
# 9. Guardar archivo limpio
# =========================
df.to_csv("archivo_limpio.csv", index=False)

print("\n✅ Limpieza completada")
print("Nuevo tamaño:", df.shape)

print(df.shape)
print(df.head())