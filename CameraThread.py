import threading
import cv2
import numpy as np
from picamera2 import Picamera2
from libcamera import controls
from gpiozero import Button
from datetime import datetime
import os

class CameraThread(threading.Thread):
    def __init__(self, output_buffer, image_queue=None):
        super().__init__()
        self.output_buffer = output_buffer
        self.image_queue = image_queue  # Queue für OCR-Verarbeitung
        self.running = True
        
        # Kamera Setup
        self.picam2 = Picamera2()
        # config = self.picam2.create_video_configuration(main={"size": (640, 480), "format": "RGB888"})
        config = self.picam2.create_video_configuration(main={"size": (1920, 1080), "format": "RGB888"})
        self.picam2.configure(config)
        self.picam2.start() # Startet nur die Kamera, nicht das Recording
        self.picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        
        # GPIO Button Setup (Pin 6)
        self.button = Button(6, pull_up=True, bounce_time=0.2)
        self.button.when_pressed = self.capture_image
        
        # Ordner für gespeicherte Bilder erstellen
        self.capture_dir = "captured_images"
        os.makedirs(self.capture_dir, exist_ok=True)
        
        print(f"Button an GPIO Pin 6 aktiviert. Bilder werden in '{self.capture_dir}/' gespeichert.")
        
    def run(self):
        print("Kamera-Thread gestartet...")
        while self.running:
            try:
                self.filter()  # Oder self.no_filter() für keinen Filter

            except Exception as e:
                print(f"Fehler im Kamera-Thread: {e}")

    def filter(self):
        # 1. Bild als Array holen (OpenCV Format)
        frame = self.picam2.capture_array()

        # --- HIER FILTER EINFÜGEN ---
        
        # Beispiel 1: Alles in Graustufen
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        # Überprüfen ob das Bild scharf oder unscharf ist (Laplacian Varianz)
        laplacian_var = cv2.Laplacian(frame, cv2.CV_64F).var()
        if laplacian_var < 100:
            cv2.putText(frame, "Unscharf", (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            

        # 2. Dann "Thresholding" anwenden
        # Alle Pixel über 127 werden Weiß (255), alles darunter Schwarz (0)
        # _, frame = cv2.threshold(frame, 80, 255, cv2.THRESH_BINARY)

        # Beispiel 3: Text einfügen
        cv2.putText(frame, "Live Filter", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # ----------------------------
        

        # 2. Bild wieder in JPEG wandeln, damit der Browser es versteht
        # (Qualität 80 für Performance)
        ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        
        # 3. In den Streaming-Buffer schreiben
        if ret:
            self.output_buffer.write(jpeg.tobytes())
            
    def no_filter(self):
        # Einfaches Capture ohne Filter
        frame = self.picam2.capture_array()
        ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ret:
            self.output_buffer.write(jpeg.tobytes())

    def capture_image(self):
        """Speichert ein hochauflösendes Bild für Texterkennung"""
        try:
            # Bild in voller Qualität aufnehmen (ohne Filter)
            frame = self.picam2.capture_array()
            # frame = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)
            # Bild um 90 Grad drehen
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            # Dateiname mit Timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.capture_dir}/capture_{timestamp}.jpg"
            
            # Als RGB speichern (nicht in Graustufen für spätere Flexibilität)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            cv2.imwrite(filename, frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            
            print(f"✓ Bild gespeichert: {filename}")
            
            # Bild zur OCR-Queue hinzufügen, falls vorhanden
            if self.image_queue is not None:
                self.image_queue.put(filename)
                print(f"→ Bild zur OCR-Verarbeitung übergeben")
            
        except Exception as e:
            print(f"Fehler beim Bild-Capture: {e}")

    def stop(self):
        self.running = False
        self.button.close()
        self.picam2.stop()