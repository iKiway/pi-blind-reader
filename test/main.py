import socket
import sys
import queue
from streaming import StreamingOutput, StreamingHandler, StreamingServer
from CameraThread import CameraThread
from OCRThread import OCRThread

# Buffer initialisieren
output = StreamingOutput()

# Queue für OCR-Verarbeitung erstellen
image_queue = queue.Queue()

# OCR Thread starten
ocr_thread = OCRThread(image_queue)
ocr_thread.start()

# Kamera Thread starten (mit OCR Queue)
camera_thread = CameraThread(output, image_queue)
camera_thread.start()

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    
    # Den Buffer an den Server übergeben, damit der Handler ihn findet
    server.set_output(output)

    # IP Adresse ermitteln (nur für die Anzeige)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip_address = s.getsockname()[0]
    except Exception:
        ip_address = '127.0.0.1'
    finally:
        s.close()

    print("=" * 50)
    print(f"Server läuft auf: http://{ip_address}:8000")
    print("Drücke STRG+C zum Beenden")
    print("=" * 50)

    server.serve_forever()

except KeyboardInterrupt:
    print("\nBeende...")
finally:
    camera_thread.stop()
    ocr_thread.stop()
    camera_thread.join()
    ocr_thread.join()
    sys.exit(0)