import os
import json
import time
import cv2
import numpy as np
import winsound
import threading
import queue
from google import genai
from google.genai import types
from google.cloud import texttospeech
from langdetect import detect

# --- PFADE ---
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_cloud_credentials.json"

# --- KONFIGURATION ---
OUTPUT_DIR = "captured_images"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "scharfes_bild.jpg")
SHARPNESS_THRESHOLD = 12.0

def calculate_sharpness_score(image_array):
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return laplacian.var()

def take_picture():
    print("Initialisiere PC Kamera...")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    cap = cv2.VideoCapture(0)
    # Versuche Full-HD aufzulösen
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    if not cap.isOpened():
        print("Fehler: Kamera konnte nicht geöffnet werden.")
        return False

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
            score = calculate_sharpness_score(frame)
            print(f"Gemessener Schärfe-Score: {score:.2f} (Ziel: > {SHARPNESS_THRESHOLD})")
            if score >= SHARPNESS_THRESHOLD:
                print("[OK] Bild ist scharf genug!")
                cv2.imwrite(OUTPUT_FILE, frame)
                print(f"Bild gespeichert unter: {OUTPUT_FILE}")
                success = True
                break 
            else:
                print("[FEHLER] Bild ist zu unscharf. Bitte erneut 'w' drücken.")
        elif key == ord('q'):
            print("Abgebrochen durch Benutzer.")
            break

    cap.release()
    cv2.destroyAllWindows()
    return success

def analyze_image_with_gemini(image_path):
    print("Analysiere Bild mit Gemini 2.0 Flash...")
    
    api_key_path = 'api_key_google.txt'
    client = None
    
    # Check ob ein API-Key vorhanden ist
    if os.path.exists(api_key_path):
        with open(api_key_path, 'r') as f:
            api_key = f.read().strip()
            client = genai.Client(api_key=api_key)
    else:
        # Vertex AI Fallback über die Credentials-Datei
        try:
            with open("google_cloud_credentials.json", 'r') as f:
                creds_data = json.load(f)
                project_id = creds_data.get('project_id')
            client = genai.Client(vertexai=True, project=project_id, location='us-central1')
        except Exception as e:
            print(f"Fehler bei der Initialisierung des Gemini-Clients: {e}")
            print("Bitte stelle sicher, dass 'api_key_google.txt' existiert oder die Vertex AI API im Google Cloud Projekt aktiviert ist.")
            return ""

#     prompt = """Du bist das Lesemodul eines Vorlesegeräts. Analysiere das Bild und handle nach Dokumenttyp:
# - ZEITUNG/MAGAZIN: Lies spaltenweise von oben nach unten. Ignoriere Werbung, Bildunterschriften und Impressum.
# - BRIEF/DOKUMENT: Lies von oben links nach unten rechts. Ignoriere Briefkopf/Absenderadresse, beginne bei Betreff oder Anrede.
# - BUCH: Lies Fließtext fortlaufend, ignoriere Kopf-/Fußzeilen und Seitenzahlen.
# Entferne alle Silbentrennungen am Zeilenende. Gib ausschließlich den reinen Vorlesetext ohne Markdown oder Begleittext aus."""
    
    prompt = """Du bist das Lesemodul eines Vorlesegeräts. Analysiere das Bild und handle nach Dokumenttyp:
- ZEITUNG/MAGAZIN: Lies spaltenweise von oben nach unten. Ignoriere zwingend den gesamten Seitenkopf (Zeitungsname, Datum, Ausgabe-/Heftnummer, Ressort, Seitenzahlen), Bildunterschriften, Infokästen, Autorenzeilen und Werbung. Beginne erst bei der eigentlichen Schlagzeile bzw. Dachzeile des Hauptartikels.
- BRIEF/DOKUMENT: Lies von oben links nach unten rechts. Ignoriere Absenderangaben, Adressfeld, Falzmarken und Fußzeilen; beginne erst bei Betreff oder Anrede.
- BUCH: Lies Fließtext fortlaufend, ignoriere Kopfzeilen, Fußzeilen und Seitenzahlen.

Formatierungsregeln für die Audioausgabe:
- Entferne alle Silbentrennungen am Zeilenende und füge getrennte Wörter nahtlos zusammen.
- Beende jede Überschrift und Unterüberschrift zwingend mit einem Punkt, auch wenn im Layout kein Punkt steht.
- Trenne Überschriften, Unterüberschriften und Absätze jeweils durch genau zwei Zeilenumbrüche (eine Leerzeile dazwischen).
- Gib ausschließlich den reinen Text ohne Sonderzeichen-Syntax, ohne Markdown und ohne Begleittext aus."""

# Formatierungsregeln für die Audioausgabe:
# - Entferne alle Silbentrennungen am Zeilenende und setze getrennte Wörter nahtlos zusammen.
# - Bette den gesamten Text in <speak>...</speak> ein.
# - Füge nach Hauptüberschriften ein: <break time="1500ms"/>
# - Füge nach Unterüberschriften ein: <break time="1000ms"/>
# - Füge zwischen Sinnabschnitten ein: <break time="600ms"/>
# - Gib ausschließlich das fertige SSML ohne Markdown-Codeblöcke (kein ```xml) oder Begleittext aus."""
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                prompt
            ],
            config=types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
        return response.text
    except Exception as e:
        print(f"Fehler bei Gemini API Aufruf: {e}")
        return ""

def synthesize_speech_standard(text):
    if not text:
        return
        
    print("Generiere Audio (Google Text-to-Speech)...")
    try:
        language = detect(text)
        print(f"Erkannte Sprache: {language}")
    except Exception as e:
        print(f"Spracherkennung fehlgeschlagen ({e}), verwende Standard (de-DE).")
        language = "de"

    # Wähle Standardstimme basierend auf der erkannten Sprache (OHNE WaveNet)
    if language == 'el':
        voice_name = "el-GR-Standard-A"
        language_code = "el-GR"
    elif language == 'en':
        voice_name = "en-US-Standard-A" 
        language_code = "en-US"
    else:
        voice_name = "de-DE-Standard-A"
        language_code = "de-DE"
        
    print(f"Verwende Stimme: {voice_name}")

    # Text in Stücke aufteilen (Limit 5000 Bytes, wir nutzen max 4800 Bytes zur Sicherheit)
    # Wichtig: Bei Sprachen wie Griechisch (2 Bytes pro Zeichen) oder Umlauten reicht Zeichen zählen nicht!
    words = text.split()
    chunks = []
    current_chunk = []
    current_bytes = 0
    
    for word in words:
        word_bytes = len(word.encode('utf-8'))
        # +1 byte für das angenommene Leerzeichen
        if current_bytes + word_bytes + 1 > 4800:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_bytes = word_bytes
        else:
            current_chunk.append(word)
            current_bytes += word_bytes + 1

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    audio_queue = queue.Queue()
    
    def tts_worker():
        try:
            client = texttospeech.TextToSpeechClient()
            for i, chunk in enumerate(chunks):
                synthesis_input = texttospeech.SynthesisInput(text=chunk)
                voice = texttospeech.VoiceSelectionParams(
                    language_code=language_code,
                    name=voice_name
                )
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16
                )
                
                response = client.synthesize_speech(
                    input=synthesis_input, voice=voice, audio_config=audio_config
                )
                
                output_file = f"temp_google_tts_{i}.wav"
                with open(output_file, "wb") as out:
                    out.write(response.audio_content)
                
                audio_queue.put(output_file)
                
        except Exception as e:
            print(f"Fehler bei Google Text-to-Speech (Worker): {e}")
        finally:
            # Signalisiert, dass alle Audio-Chunks generiert wurden
            audio_queue.put(None)
            
    # Starte den Worker-Thread, der parallel die Audios von Google anfragt
    threading.Thread(target=tts_worker, daemon=True).start()
    
    # Wiedergabe-Schleife im Hauptthread
    print("Spiele Audio ab...")
    while True:
        file_to_play = audio_queue.get()
        if file_to_play is None:
            break
        
        winsound.PlaySound(file_to_play, winsound.SND_FILENAME)
        
        # Räume die temporäre Datei nach dem Abspielen direkt auf
        try:
            os.remove(file_to_play)
        except OSError:
            pass

def main():
    use_existing = False
    if os.path.exists(OUTPUT_FILE):
        print(f"Bestehendes Bild gefunden: {OUTPUT_FILE}")
        choice = input("Möchtest du das bestehende Bild verwenden (j) oder ein neues aufnehmen (n)? [j/n]: ").strip().lower()
        if choice == 'j':
            use_existing = True
            
    success = True
    if not use_existing:
        success = take_picture()
        
    if success and os.path.exists(OUTPUT_FILE):
        text = analyze_image_with_gemini(OUTPUT_FILE)
        if text:
            print("\n--- Extrahierter Text ---")
            print(text)
            print("-------------------------\n")
            synthesize_speech_standard(text)
        else:
            print("Es konnte kein Text extrahiert werden.")
    else:
        print("Konnte kein Bild aufnehmen oder finden.")

if __name__ == "__main__":
    main()
