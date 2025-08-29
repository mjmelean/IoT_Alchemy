import os
import json
from device import DeviceSimulator
from utils import generar_serial

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ No se pudo cargar config.json: {e}")
        return {}
    

class DevicesManager:
    def __init__(self):
        self.devices = {}  # serial -> DeviceSimulator
        self.config = load_config()

    def create_from_template(self, template, count=1, serial_custom=None):
        """
        Crea uno o varios dispositivos desde una plantilla.
        - Si serial_custom viene, solo crea 1 con ese serial exacto.
        - Si no, genera 'count' dispositivos con serial aleatorio.
        """
        created = []
        if serial_custom:
            seriales = [serial_custom]
        else:
            seriales = [generar_serial(template.get("serial_prefix", "DEV")) for _ in range(count)]

        for serial in seriales:
            params_rules = template.get("parametros", {}) or {}
            interval = int(template.get("configuracion", {}).get("intervalo_envio", 5))

            d = DeviceSimulator(
                serial=serial,
                parametros_rules=params_rules,
                mqtt_topic=self.config.get("mqtt_topic_estado", "dispositivos/estado"),
                interval=interval,
                mqtt_host=self.config.get("mqtt_host", "localhost"),
                backend_url=self.config.get("backend_url"),
                poll_config_interval=self.config.get("poll_config_interval", 3)
            )
            self.devices[serial] = d
            created.append(d)
        return created

    def list_devices(self):
        return list(self.devices.values())

    def get(self, serial):
        return self.devices.get(serial)

    def remove(self, serial):
        d = self.devices.pop(serial, None)
        if d:
            d.stop()
            return True
        return False

    def start_all(self):
        for d in self.devices.values():
            d.start()

    def stop_all(self):
        for d in self.devices.values():
            d.stop()
