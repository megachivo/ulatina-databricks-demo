-- =====================================================================
-- GOLD: tablas de negocio listas para dashboards, Genie y ML.
-- =====================================================================

CREATE OR REFRESH MATERIALIZED VIEW gold_ventas_diarias
COMMENT "Ventas completadas por día, provincia, categoría y canal de adquisición."
AS SELECT
  l.fecha,
  c.provincia,
  p.categoria,
  c.canal_adquisicion,
  COUNT(DISTINCT l.orden_id)               AS ordenes,
  SUM(l.cantidad)                          AS unidades,
  SUM(l.subtotal_crc)                      AS ingreso_crc,
  SUM(l.cantidad * p.margen_unitario_crc)  AS margen_crc
FROM silver_lineas_orden l
JOIN silver_productos p USING (producto_id)
JOIN silver_clientes  c USING (cliente_id)
WHERE l.estado = 'completada'
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW gold_productos
COMMENT "Desempeño por producto: ventas, margen y calificación promedio."
AS WITH ventas AS (
  SELECT producto_id,
         SUM(cantidad)     AS unidades,
         SUM(subtotal_crc) AS ingreso_crc
  FROM silver_lineas_orden
  WHERE estado = 'completada'
  GROUP BY producto_id
), resenas AS (
  SELECT producto_id,
         COUNT(*)                         AS resenas,
         ROUND(AVG(calificacion), 2)      AS calificacion_promedio
  FROM silver_resenas
  GROUP BY producto_id
)
SELECT p.producto_id, p.producto, p.categoria, p.precio_crc,
       COALESCE(v.unidades, 0)    AS unidades,
       COALESCE(v.ingreso_crc, 0) AS ingreso_crc,
       COALESCE(v.unidades, 0) * p.margen_unitario_crc AS margen_crc,
       COALESCE(r.resenas, 0)     AS resenas,
       r.calificacion_promedio
FROM silver_productos p
LEFT JOIN ventas  v USING (producto_id)
LEFT JOIN resenas r USING (producto_id);

-- ---------------------------------------------------------------------
-- Vista 360 del cliente para el modelo de ABANDONO (churn).
-- Fecha de corte = último día con datos - 60 días.
--   * Variables (features): solo usan información ANTES del corte.
--   * Etiqueta `abandono`  : 1 si el cliente NO compró después del corte.
-- Así evitamos "ver el futuro" (data leakage).
-- ---------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW gold_clientes_360
COMMENT "Variables por cliente antes de la fecha de corte + etiqueta de abandono (churn)."
AS WITH corte AS (
  SELECT date_sub(MAX(fecha), 60) AS fecha_corte FROM silver_ordenes
), hist AS (
  SELECT o.* FROM silver_ordenes o, corte WHERE o.fecha <= corte.fecha_corte
), futuro AS (
  SELECT DISTINCT o.cliente_id FROM silver_ordenes o, corte
  WHERE o.fecha > corte.fecha_corte AND o.estado = 'completada'
), compras AS (
  SELECT h.cliente_id,
         COUNT(*)                                             AS ordenes,
         SUM(CASE WHEN h.estado = 'devuelta' THEN 1 ELSE 0 END) / COUNT(*) AS tasa_devolucion,
         SUM(CASE WHEN h.estado = 'cancelada' THEN 1 ELSE 0 END) / COUNT(*) AS tasa_cancelacion,
         MAX(h.fecha)                                         AS ultima_compra,
         MIN(h.fecha)                                         AS primera_compra,
         mode(h.metodo_pago)                                  AS metodo_pago_preferido
  FROM hist h GROUP BY h.cliente_id
), gasto AS (
  SELECT l.cliente_id,
         SUM(l.subtotal_crc)            AS gasto_total_crc,
         COUNT(DISTINCT p.categoria)    AS categorias_distintas
  FROM silver_lineas_orden l
  JOIN silver_productos p USING (producto_id)
  JOIN hist h ON h.orden_id = l.orden_id
  WHERE l.estado = 'completada'
  GROUP BY l.cliente_id
), opinion AS (
  SELECT r.cliente_id,
         COUNT(*)                                              AS resenas,
         AVG(r.calificacion)                                   AS calificacion_promedio,
         SUM(CASE WHEN r.calificacion <= 2 THEN 1 ELSE 0 END)  AS resenas_negativas
  FROM silver_resenas r, corte
  WHERE CAST(r.fecha_resena AS DATE) <= corte.fecha_corte
  GROUP BY r.cliente_id
)
SELECT
  c.cliente_id,
  c.provincia,
  c.canal_adquisicion,
  k.metodo_pago_preferido,
  datediff(corte.fecha_corte, c.fecha_registro)  AS antiguedad_dias,
  k.ordenes,
  COALESCE(g.gasto_total_crc, 0)                 AS gasto_total_crc,
  COALESCE(g.gasto_total_crc, 0) / k.ordenes     AS ticket_promedio_crc,
  COALESCE(g.categorias_distintas, 0)            AS categorias_distintas,
  datediff(corte.fecha_corte, k.ultima_compra)   AS dias_desde_ultima_compra,
  k.tasa_devolucion,
  k.tasa_cancelacion,
  COALESCE(o.resenas, 0)                         AS resenas,
  o.calificacion_promedio,
  COALESCE(o.resenas_negativas, 0)               AS resenas_negativas,
  CASE WHEN f.cliente_id IS NULL THEN 1 ELSE 0 END AS abandono
FROM compras k
JOIN silver_clientes c USING (cliente_id)
CROSS JOIN corte
LEFT JOIN gasto   g USING (cliente_id)
LEFT JOIN opinion o USING (cliente_id)
LEFT JOIN futuro  f USING (cliente_id);
