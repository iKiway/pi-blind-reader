from google.cloud import vision
import io
import os
import json
import subprocess
from openai import OpenAI
import time
import cv2
import numpy as np
from picamera2 import Picamera2
from langdetect import detect

subprocess.run(['sudo', 'modprobe', 'snd_bcm2835'], check=False)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/kimon/pi-blind-reader/google_cloud_credentials.json"

with open('/home/kimon/pi-blind-reader/api_key_open_ai.txt', 'r') as f:
    openai_api_key = f.read().strip()
    
# openai.api_key = openai_api_key

# --- KONFIGURATION ---
OUTPUT_FILE = "captured_images/scharfes_bild.jpg"
MAX_RETRIES = 5         # Wie oft versuchen?
SHARPNESS_THRESHOLD = 150.0  # WICHTIG: Dieser Wert muss je nach Motiv angepasst werden!
                             # Text/Kontrastreich: höher (z.B. 200-500)
                             # Landschaft/Wenig Kontrast: niedriger (z.B. 50-150)
WARMUP_TIME = 2.0       # Zeit für den Autofokus, sich vor dem ersten Bild einzustellen


PATH_PIPER = "/home/kimon/piper_tts/piper/piper"
MODEL_DE = "/home/kimon/piper_tts/de_DE-thorsten-medium.onnx"
MODEL_GR = "/home/kimon/piper_tts/el_GR-rapunzelina-medium.onnx"

def calculate_sharpness_score(image_array):
    """
    Berechnet einen Schärfegrad basierend auf der Laplace-Varianz.
    Höherer Wert = schärferes Bild.
    Erwartet ein BGR Bild (wie von OpenCV/picamera2 geliefert).
    """
    # 1. In Graustufen umwandeln (Farbe lenkt nur ab)
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    
    # 2. Laplace-Filter anwenden um Kanten zu finden
    # cv2.CV_64F wird genutzt, um Überläufe bei der Berechnung zu vermeiden
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    
    # 3. Die Varianz berechnen (Wie stark schwanken die Kantenwerte?)
    score = laplacian.var()
    return score

def take_picture():
    print("Initialisiere Kamera Modul 3...")
    picam2 = Picamera2()
    
    # Konfiguration für Full HD (1920x1080)
    config = picam2.create_still_configuration(main={"size": (1920, 1080)})
    picam2.configure(config)

    # Kamera starten. Der Autofokus (Continuous AF) beginnt zu arbeiten.
    picam2.start()
    
    print(f"Warte {WARMUP_TIME} Sekunden, damit sich der Autofokus einstellen kann...")
    time.sleep(WARMUP_TIME)

    attempt = 1
    success = False

    while attempt <= MAX_RETRIES:
        print(f"--- Versuch {attempt} von {MAX_RETRIES} ---")
        
        # BILD AUFNEHMEN (direkt in den Arbeitsspeicher als Numpy Array)
        # Wir speichern noch nicht auf die SD-Karte, das wäre zu langsam.
        print("Mache Aufnahme...")
        # capture_array() holt das Bild
        image_array = picam2.capture_array()
        
        # SCHÄRFE PRÜFEN
        score = calculate_sharpness_score(image_array)
        print(f"Gemessener Schärfe-Score: {score:.2f} (Ziel: > {SHARPNESS_THRESHOLD})")
        
        if score >= SHARPNESS_THRESHOLD:
            print("✅ Bild ist scharf genug!")
            # Jetzt erst speichern wir das Bild auf die Festplatte
            # Wir nutzen opencv zum Speichern, da wir das Bild eh schon im cv2-Format haben
            image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)  # In BGR umwandeln für OpenCV
            image_array = cv2.rotate(image_array, cv2.ROTATE_90_COUNTERCLOCKWISE)  # Falls Kamera auf dem Kopf montiert ist
            cv2.imwrite(OUTPUT_FILE, image_array)
            print(f"Bild gespeichert unter: {OUTPUT_FILE}")
            success = True
            break # Schleife verlassen
        else:
            print("❌ Bild ist zu unscharf.")
            if attempt < MAX_RETRIES:
                print("Warte kurz und fokussiere neu für nächsten Versuch...")
                # Ein kurzer Sleep zwingt den kontinuierlichen Autofokus oft dazu,
                # nachzuregeln, wenn sich das Motiv leicht verändert hat.
                time.sleep(1.5) 
            
        attempt += 1

    # Kamera sauber herunterfahren
    picam2.stop()
    picam2.close()

    if not success:
        print("\nAUFGABE FEHLGESCHLAGEN.")
        print(f"Konnte nach {MAX_RETRIES} Versuchen kein scharfes Bild machen.")
        print("Tipp: Prüfen Sie das Licht, den Abstand (mind. 5cm) oder passen Sie den SHARPNESS_THRESHOLD an.")

def detect_document_text(path):
    client = vision.ImageAnnotatorClient()

    with io.open(path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)

    # Wir nutzen document_text_detection (besser für Briefe als einfaches text_detection)
    response = client.document_text_detection(image=image)
    
    # Extrahiere den Text direkt aus der Response
    if response.text_annotations:
        return response.text_annotations[0].description
    else:
        return ""

def extract_letter_text_with_openai(raw_ocr_text):
    client = OpenAI(api_key=openai_api_key)
    
    prompt = f"""Du erhältst einen rohen OCR-Text. Das kann ein Brief, eine Buchseite, ein Artikel oder eine Notiz sein.
    Deine Aufgabe: Identifiziere den Dokumententyp und extrahiere NUR den relevanten Hauptinhalt (lesbaren Text).

    REGELN FÜR DEN INHALT:
    1. SPRACHE: Behalte IMMER die Originalsprache bei (Deutsch, Griechisch, etc.). Übersetze NICHT.
    2. BEI BRIEFEN: 
    - Entferne Adressfelder, Kopfzeilen, Metadaten, Telefonnummern.
    - Behalte Anrede, Textkörper und Grußformel.
    3. BEI BUCHSEITEN / ARTIKELN: 
    - Entferne Seitenzahlen, Kopfzeilen (Running Headers), Fußnoten-Referenzen.
    - Verbinde getrennte Wörter am Zeilenende wieder korrekt.
    4. ALLGEMEIN: 
    - Korrigiere OCR-Fehler (z.B. falsche Zeichen, 'l' statt '1'), aber verfälsche nicht den Inhalt.
    - Entferne "Rauschen" (einzelne sinnlose Zeichenfragmente).

    Hier ist der OCR-Text:

    {raw_ocr_text}

    Gib NUR den bereinigten Text zurück, ohne Einleitung oder Erklärung."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Du bist ein Experte für Textrekonstruktion und OCR-Korrektur."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=8000,
        temperature=0.2,
    )

    cleaned_text = response.choices[0].message.content.strip()
    return cleaned_text

def read_out_cleaned_text_on_device(cleaned_text):
    if cleaned_text:
        # Text direkt über subprocess.Popen an Piper senden (besser als echo)
        piper_process = subprocess.Popen(
            ['/home/kimon/piper_tts/piper/piper', '--model', '/home/kimon/piper_tts/de_DE-thorsten-medium.onnx', '--output-raw'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        aplay_process = subprocess.Popen(
            ['aplay', '-r', '22050', '-f', 'S16_LE', '-t', 'raw', '-'],
            stdin=piper_process.stdout
        )
        piper_process.stdin.write(cleaned_text.encode('utf-8'))
        piper_process.stdin.close()
        aplay_process.wait()
        print(f"Text vorgelesen: {len(cleaned_text)} Zeichen")
        
def read_out_cleaned_text_openai(cleaned_text):
    if cleaned_text:
        try:
            cleint = OpenAI(api_key=openai_api_key)
            response = cleint.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=cleaned_text
            )
            process = subprocess.Popen(
                ["mpg321", "-"],  # '-' bedeutet: Lies von Standard-Input
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL # Fehlermeldungen unterdrücken
            )
            
            # Die Audio-Daten in den Prozess schreiben
            for chunk in response.iter_bytes():
                process.stdin.write(chunk)
                
            process.stdin.close()
            process.wait()

        except Exception as e:
            print(f"Fehler bei der Sprachausgabe: {e}")
                
def read_out_offline_smart(text):
    """
    Erkennt die Sprache und liest mit der passenden Piper-Stimme vor.
    """
    try:
        # 1. Sprache erkennen
        language = detect(text)
        print(f"Erkannte Sprache: {language}")

        # 2. Passendes Modell wählen
        if language == 'el': # 'el' steht für Griechisch (Ellinika)
            model = MODEL_GR
            length_scale = "1.0"  # Langsamer für Griechisch (höher = langsamer)
            print("Wähle Griechische Stimme...")
        else:
            # Fallback ist immer Deutsch
            model = MODEL_DE
            length_scale = "1.0"  # Normale Geschwindigkeit für Deutsch
            print("Wähle Deutsche Stimme...")

        # 3. Piper aufrufen
        # Wir pipen den Text in Piper -> und das Audio direkt in aplay
        command = f'echo "{text}" | {PATH_PIPER} --model {model} --length-scale {length_scale} --output_raw | aplay -r 22050 -f S16_LE -t raw -'
        
        # Befehl ausführen
        subprocess.run(command, shell=True)

    except Exception as e:
        print(f"Fehler bei der Sprachausgabe: {e}")
    

def main():
    take_picture()
    response = detect_document_text('captured_images/scharfes_bild.jpg')
    # print(response)
    cleaned_text = extract_letter_text_with_openai(response)
    print(cleaned_text)
    read_out_offline_smart(cleaned_text)
    
main()