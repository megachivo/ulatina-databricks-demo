"""Genera dashboards/ticomarket.lvdash.json (AI/BI dashboard del demo).

Uso:  python3 dashboards/build_dashboard.py
Las consultas usan nombres de tabla sin catálogo/esquema; el bundle los
inyecta con dataset_catalog / dataset_schema.
"""
import json
from pathlib import Path

CRC = {"type": "number-currency", "currencyCode": "CRC", "abbreviation": "compact",
       "decimalPlaces": {"type": "max", "places": 1}}
COMPACT = {"type": "number", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 1}}
PCT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}

datasets = [
    {"name": "ds_ventas", "displayName": "Ventas diarias",
     "queryLines": ["SELECT fecha, provincia, categoria, canal_adquisicion, ordenes, unidades, ingreso_crc, margen_crc\n",
                    "FROM gold_ventas_diarias"]},
    {"name": "ds_riesgo", "displayName": "Riesgo de abandono",
     "queryLines": ["SELECT cliente_id, provincia, canal_adquisicion, segmento_riesgo, gasto_total_crc, prob_abandono,\n",
                    "       CASE WHEN segmento_riesgo = 'Alto' THEN 1 ELSE 0 END AS riesgo_alto,\n",
                    "       CASE WHEN segmento_riesgo = 'Alto' THEN gasto_total_crc ELSE 0 END AS gasto_en_riesgo_crc\n",
                    "FROM gold_riesgo_abandono"]},
    {"name": "ds_top_riesgo", "displayName": "Top clientes en riesgo",
     "queryLines": ["SELECT r.cliente_id, c.nombre, r.provincia, r.canal_adquisicion, r.gasto_total_crc,\n",
                    "       ROUND(r.prob_abandono, 3) AS prob_abandono\n",
                    "FROM gold_riesgo_abandono r JOIN silver_clientes c USING (cliente_id)\n",
                    "WHERE r.segmento_riesgo = 'Alto'\n",
                    "ORDER BY r.gasto_total_crc DESC LIMIT 25"]},
    {"name": "ds_resenas", "displayName": "Reseñas analizadas con IA",
     "queryLines": ["SELECT fecha, categoria, producto, tema, sentimiento, calificacion, texto\n",
                    "FROM gold_resenas_ia"]},
]


def text(name, lines, x, y, w, h):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": lines}},
            "position": {"x": x, "y": y, "width": w, "height": h}}


def counter(name, ds, title, expr, field, fmt, x, y, w=4, h=3):
    return {"widget": {
        "name": name,
        "queries": [{"name": "main_query", "query": {
            "datasetName": ds, "fields": [{"name": field, "expression": expr}], "disaggregated": False}}],
        "spec": {"version": 2, "widgetType": "counter",
                 "encodings": {"value": {"fieldName": field, "displayName": title, **({"format": fmt} if fmt else {})}},
                 "frame": {"title": title, "showTitle": True}}},
        "position": {"x": x, "y": y, "width": w, "height": h}}


def chart(name, kind, ds, title, x_field, x_expr, x_type, y_field, y_expr, y_fmt=None, color=None,
          pos=(0, 0, 6, 6), horizontal=False, sort_value=False):
    fields = [{"name": x_field, "expression": x_expr}, {"name": y_field, "expression": y_expr}]
    if color:
        fields.append({"name": color, "expression": f"`{color}`"})
    cat = {"fieldName": x_field, "scale": {"type": x_type}, "displayName": title.split(" por ")[-1].capitalize()}
    if sort_value:
        cat["scale"]["sort"] = {"by": "value"}
    val = {"fieldName": y_field, "scale": {"type": "quantitative"}, "displayName": title.split(" por ")[0]}
    if y_fmt:
        val["format"] = y_fmt
    enc = {"x": val, "y": cat} if horizontal else {"x": cat, "y": val}
    if color:
        enc["color"] = {"fieldName": color, "scale": {"type": "categorical"}, "displayName": color.replace("_", " ").capitalize()}
    x, y, w, h = pos
    return {"widget": {
        "name": name,
        "queries": [{"name": "main_query", "query": {"datasetName": ds, "fields": fields, "disaggregated": False}}],
        "spec": {"version": 3, "widgetType": kind, "encodings": enc, "frame": {"title": title, "showTitle": True}}},
        "position": {"x": x, "y": y, "width": w, "height": h}}


def multi_filter(name, ds_fields, title, x, y, w=4, h=2, kind="filter-multi-select"):
    queries, enc = [], []
    for ds, field in ds_fields:
        qn = f"{name}_{ds}"
        queries.append({"name": qn, "query": {"datasetName": ds,
                                              "fields": [{"name": field, "expression": f"`{field}`"}],
                                              "disaggregated": False}})
        enc.append({"fieldName": field, "displayName": title, "queryName": qn})
    return {"widget": {"name": name, "queries": queries,
                       "spec": {"version": 2, "widgetType": kind, "encodings": {"fields": enc},
                                "frame": {"title": title, "showTitle": True}}},
            "position": {"x": x, "y": y, "width": w, "height": h}}


def table(name, ds, title, cols, pos):
    x, y, w, h = pos
    return {"widget": {
        "name": name,
        "queries": [{"name": "main_query", "query": {
            "datasetName": ds, "fields": [{"name": c, "expression": f"`{c}`"} for c, _ in cols], "disaggregated": True}}],
        "spec": {"version": 2, "widgetType": "table",
                 "encodings": {"columns": [{"fieldName": c, "displayName": d} for c, d in cols]},
                 "frame": {"title": title, "showTitle": True}}},
        "position": {"x": x, "y": y, "width": w, "height": h}}


pagina_ventas = [
    text("titulo_ventas", ["# TicoMarket · Ventas\n",
                           "Ventas completadas del último año (capa **gold** del pipeline medallion). "
                           "Las ventas vienen bajando desde enero: ¿es estacionalidad o estamos perdiendo clientes? "
                           "La pestaña **Clientes y abandono** responde con Machine Learning."], 0, 0, 12, 2),
    {"widget": {"name": "filtro_fecha",
                "queries": [{"name": "filtro_fecha_ds_ventas", "query": {"datasetName": "ds_ventas",
                             "fields": [{"name": "fecha", "expression": "`fecha`"}], "disaggregated": False}}],
                "spec": {"version": 2, "widgetType": "filter-date-range-picker",
                         "encodings": {"fields": [{"fieldName": "fecha", "displayName": "Fecha", "queryName": "filtro_fecha_ds_ventas"}]},
                         "frame": {"title": "Fecha", "showTitle": True}}},
     "position": {"x": 0, "y": 2, "width": 4, "height": 2}},
    multi_filter("filtro_provincia", [("ds_ventas", "provincia")], "Provincia", 4, 2),
    multi_filter("filtro_categoria", [("ds_ventas", "categoria")], "Categoría", 8, 2),
    counter("kpi_ingreso", "ds_ventas", "Ingreso", "SUM(`ingreso_crc`)", "sum(ingreso_crc)", CRC, 0, 4),
    counter("kpi_ordenes", "ds_ventas", "Órdenes", "SUM(`ordenes`)", "sum(ordenes)", COMPACT, 4, 4),
    counter("kpi_margen", "ds_ventas", "Margen bruto", "SUM(`margen_crc`)", "sum(margen_crc)", CRC, 8, 4),
    chart("tendencia_mensual", "line", "ds_ventas", "Ingreso por mes",
          "monthly(fecha)", 'DATE_TRUNC("MONTH", `fecha`)', "temporal",
          "sum(ingreso_crc)", "SUM(`ingreso_crc`)", CRC, color="categoria", pos=(0, 7, 12, 6)),
    chart("ingreso_provincia", "bar", "ds_ventas", "Ingreso por provincia",
          "provincia", "`provincia`", "categorical", "sum(ingreso_crc)", "SUM(`ingreso_crc`)", CRC,
          pos=(0, 13, 6, 6), horizontal=True, sort_value=True),
    chart("ingreso_canal", "bar", "ds_ventas", "Ingreso por canal de adquisición",
          "canal_adquisicion", "`canal_adquisicion`", "categorical", "sum(ingreso_crc)", "SUM(`ingreso_crc`)", CRC,
          pos=(6, 13, 6, 6), horizontal=True, sort_value=True),
]

pagina_clientes = [
    text("titulo_clientes", ["# Clientes y abandono (Machine Learning)\n",
                             "Probabilidad de abandono calculada por el modelo `modelo_abandono` registrado en Unity Catalog "
                             "(MLflow + scikit-learn). Riesgo **Alto** = probabilidad > 70 %."], 0, 0, 12, 2),
    multi_filter("filtro_canal", [("ds_riesgo", "canal_adquisicion")], "Canal de adquisición", 0, 2, 6),
    multi_filter("filtro_prov_riesgo", [("ds_riesgo", "provincia")], "Provincia", 6, 2, 6),
    counter("kpi_riesgo_alto", "ds_riesgo", "Clientes en riesgo alto", "SUM(`riesgo_alto`)", "sum(riesgo_alto)", None, 0, 4),
    counter("kpi_prob_media", "ds_riesgo", "Probabilidad media de abandono", "AVG(`prob_abandono`)", "avg(prob_abandono)", PCT, 4, 4),
    counter("kpi_gasto_riesgo", "ds_riesgo", "Gasto histórico en riesgo", "SUM(`gasto_en_riesgo_crc`)", "sum(gasto_en_riesgo_crc)", CRC, 8, 4),
    chart("clientes_segmento", "bar", "ds_riesgo", "Clientes por segmento de riesgo",
          "segmento_riesgo", "`segmento_riesgo`", "categorical", "count(cliente_id)", "COUNT(`cliente_id`)",
          pos=(0, 7, 6, 6)),
    chart("riesgo_canal", "bar", "ds_riesgo", "Probabilidad de abandono por canal",
          "canal_adquisicion", "`canal_adquisicion`", "categorical", "avg(prob_abandono)", "AVG(`prob_abandono`)", PCT,
          pos=(6, 7, 6, 6), horizontal=True, sort_value=True),
    table("top_riesgo", "ds_top_riesgo", "Clientes valiosos en riesgo alto (para campaña de retención)",
          [("cliente_id", "Cliente"), ("nombre", "Nombre"), ("provincia", "Provincia"),
           ("canal_adquisicion", "Canal"), ("gasto_total_crc", "Gasto histórico (₡)"), ("prob_abandono", "Prob. abandono")],
          (0, 13, 12, 7)),
]

pagina_resenas = [
    text("titulo_resenas", ["# Voz del cliente (IA generativa)\n",
                            "Las 500 reseñas más recientes, clasificadas con `ai_analyze_sentiment` y `ai_classify` "
                            "directamente en SQL."], 0, 0, 12, 2),
    multi_filter("filtro_sentimiento", [("ds_resenas", "sentimiento")], "Sentimiento", 0, 2, 6),
    multi_filter("filtro_tema", [("ds_resenas", "tema")], "Tema", 6, 2, 6),
    chart("resenas_tema", "bar", "ds_resenas", "Reseñas por tema",
          "tema", "`tema`", "categorical", "count(texto)", "COUNT(`texto`)", color="sentimiento", pos=(0, 4, 6, 6)),
    {"widget": {"name": "pie_sentimiento",
                "queries": [{"name": "main_query", "query": {"datasetName": "ds_resenas", "fields": [
                    {"name": "sentimiento", "expression": "`sentimiento`"},
                    {"name": "count(texto)", "expression": "COUNT(`texto`)"}], "disaggregated": False}}],
                "spec": {"version": 3, "widgetType": "pie",
                         "encodings": {"angle": {"fieldName": "count(texto)", "scale": {"type": "quantitative"}, "displayName": "Reseñas"},
                                       "color": {"fieldName": "sentimiento", "scale": {"type": "categorical", "mappings": [
                                           {"value": "positive", "color": "#3BA272"}, {"value": "negative", "color": "#E4572E"},
                                           {"value": "neutral", "color": "#A0A7B4"}, {"value": "mixed", "color": "#F2B134"}]},
                                                 "displayName": "Sentimiento"}},
                         "frame": {"title": "Sentimiento general", "showTitle": True}}},
     "position": {"x": 6, "y": 4, "width": 6, "height": 6}},
    table("tabla_resenas", "ds_resenas", "Reseñas",
          [("fecha", "Fecha"), ("producto", "Producto"), ("calificacion", "★"), ("tema", "Tema"),
           ("sentimiento", "Sentimiento"), ("texto", "Reseña")], (0, 10, 12, 7)),
]

dashboard = {
    "datasets": datasets,
    "pages": [
        {"name": "ventas", "displayName": "Ventas", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": pagina_ventas},
        {"name": "clientes", "displayName": "Clientes y abandono", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": pagina_clientes},
        {"name": "resenas", "displayName": "Voz del cliente (IA)", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": pagina_resenas},
    ],
    "uiSettings": {"theme": {
        "canvasBackgroundColor": {"light": "#F7F8FA", "dark": "#1F272D"},
        "widgetBackgroundColor": {"light": "#FFFFFF", "dark": "#11171C"},
        "widgetBorderColor": {"light": "#FFFFFF", "dark": "#11171C"},
        "fontColor": {"light": "#11171C", "dark": "#E8ECF0"},
        "selectionColor": {"light": "#2272B4", "dark": "#8ACAFF"},
        "visualizationColors": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442"],
        "widgetHeaderAlignment": "LEFT",
        "widgetCornerRadius": 8,
    }},
}

out = Path(__file__).with_name("ticomarket.lvdash.json")
out.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"OK -> {out}")
