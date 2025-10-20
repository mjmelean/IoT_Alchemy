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

# -------------------------------
# Mapas de días y helpers de tiempo
# -------------------------------
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
EN_DAYS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]

def _now():
    return datetime.datetime.now()

def _today_key_en(now=None):
    now = now or _now()
    return now.strftime("%A").lower()  # "monday".."sunday"

def _norm_days(lst):
    out = []
    for d in lst or []:
        dl = str(d).strip().lower()
        if dl in DAY_MAP:
            out.append(DAY_MAP[dl])
        else:
            out.append(dl)
    return out

def _parse_hhmm(s):
    return datetime.datetime.strptime(s, "%H:%M").time()

def _is_time_in_range(t, start, end):
    # soporta rangos que cruzan medianoche
    if start <= end:
        return start <= t <= end
    return t >= start or t <= end

# ------------------------------------
# Detección de "kind" y capability/canal
# ------------------------------------
# 1) Kind por prefijo de serial (fallback si no lo da la config)
KIND_BY_SERIAL_PREFIX = {
    "LGT0": "luz",
    "RGD0": "riego",
    "SHD0": "persiana",
    "FAN0": "ventilador",
    "DRL0": "puerta",
    "TMP0": "termometro",
    "CAM0": "camara",
    "PLG0": "enchufe",
    "LUX0": "sensor_luz",
    "CO20": "sensor_co2",
    "SMK0": "sensor_humo",
    "MOV0": "sensor_mov",
    "SND0": "sensor_ruido",
}

# 2) Canal recomendado por kind (coincide con el plan de “canales”)
CHANNEL_BY_KIND = {
    "luz": "horarios",
    "enchufe": "horarios",
    "camara": "horarios",          # se trata como binario
    "persiana": "horarios_pos",
    "cortina": "horarios_pos",
    "riego": "horarios_riego",
    "ventilador": "horarios_speed",
    "puerta": "horarios_lock",
    "termometro": "horarios_temp",
    "aire": "horarios_temp",
    # Sensores → sin programación propia (usa solo intervalo_envio)
}

# 3) Capability por kind
CAPABILITY_BY_KIND = {
    "luz": "binary",
    "enchufe": "binary",
    "camara": "binary",
    "persiana": "position",
    "cortina": "position",
    "ventilador": "speed",
    "puerta": "lock",
    "riego": "duration",
    "termometro": "setpoint",
    "aire": "setpoint",
    # sensores → "sensor" (solo lectura)
    "sensor_luz": "sensor",
    "sensor_co2": "sensor",
    "sensor_humo": "sensor",
    "sensor_mov": "sensor",
    "sensor_ruido": "sensor",
}

def _guess_kind(serial: str, cfg: dict) -> str:
    # prioridad: configuracion.kind / configuracion.subtipo → prefijo serial → fallback
    for key in ("kind", "subtipo"):
        v = cfg.get(key)
        if v:
            return str(v).strip().lower()
    # por prefijo
    for pref, kind in KIND_BY_SERIAL_PREFIX.items():
        if str(serial).startswith(pref):
            return kind
    # si no hay pista, asume binario
    return "luz"

def _capability_for_kind(kind: str) -> str:
    return CAPABILITY_BY_KIND.get(kind, "binary")

def _channel_for_kind(kind: str) -> str:
    return CHANNEL_BY_KIND.get(kind, "horarios")

# ------------------------------------
# Simulador
# ------------------------------------
class DeviceSimulator:
    """
    Publica SOLO por MQTT:
      { "serial_number", "estado", "parametros" }

    Lee por HTTP (GET /dispositivos/<id>) para aplicar configuraciones remotas:
      - configuracion.intervalo_envio → self.interval
      - configuracion.encendido (manual) → self.apagado
      - configuracion.modo = manual/horario
      - (NUEVO) canales horarios_* según capability/kind
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

        # Extras que algunos kinds usan
        self.parametros.setdefault("posicion", 0)        # persiana
        self.parametros.setdefault("velocidad", 0)       # ventilador
        self.parametros.setdefault("riego_en_curso", False)
        self.parametros.setdefault("setpoint_c", None)   # termostato/aire
        self.parametros.setdefault("lock_state", "unlock")

        # Config remota (solo lectura)
        self.poll_config_interval = max(1, int(poll_config_interval or CONFIG.get("poll_config_interval", 3)))
        self._device_id = None
        self.inyecciones = {k: False for k in self.param_rules}

        # Último encendido sincronizado al backend (solo binarios)
        self._last_encendido_sync = None

        # Interno para riego por duración
        self._riego_until_ts = None

    # ----------- Simulación numérica aleatoria -----------
    def _step(self):
        now = time.time()
        # manejar riego por duración (si quedó programado)
        if self._riego_until_ts is not None:
            self.parametros["riego_en_curso"] = now < self._riego_until_ts
            if not self.parametros["riego_en_curso"]:
                self._riego_until_ts = None

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
        # Deriva "activo/inactivo" de parámetros según capability
        # - speed 0 => inactivo
        # - posicion 0 (y sin riego en curso) => inactivo
        if "velocidad" in self.parametros and self.parametros["velocidad"] == 0:
            return "inactivo"
        if "posicion" in self.parametros and self.parametros["posicion"] == 0:
            # si es persiana totalmente cerrada, toma inactivo
            return "inactivo"
        if "riego_en_curso" in self.parametros and not self.parametros["riego_en_curso"]:
            # si no está regando ahora, considera inactivo (para cards)
            # (puedes ajustar este criterio si prefieres "activo" while armed)
            return "inactivo"

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
                # Incluso apagado publica latido/estado
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

    def _sync_encendido_to_backend(self, cfg, encendido_actual: bool):
        """Sincroniza encendido/estado al backend solo si cambió (para binarios)."""
        if not (self.backend_url and self._device_id is not None):
            return

        if self._last_encendido_sync is not None and self._last_encendido_sync == encendido_actual:
            return  # sin cambios

        payload = {"configuracion": cfg, "encendido": encendido_actual}
        modo = (cfg.get("modo") or "").lower()
        if modo == "horario":
            payload["estado"] = "activo" if encendido_actual else "inactivo"

        try:
            resp = requests.put(
                f"{self.backend_url}/dispositivos/{self._device_id}",
                json=payload,
                timeout=5
            )
            if resp.status_code in (200, 204):
                self._last_encendido_sync = encendido_actual
        except Exception as e:
            print(f"[CFG] Error sincronizando estado con backend: {e}")

    # ----------- Aplicación de horarios (todos los canales) -----------
    def _apply_binary_windows(self, cfg):
        """
        Soporta el formato clásico:
          "horarios": [ {dias:[...], inicio:"HH:MM", fin:"HH:MM"}, ... ]
        y el nuevo (opcional) por día:
          "horarios": { "lunes":[["07:00","on"],["23:00","off"]], "diario":[...] }
        """
        now = _now()
        today = _today_key_en(now)
        t = now.time()
        activo = False

        horarios = cfg.get("horarios")
        if isinstance(horarios, list):
            # Formato clásico ventanas ON/OFF
            for h in horarios:
                dias_cfg = _norm_days(h.get("dias", ["todos"]))
                if "todos" in dias_cfg or "all" in dias_cfg or today in dias_cfg:
                    try:
                        start_str = h.get("inicio") or h.get("start")
                        end_str   = h.get("fin")    or h.get("end")
                        if not (start_str and end_str):
                            continue
                        ini = _parse_hhmm(start_str)
                        fin = _parse_hhmm(end_str)
                        if _is_time_in_range(t, ini, fin):
                            activo = True
                    except Exception:
                        continue
        elif isinstance(horarios, dict):
            # Formato por eventos (“on”/“off”)
            todays = list(horarios.get(today, [])) + list(horarios.get("diario", []))
            # ordena por hora ascendente y aplica “último evento del día <= ahora”
            events = []
            for hhmm, action in todays:
                try:
                    tm = _parse_hhmm(hhmm)
                    events.append((tm, str(action).lower()))
                except Exception:
                    pass
            events.sort(key=lambda x: x[0])
            for tm, action in events:
                if tm <= t:
                    if action in ("on","encender","true","1"):
                        activo = True
                    elif action in ("off","apagar","false","0"):
                        activo = False

        # Deriva apagado + encendido y devuelve para posible sync binaria
        self.apagado = not activo
        cfg["encendido"] = activo
        return activo

    def _apply_pos_schedule(self, cfg):
        now = _now(); t = now.time(); today = _today_key_en(now)
        sched = cfg.get("horarios_pos") or {}
        todays = list(sched.get(today, [])) + list(sched.get("diario", []))
        pos = self.parametros.get("posicion", 0)
        events = []
        for hhmm, val in todays:
            try:
                tm = _parse_hhmm(hhmm)
                vv = max(0, min(100, int(val)))
                events.append((tm, vv))
            except Exception:
                pass
        events.sort(key=lambda x: x[0])
        for tm, vv in events:
            if tm <= t:
                pos = vv
        self.parametros["posicion"] = pos
        # si posición 0, marcamos apagado? preferimos NO tocar self.apagado aquí

    def _apply_speed_schedule(self, cfg):
        now = _now(); t = now.time(); today = _today_key_en(now)
        sched = cfg.get("horarios_speed") or {}
        todays = list(sched.get(today, [])) + list(sched.get("diario", []))
        spd = self.parametros.get("velocidad", 0)
        events = []
        for hhmm, val in todays:
            try:
                tm = _parse_hhmm(hhmm)
                vv = int(val)
                events.append((tm, vv))
            except Exception:
                pass
        events.sort(key=lambda x: x[0])
        for tm, vv in events:
            if tm <= t:
                spd = vv
        self.parametros["velocidad"] = spd

    def _apply_lock_schedule(self, cfg):
        now = _now(); t = now.time(); today = _today_key_en(now)
        sched = cfg.get("horarios_lock") or {}
        todays = list(sched.get(today, [])) + list(sched.get("diario", []))
        lock_state = self.parametros.get("lock_state", "unlock")
        events = []
        for hhmm, action in todays:
            try:
                tm = _parse_hhmm(hhmm)
                act = str(action).lower()
                if act in ("lock","unlock"):
                    events.append((tm, act))
            except Exception:
                pass
        events.sort(key=lambda x: x[0])
        for tm, act in events:
            if tm <= t:
                lock_state = act
        self.parametros["lock_state"] = lock_state

    def _apply_riego_schedule(self, cfg):
        """
        horarios_riego: {"lunes":[["06:30",10]], "diario":[...]}
        Enciende riego_en_curso durante "minutos" a partir de la hora programada.
        """
        now_dt = _now()
        t = now_dt.time(); today = _today_key_en(now_dt)
        sched = cfg.get("horarios_riego") or {}
        todays = list(sched.get(today, [])) + list(sched.get("diario", []))

        # Mantener en curso si ya había uno
        if self._riego_until_ts is not None and time.time() < self._riego_until_ts:
            self.parametros["riego_en_curso"] = True
        else:
            self.parametros["riego_en_curso"] = False
            self._riego_until_ts = None

        events = []
        for hhmm, mins in todays:
            try:
                tm = _parse_hhmm(hhmm)
                dur = max(1, int(mins))
                events.append((tm, dur))
            except Exception:
                pass
        events.sort(key=lambda x: x[0])
        # Si hay eventos previos a now, el último que "pegue" manda
        for tm, dur in events:
            if tm <= t:
                # arrancar riego que dure 'dur' min (si no estaba en curso o reiniciar ventana)
                start_dt = now_dt.replace(hour=tm.hour, minute=tm.minute, second=0, microsecond=0)
                until = start_dt + datetime.timedelta(minutes=dur)
                self._riego_until_ts = until.timestamp()
                self.parametros["riego_en_curso"] = time.time() < self._riego_until_ts

    def _apply_temp_schedule(self, cfg):
        now = _now(); t = now.time(); today = _today_key_en(now)
        sched = cfg.get("horarios_temp") or {}
        todays = list(sched.get(today, [])) + list(sched.get("diario", []))
        sp = self.parametros.get("setpoint_c", None)
        events = []
        for hhmm, val in todays:
            try:
                tm = _parse_hhmm(hhmm)
                vv = float(val)
                events.append((tm, vv))
            except Exception:
                pass
        events.sort(key=lambda x: x[0])
        for tm, vv in events:
            if tm <= t:
                sp = vv
        self.parametros["setpoint_c"] = sp

    # ----------- Aplicación general de configuración -----------
    def _aplicar_config(self, cfg):
        kind = _guess_kind(self.serial, cfg)
        capability = cfg.get("capability") or _capability_for_kind(kind)
        canal = _channel_for_kind(kind)

        modo = str(cfg.get("modo") or "").lower()
        if not modo:
            print(f"[CFG] {self.serial} aún no reclamado, ignorando configuración")
            return

        if modo == "manual":
            # En manual: encendido manda (para binarios); otros kinds se controlan por controles en vivo
            if capability == "binary":
                encendido = bool(cfg.get("encendido", True))
                self.apagado = not encendido
            # Para position/speed/lock/duration/setpoint en manual, no tocamos aquí:
            # se espera que el usuario toque sliders, etc. (o los parámetros ya definidos)

        elif modo == "horario":
            # En horario: aplicamos canal/es según capability/kind.
            # 1) Canal principal por kind
            if capability == "binary":
                enc = self._apply_binary_windows(cfg)  # también setea self.apagado y cfg["encendido"]
                # sincroniza ON/OFF con backend si cambió
                self._sync_encendido_to_backend(cfg, enc)
            elif capability == "position":
                self._apply_pos_schedule(cfg)
            elif capability == "speed":
                self._apply_speed_schedule(cfg)
            elif capability == "lock":
                self._apply_lock_schedule(cfg)
            elif capability == "duration":
                self._apply_riego_schedule(cfg)
            elif capability == "setpoint":
                self._apply_temp_schedule(cfg)
            else:  # sensor / desconocido → no hace nada especial en horario
                pass

            # 2) (Opcional) Si además vienen otros canales, también podríamos aplicarlos.
            #    Para mantenerlo simple y no mezclar, aplicamos SOLO el central del kind.

            # En horario, si el canal principal no es binario, no tocamos self.apagado aquí.
            # El estado visible lo derivamos en _estado_str() según parámetros (velocidad/posicion/riego).

        # Intervalo de envío (en ambos modos)
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
            mn = self.param_rules.get(key, {}).get("min", float("-inf"))
            mx = self.param_rules.get(key, {}).get("max", float("inf"))
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