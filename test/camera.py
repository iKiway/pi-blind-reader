import io
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Condition, Thread
from picamera2 import Picamera2

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(301)
            self.send_header("Location", "/index.html")
            self.end_headers()
        elif self.path == "/index.html":
            content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Raspberry Pi Camera Stream</title>
    <style>
        body {{
            background: #121212;
            color: #eee;
            font-family: sans-serif;
            text-align: center;
            margin: 0;
            padding: 20px;
        }}
        img {{
            max-width: 95vw;
            height: auto;
            border: 2px solid #333;
            border-radius: 6px;
        }}
    </style>
</head>
<body>
    <h2>Raspberry Pi 4B - Volle Aufl&ouml;sung Stream</h2>
    <img src="/stream.mjpg" />
</body>
</html>""".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)

        elif self.path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b"--FRAME\r\n")
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
            except Exception:
                pass
        else:
            self.send_error(404)
            self.end_headers()


def start_camera():
    global picam2, output
    picam2 = Picamera2()

    # Maximale Sensor-Auflösung abfragen und für Stream konfigurieren
    sensor_res = picam2.camera_properties.get("PixelArraySize")
    if sensor_res:
        max_size = (sensor_res[0], sensor_res[1])
    else:
        # Fallback falls Property nicht direkt lesbar ist (z. B. Cam v2: 3280x2464)
        max_size = (3280, 2464)

    print(f"Starte Stream mit voller Auflösung: {max_size[0]}x{max_size[1]}")

    # Konfiguration für Standbild/Vollauflösungs-Stream
    config = picam2.create_still_configuration(main={"size": max_size, "format": "RGB888"})
    picam2.configure(config)
    picam2.start()

    # Kontinuierliches Enkodieren als JPEG in den Output-Puffer
    while True:
        buf = io.BytesIO()
        picam2.capture_file(buf, format="jpeg")
        output.write(buf.getvalue())
        time.sleep(0.05)


if __name__ == "__main__":
    output = StreamingOutput()

    cam_thread = Thread(target=start_camera, daemon=True)
    cam_thread.start()

    address = ("", 8000)
    server = HTTPServer(address, StreamingHandler)
    print("Server läuft auf Port 8000. Beenden mit Strg+C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
    finally:
        server.server_close()