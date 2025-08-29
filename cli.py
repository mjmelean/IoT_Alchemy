# cli.py
import time
from templates_loader import cargar_plantillas
from manager import DevicesManager
from gen_qr import generar_qr_reclamo
from utils import reclamar_dispositivo, modificar_dispositivo, listar_dispositivos_backend

def show_menu():
    print("\n=== IoT Alchemy CLI ===")
    print("1) Listar plantillas")
    print("2) Crear dispositivo desde plantilla")
    print("3) Listar dispositivos activos")
    print("4) Iniciar simulación de un dispositivo")
    print("5) Detener simulación de un dispositivo")
    print("6) Modificar parámetros de un dispositivo (en vivo-inyeccion de errores)")
    print("7) Iniciar simulación de todos")
    print("8) Detener simulación de todos")
    print("9) Generar QR de dispositivo (Abre Navegador)")
    print("10) Reclamar dispositivo vía HTTP (PowerShell y cURL)")
    print("11) Modificar datos vía HTTP (PowerShell y cURL)")
    print("0) Salir")

def iniciar_cli():
    templates = cargar_plantillas()
    manager = DevicesManager()

    while True:
        show_menu()
        opt = input("Opción: ").strip()
        if opt == "1":
            if not templates:
                print("No hay plantillas en /templates")
            else:
                print("Plantillas:")
                for name in templates:
                    print(" -", name)

        elif opt == "2":
            print("Seleccione plantilla:")
            keys = list(templates.keys())
            if not keys:
                print("No hay plantillas.")
                continue
            for i, k in enumerate(keys, 1):
                print(f"{i}) {k}")
            sel = input("Número: ").strip()
            try:
                idx = int(sel) - 1
                tpl = templates[keys[idx]]
            except Exception:
                print("Selección inválida.")
                continue

            serial_custom = input("Serial personalizado (ENTER para aleatorio): ").strip() or None
            cnt = input("¿Cuántos dispositivos crear? (1): ").strip() or "1"
            try:
                cnt = int(cnt)
            except Exception:
                cnt = 1

            created = manager.create_from_template(tpl, count=cnt, serial_custom=serial_custom)
            for d in created:
                print(f"Creado: {d.serial} (intervalo: {d.interval}s)")

        elif opt == "3":
            devs = manager.list_devices()
            if not devs:
                print("No hay dispositivos creados.")
            else:
                for d in devs:
                    print(f"- {d.serial} | apagado:{d.apagado} | intervalo:{d.interval}s | params:{d.parametros}")

        elif opt == "4":
            s = input("Serial del dispositivo a iniciar: ").strip()
            d = manager.get(s)
            if not d:
                print("No encontrado.")
            else:
                d.start()
                print("Simulación iniciada.")

        elif opt == "5":
            s = input("Serial del dispositivo a detener: ").strip()
            d = manager.get(s)
            if not d:
                print("No encontrado.")
            else:
                d.stop()
                print("Simulación detenida.")

        elif opt == "6":
            s = input("Serial del dispositivo: ").strip()
            d = manager.get(s)
            if not d:
                print("No encontrado.")
            else:
                print("Parámetros actuales:", d.parametros)
                key = input("Parámetro a modificar: ").strip()
                if key not in d.parametros:
                    print("Parámetro no existe.")
                else:
                    val = input("Nuevo valor: ").strip()
                    if val.lower() in ("true", "false"):
                        newv = val.lower() == "true"
                    else:
                        try:
                            if "." in val:
                                newv = float(val)
                            else:
                                newv = int(val)
                        except Exception:
                            newv = val
                    d.set_parametro(key, newv)
                    print("Parámetro actualizado.")

        elif opt == "7":
            manager.start_all()
            print("Todas las simulaciones iniciadas.")

        elif opt == "8":
            manager.stop_all()
            print("Todas las simulaciones detenidas.")

        elif opt == "9":
            serial = input("Ingrese el serial del dispositivo: ").strip()
            generar_qr_reclamo(serial, templates)
        
        elif opt == "10":
            serial = input("Ingrese el serial del dispositivo: ")
            reclamar_dispositivo(serial, list(templates.values()))

        elif opt == "11":
            modificar_dispositivo()

        elif opt == "0":
            print("Saliendo...")
            manager.stop_all()
            break
        else:
            print("Opción inválida.")
        time.sleep(0.2)