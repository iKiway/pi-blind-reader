import io
import socket
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Condition, Thread
from picamera2 import Picamera2


def get_local_ip():
    """Ermittelt die IP-Adresse des Raspberry Pi im lokalen Netzwerk."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Dummy-Verbindung (sendet keine echten Pakete), um das aktive Interface zu finden
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

    sensor_res = picam2.camera_properties.get("PixelArraySize")
    if sensor_res:
        max_size = (sensor_res[0], sensor_res[1])
    else:
        max_size = (3280, 2464)

    print(f"Kamera initialisiert: {max_size[0]}x{max_size[1]}")

    config = picam2.create_still_configuration(main={"size": max_size, "format": "RGB888"})
    picam2.configure(config)
    picam2.start()

    while True:
        buf = io.BytesIO()
        picam2.capture_file(buf, format="jpeg")
        output.write(buf.getvalue())
        time.sleep(0.05)


if __name__ == "__main__":
    PORT = 8000
    output = StreamingOutput()

    cam_thread = Thread(target=start_camera, daemon=True)
    cam_thread.start()

    ip_address = get_local_ip()

    server = HTTPServer(("", PORT), StreamingHandler)

    print("-" * 50)
    print(f"Stream verfuegbar unter: http://{ip_address}:{PORT}")
    print("Beenden mit Strg+C")
    print("-" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
    finally:
        server.server_close()