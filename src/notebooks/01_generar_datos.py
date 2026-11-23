# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Generar datos de TicoMarket (e-commerce)
# MAGIC
# MAGIC Simulamos el sistema transaccional de una tienda en línea de Costa Rica.
# MAGIC Cada ejecución deja **archivos JSON** en un *Volume* de Unity Catalog, igual que si
# MAGIC una aplicación los exportara cada noche:
# MAGIC
# MAGIC | Carpeta | Contenido |
# MAGIC |---|---|
# MAGIC | `clientes/` | clientes registrados (solo lote 1) |
# MAGIC | `productos/` | catálogo de productos (solo lote 1) |
# MAGIC | `ordenes/` | órdenes con sus líneas (arreglo anidado `items`) |
# MAGIC | `resenas/` | reseñas en texto libre escritas por los clientes |
# MAGIC
# MAGIC * **Lote 1** = un año de historia.
# MAGIC * **Lote 2, 3, …** = un día nuevo de órdenes → sirve para mostrar ingesta **incremental** con Auto Loader.
# MAGIC
# MAGIC Los datos traen errores a propósito (clientes nulos, cantidades negativas, órdenes duplicadas)
# MAGIC para mostrar las reglas de calidad del pipeline.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "ulatina_ecommerce")
dbutils.widgets.text("lote", "1")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
LOTE = int(dbutils.widgets.get("lote"))
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
print(f"Destino: {RAW} · lote {LOTE}")

# COMMAND ----------

import json
import os
import random
from datetime import date, datetime, timedelta

FECHA_BASE = date(2026, 11, 15)   # último día del histórico (lote 1)
INICIO = FECHA_BASE - timedelta(days=364)
CORTE_CHURN = FECHA_BASE - timedelta(days=60)

N_CLIENTES = 3000
PROVINCIAS = ["San José", "Alajuela", "Heredia", "Cartago", "Puntarenas", "Guanacaste", "Limón"]
PESO_PROV = [0.36, 0.20, 0.13, 0.12, 0.08, 0.07, 0.04]
CANALES = ["Orgánico", "Google Ads", "Instagram", "Facebook Ads", "Referido"]
PESO_CANAL = [0.30, 0.25, 0.20, 0.15, 0.10]
METODOS_PAGO = ["Tarjeta", "SINPE Móvil", "PayPal", "Contra entrega"]
NOMBRES = ["Ana", "Luis", "María", "José", "Sofía", "Carlos", "Valeria", "Diego", "Camila", "Andrés",
           "Daniela", "Pablo", "Fernanda", "Mateo", "Gabriela", "Javier", "Natalia", "Esteban", "Paula", "Kevin"]
APELLIDOS = ["Rodríguez", "Vargas", "Jiménez", "Mora", "Rojas", "Solano", "Castro", "Quesada",
             "Chaves", "Araya", "Herrera", "Salazar", "Alfaro", "Calderón", "Segura", "Ulate"]

# Precio base aproximado en colones (₡) por producto.
CATEGORIAS = {
    "Electrónica":  {"Audífonos": 25000, "Parlante Bluetooth": 35000, "Smartwatch": 95000, "Cargador rápido": 12000,
                     "Teclado mecánico": 45000, "Mouse inalámbrico": 15000},
    "Hogar":        {"Cafetera": 40000, "Licuadora": 35000, "Juego de sábanas": 22000, "Lámpara LED": 12000,
                     "Olla arrocera": 28000, "Ventilador": 30000},
    "Moda":         {"Camiseta": 9000, "Tenis deportivas": 45000, "Mochila": 25000, "Gorra": 8000,
                     "Jacket impermeable": 38000, "Lentes de sol": 18000},
    "Deportes":     {"Bola de fútbol": 15000, "Mat de yoga": 14000, "Botella térmica": 11000, "Mancuernas": 30000,
                     "Bicicleta estática": 180000, "Raqueta": 40000},
    "Supermercado": {"Café molido 1kg": 6500, "Chocolate artesanal": 3500, "Salsa Lizano": 1800, "Miel de abeja": 5000,
                     "Granola": 4000, "Té verde": 3000},
    "Libros":       {"Novela": 12000, "Libro de cocina": 18000, "Cómic": 8000, "Libro de Python": 22000,
                     "Agenda 2027": 7000, "Libro infantil": 9000},
}
MARCAS = ["Pura Vida", "Tuanis", "Volcán", "Quetzal", "Arenal", "Chirripó", "Manglar"]

TEMAS = ["entrega", "calidad", "precio", "atención al cliente"]
PLANTILLAS = {
    "positivo": {
        "entrega": ["Llegó antes de lo esperado, súper rápido el envío a {prov}.", "La entrega fue puntual y el paquete venía bien protegido."],
        "calidad": ["Excelente calidad, el {prod} superó mis expectativas.", "Muy buen producto, se nota que es duradero."],
        "precio": ["Muy buen precio comparado con otras tiendas.", "Por lo que cuesta, el {prod} vale totalmente la pena."],
        "atención al cliente": ["Me atendieron muy amablemente por WhatsApp.", "El servicio al cliente resolvió mi duda en minutos."],
    },
    "negativo": {
        "entrega": ["El pedido tardó más de dos semanas en llegar a {prov}.", "Nunca me avisaron del envío y la caja llegó golpeada."],
        "calidad": ["El {prod} se dañó a los pocos días, mala calidad.", "No se parece a las fotos, material muy barato."],
        "precio": ["Demasiado caro para lo que es, no lo recomiendo.", "Me cobraron un envío carísimo, no vuelvo a comprar."],
        "atención al cliente": ["Escribí tres veces y nadie me respondió.", "Pedí una devolución y me trataron muy mal."],
    },
    "neutral": {
        "entrega": ["El envío llegó en el tiempo indicado.", "Entrega normal, sin problemas."],
        "calidad": ["El {prod} cumple, nada especial.", "Producto aceptable para uso diario."],
        "precio": ["El precio está dentro de lo normal.", "Precio razonable."],
        "atención al cliente": ["La atención fue correcta.", "Respondieron, aunque un poco lento."],
    },
}

rnd = random.Random(42 + LOTE)

def ts(d: date) -> str:
    return datetime(d.year, d.month, d.day, rnd.randint(6, 23), rnd.randint(0, 59), rnd.randint(0, 59)).isoformat()

def escribir(carpeta: str, filas: list) -> None:
    os.makedirs(f"{RAW}/{carpeta}", exist_ok=True)
    ruta = f"{RAW}/{carpeta}/lote_{LOTE:03d}.json"
    with open(ruta, "w", encoding="utf-8") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    print(f"  {ruta}: {len(filas):,} filas")

# COMMAND ----------

# MAGIC %md ## Clientes y productos (maestros)

# COMMAND ----------

# Los maestros se generan siempre con la misma semilla para que todos los lotes sean coherentes.
rm = random.Random(7)

productos = []
pid = 1
for cat, nombres in CATEGORIAS.items():
    for nombre, base in nombres.items():
        for _ in range(3):   # 3 marcas por producto
            precio = round(base * rm.uniform(0.8, 1.3), -2)
            productos.append({
                "producto_id": f"P{pid:04d}",
                "nombre": f"{nombre} {rm.choice(MARCAS)}",
                "categoria": cat,
                "precio_crc": precio,
                "costo_crc": round(precio * rm.uniform(0.45, 0.75), -2),
            })
            pid += 1

clientes = []
for i in range(1, N_CLIENTES + 1):
    nombre, apellido = rm.choice(NOMBRES), rm.choice(APELLIDOS)
    canal = rm.choices(CANALES, PESO_CANAL)[0]
    # El "abandono" es la verdad oculta que el modelo de ML intentará descubrir.
    p_abandono = 0.18 + (0.15 if canal == "Facebook Ads" else 0) + (0.08 if canal == "Instagram" else 0)
    clientes.append({
        "cliente_id": f"C{i:05d}",
        "nombre": f"{nombre} {apellido}",
        "email": f"{nombre.lower()}.{apellido.lower()}{i}@correo.cr".replace("í", "i").replace("é", "e").replace("á", "a").replace("ó", "o").replace("ú", "u"),
        "telefono": f"+506 {rm.randint(6000, 8999)}-{rm.randint(1000, 9999)}",
        "provincia": rm.choices(PROVINCIAS, PESO_PROV)[0],
        "canal_adquisicion": canal,
        "fecha_registro": (INICIO - timedelta(days=rm.randint(0, 700))).isoformat(),
        "_abandona": rm.random() < p_abandono,
        "_frecuencia": rm.choice([0.01, 0.02, 0.03, 0.05, 0.08]),  # órdenes por día
        "_fecha_abandono": (CORTE_CHURN - timedelta(days=rm.randint(1, 200))).isoformat(),
    })

if LOTE == 1:
    print("Maestros:")
    escribir("productos", productos)
    escribir("clientes", [{k: v for k, v in c.items() if not k.startswith("_")} for c in clientes])

# COMMAND ----------

# MAGIC %md ## Órdenes y reseñas

# COMMAND ----------

if LOTE == 1:
    dias = [INICIO + timedelta(days=d) for d in range(365)]
else:
    dias = [FECHA_BASE + timedelta(days=LOTE - 1)]

ordenes, resenas = [], []
for c in clientes:
    fin = date.fromisoformat(c["_fecha_abandono"]) if c["_abandona"] else dias[-1]
    for d in dias:
        if d > fin or rnd.random() > c["_frecuencia"]:
            continue
        n_items = rnd.choices([1, 2, 3, 4], [0.55, 0.25, 0.13, 0.07])[0]
        items = []
        for p in rnd.sample(productos, n_items):
            items.append({"producto_id": p["producto_id"], "cantidad": rnd.choices([1, 2, 3], [0.8, 0.15, 0.05])[0],
                          "precio_unitario_crc": p["precio_crc"]})
        estado = rnd.choices(["completada", "cancelada", "devuelta"],
                             [0.80, 0.08, 0.12] if c["_abandona"] else [0.92, 0.05, 0.03])[0]
        orden = {
            "orden_id": f"O{LOTE:03d}-{len(ordenes) + 1:07d}",
            "cliente_id": c["cliente_id"],
            "fecha_orden": ts(d),
            "estado": estado,
            "metodo_pago": rnd.choice(METODOS_PAGO),
            "costo_envio_crc": rnd.choice([0, 1500, 2500, 3500]),
            "items": items,
        }
        # --- errores intencionales de calidad ---
        r = rnd.random()
        if r < 0.01:
            orden["cliente_id"] = None
        elif r < 0.015:
            orden["items"][0]["cantidad"] = -1
        ordenes.append(orden)
        if r > 0.997:
            ordenes.append(dict(orden))   # duplicado

        # --- reseña ---
        if estado != "cancelada" and rnd.random() < (0.35 if c["_abandona"] else 0.15):
            if c["_abandona"]:
                sent = rnd.choices(["negativo", "neutral", "positivo"], [0.65, 0.25, 0.10])[0]
            else:
                sent = rnd.choices(["positivo", "neutral", "negativo"], [0.65, 0.25, 0.10])[0]
            tema = rnd.choice(TEMAS)
            prod = next(p for p in productos if p["producto_id"] == items[0]["producto_id"])
            texto = rnd.choice(PLANTILLAS[sent][tema]).format(prod=prod["nombre"], prov=c["provincia"])
            rating = {"positivo": rnd.choice([4, 5, 5]), "neutral": 3, "negativo": rnd.choice([1, 1, 2])}[sent]
            resenas.append({
                "resena_id": f"R{LOTE:03d}-{len(resenas) + 1:06d}",
                "orden_id": orden["orden_id"],
                "cliente_id": c["cliente_id"],
                "producto_id": prod["producto_id"],
                "calificacion": rating,
                "texto": texto,
                "fecha_resena": ts(d + timedelta(days=rnd.randint(2, 10))),
            })

print("Transaccionales:")
escribir("ordenes", ordenes)
escribir("resenas", resenas)

# COMMAND ----------

display(dbutils.fs.ls(f"{RAW}/ordenes"))
