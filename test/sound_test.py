#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sound- und Sprachtest für Raspberry Pi (Google Cloud Text-to-Speech)

Funktionen:
- Auswahl zwischen Deutsch und Griechisch (sowie beide nacheinander).
- Vorlesen eines mehrsätzigen Testtexts mit Google Cloud TTS (wie in vorlesen_pi_google.py).
- Automatisches Caching / Speichern als .wav Datei:
  * Beim 1. Aufruf: Über Google Cloud TTS generiert und dauerhaft als .wav gespeichert.
  * Bei wiederholtem Aufruf: Sofortiges lokales Abspielen der .wav Datei ohne erneute
    API-Nutzung (spart Latenz, Internet-Traffic und API-Kosten).
- Kann interaktiv über das Terminalmenü oder per CLI-Parameter (--lang de/el, --force)
  gesteuert werden.
- Unterstützt direkte ALSA-Wiedergabe ('aplay') auf dem Raspberry Pi sowie Winsound-
  Fallback für Windows-Tests.
"""

import os
import sys
import argparse
import subprocess
import warnings
from pathlib import Path

# Terminal-Encoding für Windows & Linux absichern
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Deprecation- & FutureWarnings von grpc/google drosseln
warnings.filterwarnings("ignore", category=FutureWarning)

from google.cloud import texttospeech

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
# --- PFADE & CREDENTIALS ---
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent if (BASE_DIR.parent / "vorlesen_pi_google.py").is_file() else BASE_DIR

# Lokales Cache-Verzeichnis für erzeugte WAV-Dateien (geteilt mit vorlesen_pi_google.py)
AUDIO_CACHE_DIR = PROJECT_ROOT / "audio_cache"

# Mögliche Speicherorte der Google Cloud Credentials
CREDENTIALS_CANDIDATES = [
    PROJECT_ROOT / "google_cloud_credentials.json",
    BASE_DIR / "google_cloud_credentials.json",
    Path("google_cloud_credentials.json"),
    Path("/home/kimon/pi-blind-reader/google_cloud_credentials.json"),
]


def init_credentials():
    """Sucht und setzt die Google Application Credentials Umgebungsvariable."""
    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ and os.path.isfile(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]):
        return os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

    for candidate in CREDENTIALS_CANDIDATES:
        if candidate.is_file():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(candidate.resolve())
            return str(candidate.resolve())

    return None


# ==============================================================================
# --- KONFIGURATION DER TESTTEXTE & STIMMEN ---
# ==============================================================================

USE_WAVENET = False  # False = Standard-Stimmen (wie in vorlesen_pi_google.py), True = WaveNet

TEST_CONFIG = {
    "de": {
        "title": "Deutsch",
        "lang_code": "de-DE",
        "voice_name": "de-DE-Wavenet-C" if USE_WAVENET else "de-DE-Standard-A",
        "filename": "sound_test_deutsch.wav",
        "text": (
            "Guten Tag! Dies ist ein Sound- und Sprachtest für den Raspberry Pi mit der Google Cloud Text-to-Speech API. "
            "Das Audiosystem, der Lautsprecher und die Tonausgabe funktionieren einwandfrei. "
            "Diese Audiodatei wurde nun als WAV-Datei auf dem Gerät gespeichert. "
            "Bei zukünftigen Tests wird sie direkt ohne erneuten API-Aufruf abgespielt."
        )
    },
    "el": {
        "title": "Griechisch (Ελληνικά)",
        "lang_code": "el-GR",
        "voice_name": "el-GR-Wavenet-A" if USE_WAVENET else "el-GR-Standard-A",
        "filename": "sound_test_griechisch.wav",
        "text": (
            "Γεια σας! Αυτός είναι ένας έλεγχος ήχου και ομιλίας για το Raspberry Pi με την υπηρεσία Google Cloud Text-to-Speech. "
            "Το ηχητικό σύστημα, το ηχείο και η αναπαραγωγή ήχου λειτουργούν κανονικά. "
            "Αυτό το αρχείο ήχου έχει αποθηκευτεί ως αρχείο WAV στη συσκευή. "
            "Σε μελλοντικούς ελέγχους θα αναπαράγεται απευθείας χωρίς νέα κλήση του API."
        )
    }
}


# ==============================================================================
# --- AUDIO-WIEDERGABE (ALSA FÜR RASPBERRY PI) ---
# ==============================================================================

def play_audio_file(file_path: Path):
    """
    Spielt eine WAV-Audiodatei ab.
    Auf Raspberry Pi / Linux wird direkt 'aplay' (ALSA / I2S-DAC) genutzt.
    Unter Windows wird winsound genutzt.
    """
    if not file_path.is_file():
        print(f"[Fehler] Audiodatei nicht gefunden: {file_path}")
        return False

    print(f"[Audio] Spiele Datei ab: {file_path.name}")

    if sys.platform.startswith("linux"):
        # Auf dem Pi nutzt aplay ALSA direkt
        res = subprocess.run(["aplay", "-q", str(file_path)], check=False)
        return res.returncode == 0
    elif HAS_WINSOUND:
        winsound.PlaySound(str(file_path), winsound.SND_FILENAME)
        return True
    else:
        # Fallback für macOS oder andere Plattformen
        for cmd in [["afplay", str(file_path)], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(file_path)]]:
            try:
                subprocess.run(cmd, check=True)
                return True
            except (FileNotFoundError, subprocess.SubprocessError):
                continue
        print("[Warnung] Kein unterstützter Audio-Player (aplay, afplay, ffplay) gefunden.")
        return False


# ==============================================================================
# --- GOOGLE CLOUD TTS SYNTHESE & CACHING ---
# ==============================================================================

def generate_tts_wav(text: str, lang_code: str, voice_name: str, output_path: Path) -> bool:
    """
    Generiert eine unkomprimierte LINEAR16-WAV-Datei über Google Cloud Text-to-Speech
    und speichert sie dauerhaft ab.
    """
    creds = init_credentials()
    if not creds:
        print("[Fehler] Keine 'google_cloud_credentials.json' gefunden!")
        print("Bitte stelle sicher, dass die Google Cloud Credentials vorhanden sind.")
        return False

    print(f"[Google Cloud API] Sende Synthese-Anfrage (Stimme: {voice_name}, Sprache: {lang_code})...")

    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code=lang_code,
            name=voice_name
        )

        # LINEAR16 erzeugt unkomprimiertes WAV (PCM 16-bit, 24kHz), ideal für aplay auf dem Pi
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )

        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.audio_content)

        file_size_kb = output_path.stat().st_size / 1024
        print(f"[OK] WAV-Datei erfolgreich erzeugt und gespeichert: {output_path.name} ({file_size_kb:.1f} KB)")
        return True

    except Exception as e:
        print(f"[Fehler bei Google Cloud TTS] {e}")
        return False


def test_language(lang_key: str, force_regenerate: bool = False):
    """
    Testet eine Sprache:
    - Wenn die WAV-Datei bereits existiert und kein 'force_regenerate' aktiv ist,
      wird die gespeicherte Datei direkt abgespielt (KEIN API-Aufruf!).
    - Andernfalls wird sie einmalig erzeugt, gespeichert und anschließend abgespielt.
    """
    if lang_key not in TEST_CONFIG:
        print(f"[Fehler] Unbekannte Sprache: {lang_key}")
        return

    config = TEST_CONFIG[lang_key]
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = AUDIO_CACHE_DIR / config["filename"]

    print("\n" + "=" * 65)
    print(f"  Test: {config['title']}")
    print("=" * 65)
    print(f"Vorlesetext:\n\"{config['text']}\"\n")

    # 1. Prüfen ob WAV-Datei bereits existiert
    if wav_path.is_file() and wav_path.stat().st_size > 0 and not force_regenerate:
        print(f"[Cache-Treffer] Lokale Datei '{wav_path.name}' bereits vorhanden.")
        print("   -> Spiele Datei direkt lokal ab (Keine Google Cloud API-Kosten!)")
    else:
        if force_regenerate and wav_path.is_file():
            print(f"[Erzwungen] Datei existiert, wird jedoch auf Wunsch neu generiert...")
        else:
            print(f"[Kein Cache] Datei '{wav_path.name}' noch nicht vorhanden.")
        
        success = generate_tts_wav(
            text=config["text"],
            lang_code=config["lang_code"],
            voice_name=config["voice_name"],
            output_path=wav_path
        )
        if not success:
            print("[Abbruch] Audio konnte nicht erstellt werden.")
            return

    # 2. Audio abspielen
    play_audio_file(wav_path)
    print(f"[Fertig] Test für {config['title']} abgeschlossen.\n")


def clear_cache():
    """Löscht alle gespeicherten Test-WAV-Dateien im Cache."""
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    deleted_count = 0
    for key in ("de", "el"):
        f = AUDIO_CACHE_DIR / TEST_CONFIG[key]["filename"]
        if f.is_file():
            f.unlink()
            deleted_count += 1
            print(f"  - Gelöscht: {f.name}")
    if deleted_count == 0:
        print("Cache war bereits leer.")
    else:
        print(f"Insgesamt {deleted_count} Datei(en) gelöscht.")


# ==============================================================================
# --- BENUTZERMENÜ & CLI ---
# ==============================================================================

def print_cache_status():
    """Zeigt an, welche Sprachdateien bereits im Cache liegen."""
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for key, cfg in TEST_CONFIG.items():
        wav = AUDIO_CACHE_DIR / cfg["filename"]
        if wav.is_file() and wav.stat().st_size > 0:
            size_kb = wav.stat().st_size / 1024
            status = f"[OK] Vorhanden ({size_kb:.1f} KB) -> spielt sofort ohne API"
        else:
            status = "[--] Nicht vorhanden -> wird bei Auswahl über API generiert"
        print(f"  * {cfg['title']:<24}: {status}")


def interactive_menu():
    """Interaktives Auswahlmenü im Terminal."""
    while True:
        print("\n" + "=" * 65)
        print("  Raspberry Pi Sound- & TTS-Test (Google Cloud Text-to-Speech)")
        print("=" * 65)
        print("Speicherort Cache:", AUDIO_CACHE_DIR.resolve())
        print("\nAktueller Cache-Status:")
        print_cache_status()
        print("\nBitte auswählen:")
        print("  [1] Deutsch vorlesen (DE)")
        print("  [2] Griechisch vorlesen (EL)")
        print("  [3] Beide nacheinander vorlesen")
        print("  [4] Neu generieren erzwingen (Google API erneut aufrufen)")
        print("  [5] Gespeicherte WAV-Dateien löschen (Cache leeren)")
        print("  [q] Beenden")
        print("=" * 65)

        try:
            choice = input("Deine Auswahl: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nProgramm beendet.")
            break

        if choice in ("1", "de", "deutsch"):
            test_language("de")
        elif choice in ("2", "el", "gr", "griechisch"):
            test_language("el")
        elif choice == "3":
            test_language("de")
            test_language("el")
        elif choice == "4":
            print("\nWelche Sprache soll neu über Google API geladen werden?")
            print("  [1] Deutsch")
            print("  [2] Griechisch")
            print("  [3] Beide")
            sub_choice = input("Auswahl: ").strip()
            if sub_choice == "1":
                test_language("de", force_regenerate=True)
            elif sub_choice == "2":
                test_language("el", force_regenerate=True)
            elif sub_choice == "3":
                test_language("de", force_regenerate=True)
                test_language("el", force_regenerate=True)
        elif choice == "5":
            clear_cache()
        elif choice in ("q", "quit", "exit"):
            print("Auf Wiedersehen!")
            break
        else:
            print("[Ungültige Eingabe] Bitte 1, 2, 3, 4, 5 oder q eingeben.")


def main():
    parser = argparse.ArgumentParser(
        description="Sound- und Sprachtest für Raspberry Pi mit Google Cloud TTS"
    )
    parser.add_argument(
        "-l", "--lang",
        choices=["de", "el", "both"],
        help="Direkt Sprache auswählen ('de', 'el' oder 'both') ohne interaktives Menü"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Erzwingt neue Generierung über die Google Cloud API, selbst wenn WAV existiert"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Löscht alle gespeicherten Test-WAV-Dateien und beendet das Programm"
    )

    args = parser.parse_args()

    # Wenn Credentials vorhanden sind, kurz initialisieren
    creds = init_credentials()
    if creds:
        print(f"[Init] Google Cloud Credentials: {creds}")
    else:
        print("[Hinweis] Keine lokalen 'google_cloud_credentials.json' gefunden.")

    if args.clear_cache:
        clear_cache()
        return

    if args.lang == "de":
        test_language("de", force_regenerate=args.force)
    elif args.lang == "el":
        test_language("el", force_regenerate=args.force)
    elif args.lang == "both":
        test_language("de", force_regenerate=args.force)
        test_language("el", force_regenerate=args.force)
    else:
        # Kein Parameter übergeben -> interaktives Menü starten
        interactive_menu()


if __name__ == "__main__":
    main()
