import time
import json
import requests
import paho.mqtt.publish as publish

serial = "ABC123456"
mqtt_payload = json.dumps({
    "serial_number": serial,
    "estado": "activo",
    "parametros": {
        "temperatura": 22.5,
        "humedad": 55
    },
    "configuracion": {
        "intervalo_medicion": 60,
        "modo": "automático"
    }
})
base_url = "http://localhost:5000"

# Enviar mensaje MQTT con info completa
publish.single("dispositivos/estado", mqtt_payload, hostname="localhost")

# Esperar registro backend
time.sleep(3)

# Consultar dispositivos no reclamados
resp = requests.get(f"{base_url}/dispositivos/no-reclamados")
dispositivos = resp.json()

target = next((d for d in dispositivos if d["serial_number"] == serial), None)
if not target:
    print("Dispositivo no encontrado para reclamar.")
    exit(1)

# Reclamar dispositivo desde app móvil
reclamo_payload = {
    "serial_number": serial,
    "nombre": "Sensor de temperatura 1",
    "tipo": "sensor",
    "modelo": "ST-1000",
    "descripcion": "Sensor en sala 1",
    "configuracion": {
        "intervalo_medicion": 60,
        "modo": "manual"
    }
}
r = requests.post(f"{base_url}/dispositivos/reclamar", json=reclamo_payload)
print(r.json())

# Verificar que ya no aparezca como no reclamado
time.sleep(1)
verif_resp = requests.get(f"{base_url}/dispositivos/no-reclamados")
no_reclamados = verif_resp.json()

if any(d["serial_number"] == serial for d in no_reclamados):
    print("Fallo: dispositivo aún no reclamado.")
else:
    print("Éxito: dispositivo reclamado correctamente.")