-- =====================================================================
-- BRONZE: copia fiel de lo que llega al Volume, sin transformar.
-- `STREAM read_files(...)` = Auto Loader: cada ejecución lee SOLO los
-- archivos nuevos (ingesta incremental) e infiere el esquema del JSON.
-- =====================================================================

CREATE OR REFRESH STREAMING TABLE bronze_clientes
COMMENT "Clientes tal como llegan del sistema de la tienda (JSON)."
AS SELECT
  *,
  _metadata.file_path AS archivo_origen,
  current_timestamp() AS fecha_ingesta
FROM STREAM read_files('${raw_path}/clientes', format => 'json');

CREATE OR REFRESH STREAMING TABLE bronze_productos
COMMENT "Catálogo de productos tal como llega (JSON)."
AS SELECT
  *,
  _metadata.file_path AS archivo_origen,
  current_timestamp() AS fecha_ingesta
FROM STREAM read_files('${raw_path}/productos', format => 'json');

CREATE OR REFRESH STREAMING TABLE bronze_ordenes
COMMENT "Órdenes crudas; cada una trae un arreglo anidado de items."
AS SELECT
  *,
  _metadata.file_path AS archivo_origen,
  current_timestamp() AS fecha_ingesta
FROM STREAM read_files(
  '${raw_path}/ordenes',
  format => 'json',
  schemaHints => 'items ARRAY<STRUCT<producto_id STRING, cantidad INT, precio_unitario_crc DOUBLE>>'
);

CREATE OR REFRESH STREAMING TABLE bronze_resenas
COMMENT "Reseñas en texto libre escritas por los clientes."
AS SELECT
  *,
  _metadata.file_path AS archivo_origen,
  current_timestamp() AS fecha_ingesta
FROM STREAM read_files('${raw_path}/resenas', format => 'json');
