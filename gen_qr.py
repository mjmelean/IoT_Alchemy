# gen_qr.py
import qrcode
import json
import webbrowser
import os
import tempfile
import threading
import time

def generar_qr_reclamo(serial, templates_dict):
    def worker():
        prefix = serial[:4]  # usamos sufijo de 4 caracteres
        template = next(
            (tpl for tpl in templates_dict.values() if tpl.get("serial_prefix") == prefix),
            None
        )

        if not template:
            print(f"No se encontró template para prefijo {prefix}")
            return

        # Datos mínimos para el reclamo
        data = {
            "serial": serial,
            "nombre": template.get("nombre", ""),
            "tipo": template.get("tipo", ""),
            "modelo": template.get("modelo", ""),
            "descripcion": template.get("descripcion", ""),
            "configuracion": template.get("configuracion", {})
        }

        # Crear QR en archivo temporal
        tmpdir = tempfile.gettempdir()
        img_path = os.path.join(tmpdir, f"qr_{serial}.png")
        qr = qrcode.make(json.dumps(data, ensure_ascii=False))
        qr.save(img_path)

        # Crear un HTML temporal que muestre el QR
        html_path = os.path.join(tmpdir, f"qr_{serial}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(f"""
            <html>
            <head>
                <title>QR Dispositivo {serial}</title>
                <script>
                    // Eliminar archivos temporales cuando se cierre la ventana
                    window.onunload = async () => {{
                        try {{
                            fetch("file://{img_path}", {{ method: "DELETE" }});
                        }} catch(e) {{}}
                    }};
                </script>
            </head>
            <body style="text-align:center; margin-top:50px; font-family:Arial">
                <h2>Dispositivo: {serial}</h2>
                <img src="file://{img_path}" style="width:300px;height:300px;" />
                <p>Escanea este QR para reclamar el dispositivo.</p>
            </body>
            </html>
            """)

        print(f"✅ QR generado en: {html_path}")
        webbrowser.open_new_tab(f"file://{html_path}")

        # Proceso de cleanup automático después de un rato
        def cleanup():
            time.sleep(60)  # espera 1 min aprox
            for path in [img_path, html_path]:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        print(f"🧹 Archivo eliminado: {path}")
                except Exception as e:
                    print(f"⚠️ No se pudo eliminar {path}: {e}")

        threading.Thread(target=cleanup, daemon=True).start()

    # Lanzamos en un hilo aparte para no bloquear
    threading.Thread(target=worker, daemon=True).start()
