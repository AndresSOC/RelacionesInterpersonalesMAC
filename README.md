```bash
# Crear el ambiente virtual DENTRO DE LA CARPETA PYTHON

python3 -m venv .venv

# Activar el ambiente virtual
source .venv/bin/activate

#Para desactivarlo

deactivate

#Instalar requerimientos

pip install -r requirements.txt

# levantar contenedores (postgres + pgadmin)
docker compose up -d --build

# ver estado
docker compose ps
```