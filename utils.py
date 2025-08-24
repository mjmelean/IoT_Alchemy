# utils.py
import random
import string
import subprocess
import json
import os
import requests

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")

def generar_serial(prefix="DEV", length=8):
    rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{rand_part}"

def clamp(v, mn, mx):
    return max(mn, min(mx, v))

def listar_dispositivos_backend(base_url="http://localhost:5000"):
    try:
        resp = requests.get(f"{base_url}/dispositivos")
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"❌ Error al listar dispositivos: {resp.status_code}")
            return []
    except Exception as e:
        print(f"❌ No se pudo conectar al backend: {e}")
        return []

#Utilizado opcion 11
def reclamar_dispositivo(serial, templates):
    prefix = serial[:4]
    template = next((t for t in templates if t.get("serial_prefix") == prefix), None)

    if not template:
        print(f"❌ No se encontró template para prefijo {prefix}")
        return

    # Construcción del payload
    payload = {
        "serial_number": serial,
        "nombre": template.get("nombre", ""),
        "tipo": template.get("tipo", ""),
        "modelo": template.get("modelo", ""),
        "descripcion": template.get("descripcion", ""),
        "configuracion": template.get("configuracion", {})
    }

    # Pasar parametros al script de PowerShell
    subprocess.run([
        "powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/reclamar.ps1",
        "-serial_number", payload["serial_number"],
        "-nombre", payload["nombre"],
        "-tipo", payload["tipo"],
        "-modelo", payload["modelo"],
        "-descripcion", payload["descripcion"],
        "-configuracion", json.dumps(payload["configuracion"])
    ])

#Utilizado opcion 12

def modificar_dispositivo(base_url="http://localhost:5000"):
    serial = input("Ingrese el serial del dispositivo a modificar: ").strip()

    dispositivos = listar_dispositivos_backend(base_url)
    if not dispositivos:
        print("❌ No hay dispositivos en el backend o no se pudo conectar.")
        return

    dispositivo = next((d for d in dispositivos if d.get("serial_number") == serial), None)
    if not dispositivo:
        print(f"❌ No se encontró un dispositivo con serial {serial}")
        return

    print(f"✅ Dispositivo encontrado: {dispositivo.get('nombre', 'Sin nombre')} ({serial})")

    # Opciones editables
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
    nuevo_valor = input(f"Ingrese el nuevo valor para {campo}: ").strip()

    if campo == "configuracion":
        try:
            nuevo_valor = json.loads(nuevo_valor)
        except json.JSONDecodeError:
            print("❌ Configuración debe ser un JSON válido (ejemplo: {\"intervalo_medicion\": 60, \"encendido\": true })")
            return

    payload = {campo: nuevo_valor}

    print("📤 Enviando actualización al backend...")

    try:
        subprocess.run([
            "powershell",
            "-ExecutionPolicy", "Bypass",
            "-File", os.path.join(SCRIPTS_DIR, "modificar.ps1"),
            "-id", str(dispositivo["id"]),
            "-payload", json.dumps(payload)
        ])
    except Exception as e:
        print(f"❌ Error al ejecutar script PowerShell: {e}")


