-- =====================================================================
-- SILVER: datos limpios, tipados y confiables.
-- Las EXPECTATIONS son reglas de calidad declarativas:
--   * ON VIOLATION DROP ROW -> descarta la fila mala
--   * (sin acción)          -> deja pasar la fila pero la cuenta como alerta
-- Los resultados se ven en la UI del pipeline (pestaña "Data quality").
-- =====================================================================

CREATE OR REFRESH MATERIALIZED VIEW silver_clientes (
  CONSTRAINT cliente_id_presente EXPECT (cliente_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT email_valido        EXPECT (email LIKE '%@%.%')
)
COMMENT "Un registro por cliente, con tipos correctos."
AS SELECT
  cliente_id,
  nombre,
  email,
  telefono,
  provincia,
  canal_adquisicion,
  CAST(fecha_registro AS DATE) AS fecha_registro
FROM bronze_clientes
QUALIFY row_number() OVER (PARTITION BY cliente_id ORDER BY fecha_ingesta DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_productos (
  CONSTRAINT precio_positivo EXPECT (precio_crc > 0) ON VIOLATION DROP ROW
)
COMMENT "Catálogo limpio con margen unitario calculado."
AS SELECT
  producto_id,
  nombre AS producto,
  categoria,
  CAST(precio_crc AS DOUBLE) AS precio_crc,
  CAST(costo_crc AS DOUBLE)  AS costo_crc,
  CAST(precio_crc - costo_crc AS DOUBLE) AS margen_unitario_crc
FROM bronze_productos
QUALIFY row_number() OVER (PARTITION BY producto_id ORDER BY fecha_ingesta DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_ordenes (
  CONSTRAINT cliente_presente EXPECT (cliente_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT estado_conocido  EXPECT (estado IN ('completada', 'cancelada', 'devuelta'))
)
COMMENT "Encabezado de órdenes: sin duplicados y sin clientes nulos."
AS SELECT
  orden_id,
  cliente_id,
  CAST(fecha_orden AS TIMESTAMP) AS fecha_orden,
  CAST(fecha_orden AS DATE)      AS fecha,
  estado,
  metodo_pago,
  CAST(costo_envio_crc AS DOUBLE) AS costo_envio_crc,
  items
FROM bronze_ordenes
QUALIFY row_number() OVER (PARTITION BY orden_id ORDER BY fecha_ingesta DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_lineas_orden (
  CONSTRAINT cantidad_positiva EXPECT (cantidad > 0) ON VIOLATION DROP ROW
)
COMMENT "Una fila por producto dentro de cada orden (explode del arreglo items)."
AS SELECT
  o.orden_id,
  o.cliente_id,
  o.fecha,
  o.estado,
  i.producto_id,
  i.cantidad,
  i.precio_unitario_crc,
  i.cantidad * i.precio_unitario_crc AS subtotal_crc
FROM silver_ordenes o
LATERAL VIEW explode(o.items) AS i;

CREATE OR REFRESH MATERIALIZED VIEW silver_resenas (
  CONSTRAINT calificacion_valida EXPECT (calificacion BETWEEN 1 AND 5) ON VIOLATION DROP ROW,
  CONSTRAINT texto_presente      EXPECT (length(texto) > 5)
)
COMMENT "Reseñas limpias, listas para analizarlas con IA."
AS SELECT
  resena_id,
  orden_id,
  cliente_id,
  producto_id,
  CAST(calificacion AS INT) AS calificacion,
  texto,
  CAST(fecha_resena AS TIMESTAMP) AS fecha_resena
FROM bronze_resenas
QUALIFY row_number() OVER (PARTITION BY resena_id ORDER BY fecha_ingesta DESC) = 1;
