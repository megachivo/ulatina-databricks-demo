# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Machine Learning: ¿qué clientes van a abandonar?
# MAGIC
# MAGIC 1. Leemos `gold_clientes_360` (variables + etiqueta `abandono`).
# MAGIC 2. Entrenamos un modelo con **scikit-learn**.
# MAGIC 3. **MLflow** registra parámetros, métricas y el modelo (experimentos reproducibles).
# MAGIC 4. Registramos el modelo en **Unity Catalog** (versionado y gobernado como una tabla).
# MAGIC 5. Calificamos a todos los clientes → tabla `gold_riesgo_abandono`.

# COMMAND ----------

# MAGIC %pip install -q scikit-learn mlflow
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "ulatina_ecommerce")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
MODELO_UC = f"{CATALOG}.{SCHEMA}.modelo_abandono"

# COMMAND ----------

import mlflow
import pandas as pd
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

df = spark.table(f"{CATALOG}.{SCHEMA}.gold_clientes_360").toPandas()
print(f"{len(df):,} clientes · tasa de abandono {df.abandono.mean():.1%}")
display(df.head(10))

# COMMAND ----------

CATEGORICAS = ["provincia", "canal_adquisicion", "metodo_pago_preferido"]
NUMERICAS = ["antiguedad_dias", "ordenes", "gasto_total_crc", "ticket_promedio_crc", "categorias_distintas",
             "dias_desde_ultima_compra", "tasa_devolucion", "tasa_cancelacion", "resenas",
             "calificacion_promedio", "resenas_negativas"]

X = df[CATEGORICAS + NUMERICAS].copy()
X[NUMERICAS] = X[NUMERICAS].astype("float64").fillna(0)
y = df["abandono"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(f"/Users/{spark.sql('select current_user()').first()[0]}/ulatina_churn")

with mlflow.start_run(run_name="gradient_boosting") as run:
    params = {"n_estimators": 150, "max_depth": 3, "learning_rate": 0.1}
    modelo = Pipeline([
        ("prep", ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAS)],
                                   remainder="passthrough")),
        ("clf", GradientBoostingClassifier(random_state=42, **params)),
    ])
    modelo.fit(X_train, y_train)

    prob = modelo.predict_proba(X_test)[:, 1]
    pred = (prob >= 0.5).astype(int)
    metricas = {"auc": roc_auc_score(y_test, prob), "f1": f1_score(y_test, pred), "accuracy": accuracy_score(y_test, pred)}
    mlflow.log_params(params)
    mlflow.log_metrics(metricas)
    mlflow.sklearn.log_model(
        modelo,
        name="modelo",
        signature=infer_signature(X_test, prob),
        input_example=X_test.head(3),
        registered_model_name=MODELO_UC,
    )
    print(metricas)

# COMMAND ----------

# MAGIC %md ## ¿Qué variables pesan más?

# COMMAND ----------

nombres = modelo.named_steps["prep"].get_feature_names_out()
importancia = (pd.DataFrame({"variable": nombres, "importancia": modelo.named_steps["clf"].feature_importances_})
               .sort_values("importancia", ascending=False).head(10))
display(importancia)

# COMMAND ----------

# MAGIC %md ## Calificar a todos los clientes con la última versión del modelo registrado

# COMMAND ----------

from mlflow import MlflowClient

version = max(int(v.version) for v in MlflowClient().search_model_versions(f"name='{MODELO_UC}'"))
cargado = mlflow.sklearn.load_model(f"models:/{MODELO_UC}/{version}")

salida = df[["cliente_id", "provincia", "canal_adquisicion", "gasto_total_crc", "abandono"]].copy()
salida["prob_abandono"] = cargado.predict_proba(X)[:, 1]
salida["segmento_riesgo"] = pd.cut(salida.prob_abandono, [-0.01, 0.3, 0.7, 1.0], labels=["Bajo", "Medio", "Alto"]).astype(str)
salida["version_modelo"] = version

(spark.createDataFrame(salida).write.mode("overwrite").option("overwriteSchema", "true")
      .saveAsTable(f"{CATALOG}.{SCHEMA}.gold_riesgo_abandono"))
spark.sql(f"COMMENT ON TABLE {CATALOG}.{SCHEMA}.gold_riesgo_abandono IS "
          f"'Probabilidad de abandono por cliente, calculada con {MODELO_UC} v{version}.'")
display(spark.sql(f"SELECT segmento_riesgo, COUNT(*) clientes, ROUND(AVG(prob_abandono),3) prob_media "
                  f"FROM {CATALOG}.{SCHEMA}.gold_riesgo_abandono GROUP BY 1 ORDER BY 3 DESC"))
