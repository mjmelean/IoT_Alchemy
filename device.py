# device.py
import json
import time
import threading
import random
import requests
from paho.mqtt import publish
from utils import clamp

class DeviceSimulator:
    """
    Publica SOLO por MQTT:
      { "serial_number", "estado", "parametros" }

    No envía nada por HTTP. Opcionalmente LEE (GET) del backend
    para aplicar configuraciones:
      configuracion.intervalo_envio -> self.interval
      configuracion.encendido (True/False) -> self.apagado
    """

    def __init__(
        self,
        serial,
        parametros_rules,
        mqtt_topic="dispositivos/estado",
        interval=5,
        mqtt_host="localhost",
        backend_url=None,
        poll_config_interval=3
    ):
        self.serial = serial
        self.param_rules = parametros_rules or {}
        self.mqtt_topic = mqtt_topic
        self.interval = max(1, int(interval))
        self.mqtt_host = mqtt_host

        # Flags e hilos
        self.running = False
        self._thread = None
        self._cfg_thread = None

        # Estado/params
        self.apagado = False  # apagado=True -> estado="inactivo"
        self.parametros = {}
        for k, rule in self.param_rules.items():
            mn = rule.get("min", 0)
            mx = rule.get("max", 1)
            t = rule.get("tipo")
            if t in ("float", "double"):
                self.parametros[k] = round(random.uniform(mn, mx), 2)
            elif t == "int":
                self.parametros[k] = random.randint(int(mn), int(mx))
            elif t == "boolean":
                self.parametros[k] = random.choice([True, False])
            else:
                self.parametros[k] = rule.get("default")

        # Config remota (solo lectura)
        self.backend_url = backend_url
        self.poll_config_interval = max(1, int(poll_config_interval))
        self._device_id = None  # cache para GET /dispositivos/<id>

    # ----------- Simulación -----------
    def _step(self):
        for k, rule in self.param_rules.items():
            t = rule.get("tipo")
            if t in ("float", "double"):
                var = rule.get("variacion", (rule.get("max", 1) - rule.get("min", 0)) * 0.05)
                cur = float(self.parametros.get(k, 0))
                nuevo = clamp(cur + random.uniform(-var, var), rule.get("min", cur), rule.get("max", cur))
                self.parametros[k] = round(nuevo, 3)
            elif t == "int":
                var = rule.get("variacion", 1)
                cur = int(self.parametros.get(k, 0))
                nuevo = int(clamp(cur + random.randint(-var, var), rule.get("min", cur), rule.get("max", cur)))
                self.parametros[k] = nuevo
            elif t == "boolean":
                prob = rule.get("prob_flip", 0.01)
                if random.random() < prob:
                    self.parametros[k] = not bool(self.parametros.get(k, False))

    def _estado_str(self):
        return "inactivo" if self.apagado else "activo"

    def build_mqtt_payload(self):
        return {
            "serial_number": self.serial,
            "estado": self._estado_str(),
            "parametros": self.parametros
        }

    def publish_estado(self):
        payload = self.build_mqtt_payload()
        try:
            publish.single(self.mqtt_topic, json.dumps(payload), hostname=self.mqtt_host)
            # print(f"[MQTT] {self.serial} -> {payload}")
        except Exception as e:
            print("[MQTT ERROR]", e)

    def _run(self):
        while self.running:
            if not self.apagado:
                self._step()
                self.publish_estado()
            else:
                # En apagado igual publicamos (estado=inactivo) para que el backend lo vea
                self.publish_estado()
            time.sleep(self.interval)

    # ----------- Config remota (solo lectura HTTP GET) -----------
    def _ensure_device_id(self):
        if not self.backend_url or self._device_id is not None:
            return
        try:
            # Buscar ID por serial (GET /dispositivos)
            r = requests.get(f"{self.backend_url}/dispositivos", timeout=5)
            if r.status_code == 200:
                lista = r.json()
                match = next((d for d in lista if d.get("serial_number") == self.serial), None)
                if match:
                    self._device_id = match["id"]
        except Exception as e:
            print(f"[CFG] Error buscando ID para {self.serial}: {e}")

    def _poll_remote_config(self):
        """Lee periódicamente /dispositivos/<id> y aplica configuracion."""
        while self.running and self.backend_url:
            try:
                self._ensure_device_id()
                if self._device_id is not None:
                    r = requests.get(f"{self.backend_url}/dispositivos/{self._device_id}", timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        cfg = data.get("configuracion") or {}
                        # Encendido/Apagado
                        encendido = cfg.get("encendido")
                        if encendido is not None:
                            self.apagado = not bool(encendido)
                        # Intervalo de envío
                        intervalo = cfg.get("intervalo_envio")
                        if isinstance(intervalo, (int, float)) and intervalo > 0:
                            self.interval = int(intervalo)
            except Exception as e:
                print(f"[CFG] Error leyendo configuración remota: {e}")
            time.sleep(self.poll_config_interval)

    # ----------- API pública -----------
    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if self.backend_url:
            self._cfg_thread = threading.Thread(target=self._poll_remote_config, daemon=True)
            self._cfg_thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)

    def set_parametro(self, key, value):
        if key in self.parametros:
            self.parametros[key] = value
            return True
        return False

    def set_parametros_bulk(self, new_params: dict):
        for k, v in new_params.items():
            if k in self.parametros:
                self.parametros[k] = v

    def apagar(self):
        self.apagado = True

    def encender(self):
        self.apagado = False
