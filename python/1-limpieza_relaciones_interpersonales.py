import pandas as pd
import spacy
import re
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

INPUT_PATH = PROJECT_ROOT / "documents" / "data" / "RelacionesPersonales.csv"
OUTPUT_CLEAN_PATH = PROJECT_ROOT / "documents" / "data" / "RelacionesPersonales(limpio).csv"
CONFIG_PATH = SCRIPT_DIR / "relaciones_config.json"


def load_config(path):
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    return {
        "semantic_concepts": config.get("semantic_concepts", {}),
        "cleaner_by_column": config.get("cleaner_by_column", {}),
        "int_cast_columns": set(config.get("int_cast_columns", [])),
        "semantic_threshold": float(config.get("semantic_threshold", 0.45)),
        "semantic_max_labels": int(config.get("semantic_max_labels", 3)),
    }


def normalize_text(value):
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().lower().split())


def spacy_clean_text(text, nlp):
    if not text:
        return ""

    doc = nlp(text)
    lemmas = [
        token.lemma_.lower()
        for token in doc
        if token.is_alpha and not token.is_stop and not token.is_punct and not token.like_num
    ]
    return " ".join(lemmas)


def semantic_refine_text(text, concept_docs, nlp, threshold, max_labels):
    if not text:
        return ""

    doc = nlp(text)
    if not doc.vector_norm:
        return text

    scored = []
    for label, concept_doc in concept_docs.items():
        if concept_doc.vector_norm:
            scored.append((label, doc.similarity(concept_doc)))

    scored.sort(key=lambda item: item[1], reverse=True)
    selected = [label for label, score in scored if score >= threshold][:max_labels]

    if selected:
        return ", ".join(selected)
    return text


def clean_habilidad_social(value):
    text = normalize_text(value)
    if not text:
        return pd.NA

    # Prioriza el valor numerico cuando venga en la respuesta.
    if text.isdigit():
        n = int(text)
        return n if 1 <= n <= 5 else pd.NA

    if any(x in text for x in ["muy malo", "nada", "muy poco"]):
        return 1
    if any(x in text for x in ["poco", "no mucho"]):
        return 2
    if any(x in text for x in ["bastante", "excelente", "muy habil", "muy hábil"]):
        return 5
    if any(x in text for x in ["mas o menos", "más o menos", "moderad", "conforme"]):
        return 3
    if any(x in text for x in ["bueno", "buena", "hábil", "habil"]):
        return 4

    return pd.NA


def clean_boolean(value):
    text = normalize_text(value)
    if not text:
        return pd.NA

    if text in {"1", "si", "sí", "s", "true", "verdadero"}:
        return 1
    if text in {"0", "no", "n", "false", "falso"}:
        return 0
    if text.startswith("si") or text.startswith("sí"):
        return 1
    if text.startswith("no"):
        return 0
    return pd.NA


def clean_tiempo_soltero(value):
    text = normalize_text(value)
    if not text:
        return pd.NA

    if "no llevo tiempo" in text:
        return 0

    if any(x in text for x in ["actual", "pareja", "novi", "novio", "novia", "nada"]):
        if any(x in text for x in ["sin pareja", "sin novi", "sin novio", "sin novia"]):
            pass
        else:
            return 0

    rango = re.search(r"(\d+)\s*-\s*(\d+)", text)
    if rango:
        return int(round((int(rango.group(1)) + int(rango.group(2))) / 2))

    meses = re.search(r"(\d+)\s*mes", text)
    if meses:
        return int(round(int(meses.group(1)) / 12))

    numero = re.search(r"\d+(?:\.\d+)?", text)
    if numero:
        return max(0, int(float(numero.group(0))))

    return pd.NA


def clean_participacion(value):
    text = normalize_text(value)
    if not text:
        return pd.NA

    if text in {"0", "1", "2"}:
        return int(text)
    if text == "poco":
        return 0
    if any(x in text for x in ["casi no", "no lo hago", "no mucho"]) or text == "no":
        return 0
    if "a veces" in text:
        return 1
    if any(x in text for x in ["si", "sí"]):
        return 2
    return pd.NA


def clean_comunicacion(value):
    text = normalize_text(value)
    if not text:
        return pd.NA

    if text in {"0", "1"}:
        return int(text)
    if "evitar" in text:
        return 0
    if "depende" in text:
        return 1
    if "mensaje" in text:
        return 0
    if "persona" in text or "direct" in text:
        return 1
    return pd.NA


def clean_integracion(value):
    text = normalize_text(value)
    if not text:
        return pd.NA

    if text.isdigit():
        n = int(text)
        return n if 1 <= n <= 5 else pd.NA

    diez = re.search(r"(\d+)\s*de\s*10", text)
    if diez:
        mapped = int(round((int(diez.group(1)) / 10) * 5))
        return min(5, max(1, mapped))

    if any(x in text for x in ["poco comodo", "poco comoda"]):
        return 1
    if text == "mucho":
        return 5
    if any(x in text for x in ["no mucho", "algo incomodo"]):
        return 2
    if any(x in text for x in ["neutral", "normal"]):
        return 3
    if any(x in text for x in ["comodo", "cómodo", "bastante"]):
        return 4
    if any(x in text for x in ["muy comodo", "muy cómodo", "excelente"]):
        return 5
    return pd.NA


def clean_energia_interpersonal(value):
    text = normalize_text(value)
    if not text:
        return pd.NA

    if text.isdigit():
        n = int(text)
        return n if 1 <= n <= 5 else pd.NA

    if any(x in text for x in ["agotado", "cansad", "abrumad"]):
        return 1
    if any(x in text for x in ["no me gusta", "incomodo"]):
        return 2
    if any(x in text for x in ["normal", "no me molesta", "neutral"]):
        return 3
    if any(x in text for x in ["bien", "alegre"]):
        return 4
    if "excelente" in text:
        return 5
    return pd.NA


def clean_enfoque(value):
    text = normalize_text(value)
    if not text:
        return pd.NA

    base = clean_boolean(text)
    if pd.notna(base):
        return base

    if any(x in text for x in ["siempre", "usualmente sí", "solo al chofer", "sólo al chofer"]):
        return 1
    if any(x in text for x in ["pena", "no siempre", "no lo hago", "nunca"]):
        return 0
    return pd.NA


def clean_colaborativo(value):
    text = normalize_text(value)
    if not text:
        return pd.NA

    base = clean_boolean(text)
    if pd.notna(base):
        return base

    if any(x in text for x in ["depende", "a veces"]):
        return 1
    if any(x in text for x in ["casi no", "dificil", "difícil", "me es dificil", "me es difícil"]):
        return 0
    return pd.NA


def build_semantic_concept_docs(nlp_model, semantic_concepts):
    return {
        column: {label: nlp_model(label) for label in labels}
        for column, labels in semantic_concepts.items()
    }


def apply_column_cleaning(df, nlp_model, cleaner_by_column, int_cast_columns):
    for column in [c for c in df.columns if c != "num_cuenta"]:
        normalized_series = df[column].apply(normalize_text)
        cleaner_name = cleaner_by_column.get(column)

        if cleaner_name:
            cleaner = globals()[cleaner_name]
            cleaned_series = normalized_series.apply(cleaner)
            if column in int_cast_columns:
                cleaned_series = cleaned_series.astype("Int64")
            df[column] = cleaned_series
        else:
            df[column] = normalized_series.apply(lambda text: spacy_clean_text(text, nlp_model))

    return df


def clean_relaciones_dataframe(input_path=INPUT_PATH, config_path=CONFIG_PATH):
    df = pd.read_csv(input_path)
    nlp = spacy.load("es_core_news_md")
    config = load_config(config_path)

    semantic_concept_docs = build_semantic_concept_docs(nlp, config["semantic_concepts"])

    if "num_cuenta" in df.columns:
        df["num_cuenta"] = pd.to_numeric(df["num_cuenta"], errors="coerce").astype("Int64")

    df = apply_column_cleaning(df, nlp, config["cleaner_by_column"], config["int_cast_columns"])

    # Segunda pasada semantica para acercar el texto a la intencion real.
    for column, concept_docs in semantic_concept_docs.items():
        if column in df.columns:
            df[column] = df[column].apply(
                lambda text: semantic_refine_text(
                    normalize_text(text),
                    concept_docs,
                    nlp,
                    config["semantic_threshold"],
                    config["semantic_max_labels"],
                )
            )

    return df


def main():
    cleaned_df = clean_relaciones_dataframe()
    cleaned_df.to_csv(OUTPUT_CLEAN_PATH, index=False)
    print(f"Archivo limpio generado: {OUTPUT_CLEAN_PATH}")


if __name__ == "__main__":
    main()
