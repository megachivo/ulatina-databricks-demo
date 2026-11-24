# Databricks de punta a punta · Demo Ulatina

Demo de **90 minutos** para estudiantes universitarios. Caso: **TicoMarket**, una tienda en línea de Costa Rica.
Recorremos todo el ciclo de los datos en una sola plataforma: desde archivos crudos hasta IA generativa,
Machine Learning y una aplicación web.

```
 Archivos JSON ──► Volume (UC) ──► Lakeflow Pipeline ──► Gold ──┬─► Dashboard AI/BI
  (la tienda)                     bronze → silver → gold        ├─► Genie (preguntas en español)
                                  + reglas de calidad           ├─► AI Functions (reseñas con LLM)
                                                                ├─► MLflow: modelo de abandono
                                                                └─► Unity Catalog: gobierno y linaje
                         Todo orquestado por un Job · desplegado con un Bundle desde Git
                         Final: Doom jugado por IA como Databricks App
```

## Qué hay en el repo

| Ruta | Qué es | Funcionalidad que muestra |
|---|---|---|
| `databricks.yml`, `resources/` | Bundle (infraestructura como código) | Declarative Automation Bundles, CI/CD |
| `src/notebooks/01_generar_datos.py` | Simula la tienda y deja JSON en un Volume | Notebooks, Volumes |
| `src/pipeline/transformations/*.sql` | Medallion bronze → silver → gold | Lakeflow Declarative Pipelines, Auto Loader, Expectations |
| `src/notebooks/03_ia_resenas.sql` | Sentimiento, tema y respuestas con LLM | AI Functions (`ai_analyze_sentiment`, `ai_classify`, `ai_query`) |
| `src/notebooks/04_ml_churn.py` | Modelo de abandono de clientes | MLflow, Unity Catalog Model Registry |
| `src/notebooks/05_gobierno_uc.sql` | Tags, máscaras de PII, filtros de fila | Unity Catalog |
| `dashboards/` | Dashboard de 3 páginas | AI/BI Dashboards |
| `genie/crear_genie.py` | Espacio de Genie con instrucciones en español | Genie |
| `docs/doom.md` | Cómo desplegar Doom jugado por `ai_decide` | Databricks Apps |

Tablas que se crean en `workspace.ulatina_ecommerce`:

| Capa | Tablas |
|---|---|
| Bronze | `bronze_clientes`, `bronze_productos`, `bronze_ordenes`, `bronze_resenas` |
| Silver | `silver_clientes`, `silver_productos`, `silver_ordenes`, `silver_lineas_orden`, `silver_resenas` |
| Gold | `gold_ventas_diarias`, `gold_productos`, `gold_clientes_360`, `gold_resenas_ia`, `gold_respuestas_sugeridas`, `gold_riesgo_abandono` |
| Gobierno | `clientes_mercadeo` (con máscaras), `v_ventas_gerente_regional`, funciones `mascara_email`, `mascara_telefono`, `filtro_provincia` |
| ML | modelo `modelo_abandono` |

---

## Agenda (90 min)

La sesión abre con la **charla con slides (~27 min)**, que explica *qué* es Databricks y *por qué* existe.
Después viene el **demo (~58 min)**, que muestra en vivo esas mismas piezas con TicoMarket, y cierran **5 min de preguntas**.
La charla ya cubre la introducción, Free Edition y las certificaciones, así que el demo no las repite.

| Min | Bloque | Qué mostrar | Dónde |
|---|---|---|---|
| 0–27 | **Charla** | Lakehouse, Unity Catalog, Lakeflow, Genie, AI/BI, Apps; QR de Free Edition y sus límites; certificaciones. Cierra con *"vamos a la plataforma"* | Slides |
| 27–32 | **1 · Workspace y datos crudos** | Git folder conectado a GitHub, notebook 01, el Volume `raw` con los JSON | Workspace → Git folder; Catalog → `raw` |
| 32–43 | **2 · Pipeline medallion** | Grafo del pipeline, bronze/silver/gold, pestaña *Data quality* (filas descartadas), **ingesta incremental**: correr el job con `lote=2` y ver que solo entran los archivos nuevos | Jobs & Pipelines |
| 43–49 | **3 · Unity Catalog** | Linaje de `gold_ventas_diarias` hasta el JSON, tags `pii`, email enmascarado, `SHOW GRANTS` | Catalog Explorer; notebook 05 |
| 49–55 | **4 · SQL y Dashboard** | SQL Editor sobre gold; dashboard *Ulatina - TicoMarket* (ventas, abandono, reseñas) con filtros | SQL Editor; Dashboards |
| 55–61 | **5 · Genie** | Preguntas en español (ver abajo); mostrar el SQL que generó | Genie |
| 61–68 | **6 · IA generativa en SQL** | `ai_analyze_sentiment`, `ai_classify` y `ai_query` respondiendo a clientes molestos | notebook 03 |
| 68–76 | **7 · Machine Learning** | Experimento MLflow (métricas, importancia de variables), modelo versionado en UC, tabla de riesgo | notebook 04; Experiments; Catalog → Models |
| 76–80 | **8 · Orquestación y CI/CD** | El job con 5 tareas (DAG), historial de ejecuciones; el bundle como código en Git | Jobs; GitHub |
| 80–85 | **9 · Databricks Apps** | Doom jugado por IA | App `doom-ulatina` |
| 85–90 | **Preguntas** | Recordar el repo para replicarlo en Free Edition | — |

**Si el tiempo se aprieta**, recortar en este orden: módulo 8 (mencionarlo de palabra), módulo 3 (solo el email enmascarado), módulo 1 (arrancar directo en el pipeline).

### Preguntas para Genie

- ¿Cuál fue el ingreso total por provincia en los últimos 3 meses?
- ¿Qué categoría vende más en Guanacaste?
- ¿Cuántos clientes en riesgo alto de abandono hay por canal?
- ¿De qué se quejan más los clientes en las reseñas negativas?
- *(seguimiento)* ¿Y cuál de esos clientes gastó más?

### Mensajes clave por módulo

1. **Un solo lugar** para archivos, tablas, modelos, dashboards y apps, gobernado por Unity Catalog.
2. **Declarativo:** en el pipeline se dice *qué* tabla se quiere, no *cómo* procesarla; Databricks maneja el orden, los reintentos y la ingesta incremental.
3. **Calidad como código:** las *expectations* descartan órdenes sin cliente, cantidades negativas y duplicados (los datos traen esos errores a propósito).
4. **Sin fugas de información:** el modelo de abandono usa solo datos *antes* de la fecha de corte (60 días antes del último dato).
5. **IA para todos:** un analista que sabe SQL ya puede usar un LLM (`ai_query`) o preguntar en español (Genie).
6. **Gobierno:** el correo y el teléfono se enmascaran según quién consulta. En Free Edition ni el dueño ve el dato real, porque no pertenece al grupo de cuenta `admins`. Es un buen ejemplo de que la regla aplica para todos.

---

## Preparación (el día antes)

```bash
# 1. Perfil del CLI apuntando al workspace
databricks configure --host https://<workspace>.cloud.databricks.com --profile ulatina-demo

# 2. Desplegar y correr todo (≈10 min)
databricks bundle deploy -t dev --profile ulatina-demo
databricks bundle run ecommerce_e2e -t dev --profile ulatina-demo

# 3. Genie
python3 genie/crear_genie.py --profile ulatina-demo

# 4. Doom (opcional): ver docs/doom.md
```

**30 minutos antes de la clase:**
- Encender el SQL warehouse *Serverless Starter Warehouse* (abrir el dashboard lo enciende).
- Iniciar la app de Doom: `databricks apps start doom-ulatina --profile ulatina-demo`.
- Abrir pestañas: Git folder, pipeline, Catalog (`ulatina_ecommerce`), dashboard, Genie, notebook 03, experimento MLflow, job, app.

### Demo en vivo de ingesta incremental (módulo 2)

```bash
databricks bundle run ecommerce_e2e -t dev --profile ulatina-demo --params lote=2
```
Genera un día nuevo de órdenes (`lote_002.json`). En el pipeline, las tablas bronze solo procesan el archivo nuevo.

### Reiniciar el demo desde cero

```bash
for d in clientes productos ordenes resenas; do
  databricks fs rm -r dbfs:/Volumes/workspace/ulatina_ecommerce/raw/$d --profile ulatina-demo
done
databricks bundle run ecommerce_e2e -t dev --profile ulatina-demo --only generar_datos
databricks bundle run ecommerce_medallion -t dev --profile ulatina-demo --full-refresh-all
databricks bundle run ecommerce_e2e -t dev --profile ulatina-demo --only ia_resenas,ml_churn,gobierno_uc
```

### Borrar todo

```bash
databricks bundle destroy -t dev --auto-approve --profile ulatina-demo
```

---

## Para estudiantes: correrlo en su propia cuenta gratis

1. Crear cuenta en **Databricks Free Edition**: <https://www.databricks.com/learn/free-edition>
2. *Workspace → Create → Git folder* → URL `https://github.com/megachivo/ulatina-databricks-demo`
3. Abrir la carpeta, hacer clic en el ícono de **Deployments** (cohete) → *Deploy* → correr el job *Ulatina - E-commerce End-to-End*.
4. Alternativa sin bundle: abrir los notebooks de `src/notebooks/` y correrlos en orden, creando el pipeline a mano desde *Jobs & Pipelines → ETL pipeline* con la carpeta `src/pipeline/transformations`.

Todos los datos son **sintéticos**; ningún cliente es real.
