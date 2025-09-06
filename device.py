# device.py
import json
import os
import time
import threading
import random
import requests
import datetime
from paho.mqtt import publish
from utils import clamp

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

# Mapa de equivalencias español -> inglés
DAY_MAP = {
    "lunes": "monday",
    "martes": "tuesday",
    "miercoles": "wednesday",
    "miércoles": "wednesday",
    "jueves": "thursday",
    "viernes": "friday",
    "sabado": "saturday",
    "sábado": "saturday",
    "domingo": "sunday",
}

class DeviceSimulator:
    """
    Publica SOLO por MQTT:
      { "serial_number", "estado", "parametros" }

    No envía nada por HTTP. Opcionalmente LEE (GET) del backend
    para aplicar configuraciones:
      configuracion.intervalo_envio -> self.interval
      configuracion.encendido (True/False) -> self.apagado
      configuracion.modo ("manual"/"horario") -> define comportamiento
    """

    def __init__(
        self,
        serial,
        parametros_rules,
        mqtt_topic=None,
        interval=5,
        mqtt_host=None,
        backend_url=None,
        poll_config_interval=None
    ):
        self.serial = serial
        self.param_rules = parametros_rules or {}
        self.mqtt_topic = mqtt_topic or CONFIG.get("mqtt_topic_estado", "dispositivos/estado")
        self.mqtt_host = mqtt_host or CONFIG.get("mqtt_host", "localhost")
        self.backend_url = backend_url or CONFIG.get("backend_url")
        self.interval = max(1, int(interval))

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
        self.poll_config_interval = max(1, int(poll_config_interval or CONFIG.get("poll_config_interval", 3)))
        self._device_id = None  # cache para GET /dispositivos/<id>
        self.inyecciones = {k: False for k in self.param_rules}

        # Último encendido sincronizado al backend
        self._last_encendido_sync = None

    # ----------- Simulación -----------
    def _step(self):
        for k, rule in self.param_rules.items():
            if self.inyecciones.get(k, False):
                continue

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
        except Exception as e:
            print("[MQTT ERROR]", e)

    def _run(self):
        while self.running:
            if not self.apagado:
                self._step()
                self.publish_estado()
            else:
                self.publish_estado()
            time.sleep(self.interval)

    # ----------- Config remota (solo lectura HTTP GET) -----------
    def _ensure_device_id(self):
        if not self.backend_url or self._device_id is not None:
            return
        try:
            r = requests.get(f"{self.backend_url}/dispositivos", timeout=5)
            if r.status_code == 200:
                lista = r.json()
                match = next((d for d in lista if d.get("serial_number") == self.serial), None)
                if match:
                    self._device_id = match["id"]
        except Exception as e:
            print(f"[CFG] Error buscando ID para {self.serial}: {e}")

    def _sync_encendido_to_backend(self, cfg):
        """Sincroniza encendido al backend solo si cambió."""
        if not (self.backend_url and self._device_id is not None):
            return
        new_val = bool(cfg.get("encendido"))
        if self._last_encendido_sync is not None and self._last_encendido_sync == new_val:
            return  # no hay cambios
        try:
            resp = requests.put(
                f"{self.backend_url}/dispositivos/{self._device_id}",
                json={"configuracion": cfg, "encendido": new_val},
                timeout=5
            )
            if resp.status_code in (200, 204):
                self._last_encendido_sync = new_val
        except Exception as e:
            print(f"[CFG] Error sincronizando estado con backend: {e}")

    def _aplicar_config(self, cfg):
        # Si no hay modo → dispositivo no reclamado todavía
        modo = cfg.get("modo")
        if not modo:
            print(f"[CFG] {self.serial} aún no reclamado, ignorando configuración")
            return

        if modo == "manual":
            # En manual: encendido manda, estado escucha
            encendido = cfg.get("encendido", True)
            self.apagado = not bool(encendido)

        elif modo == "horario":
            # En horario: estado manda, encendido escucha
            ahora = datetime.datetime.now()
            dia_actual = ahora.strftime("%A").lower()

            activo = False
            for h in cfg.get("horarios", []):
                dias_cfg = [d.lower() for d in h.get("dias", ["todos"])]
                dias_norm = []
                for d in dias_cfg:
                    if d in DAY_MAP:
                        dias_norm.append(DAY_MAP[d])
                    else:
                        dias_norm.append(d)

                if "todos" in dias_norm or "all" in dias_norm or dia_actual in dias_norm:
                    try:
                        start_str = h.get("inicio") or h.get("start")
                        end_str   = h.get("fin")    or h.get("end")
                        if not (start_str and end_str):
                            continue
                        ini = datetime.datetime.strptime(start_str, "%H:%M").time()
                        fin = datetime.datetime.strptime(end_str, "%H:%M").time()

                        if ini < fin:
                            if ini <= ahora.time() <= fin:
                                activo = True
                        else:  # cruza medianoche
                            if ahora.time() >= ini or ahora.time() <= fin:
                                activo = True
                    except Exception as e:
                        print(f"[CFG] Horario inválido: {h} ({e})")

            # Estado manda
            self.apagado = not activo
            cfg["encendido"] = activo
            self._sync_encendido_to_backend(cfg)

        # Intervalo de envío
        intervalo = cfg.get("intervalo_envio")
        if isinstance(intervalo, (int, float)) and intervalo > 0:
            self.interval = int(intervalo)

    def _poll_remote_config(self):
        while self.running and self.backend_url:
            try:
                self._ensure_device_id()
                if self._device_id is not None:
                    r = requests.get(f"{self.backend_url}/dispositivos/{self._device_id}", timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        cfg = data.get("configuracion") or {}
                        self._aplicar_config(cfg)
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
            mn = self.param_rules[key].get("min", float("-inf"))
            mx = self.param_rules[key].get("max", float("inf"))
            if isinstance(value, (int, float)) and (value < mn or value > mx):
                self.inyecciones[key] = True
            else:
                self.inyecciones[key] = False
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
