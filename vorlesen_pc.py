import os
import io
import json
import subprocess
import time
import cv2
import numpy as np
from google.cloud import vision
from openai import OpenAI
from langdetect import detect
import winsound

# subprocess.run(['sudo', 'modprobe', 'snd_bcm2835'], check=False) # Nicht auf Windows/PC benötigt

# --- PFADE (Angepasst für PC) ---
# Bitte hier die Pfade für deinen PC eintragen, wenn sie im gleichen Ordner liegen
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_cloud_credentials.json"

try:
    with open('api_key_open_ai.txt', 'r') as f:
        openai_api_key = f.read().strip()
except FileNotFoundError:
    print("Warnung: api_key_open_ai.txt nicht gefunden.")
    openai_api_key = ""

# --- KONFIGURATION ---
OUTPUT_DIR = "captured_images"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "scharfes_bild.jpg")
MAX_RETRIES = 5         
SHARPNESS_THRESHOLD = 12.0  
WARMUP_TIME = 2.0       

PATH_PIPER = "piper" # Piper Befehl (über pip installiert)
MODEL_DE = r"models_piper\de_DE-thorsten-high.onnx"
MODEL_GR = r"models_piper\el_GR-rapunzelina-medium.onnx"

def calculate_sharpness_score(image_array):
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    score = laplacian.var()
    return score

def take_picture():
    print("Initialisiere PC Kamera...")
    
    # Sicherstellen, dass das Ausgabeverzeichnis existiert
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    cap = cv2.VideoCapture(0) # Standardkamera (0)
    
    # Versuche Full-HD aufzulösen
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    if not cap.isOpened():
        print("Fehler: Kamera konnte nicht geöffnet werden.")
        return

    read_out_offline_smart("Kamerafenster geöffnet. Drücke W, um ein Bild aufzunehmen.")
    print("Drücke 'w' im Kamerafenster, um das Bild zu machen (oder 'q' zum Abbrechen).")

    success = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Fehler beim Abrufen des Kamera-Feeds.")
            break
            
        cv2.imshow("Kamera - Druecke 'w' zum Aufnehmen", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('w'):
            print("Aufnahme ausgelöst!")
            score = calculate_sharpness_score(frame)
            print(f"Gemessener Schärfe-Score: {score:.2f} (Ziel: > {SHARPNESS_THRESHOLD})")
            
            if score >= SHARPNESS_THRESHOLD:
                print("[OK] Bild ist scharf genug!")
                cv2.imwrite(OUTPUT_FILE, frame)
                print(f"Bild gespeichert unter: {OUTPUT_FILE}")
                success = True
                read_out_offline_smart("Bild aufgenommen und wird verarbeitet. Bitte warten.")
                break 
            else:
                print("[FEHLER] Bild ist zu unscharf. Bitte erneut 'w' drücken.")
                read_out_offline_smart("Bild war unscharf. Bitte erneut W drücken.")
                
        elif key == ord('q'):
            print("Abgebrochen durch Benutzer.")
            break

    cap.release()
    cv2.destroyAllWindows()

    if not success:
        print("\nAUFGABE FEHLGESCHLAGEN.")
        print("Es wurde kein scharfes Bild aufgenommen.")

def detect_document_text(path):
    client = vision.ImageAnnotatorClient()

    with io.open(path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)

    response = client.document_text_detection(image=image)
    
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
        wav_file = "temp_output_long.wav"
        try:
            subprocess.run(
                ['python', '-m', 'piper', '--model', MODEL_DE, '--output_file', wav_file],
                input=cleaned_text.encode('utf-8'),
                check=True
            )
            winsound.PlaySound(wav_file, winsound.SND_FILENAME)
        except Exception as e:
            print(f"[Sprachausgabe simuliert (Fehler: {e})]: {cleaned_text}")
        print(f"Text vorgelesen: {len(cleaned_text)} Zeichen")
        
def read_out_cleaned_text_openai(cleaned_text):
    if cleaned_text:
        try:
            client = OpenAI(api_key=openai_api_key)
            response = client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=cleaned_text
            )
            mp3_file = "temp_openai.mp3"
            
            with open(mp3_file, 'wb') as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
                    
            os.startfile(mp3_file)

        except Exception as e:
            print(f"Fehler bei der Sprachausgabe: {e}")
                
def read_out_offline_smart(text):
    """
    Erkennt die Sprache und liest mit der passenden Piper-Stimme vor.
    """
    try:
        language = detect(text)
        print(f"Erkannte Sprache: {language}")

        if language == 'el':
            model = MODEL_GR
            length_scale = "1.1"
            print("Wähle Griechische Stimme...")
        else:
            model = MODEL_DE
            length_scale = "1.0"
            print("Wähle Deutsche Stimme...")

        wav_file = "temp_audio.wav"
        
        command = ['python', '-m', 'piper', '--model', model, '--length_scale', length_scale, '--output_file', wav_file]
        
        try:
            subprocess.run(command, input=text.encode('utf-8'), check=True)
            winsound.PlaySound(wav_file, winsound.SND_FILENAME)
        except Exception as e:
            print(f"[Sprachausgabe simuliert (Fehler: {e})]: {text}")

    except Exception as e:
        print(f"Fehler bei der Sprachausgabe: {e}")
    

def main():
    take_picture()
    if os.path.exists(OUTPUT_FILE):
        response = detect_document_text(OUTPUT_FILE)
        # print(response)
        cleaned_text = extract_letter_text_with_openai(response)
        print(cleaned_text)
        read_out_offline_smart(cleaned_text)
        read_out_offline_smart("Vorlesen beendet.")
    else:
         print("Konnte kein Bild finden zum Analysieren.")
    
if __name__ == "__main__":
    main()
