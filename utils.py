# utils.py
import random
import string
import subprocess
import json
import os
import requests
import tempfile
from requests.exceptions import RequestException, Timeout, ConnectionError

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
DEFAULT_TIMEOUT = 5  # segundos

# ---------------- Config ----------------
def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ No se pudo cargar config.json: {e}")
        return {}

def get_backend_url(path=""):
    config = load_config()
    base_url = config.get("backend_url", "http://localhost:5000").rstrip("/")
    if path:
        return f"{base_url}/{path.lstrip('/')}"
    return base_url

# ---------------- Utils varias ----------------
def generar_serial(prefix="DEV", length=8):
    rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{rand_part}"

def clamp(v, mn, mx):
    return max(mn, min(mx, v))

def listar_dispositivos_backend():
    try:
        resp = requests.get(get_backend_url("dispositivos"), timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        print(f"❌ Error al listar dispositivos: {resp.status_code}")
    except (Timeout, ConnectionError, RequestException) as e:
        print(f"❌ No se pudo conectar al backend: {e}")
    return []

# ---------------- Normalización de configuración ----------------
def _strip_schedule_channels(cfg: dict):
    """Elimina canales de horarios cuando modo='manual' para evitar choques."""
    for k in list(cfg.keys()):
        if k.startswith("horarios"):
            cfg.pop(k, None)

# ---------------- Opción 10: Reclamar dispositivo ----------------
def reclamar_dispositivo(serial, templates):
    prefix = serial[:4]
    template = next((t for t in templates if t.get("serial_prefix") == prefix), None)

    if not template:
        print(f"❌ No se encontró template para prefijo {prefix}")
        return

    payload = {
        "serial_number": serial,
        "nombre": template.get("nombre", ""),
        "tipo": template.get("tipo", ""),
        "modelo": template.get("modelo", ""),
        "descripcion": template.get("descripcion", ""),
        "configuracion": template.get("configuracion", {}) or {},
        # Si empiezas a usar capabilities en las plantillas
        "capabilities": template.get("capabilities", [])
    }

    # Guardamos el payload en un archivo temporal y se lo pasamos al .ps1
    try:
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tf:
            json.dump(payload, tf, ensure_ascii=False)
            tmp_path = tf.name

        subprocess.run([
            "powershell", "-ExecutionPolicy", "Bypass",
            "-File", os.path.join(SCRIPTS_DIR, "reclamar.ps1"),
            "-payloadPath", tmp_path
        ], check=False)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

# ---------------- Opción 11: Modificar dispositivo ----------------
def modificar_dispositivo():
    serial = input("Ingrese el serial del dispositivo a modificar: ").strip()
    dispositivos = listar_dispositivos_backend()

    if not dispositivos:
        print("❌ No hay dispositivos en el backend o no se pudo conectar.")
        return

    dispositivo = next((d for d in dispositivos if d.get("serial_number") == serial), None)
    if not dispositivo:
        print(f"❌ No se encontró un dispositivo con serial {serial}")
        return

    print(f"✅ Dispositivo encontrado: {dispositivo.get('nombre', 'Sin nombre')} ({serial})")

    opciones = {
        "1": "nombre",
        "2": "tipo",
        "3": "modelo",
        "4": "descripcion",
        "5": "configuracion"
    }

    print("¿Qué desea modificar?")
    for k, v in opciones.items():
        print(f"{k}) {v}")

    choice = input("Opción: ").strip()
    if choice not in opciones:
        print("❌ Opción inválida")
        return

    campo = opciones[choice]

    if campo == "configuracion":
        print('Ingrese el JSON parcial con los cambios (ej: {"modo": "horario"}):')
        raw_valor = input("> ").strip()
        try:
            nuevo_valor = json.loads(raw_valor)
            if not isinstance(nuevo_valor, dict):
                print("❌ La configuración debe ser un objeto JSON (ej: {\"encendido\": true})")
                return
        except json.JSONDecodeError as e:
            print(f"❌ JSON inválido: {e}")
            return

        config_actual = (dispositivo.get("configuracion") or {}).copy()
        config_actual.update(nuevo_valor)

        # Normalización real del modo
        modo = (config_actual.get("modo") or "").lower()
        if modo == "manual":
            # En manual manda 'encendido'; elimina horarios* para que no choquen
            _strip_schedule_channels(config_actual)
            if "encendido" not in config_actual:
                config_actual["encendido"] = True
            print("✅ Modo 'manual': se eliminaron canales 'horarios*' y se respetará 'encendido'.")
        elif modo == "horario":
            # En horario mandan los canales de horarios; no fuerces 'encendido'
            if not any(k.startswith("horarios") for k in config_actual.keys()):
                print("⚠️ Modo 'horario' sin canales 'horarios*' definidos.")
            print("✅ Modo 'horario': los horarios controlan el estado.")
        else:
            print("ℹ️ 'modo' no cambiado.")

        payload = {"configuracion": config_actual}

    else:
        nuevo_valor = input(f"Ingrese el nuevo valor para {campo}: ").strip()
        if not nuevo_valor:
            print("❌ El valor no puede estar vacío.")
            return
        payload = {campo: nuevo_valor}

    print("📤 Enviando actualización al backend (PowerShell)...")

    # Igual que en reclamar: pasamos por archivo temporal para evitar problemas de comillas
    try:
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tf:
            json.dump(payload, tf, ensure_ascii=False)
            tmp_path = tf.name

        subprocess.run([
            "powershell", "-ExecutionPolicy", "Bypass",
            "-File", os.path.join(SCRIPTS_DIR, "modificar.ps1"),
            "-id", str(dispositivo["id"]),
            "-payloadPath", tmp_path
        ], check=False)
    except Exception as e:
        print(f"❌ Error al ejecutar script PowerShell: {e}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass