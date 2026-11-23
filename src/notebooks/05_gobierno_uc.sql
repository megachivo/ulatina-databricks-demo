-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 05 · Gobierno con Unity Catalog
-- MAGIC
-- MAGIC Un solo lugar para **permisos, auditoría, linaje y descubrimiento** de datos, modelos y archivos.
-- MAGIC
-- MAGIC 1. Documentar: comentarios y *tags* (p. ej. marcar columnas con datos personales, PII).
-- MAGIC 2. Proteger: enmascarar el correo y el teléfono para quien no sea del grupo autorizado.
-- MAGIC 3. Permisos: `GRANT` / `REVOKE` con SQL estándar.
-- MAGIC 4. Linaje: lo genera Databricks solo (ver pestaña **Lineage** en Catalog Explorer).
-- MAGIC 5. Auditoría: tablas de sistema (`system.access.audit`).

-- COMMAND ----------

CREATE WIDGET TEXT catalog DEFAULT 'workspace';
CREATE WIDGET TEXT schema DEFAULT 'ulatina_ecommerce';

-- COMMAND ----------

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

-- COMMAND ----------

-- MAGIC %md ## 1. Tags: clasificar datos sensibles

-- COMMAND ----------

ALTER SCHEMA IDENTIFIER(:schema) SET TAGS ('dominio' = 'ecommerce', 'curso' = 'ulatina');

-- COMMAND ----------

ALTER TABLE gold_riesgo_abandono SET TAGS ('capa' = 'gold', 'origen' = 'modelo_ml');
ALTER TABLE gold_resenas_ia      SET TAGS ('capa' = 'gold', 'origen' = 'ai_functions');

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 2. Enmascarar datos personales (column masks)
-- MAGIC La función decide qué ve cada usuario. Solo el grupo `admins` ve el dato real.
-- MAGIC (Las tablas que crea el pipeline se protegen igual, declarando el `MASK` en su definición.)

-- COMMAND ----------

CREATE OR REPLACE FUNCTION mascara_email(email STRING)
RETURN CASE WHEN is_account_group_member('admins') THEN email
            ELSE CONCAT(LEFT(email, 2), '****@', SPLIT_PART(email, '@', 2)) END;

CREATE OR REPLACE FUNCTION mascara_telefono(telefono STRING)
RETURN CASE WHEN is_account_group_member('admins') THEN telefono
            ELSE CONCAT('+506 ****-', RIGHT(telefono, 4)) END;

-- COMMAND ----------

-- Copia gestionada de los clientes para la parte de mercadeo (fuera del pipeline).
CREATE OR REPLACE TABLE clientes_mercadeo
COMMENT 'Clientes para campañas de mercadeo; email y teléfono enmascarados.'
AS SELECT c.*, r.prob_abandono, r.segmento_riesgo
FROM silver_clientes c
LEFT JOIN gold_riesgo_abandono r USING (cliente_id);

ALTER TABLE clientes_mercadeo ALTER COLUMN email    SET MASK mascara_email;
ALTER TABLE clientes_mercadeo ALTER COLUMN telefono SET MASK mascara_telefono;
ALTER TABLE clientes_mercadeo ALTER COLUMN email    SET TAGS ('pii' = 'email');
ALTER TABLE clientes_mercadeo ALTER COLUMN telefono SET TAGS ('pii' = 'telefono');

-- COMMAND ----------

SELECT cliente_id, nombre, email, telefono, segmento_riesgo FROM clientes_mercadeo LIMIT 10;

-- COMMAND ----------

-- MAGIC %md ## 3. Filtros de fila: cada gerente regional ve solo su provincia

-- COMMAND ----------

CREATE OR REPLACE FUNCTION filtro_provincia(provincia STRING)
RETURN is_account_group_member('admins') OR provincia = 'San José';

CREATE OR REPLACE VIEW v_ventas_gerente_regional
COMMENT 'Ejemplo de vista segura: quien no es admin solo ve San José.'
AS SELECT * FROM gold_ventas_diarias WHERE filtro_provincia(provincia);

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 4. Permisos
-- MAGIC ```sql
-- MAGIC GRANT USE SCHEMA ON SCHEMA ulatina_ecommerce TO `estudiantes`;
-- MAGIC GRANT SELECT ON TABLE clientes_mercadeo TO `estudiantes`;
-- MAGIC SHOW GRANTS ON TABLE clientes_mercadeo;
-- MAGIC ```

-- COMMAND ----------

SHOW GRANTS ON TABLE clientes_mercadeo;

-- COMMAND ----------

-- MAGIC %md ## 5. Descubrimiento: buscar todo lo marcado como PII

-- COMMAND ----------

SELECT catalog_name, schema_name, table_name, column_name, tag_name, tag_value
FROM system.information_schema.column_tags
WHERE schema_name = :schema;
