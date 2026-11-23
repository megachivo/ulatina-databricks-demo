-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 03 · IA generativa con SQL: analizar reseñas
-- MAGIC
-- MAGIC Con **AI Functions** se usa un modelo de lenguaje (LLM) directamente desde SQL,
-- MAGIC sin escribir Python ni montar infraestructura:
-- MAGIC
-- MAGIC | Función | Para qué |
-- MAGIC |---|---|
-- MAGIC | `ai_analyze_sentiment(texto)` | positivo / negativo / neutral / mixto |
-- MAGIC | `ai_classify(texto, ARRAY(...))` | clasificar en las categorías que yo defino |
-- MAGIC | `ai_extract(texto, ARRAY(...))` | sacar entidades (producto, lugar, …) |
-- MAGIC | `ai_query(modelo, prompt)` | cualquier tarea con un prompt libre |

-- COMMAND ----------

CREATE WIDGET TEXT catalog DEFAULT 'workspace';
CREATE WIDGET TEXT schema DEFAULT 'ulatina_ecommerce';

-- COMMAND ----------

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

-- COMMAND ----------

-- MAGIC %md ## 1. Probar una función con un texto cualquiera

-- COMMAND ----------

SELECT
  ai_analyze_sentiment('El pedido tardó dos semanas y llegó golpeado') AS sentimiento,
  ai_classify('El pedido tardó dos semanas y llegó golpeado',
              ARRAY('entrega', 'calidad', 'precio', 'atención al cliente')) AS tema;

-- COMMAND ----------

-- MAGIC %md ## 2. Enriquecer las reseñas más recientes (500)

-- COMMAND ----------

CREATE OR REPLACE TABLE gold_resenas_ia
COMMENT 'Reseñas enriquecidas con IA: sentimiento y tema detectado por un LLM.'
AS
WITH recientes AS (
  SELECT * FROM silver_resenas ORDER BY fecha_resena DESC LIMIT 500
)
SELECT
  r.resena_id,
  r.cliente_id,
  r.producto_id,
  p.producto,
  p.categoria,
  r.calificacion,
  r.texto,
  CAST(r.fecha_resena AS DATE)                    AS fecha,
  ai_analyze_sentiment(r.texto)                   AS sentimiento,
  ai_classify(r.texto, ARRAY('entrega', 'calidad', 'precio', 'atención al cliente')) AS tema
FROM recientes r
JOIN silver_productos p USING (producto_id);

-- COMMAND ----------

SELECT tema, sentimiento, COUNT(*) AS resenas
FROM gold_resenas_ia
GROUP BY ALL
ORDER BY tema, resenas DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 3. `ai_query`: redactar una respuesta para clientes molestos
-- MAGIC Usamos un modelo fundacional servido por Databricks (Llama 3.3 70B).

-- COMMAND ----------

CREATE OR REPLACE TABLE gold_respuestas_sugeridas
COMMENT 'Borradores de respuesta generados por un LLM para reseñas negativas.'
AS
SELECT
  resena_id,
  producto,
  tema,
  texto,
  ai_query(
    'databricks-meta-llama-3-3-70b-instruct',
    CONCAT(
      'Sos el equipo de servicio al cliente de TicoMarket, una tienda en línea de Costa Rica. ',
      'Escribí una respuesta corta (máximo 3 oraciones), empática y en español costarricense ',
      'a esta reseña negativa sobre el producto "', producto, '" (tema: ', tema, '). ',
      'Ofrecé una solución concreta. Reseña: ', texto
    )
  ) AS respuesta_sugerida
FROM gold_resenas_ia
WHERE sentimiento = 'negative'
LIMIT 15;

-- COMMAND ----------

SELECT texto, respuesta_sugerida FROM gold_respuestas_sugeridas;
