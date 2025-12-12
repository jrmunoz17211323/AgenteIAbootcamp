from flask import Flask, request, jsonify
import json
import re
import os

app = Flask(__name__)

# Cargar inventario desde archivo JSON (se recarga al iniciar la app)
INVENTORY_PATH = os.path.join(os.path.dirname(__file__), "inventory.json")

def load_inventory():
    try:
        with open(INVENTORY_PATH, "r", encoding="utf-8") as f:
            items = json.load(f)
            # convertir a dict por nombre en minúsculas para búsqueda simple
            return {i["name"].lower(): i for i in items}
    except Exception:
        return {}

inventory = load_inventory()

@app.get("/")
def home():
    return "Agente de prueba funcionando correctamente"

@app.get("/inventario")
def ver_inventario():
    # Devuelve inventario rápido (resumen)
    return jsonify(list(inventory.values()))

def parse_items_from_message(message):
    """
    Intento sencillo de extraer (producto, cantidad) desde texto libre.
    Regla básica:
      - Busca patrones "N <producto>" (ej: '5 cemento') o '<producto> 5' o solo el nombre.
      - Si encuentra nombre sin número asume cantidad = 1.
    """
    message_l = message.lower()
    found = []
    # buscar "numero + producto"
    for name in inventory.keys():
        # patrón: número seguido del nombre (ej. "5 cemento")
        m = re.search(r"(\d+)\s*(?:bultos|unidades|uds|u|kg| )?\s*" + re.escape(name), message_l)
        if m:
            qty = int(m.group(1))
            found.append((name, qty))
            continue
        # patrón: nombre seguido de número (ej. "cemento 5")
        m2 = re.search(re.escape(name) + r"\s*(\d+)", message_l)
        if m2:
            qty = int(m2.group(1))
            found.append((name, qty))
            continue
        # si aparece el nombre sin número -> asumir 1
        if name in message_l:
            # verificar que no hay ya un ítem registrado (para no duplicar)
            if not any(n == name for n,_ in found):
                found.append((name, 1))
    return found

@app.post("/agente")
def agente():
    """
    Espera JSON con:
      - 'mensaje': texto libre (ej: "Necesito 5 cemento y 2 varilla")
    O bien:
      - 'items': lista de objetos {"name":"cemento","cantidad":5}
    Devuelve JSON con detalle y total.
    """
    data = request.get_json(force=True, silent=True) or {}
    items_to_quote = []

    # Modo 1: lista estructurada
    if isinstance(data.get("items"), list):
        for it in data["items"]:
            name = (it.get("name") or "").strip().lower()
            qty = int(it.get("cantidad") or it.get("qty") or 1)
            if name:
                items_to_quote.append((name, qty))

    # Modo 2: texto libre
    elif isinstance(data.get("mensaje"), str):
        parsed = parse_items_from_message(data["mensaje"])
        items_to_quote.extend(parsed)

    # Si no dieron nada, devolver ayuda
    if not items_to_quote:
        return jsonify({
            "error": "No encontré ítems a cotizar. Envía 'items' o 'mensaje'. Ej: {\"mensaje\":\"Necesito 5 cemento\"}"
        }), 400

    # Construir cotización
    detalle = []
    total = 0
    missing = []
    for name, qty in items_to_quote:
        if name in inventory:
            product = inventory[name]
            unit_price = float(product.get("price", 0))
            subtotal = unit_price * int(qty)
            # sumar con precisión básica
            total += subtotal
            detalle.append({
                "sku": product.get("sku"),
                "name": product.get("name"),
                "cantidad": int(qty),
                "precio_unitario": unit_price,
                "subtotal": subtotal
            })
        else:
            missing.append({"name": name, "cantidad": qty})

    response = {
        "detalle": detalle,
        "total": total,
        "faltantes_en_inventario": missing,
        "mensaje_origen": data.get("mensaje") if data.get("mensaje") else None
    }

    return jsonify(response)

if __name__ == "__main__":
    # puerto ya configurado en Render (10000), local default 10000 también
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
