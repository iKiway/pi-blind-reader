import io
import socket
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Condition, Thread
from picamera2 import Picamera2


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


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
    <title>Raspberry Pi Camera Stream (4:3)</title>
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
            max-width: 90vw;
            max-height: 85vh;
            aspect-ratio: 4 / 3;
            object-fit: contain;
            border: 2px solid #444;
            border-radius: 6px;
        }}
    </style>
</head>
<body>
    <h2>Raspberry Pi 4B - Natives 4:3 Sichtfeld ({actual_res[0]}x{actual_res[1]})</h2>
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
    global picam2, output, actual_res
    picam2 = Picamera2()

    # Sensor-Modi durchsuchen nach dem größten 4:3-Modus
    sensor_modes = picam2.sensor_modes
    max_mode = None
    max_pixels = 0

    for mode in sensor_modes:
        w, h = mode["size"]
        ratio = w / h
        # Prüfen, ob das Seitenverhältnis ca. 4:3 (1.33) ist
        if 1.30 <= ratio <= 1.36:
            pixels = w * h
            if pixels > max_pixels:
                max_pixels = pixels
                max_mode = (w, h)

    # Fallback falls keine Modi geparst wurden:
    if not max_mode:
        props = picam2.camera_properties.get("PixelArraySize")
        max_mode = (props[0], props[1]) if props else (3280, 2464)

    actual_res = max_mode
    print(f"Erzwinge nativen 4:3-Sensor-Modus: {actual_res[0]}x{actual_res[1]}")

    # Konfiguration mit fixem 4:3 Sensor-Input und Main-Output
    config = picam2.create_still_configuration(
        main={"size": actual_res, "format": "RGB888"},
        sensor={"output_size": actual_res}
    )
    picam2.configure(config)
    picam2.start()

    while True:
        buf = io.BytesIO()
        picam2.capture_file(buf, format="jpeg")
        output.write(buf.getvalue())
        time.sleep(0.05)


if __name__ == "__main__":
    PORT = 8000
    actual_res = (0, 0)
    output = StreamingOutput()

    cam_thread = Thread(target=start_camera, daemon=True)
    cam_thread.start()

    ip_address = get_local_ip()

    server = HTTPServer(("", PORT), StreamingHandler)

    print("-" * 50)
    print(f"Stream verfügbar unter: http://{ip_address}:{PORT}")
    print("Beenden mit Strg+C")
    print("-" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
    finally:
        server.server_close()