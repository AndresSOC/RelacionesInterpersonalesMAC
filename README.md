```bash
# Crear el ambiente virtual

python3 -m venv .venv

# Activar el ambiente virtual
source .venv/bin/activate

#Para desactivarlo

deactivate

#Instalar requerimientos

pip install -r requirements.txt

# levantar contenedores (postgres) recomiendo utilizar como manejador DBAVER
docker compose up -d --build

# ver estado
docker compose ps

# El modelo de spaCy se instala junto con requirements.txt
```