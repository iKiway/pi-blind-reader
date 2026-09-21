#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vorlesegerät für Raspberry Pi (Kamera-Modul 3 + Google Cloud Gemini & TTS)

Kombiniert:
- Hardware/Kamera-Workaround aus vorlesen.py (Picamera2, Autofokus-Warmup,
  Laplace-Schärfeprüfung im RAM, 90°-Drehung, Ressourcensicherheit).
- Cloud-Pipeline aus vorlesen_pc_google.py (Gemini 2.5 Flash Lite Vision
  für OCR + Dokumentanalyse + Formatierung sowie Google Cloud TTS mit
  parallelem Audio-Streaming).
- Raspberry Pi Optimierungen (aplay ALSA-Playback, sparsamer RAM-Umgang,
  automatische Pfadauflösung, Statusansagen).
"""

import os
import sys
import time
import json
import queue
import tempfile
import threading
import subprocess
from pathlib import Path

import cv2
import numpy as np
from langdetect import detect
from google import genai
from google.genai import types
from google.cloud import texttospeech

# Picamera2 nur importieren, wenn vorhanden (auf Raspberry Pi)
try:
    from picamera2 import Picamera2
    HAS_PICAMERA = True
except ImportError:
    HAS_PICAMERA = False

# Sound-Treiber auf Linux/Raspberry Pi laden (falls nicht bereits aktiv)
if sys.platform.startswith("linux"):
    try:
        subprocess.run(['sudo', 'modprobe', 'snd_bcm2835'], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# Optionales winsound für Windows-Entwicklung/Tests
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


# ==============================================================================
# --- KONFIGURATION ---
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent

# Pfade zu Schlüsseln & Anmeldedaten
CREDENTIALS_CANDIDATES = [
    BASE_DIR / "google_cloud_credentials.json",
    Path("google_cloud_credentials.json"),
    Path("/home/kimon/pi-blind-reader/google_cloud_credentials.json"),
]

API_KEY_CANDIDATES = [
    BASE_DIR / "api_key_google.txt",
    Path("api_key_google.txt"),
    Path("/home/kimon/pi-blind-reader/api_key_google.txt"),
]

# Kamera-Einstellungen
OUTPUT_DIR = BASE_DIR / "captured_images"
OUTPUT_FILE = OUTPUT_DIR / "scharfes_bild.jpg"
MAX_RETRIES = 5               # Maximale Versuche für ein scharfes Bild
SHARPNESS_THRESHOLD = 12.0    # Schwellenwert (Laplace-Varianz)
WARMUP_TIME = 2.0             # Sekunden Wartezeit für kontinuierlichen Autofokus
CAMERA_RESOLUTION = (1920, 1080)  # Full HD
# Bilddrehung: Bei Raspberry Pi Kamera-Modul 3 oft 90° gegen den Uhrzeigersinn
CAMERA_ROTATION = cv2.ROTATE_90_COUNTERCLOCKWISE

# Audio / TTS-Einstellungen
USE_WAVENET = False           # True = Hochwertigere WaveNet/Neural2 Stimmen, False = Standard
ENABLE_AUDIO_FEEDBACK = True  # Akustische Statusansagen ("Dokument bereit...", etc.)
GEMINI_MODEL = "gemini-2.5-flash-lite"


# ==============================================================================
# --- INITIALISIERUNG DER CREDENTIALS ---
# ==============================================================================

def find_first_existing_path(candidate_paths):
    """Sucht den ersten existierenden Pfad aus einer Liste von Kandidaten."""
    for p in candidate_paths:
        if p.is_file():
            return str(p)
    return None

# Google Application Credentials setzen
creds_path = find_first_existing_path(CREDENTIALS_CANDIDATES)
if creds_path:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    print(f"[Init] Google Cloud Credentials geladen: {creds_path}")
elif "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    print(f"[Init] Google Cloud Credentials aus Umgebungsvariable: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")
else:
    print("[Warnung] Keine 'google_cloud_credentials.json' gefunden.")

api_key_file = find_first_existing_path(API_KEY_CANDIDATES)


# ==============================================================================
# --- AUDIO-AUSGABE & STATUSANSAGEN (FÜR RASPBERRY PI) ---
# ==============================================================================

def play_audio_file(file_path):
    """
    Spielt eine WAV-Audiodatei auf dem jeweiligen Betriebssystem ab.
    Auf Raspberry Pi / Linux wird direkt 'aplay' (ALSA) verwendet.
    """
    if sys.platform.startswith("linux"):
        # Auf dem Pi nutzt aplay ALSA / I2S-DAC direkt
        subprocess.run(["aplay", "-q", str(file_path)], check=False)
    elif HAS_WINSOUND:
        winsound.PlaySound(str(file_path), winsound.SND_FILENAME)
    else:
        # Fallback für macOS oder andere Plattformen
        for cmd in [["afplay", str(file_path)], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(file_path)]]:
            try:
                subprocess.run(cmd, check=True)
                break
            except (FileNotFoundError, subprocess.SubprocessError):
                continue

def speak_status(text):
    """
    Gibt kurze akustische Statusmeldungen für barrierefreie Bedienung aus.
    Erfolgt direkt via Google Cloud TTS (kurze Synthese ~0.2s).
    """
    print(f"[Statusansage] {text}")
    if not ENABLE_AUDIO_FEEDBACK:
        return

    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="de-DE",
            name="de-DE-Standard-A"
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_name = tmp.name
            tmp.write(response.audio_content)

        play_audio_file(tmp_name)
        try:
            os.remove(tmp_name)
        except OSError:
            pass
    except Exception as e:
        print(f"[Warnung] Statusansage konnte nicht wiedergegeben werden: {e}")


# ==============================================================================
# --- KAMERA & SCHÄRFEPRÜFUNG (WORKAROUND VON VORLESEN.PY) ---
# ==============================================================================

def calculate_sharpness_score(image_array):
    """
    Berechnet einen Schärfegrad basierend auf der Laplace-Varianz.
    Höherer Wert = schärferes Bild.
    Funktioniert direkt im RAM auf dem Bild-Array.
    """
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(laplacian.var())

def take_picture():
    """
    Nimmt ein scharfes Bild mit Picamera2 auf dem Raspberry Pi auf.
    Führt Autofokus-Warmup durch und bewertet die Schärfe direkt im RAM,
    bevor auf die SD-Karte geschrieben wird.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not HAS_PICAMERA:
        print("[Fehler] 'picamera2' ist nicht installiert oder nicht verfügbar.")
        print("Falls du auf einem PC testest, stelle sicher, dass 'captured_images/scharfes_bild.jpg' existiert.")
        if OUTPUT_FILE.is_file():
            print(f"[Info] Verwende vorhandenes Testbild: {OUTPUT_FILE}")
            return True
        return False

    print("Initialisiere Picamera2 (Kamera-Modul 3)...")
    picam2 = Picamera2()
    
    # Still-Konfiguration (Full HD für optimale Erkennung bei schneller Verarbeitung)
    config = picam2.create_still_configuration(main={"size": CAMERA_RESOLUTION})
    picam2.configure(config)

    speak_status("Dokument bereit zum Fotografieren. Bitte halten Sie das Dokument ruhig.")

    success = False
    try:
        # Kamera starten: Autofokus beginnt zu arbeiten
        picam2.start()
        print(f"Warte {WARMUP_TIME} Sekunden für Autofokus-Einstellung...")
        time.sleep(WARMUP_TIME)

        attempt = 1
        while attempt <= MAX_RETRIES:
            print(f"\n--- Aufnahmeversuch {attempt} von {MAX_RETRIES} ---")
            
            # Bild direkt in den Arbeitsspeicher holen (spart Schreibzyklen auf der SD-Karte)
            image_array = picam2.capture_array()

            # Schärfe prüfen
            score = calculate_sharpness_score(image_array)
            print(f"Gemessener Schärfe-Score: {score:.2f} (Schwelle: > {SHARPNESS_THRESHOLD})")

            if score >= SHARPNESS_THRESHOLD:
                print("✅ Bild ist scharf genug!")
                # In BGR für OpenCV konvertieren
                image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                
                # Falls Kamera auf dem Kopf oder seitlich montiert ist
                if CAMERA_ROTATION is not None:
                    image_bgr = cv2.rotate(image_bgr, CAMERA_ROTATION)
                
                cv2.imwrite(str(OUTPUT_FILE), image_bgr)
                print(f"Bild erfolgreich gespeichert: {OUTPUT_FILE}")
                success = True
                speak_status("Bild aufgenommen und wird verarbeitet. Bitte warten.")
                break
            else:
                print("❌ Bild ist zu unscharf.")
                if attempt < MAX_RETRIES:
                    print("Warte 1.5s zur Neufokussierung...")
                    time.sleep(1.5)
            
            attempt += 1

    except Exception as e:
        print(f"[Fehler bei Kameraaufnahme] {e}")
    finally:
        # Kamera-Hardware immer sicher freigeben
        try:
            picam2.stop()
            picam2.close()
        except Exception:
            pass

    if not success:
        print("\n[Abbruch] Konnte kein ausreichend scharfes Bild aufnehmen.")
        speak_status("Es konnte kein scharfes Bild aufgenommen werden. Bitte Licht und Abstand prüfen.")
    
    return success


# ==============================================================================
# --- CLOUD-VISION MIT GEMINI 2.5 FLASH LITE (VON VORLESEN_PC_GOOGLE.PY) ---
# ==============================================================================

def get_gemini_client():
    """Initialisiert den Gemini Client entweder per API-Key oder per Vertex AI Credentials."""
    if api_key_file and os.path.exists(api_key_file):
        with open(api_key_file, 'r', encoding='utf-8') as f:
            api_key = f.read().strip()
        if api_key:
            print("[Gemini] Verwende API-Key aus 'api_key_google.txt'")
            return genai.Client(api_key=api_key)

    # Vertex AI Fallback über google_cloud_credentials.json
    if creds_path and os.path.exists(creds_path):
        try:
            with open(creds_path, 'r', encoding='utf-8') as f:
                creds_data = json.load(f)
                project_id = creds_data.get('project_id')
            print(f"[Gemini] Verwende Vertex AI Fallback (Projekt: {project_id})")
            return genai.Client(vertexai=True, project=project_id, location='us-central1')
        except Exception as e:
            print(f"[Gemini Init Fehler] {e}")

    # Letzter Versuch: Standard-Client
    return genai.Client()

def analyze_image_with_gemini(image_path):
    """
    Analysiert das Bild mit Gemini 2.5 Flash Lite.
    Führt multimodale Erkennung, Layoutanalyse (Spalten, Briefköpfe, Fließtext)
    und Textbereinigung für Audioausgabe in einem einzigen Schritt durch.
    """
    print(f"\nAnalysiere Bild mit {GEMINI_MODEL}...")
    try:
        client = get_gemini_client()
    except Exception as e:
        print(f"[Fehler] Konnte Gemini-Client nicht initialisieren: {e}")
        return ""

    prompt = """Du bist das Lesemodul eines Vorlesegeräts. Analysiere das Bild und handle nach Dokumenttyp:
- ZEITUNG/MAGAZIN: Lies spaltenweise von oben nach unten. Ignoriere zwingend den gesamten Seitenkopf (Zeitungsname, Datum, Ausgabe-/Heftnummer, Ressort, Seitenzahlen), Bildunterschriften, Infokästen, Autorenzeilen und Werbung. Beginne erst bei der eigentlichen Schlagzeile bzw. Dachzeile des Hauptartikels.
- BRIEF/DOKUMENT: Lies von oben links nach unten rechts. Ignoriere Absenderangaben, Adressfeld, Falzmarken und Fußzeilen; beginne erst bei Betreff oder Anrede.
- BUCH: Lies Fließtext fortlaufend, ignoriere Kopfzeilen, Fußzeilen und Seitenzahlen.

Formatierungsregeln für die Audioausgabe:
- Entferne alle Silbentrennungen am Zeilenende und füge getrennte Wörter nahtlos zusammen.
- Beende jede Überschrift und Unterüberschrift zwingend mit einem Punkt, auch wenn im Layout kein Punkt steht.
- Trenne Überschriften, Unterüberschriften und Absätze jeweils durch genau zwei Zeilenumbrüche (eine Leerzeile dazwischen).
- Gib ausschließlich den reinen Text ohne Sonderzeichen-Syntax, ohne Markdown und ohne Begleittext aus."""

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                prompt
            ],
            config=types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
        return (response.text or "").strip()
    except Exception as e:
        print(f"[Fehler bei Gemini API Aufruf] {e}")
        return ""


# ==============================================================================
# --- GOOGLE CLOUD TEXT-TO-SPEECH STREAMING (OPTIMIERT FÜR RASPBERRY PI) ---
# ==============================================================================

def select_tts_voice(text):
    """Erkennt die Sprache und wählt die passende Stimme aus."""
    try:
        language = detect(text)
        print(f"[Spracherkennung] Erkannte Sprache: {language}")
    except Exception as e:
        print(f"[Spracherkennung] Fallback auf Deutsch ({e})")
        language = "de"

    if language == 'el':
        language_code = "el-GR"
        voice_name = "el-GR-Wavenet-A" if USE_WAVENET else "el-GR-Standard-A"
    elif language == 'en':
        language_code = "en-US"
        voice_name = "en-US-Wavenet-A" if USE_WAVENET else "en-US-Standard-A"
    else:
        language_code = "de-DE"
        voice_name = "de-DE-Wavenet-C" if USE_WAVENET else "de-DE-Standard-A"

    return language_code, voice_name

def chunk_text_by_bytes(text, max_bytes=4800):
    """
    Teilt langen Text in Stücke auf, die das Google Cloud TTS Limit von 5000 Bytes
    sicher einhalten. Berücksichtigt Multi-Byte-Zeichen (Griechisch, Umlaute).
    """
    words = text.split()
    chunks = []
    current_chunk = []
    current_bytes = 0

    for word in words:
        word_bytes = len(word.encode('utf-8'))
        # +1 Byte für das Leerzeichen
        if current_bytes + word_bytes + 1 > max_bytes:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_bytes = word_bytes
        else:
            current_chunk.append(word)
            current_bytes += word_bytes + 1

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def synthesize_speech_streaming(text):
    """
    Synthetisiert und spielt Text über Google Cloud TTS ab.
    Nutzt einen Hintergrund-Thread (Worker) und eine Warteschlange:
    Während der erste Abschnitt bereits über die Lautsprecher abgespielt wird,
    wird der nächste Abschnitt im Hintergrund generiert (minimale Latenz).
    """
    if not text:
        return

    language_code, voice_name = select_tts_voice(text)
    chunks = chunk_text_by_bytes(text)
    print(f"[TTS] Text in {len(chunks)} Chunks aufgeteilt. Stimme: {voice_name}")

    audio_queue = queue.Queue(maxsize=3)
    temp_dir = Path(tempfile.gettempdir()) / "pi_reader_tts"
    temp_dir.mkdir(parents=True, exist_ok=True)

    def tts_worker():
        try:
            client = texttospeech.TextToSpeechClient()
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16
            )

            for i, chunk in enumerate(chunks):
                synthesis_input = texttospeech.SynthesisInput(text=chunk)
                response = client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
                
                output_file = temp_dir / f"chunk_{i}_{int(time.time()*1000)}.wav"
                with open(output_file, "wb") as out:
                    out.write(response.audio_content)

                audio_queue.put(str(output_file))

        except Exception as e:
            print(f"[Fehler bei Google TTS Worker] {e}")
        finally:
            audio_queue.put(None)  # Ende-Signal

    # Worker-Thread im Hintergrund starten
    worker_thread = threading.Thread(target=tts_worker, daemon=True)
    worker_thread.start()

    # Wiedergabe-Schleife im Hauptthread
    print("▶️  Starte Audio-Wiedergabe...")
    try:
        while True:
            file_to_play = audio_queue.get()
            if file_to_play is None:
                break
            
            try:
                play_audio_file(file_to_play)
            finally:
                # Datei nach dem Abspielen sofort löschen
                try:
                    os.remove(file_to_play)
                except OSError:
                    pass
    except KeyboardInterrupt:
        print("\n[Abbruch] Wiedergabe durch Benutzer beendet.")


# ==============================================================================
# --- HAUPTPROGRAMM ---
# ==============================================================================

def main():
    print("==================================================")
    print("  Raspberry Pi Vorlesegerät (Google Cloud Edition)")
    print("==================================================")
    
    # 1. Bildaufnahme mit Picamera2 & Laplace-Schärfeprüfung
    picture_taken = take_picture()
    if not picture_taken or not OUTPUT_FILE.is_file():
        print("[Fehler] Kein gültiges Bild vorhanden.")
        return

    # 2. Textanalyse mit Gemini 2.5 Flash Lite
    text = analyze_image_with_gemini(str(OUTPUT_FILE))
    
    if text:
        print("\n" + "=" * 50)
        print("  EXTRAHIERTER VORLESETEXT")
        print("=" * 50)
        print(text)
        print("=" * 50 + "\n")

        # 3. Audioausgabe via Google Cloud Text-to-Speech Streaming
        synthesize_speech_streaming(text)
        speak_status("Vorlesen beendet.")
    else:
        print("[Info] Es konnte kein relevanter Text extrahiert werden.")
        speak_status("Es wurde kein lesbarer Text auf der Seite gefunden.")

if __name__ == "__main__":
    main()
