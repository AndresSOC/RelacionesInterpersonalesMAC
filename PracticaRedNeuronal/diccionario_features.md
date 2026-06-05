# Diccionario de Features - California Housing

## Features Originales (8)

| Feature | Tipo | Descripción | Rango |
|---------|------|-----------|-------|
| `HouseAge` | Numérico | Edad de la vivienda en años | 1-52 |
| `AveRooms` | Numérico | Promedio de cuartos por vivienda | 1.0-141.0 |
| `AveBedrms` | Numérico | Promedio de dormitorios por vivienda | 0.3-34.0 |
| `Population` | Numérico | Población en el bloque censal | 3-35682 |
| `AveOccup` | Numérico | Promedio de ocupantes por vivienda | 0.7-55.2 |
| `MedInc` | Numérico | Ingreso medio en unidades de $10,000 | 0.5-15.0 |
| `Latitude` | Numérico | Latitud de la ubicación | 32.5-41.9 |
| `Longitude` | Numérico | Longitud de la ubicación | -124.4 a -114.1 |

---
## Features Engineered (8 nuevas)

| Feature | Tipo | Fórmula | Rango | Por qué importa |
|---------|------|---------|-------|-----------------|
| `RoomsPerBedroom` | Ratio | `AveRooms / AveBedrms` | ~0.5-50+ | Tamaño promedio de la vivienda → casas grandes = más valor |
| `BedroomRatio` | Ratio | `AveBedrms / AveRooms` | ~0.02-2.0 | Proporción dormitorios → más dormitorios = más atractivo |
| `IncomePerRoom` | Ratio | `MedInc / AveRooms` | Varía | Riqueza ajustada → casa pequeña en área rica > casa grande pobre |
| `IncomePerPerson` | Ratio | `MedInc / AveOccup` | ~0.1-20+ | Poder adquisitivo → ingreso per cápita de habitantes |
| `PopPerRoom` | Densidad | `AveOccup / AveRooms` | ~0.1-10+ | ocupantes por cuarto → aglomeración reduce precio |
| `HouseAge_sq` | Polinomial | `HouseAge ** 2` | 1-2704 | Efecto no-lineal → depreciación acelerada con edad |
| `LatLon` | Interacción | `Latitude * Longitude` | ~-5000 a -3700 | Ubicación combinada → zonas especiales (Bay Area) |
| `NearCoast` | Binaria (0/1) | `(Lat > 37.5) & (Lon < -121.5)` | 0 o 1 | Cercanía costa → premium de precio |

---

## Resumen Estadístico

| Aspecto | Total Features | Originales | Nuevas |
|---------|---|---|---|
| **Cantidad** | 16 | 8 | 8 |
| **Numéricos** | 15 | 8 | 7 |
| **Binarios** | 1 | 0 | 1 |
| **Ratios/Proporciones** | 5 | 0 | 5 |
| **Polinomiales** | 1 | 0 | 1 |
| **Interacciones** | 1 | 0 | 1 |
| **Indicadores** | 1 | 0 | 1 |

---

## Correlación Esperada con Target

**Correlación Positiva Fuerte:**
- `MedInc` (ingreso) → muy correlacionado
- `IncomePerRoom` → captura riqueza ajustada
- `IncomePerPerson` → poder adquisitivo

**Correlación Positiva Moderada:**
- `Latitude` → cercanía costa
- `NearCoast` → premium de costa

**Correlación Negativa:**
- `HouseAge` / `HouseAge_sq` → casas viejas = menos caras
- `PopPerRoom` → hacinamiento = menos atractivo

**Correlación Débil o Nula:**
- `BedroomRatio` (puede variar según preferencias)
- `Population` (depende del contexto)

---

## Notas de Uso

- **Escalado:** Features deben escalarse (StandardScaler) antes de modelos sensibles a escala (Ridge, SVM, NN)
- **Multicolinealidad:** `RoomsPerBedroom` y `BedroomRatio` son inversas, considera usar una sola
- **Valores extremos:** `AveRooms`, `AveBedrms` pueden tener outliers → verificar antes de usar
- **Variables categóricas:** `NearCoast` ya está en formato 0/1, no requiere encoding adicional