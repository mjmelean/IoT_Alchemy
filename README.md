# ⚗️ IoT Alchemy

## 📝 Descripción

**IoT Alchemy** es un simulador de dispositivos IoT basado en CLI. Permite crear dispositivos a partir de plantillas JSON, iniciar su simulación y generar QR para su reclamo.

### 🛠️ Funcionalidades

-   Crear dispositivos desde plantillas (`/templates/*.json`)
    
-   Iniciar/detener simulaciones individuales o múltiples.
    
-   Modificar parámetros en tiempo real.

-   Inyeccion de errores para pruebas (al modificar parametros y excederse del max o min).
    
-   Generar QR con datos de reclamo para app móvil (abre en navegador).
    
-   Reclamar y modificar dispositivos (PowerShell y cURL)
    
-   Integración directa con el **Backend IoT** 🚀 vía MQTT y HTTP.
    

👉 [**Click aqui para instalar cURL**](https://curl.se/download.html)
⚙️ [**Click aqui para ir a IoT BackEnd**](https://github.com/mjmelean/IoT_Backend)

## 📁 Estructura de IoT Alchemy

```
    |--cli.py
    |--config.json
    |--device.py
    |--gen_qr.py
    |--main.py
    |--manager.py
    |--templates_loader.py
    |--utils.py
    |--scripts/
        |--modificar.ps1
        |--reclamar.ps1
    |--templates/
        |--sensor_mov.json
        |--sensor_temp.json
        |--otras plantillas.....

```

-   `cli.py` 💻 〞 CLI principal.
    
-   `device.py` 📱 〞 Simulador de dispositivos.
    
-   `manager.py` ⚙️ 〞 Gestión general de dispositivos.
    
-   `gen_qr.py` 🔳 〞 Generación de QR.
    
-   `templates_loader.py` 📄 〞 Cargador de plantillas .json.
    
-   `utils.py` 🔧 〞 Utiliades de IoT Alchemy.
    
-   `config.json` ⚙️ 〞 Configuración del IoT Alchemy.
    
-   `main.py` 🚀 〞 Ejecución de IoT Alchemy.
    
-   `templates/` 📂 〞 Ubicación de plantillas.
    
-   `scripts/` 📜 〞 Ubicación de scripts (PowerShell y cURL).
    

## 📋 Opciones del CLI

```
1) Listar plantillas
2) Crear dispositivo desde plantilla
3) Listar dispositivos activos
4) Iniciar simulacion de un dispositivo
5) Detener simulacion de un dispositivo
6) Modificar parametros de un dispositivo (en vivo)
7) Iniciar simulacion de todos
8) Detener simulacion de todos
9) Generar QR de dispositivo (Abre navegador)
10) Reclamar dispositivo via HTTP (PowerShell y cURL)
11) Modificar datos via HTTP (PowerShell y cURL)
0) Salir

```

## 📄 Ejemplo de plantilla

```json
{
  "serial_prefix": "TMP0",
  "nombre": "Sensor de Temperatura Generico",
  "tipo": "sensor",
  "modelo": "ST-1000",
  "descripcion": "Sensor de temperatura",
  "configuracion": {
    "intervalo_envio": 5,
    "encendido": true
  },
  "parametros": {
    "temperatura": {
      "tipo": "float",
      "min": 20.0,
      "max": 30.0,
      "variacion": 0.3
    },
    "humedad": {
      "tipo": "int",
      "min": 30,
      "max": 70,
      "variacion": 2
    }
    }
}

```

## 🔳 Ejemplo de QR generado

```json
{
  "serial": "TMP0YBHV71SA",
  "nombre": "Sensor de Temperatura Generico",
  "tipo": "sensor",
  "modelo": "ST-1000",
  "descripcion": "Sensor de temperatura",
  "configuracion": {
    "intervalo_envio": 5,
    "encendido": true
  }
}

```

![Código QR para la página de ejemplo](https://i.postimg.cc/FHgMqvMg/qr-TMP0-YBHV71-SA.png)