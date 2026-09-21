import threading
import queue
import time
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("⚠️  pytesseract nicht installiert. Installiere mit: pip install pytesseract pillow")
    print("⚠️  Außerdem muss tesseract-ocr installiert sein: sudo apt install tesseract-ocr tesseract-ocr-deu")

class OCRThread(threading.Thread):
    def __init__(self, image_queue):
        super().__init__()
        self.image_queue = image_queue
        self.running = True
        
        # Tesseract-Konfiguration (Deutsch + Englisch)
        self.tesseract_config = '--psm 6 --oem 3'  # PSM 6 = uniform block of text
        self.languages = 'deu+eng'  # Deutsch + Englisch
        
        if TESSERACT_AVAILABLE:
            print("OCR-Thread bereit. Sprachen: Deutsch + Englisch")
        
    def run(self):
        print("OCR-Thread gestartet, warte auf Bilder...")
        
        while self.running:
            try:
                # Warte auf ein Bild aus der Queue (Timeout 1 Sekunde)
                try:
                    image_path = self.image_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                if not TESSERACT_AVAILABLE:
                    print(f"⚠️  Kann {image_path} nicht verarbeiten - pytesseract nicht installiert")
                    self.image_queue.task_done()
                    continue
                
                # OCR durchführen
                print(f"🔍 Analysiere: {image_path}")
                start_time = time.time()
                
                text = self.run_ocr(image_path)
                
                elapsed = time.time() - start_time
                
                # Ergebnis ausgeben
                print(f"\n{'='*60}")
                print(f"📄 Datei: {image_path}")
                print(f"⏱️  Zeit: {elapsed:.2f}s")
                print(f"{'='*60}")
                if text.strip():
                    print(text)
                else:
                    print("(Kein Text erkannt)")
                print(f"{'='*60}\n")
                
                # Optional: Text in Datei speichern
                self.save_text(image_path, text)
                
                self.image_queue.task_done()
                
            except Exception as e:
                print(f"❌ Fehler bei OCR: {e}")
                
    def run_ocr(self, image_path):
        """Führt OCR auf einem Bild aus"""
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(
                image, 
                lang=self.languages,
                config=self.tesseract_config
            )
            return text
        except Exception as e:
            return f"Fehler: {e}"
    
    def save_text(self, image_path, text):
        """Speichert den erkannten Text als .txt Datei"""
        try:
            txt_path = image_path.replace('.jpg', '.txt')
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
        except Exception as e:
            print(f"Fehler beim Speichern des Texts: {e}")
    
    def stop(self):
        self.running = False
