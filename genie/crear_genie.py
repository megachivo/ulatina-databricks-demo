"""Crea (o actualiza) el espacio de Genie "TicoMarket - Pregúntele a sus datos".

Uso:
  python3 genie/crear_genie.py --profile <PERFIL> [--catalog workspace] [--schema ulatina_ecommerce]
                               [--warehouse-id <ID>] [--space-id <ID para actualizar>]
"""
import argparse
import json
import subprocess

p = argparse.ArgumentParser()
p.add_argument("--profile", required=True)
p.add_argument("--catalog", default="workspace")
p.add_argument("--schema", default="ulatina_ecommerce")
p.add_argument("--warehouse-id")
p.add_argument("--space-id")
a = p.parse_args()


def cli(*args):
    out = subprocess.run(["databricks", *args, "--profile", a.profile, "-o", "json"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


if not a.warehouse_id:
    a.warehouse_id = next(w["id"] for w in cli("warehouses", "list"))

fq = lambda t: f"{a.catalog}.{a.schema}.{t}"
hexid = lambda prefix, n: f"{prefix}{n:031d}"

tablas = {
    "gold_ventas_diarias": [
        {"column_name": "canal_adquisicion", "enable_entity_matching": True, "enable_format_assistance": True,
         "synonyms": ["canal", "canal de marketing"]},
        {"column_name": "categoria", "enable_entity_matching": True, "enable_format_assistance": True},
        {"column_name": "ingreso_crc", "description": ["Ingreso en colones de órdenes completadas."],
         "synonyms": ["ventas", "facturación", "revenue"]},
        {"column_name": "provincia", "enable_entity_matching": True, "enable_format_assistance": True},
    ],
    "gold_productos": [],
    "gold_riesgo_abandono": [
        {"column_name": "prob_abandono", "description": ["Probabilidad (0-1) de que el cliente abandone, según el modelo ML."],
         "synonyms": ["churn", "riesgo"]},
        {"column_name": "segmento_riesgo", "enable_entity_matching": True},
    ],
    "gold_resenas_ia": [
        {"column_name": "sentimiento", "enable_entity_matching": True,
         "description": ["Valores en inglés: positive, negative, neutral, mixed."]},
        {"column_name": "tema", "enable_entity_matching": True},
    ],
    "silver_clientes": [
        {"column_name": "email", "exclude": True},
        {"column_name": "telefono", "exclude": True},
    ],
}

preguntas = [
    "¿Cuál fue el ingreso total por provincia en los últimos 3 meses?",
    "¿Qué categoría vende más en Guanacaste?",
    "Muéstrame la tendencia mensual de órdenes por canal de adquisición",
    "¿Cuántos clientes en riesgo alto de abandono hay por canal?",
    "¿Cuáles son los 10 productos con peor calificación promedio?",
    "¿De qué se quejan más los clientes en las reseñas negativas?",
]

espacio = {
    "version": 2,
    "config": {"sample_questions": [{"id": hexid("1", i), "question": [q]} for i, q in enumerate(preguntas)]},
    "data_sources": {"tables": sorted(
        [{"identifier": fq(t), **({"column_configs": sorted(c, key=lambda x: x["column_name"])} if c else {})}
         for t, c in tablas.items()], key=lambda x: x["identifier"])},
    "instructions": {
        "text_instructions": [{"id": hexid("3", 1), "content": [
            "Sos el analista de datos de TicoMarket, una tienda en línea de Costa Rica. Respondé siempre en español.\n",
            "Montos en colones costarricenses (₡, columnas *_crc). Mostrá los montos grandes en millones.\n",
            "Ventas e ingreso: usar gold_ventas_diarias (solo incluye órdenes completadas).\n",
            "Abandono / churn / riesgo: usar gold_riesgo_abandono. Riesgo alto = segmento_riesgo = 'Alto'.\n",
            "Reseñas y quejas: usar gold_resenas_ia; sentimiento negativo = 'negative'.\n",
            "'Último mes' = desde date_sub(max(fecha), 30) de la tabla consultada, no la fecha de hoy.\n",
        ]}],
        "example_question_sqls": [
            {"id": hexid("2", 1), "question": ["¿Cuál es el ingreso por categoría?"],
             "sql": [f"SELECT categoria, ROUND(SUM(ingreso_crc) / 1e6, 2) AS ingreso_millones_crc\n",
                     f"FROM {fq('gold_ventas_diarias')}\nGROUP BY categoria\nORDER BY ingreso_millones_crc DESC"]},
            {"id": hexid("2", 2), "question": ["¿Cuántos clientes hay en cada segmento de riesgo?"],
             "sql": [f"SELECT segmento_riesgo, COUNT(*) AS clientes, ROUND(AVG(prob_abandono), 3) AS prob_media\n",
                     f"FROM {fq('gold_riesgo_abandono')}\nGROUP BY segmento_riesgo"]},
        ],
    },
}

payload = json.dumps(espacio, ensure_ascii=False)
titulo = "TicoMarket - Pregúntele a sus datos"
desc = "Genie del demo Ulatina: ventas, clientes en riesgo de abandono y reseñas analizadas con IA."
if a.space_id:
    r = cli("genie", "update-space", a.space_id, "--json",
            json.dumps({"serialized_space": payload, "title": titulo, "description": desc, "warehouse_id": a.warehouse_id}))
else:
    r = cli("genie", "create-space", a.warehouse_id, payload, "--title", titulo, "--description", desc)
print(json.dumps({"space_id": r.get("space_id"), "title": r.get("title")}, ensure_ascii=False))
