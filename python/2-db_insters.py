from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


user = "postgres"
password = "postgres"
host = "localhost"
port = "5440"
database = "interpersonalrelation"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CLEAN_INPUT_PATH = PROJECT_ROOT / "documents" / "data" / "RelacionesPersonales(limpio).csv"


def get_connection(db_user, db_password, db_host, db_port, db_name):
    return create_engine(
        url="postgresql+psycopg2://{0}:{1}@{2}:{3}/{4}".format(
            db_user,
            db_password,
            db_host,
            db_port,
            db_name,
        )
    )


def nullable_int(value):
    if pd.isna(value):
        return None
    return int(value)


def nullable_bool(value):
    if pd.isna(value):
        return None
    return bool(int(value))


def load_clean_dataframe(path=CLEAN_INPUT_PATH):
    df = pd.read_csv(path)

    int_columns = [
        "num_cuenta",
        "habilidadSocial",
        "amigos",
        "noviazgo",
        "enfoque",
        "colaborativo",
        "tiempoSoltero",
        "participacion",
        "comunicacion",
        "integracion",
        "energiaInterpersonal",
    ]
    for col in int_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    return df


def upsert_relaciones_data(engine, df):
    upsert_vinculacion = text(
        """
        INSERT INTO vinculacion_afectiva (vinculacionAfectiva, confianzaInterpersonal, noviazgo, tiempoSoltero)
        VALUES (:id, :confianza, :noviazgo, :tiempo_soltero)
        ON CONFLICT (vinculacionAfectiva) DO UPDATE
        SET confianzaInterpersonal = EXCLUDED.confianzaInterpersonal,
            noviazgo = EXCLUDED.noviazgo,
            tiempoSoltero = EXCLUDED.tiempoSoltero
        """
    )

    upsert_sociabilidad = text(
        """
        INSERT INTO sociabilidad (perfilSocial, habilidadSocial, amigos, energiaInterpersonal)
        VALUES (:id, :habilidad, :amigos, :energia)
        ON CONFLICT (perfilSocial) DO UPDATE
        SET habilidadSocial = EXCLUDED.habilidadSocial,
            amigos = EXCLUDED.amigos,
            energiaInterpersonal = EXCLUDED.energiaInterpersonal
        """
    )

    upsert_estilo_vida = text(
        """
        INSERT INTO estilo_vida (estiloVida, enfoque, tiempoLibre)
        VALUES (:id, :enfoque, :tiempo_libre)
        ON CONFLICT (estiloVida) DO UPDATE
        SET enfoque = EXCLUDED.enfoque,
            tiempoLibre = EXCLUDED.tiempoLibre
        """
    )

    upsert_colaboracion = text(
        """
        INSERT INTO colaboracion (colaboracion, colaborativo, integracion, participacion)
        VALUES (:id, :colaborativo, :integracion, :participacion)
        ON CONFLICT (colaboracion) DO UPDATE
        SET colaborativo = EXCLUDED.colaborativo,
            integracion = EXCLUDED.integracion,
            participacion = EXCLUDED.participacion
        """
    )

    upsert_comunicacion = text(
        """
        INSERT INTO estilo_comunicacion (comunicacionInterpersonal, comunicacion, inciativaInteraccional)
        VALUES (:id, :comunicacion, :iniciativa)
        ON CONFLICT (comunicacionInterpersonal) DO UPDATE
        SET comunicacion = EXCLUDED.comunicacion,
            inciativaInteraccional = EXCLUDED.inciativaInteraccional
        """
    )

    upsert_relaciones = text(
        """
        INSERT INTO relaciones_intepersonales (
            num_cuenta,
            vinculacionAfectiva,
            perfilSocial,
            estiloVida,
            colaboracion,
            comunicacionIntepersonal
        )
        VALUES (:id, :id, :id, :id, :id, :id)
        ON CONFLICT (num_cuenta) DO UPDATE
        SET vinculacionAfectiva = EXCLUDED.vinculacionAfectiva,
            perfilSocial = EXCLUDED.perfilSocial,
            estiloVida = EXCLUDED.estiloVida,
            colaboracion = EXCLUDED.colaboracion,
            comunicacionIntepersonal = EXCLUDED.comunicacionIntepersonal
        """
    )

    with engine.begin() as connector:
        for row in df.itertuples(index=False):
            row_id = nullable_int(row.num_cuenta)
            if row_id is None:
                continue

            connector.execute(
                upsert_vinculacion,
                {
                    "id": row_id,
                    "confianza": row.confianzaInterpersonal,
                    "noviazgo": nullable_bool(row.noviazgo),
                    "tiempo_soltero": nullable_int(row.tiempoSoltero),
                },
            )

            connector.execute(
                upsert_sociabilidad,
                {
                    "id": row_id,
                    "habilidad": nullable_int(row.habilidadSocial),
                    "amigos": nullable_bool(row.amigos),
                    "energia": nullable_int(row.energiaInterpersonal),
                },
            )

            connector.execute(
                upsert_estilo_vida,
                {
                    "id": row_id,
                    "enfoque": nullable_bool(row.enfoque),
                    "tiempo_libre": row.tiempoLibre,
                },
            )

            connector.execute(
                upsert_colaboracion,
                {
                    "id": row_id,
                    "colaborativo": nullable_bool(row.colaborativo),
                    "integracion": nullable_int(row.integracion),
                    "participacion": nullable_int(row.participacion),
                },
            )

            connector.execute(
                upsert_comunicacion,
                {
                    "id": row_id,
                    "comunicacion": nullable_bool(row.comunicacion),
                    "iniciativa": row.inciativaInteraccional,
                },
            )

            connector.execute(upsert_relaciones, {"id": row_id})


def main():
    engine = get_connection(user, password, host, port, database)
    df = load_clean_dataframe()
    upsert_relaciones_data(engine, df)
    print(f"Datos cargados a PostgreSQL ({host}:{port}/{database})")


if __name__ == "__main__":
    main()
