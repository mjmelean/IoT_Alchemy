# IoT Alchemy

## Descripcion

**IoT Alchemy** es un simulador de dispositivos IoT basado en CLI.  
Permite crear dispositivos a partir de plantillas JSON, iniciar su simulacion y generar QR para su reclamo.

###  Funcionalidades

-   Crear dispositivos desde plantillas (`/templates/*.json`)

-   Iniciar/detener simulaciones individuales o multiples.
    
-   Modificar parametros en tiempo real.
    
-   Generar QR con datos de reclamo para app movil (abre en navegador).
    
-   Integracion directa con el **Backend IoT** via MQTT y HTTP.
    

----------

## Estructura IoT Alchemy

```
IoT-Alchemy/
templates/       # Plantillas JSON
cli.py           # CLI principal
device.py		 # Simulador de dispositivos
manager.py		 # Gestion general de dispositivos
gen_qr.py        # Generacion de QR
templates_loader.py # Carga plantillas .json
main.py          # Entrada
utils.py		 # funciones utiles
config.json		 # configuracion del simulador
```
----------

##  Opciones del CLI

Menu:
```
1) Listar plantillas
2) Crear dispositivo desde plantilla
3) Listar dispositivos activos
4) Iniciar simulaci車n de un dispositivo
5) Detener simulaci車n de un dispositivo
6) Modificar par芍metros de un dispositivo (en vivo)
7) Simular apagado / encendido
8) Iniciar simulaci車n de todos
9) Detener simulaci車n de todos
10) Generar QR de dispositivo (Abre navegador)
11) Reclamar dispositivo (Via Powershell)
0) Salir
```

----------

##  Ejemplo de plantilla

```json
{
  "serial_prefix": "TMP0",
  "nombre": "Sensor de Temperatura Generico",
  "tipo": "sensor",
  "modelo": "ST-1000",
  "descripcion": "Sensor de temperatura",
  "configuracion": {
    "intervalo_envio": 5,
    "apagar": "off"
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

----------

##  Ejemplo de QR generado

```json
{
  "serial": "TMP0YBHV71SA",
  "nombre": "Sensor de Temperatura Generico",
  "tipo": "sensor",
  "modelo": "ST-1000",
  "descripcion": "Sensor de temperatura",
  "configuracion": {
    "intervalo_envio": 5,
    "apagar": "off"
  }
}
```

Se envia directamente al backend en:

```
/dispositivos/reclamar
```
