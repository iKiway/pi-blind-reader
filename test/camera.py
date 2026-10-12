#!/usr/bin/python3

# Mostly copied from https://picamera.readthedocs.io/en/release-1.13/recipes2.html
# Run this script, then point a web browser at http:<this-ip-address>:8000
# Note: needs simplejpeg to be installed (pip3 install simplejpeg).

import io
import logging
import socketserver
import socket
from http import server
from threading import Condition

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from libcamera import controls

PAGE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Picamera2 MJPEG Streaming Demo</title>
<style>
  body {
    margin: 0;
    padding: 20px;
    background-color: #1e1e1e;
    color: #f0f0f0;
    font-family: system-ui, -apple-system, sans-serif;
    text-align: center;
  }
  h1 {
    margin-bottom: 6px;
  }
  p {
    margin-top: 0;
    margin-bottom: 16px;
    color: #aaa;
  }
  .stream-container {
    display: inline-block;
    max-width: 95vw;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    border-radius: 8px;
    overflow: hidden;
    background: #000;
  }
  img {
    display: block;
    max-width: 100%;
    height: auto;
  }
</style>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<p>Auflösung: {width} &times; {height} (Originalauflösung / maximaler Weitwinkel)</p>
<div class="stream-container">
  <img src="stream.mjpg" alt="Live Camera Stream" />
</div>
</body>
</html>
"""


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            page_html = PAGE.replace('{width}', str(sensor_resolution[0])).replace('{height}', str(sensor_resolution[1]))
            content = page_html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
# Native Sensor-Auflösung abfragen (volles Sichtfeld / maximaler Weitwinkel ohne Crop)
sensor_resolution = picam2.sensor_resolution
config = picam2.create_video_configuration(
    main={"size": sensor_resolution, "format": "RGB888"},
    sensor={"output_size": sensor_resolution}
)
picam2.configure(config)
output = StreamingOutput()
picam2.start_recording(JpegEncoder(), FileOutput(output))

# Aktiviere Continuous Autofokus
picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    
    # Get the actual network IP address
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to an external address (doesn't actually send data)
        s.connect(('8.8.8.8', 80))
        ip_address = s.getsockname()[0]
    except Exception:
        ip_address = '127.0.0.1'
    finally:
        s.close()
    
    print("=" * 50)
    print("Camera Server gestartet!")
    print(f"Sensor-Auflösung: {sensor_resolution[0]}x{sensor_resolution[1]} (Original / maximaler Weitwinkel)")
    print(f"Öffne im Browser: http://{ip_address}:8000")
    print("=" * 50)
    
    server.serve_forever()
finally:
    picam2.stop_recording()