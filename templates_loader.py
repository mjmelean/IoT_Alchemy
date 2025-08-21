# templates_loader.py
import os
import json

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

def cargar_plantillas():
    plantillas = {}
    if not os.path.isdir(TEMPLATE_DIR):
        return plantillas
    for archivo in os.listdir(TEMPLATE_DIR):
        if archivo.endswith(".json"):
            nombre = archivo.replace(".json", "")
            ruta = os.path.join(TEMPLATE_DIR, archivo)
            with open(ruta, "r", encoding="utf-8") as f:
                plantillas[nombre] = json.load(f)
    return plantillas
