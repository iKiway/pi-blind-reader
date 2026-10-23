#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sound- und Sprachtest für Raspberry Pi (Google Cloud Text-to-Speech)
Optimiert für MAX98357A I2S Mono-Verstärker

Warum dieses Skript auf dem MAX98357A funktioniert:
- Der MAX98357A ist ein reiner I2S-DAC und besitzt KEINEN internen Hardware-Mixer.
  Klassische 'amixer'-Befehle schlagen daher standardmäßig fehl.
- Dieses Skript implementiert eine softwareseitige Echtzeit-PCM-Lautstärkeregelung:
  Die 16-Bit-Audiodaten werden in 50ms-Blöcken direkt in Python im Speicher skaliert
  und per Pipe an 'aplay' übergeben.
- Tastensteuerung während des Vorlesens:
  * 'w' / 'W' = Lauter (+5%)
  * 's' / 'S' = Leiser (-5%)
  * 'q' / 'Q' = Wiedergabe sofort stoppen
- Automatisches Caching / Speichern als .wav Datei:
  * 1. Aufruf: Über Google Cloud TTS generiert und dauerhaft als .wav gespeichert.
  * Wiederholter Aufruf: Sofortiges Abspielen der .wav Datei ohne API-Aufruf (keine Kosten/Internet).
- Unterstützt Deutsch und Griechisch (sowie beide nacheinander).
"""

import os
import sys
import wave
import time
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

# Windows Tastaturabfrage via msvcrt
if sys.platform.startswith("win"):
    try:
        import msvcrt
        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False
else:
    HAS_MSVCRT = False


# ==============================================================================
# --- PFADE & CREDENTIALS ---
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent if (BASE_DIR.parent / "vorlesen_pi_google.py").is_file() else BASE_DIR

# Lokales Cache-Verzeichnis für erzeugte WAV-Dateien
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
# --- ECHTZEIT-PCM-LAUTSTÄRKESKALIERUNG (FÜR MAX98357A) ---
# ==============================================================================

# Standard-Lautstärke: 80% (0.80)
# HINWEIS: 100% führt beim MAX98357A 3W-Verstärker leicht zu Clipping/Verzerrungen.
# 80-85% liefert den saubersten Klang.
CURRENT_VOLUME = 0.80

try:
    import audioop

    def scale_pcm_chunk(chunk_bytes: bytes, volume_factor: float) -> bytes:
        """Skaliert 16-Bit PCM-Audiodaten in C (blitzschnell via audioop)."""
        factor = max(0.0, min(1.2, volume_factor))
        return audioop.mul(chunk_bytes, 2, factor)

except ImportError:
    import numpy as np

    def scale_pcm_chunk(chunk_bytes: bytes, volume_factor: float) -> bytes:
        """Fallback über NumPy, falls audioop nicht vorhanden ist."""
        factor = max(0.0, min(1.2, volume_factor))
        arr = np.frombuffer(chunk_bytes, dtype=np.int16)
        scaled = np.clip(arr * factor, -32768, 32767).astype(np.int16)
        return scaled.tobytes()


def format_volume_bar(percent: int) -> str:
    """Erzeugt eine universelle Lautstärkeleiste, z.B. '[########..]  80%'."""
    filled = max(0, min(10, int(percent / 10)))
    empty = 10 - filled
    bar = "#" * filled + "." * empty
    return f"[{bar}] {percent:>3}%"


def set_volume_relative(step_percent: int) -> float:
    """Erhöht oder verringert die globale Lautstärke um step_percent."""
    global CURRENT_VOLUME
    new_vol = CURRENT_VOLUME + (step_percent / 100.0)
    CURRENT_VOLUME = max(0.0, min(1.0, round(new_vol, 2)))
    return CURRENT_VOLUME


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
            "Guten Tag! Dies ist ein Sound- und Sprachtest für den Raspberry Pi mit dem MAX98357A I2S Verstärker. "
            "Das Audiosystem, die Lautstärkeregelung und die Sprachausgabe funktionieren einwandfrei. "
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
            "Γεια σας! Αυτός είναι ένας έλεγχος ήχου και ομιλίας για το Raspberry Pi με τον ενισχυτή MAX98357A. "
            "Το ηχητικό σύστημα, η ρύθμιση έντασης και η αναπαραγωγή ήχου λειτουργούν κανονικά. "
            "Αυτό το αρχείο ήχου έχει αποθηκευτεί ως αρχείο WAV στη συσκευή. "
            "Σε μελλοντικούς ελέγχους θα αναπαράγεται απευθείας χωρίς νέα κλήση του API."
        )
    }
}


# ==============================================================================
# --- AUDIO-WIEDERGABE MIT LIVE-SOFTWARE-STREAMING ---
# ==============================================================================

def play_audio_file(file_path: Path) -> bool:
    """
    Spielt die WAV-Datei ab und skaliert die Audio-Samples in Echtzeit.
    
    Da der MAX98357A keinen Hardware-Lautstärkeregler besitzt, wird der Audiostream
    in 50ms-Häppchen aufgeteilt. Jeder Block wird mit der aktuellen Lautstärke
    skaliert, bevor er an den Audioplayer übergeben wird.
    
    Tasten während der Wiedergabe:
      - 'w' / 'W': Lauter (+5%)
      - 's' / 'S': Leiser (-5%)
      - 'q' / 'Q': Wiedergabe sofort stoppen
    """
    global CURRENT_VOLUME

    if not file_path.is_file():
        print(f"[Fehler] Datei nicht gefunden: {file_path}")
        return False

    try:
        wav_in = wave.open(str(file_path), "rb")
    except Exception as e:
        print(f"[Fehler] Konnte WAV-Datei nicht öffnen: {e}")
        return False

    framerate = wav_in.getframerate()
    channels = wav_in.getnchannels()
    sample_width = wav_in.getsampwidth()
    total_frames = wav_in.getnframes()
    bytes_per_frame = channels * sample_width

    # 50 Millisekunden pro Audio-Block (~1200 Frames bei 24kHz)
    chunk_frames = max(256, int(framerate * 0.05))

    # Player-Befehl zusammenstellen
    if sys.platform.startswith("linux"):
        # aplay liest rohes PCM direkt von stdin
        player_cmd = [
            "aplay",
            "-q",
            "-r", str(framerate),
            "-f", "S16_LE",
            "-c", str(channels),
            "-t", "raw",
            "-"
        ]
    elif sys.platform.startswith("win"):
        # ffplay für Windows-Entwicklung (falls vorhanden)
        player_cmd = [
            "ffplay",
            "-nodisp",
            "-autoexit",
            "-loglevel", "quiet",
            "-f", "s16le",
            "-ar", str(framerate),
            "-ch_layout", "mono" if channels == 1 else "stereo",
            "-i", "-"
        ]
    else:
        player_cmd = [
            "ffplay",
            "-nodisp",
            "-autoexit",
            "-loglevel", "quiet",
            "-f", "s16le",
            "-ar", str(framerate),
            "-ch_layout", "mono" if channels == 1 else "stereo",
            "-i", "-"
        ]

    print(f"\n▶️  Wiedergabe: {file_path.name}")
    print("   ┌──────────────────────────────────────────────────────────┐")
    print("   │  MAX98357A Live-Regelung während des Vorlesens:          │")
    print("   │  [W] = Lauter (+5%)   [S] = Leiser (-5%)   [Q] = Stop    │")
    print("   └──────────────────────────────────────────────────────────┘")
    vol_pct = int(round(CURRENT_VOLUME * 100))
    print(f"   Aktuelle Lautstärke: {format_volume_bar(vol_pct)}")

    # Player-Subprozess mit Standard-Input-Pipe starten
    try:
        proc = subprocess.Popen(
            player_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"[Warnung] Player konnte nicht gestartet werden: {e}")
        # Notfall-Fallback auf Standard-Wiedergabe
        if HAS_WINSOUND:
            winsound.PlaySound(str(file_path), winsound.SND_FILENAME)
            return True
        return False

    # Vorbereitung für nicht-blockierende Tastatureingabe
    old_term_settings = None
    is_linux_tty = sys.platform.startswith("linux") and sys.stdin.isatty()
    if is_linux_tty:
        import termios
        import tty
        import select
        fd = sys.stdin.fileno()
        try:
            old_term_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        except Exception:
            old_term_settings = None

    frames_sent = 0
    start_time = time.time()
    aborted = False

    try:
        while True:
            raw_chunk = wav_in.readframes(chunk_frames)
            if not raw_chunk:
                break

            n_frames = len(raw_chunk) // bytes_per_frame
            frames_sent += n_frames

            # Echtzeit-Taktsynchronisation (halten ~50ms Puffer vor der Hardware)
            expected_elapsed = frames_sent / framerate
            now = time.time() - start_time
            lead_time = expected_elapsed - now
            wait_time = lead_time - 0.05

            # Tastenabfrage während der Wartezeit
            if is_linux_tty:
                import select
                timeout = max(0.0, min(0.08, wait_time))
                rlist, _, _ = select.select([sys.stdin], [], [], timeout)
                if rlist:
                    ch = sys.stdin.read(1)
                    if ch.lower() == 'w':
                        set_volume_relative(+5)
                        v_pct = int(round(CURRENT_VOLUME * 100))
                        sys.stdout.write(f"\r   [Lauter +5%]  {format_volume_bar(v_pct)}       ")
                        sys.stdout.flush()
                    elif ch.lower() == 's':
                        set_volume_relative(-5)
                        v_pct = int(round(CURRENT_VOLUME * 100))
                        sys.stdout.write(f"\r   [Leiser -5%]  {format_volume_bar(v_pct)}       ")
                        sys.stdout.flush()
                    elif ch.lower() == 'q' or ch == '\x1b':
                        aborted = True
                        sys.stdout.write("\n   [Abbruch] Wiedergabe durch Benutzer beendet.\n")
                        sys.stdout.flush()
                        break
            elif HAS_MSVCRT:
                # Windows Tastaturabfrage
                if wait_time > 0:
                    time.sleep(min(0.05, wait_time))
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if isinstance(ch, bytes):
                        try:
                            ch = ch.decode("utf-8", errors="ignore")
                        except Exception:
                            ch = ""
                    if ch.lower() == 'w':
                        set_volume_relative(+5)
                        v_pct = int(round(CURRENT_VOLUME * 100))
                        sys.stdout.write(f"\r   [Lauter +5%]  {format_volume_bar(v_pct)}       ")
                        sys.stdout.flush()
                    elif ch.lower() == 's':
                        set_volume_relative(-5)
                        v_pct = int(round(CURRENT_VOLUME * 100))
                        sys.stdout.write(f"\r   [Leiser -5%]  {format_volume_bar(v_pct)}       ")
                        sys.stdout.flush()
                    elif ch.lower() == 'q' or ch == '\x1b':
                        aborted = True
                        sys.stdout.write("\n   [Abbruch] Wiedergabe durch Benutzer beendet.\n")
                        sys.stdout.flush()
                        break
            else:
                if wait_time > 0:
                    time.sleep(min(0.05, wait_time))

            # Audioblock in Echtzeit mit der aktuellen Lautstärke skalieren
            scaled_chunk = scale_pcm_chunk(raw_chunk, CURRENT_VOLUME)

            # An Player-Pipe senden
            try:
                proc.stdin.write(scaled_chunk)
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                break

    finally:
        # Terminal-Einstellungen sauber wiederherstellen
        if old_term_settings is not None:
            import termios
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_term_settings)
            except Exception:
                pass

        wav_in.close()

        if aborted:
            try:
                proc.terminate()
            except Exception:
                pass
        else:
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            sys.stdout.write("\n")
            sys.stdout.flush()

    return True


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

        # LINEAR16 = unkomprimiertes WAV (PCM 16-bit, 24kHz Mono)
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

    # 2. Audio abspielen mit Echtzeit-Software-Lautstärkeregelung
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
    global CURRENT_VOLUME
    while True:
        vol_pct = int(round(CURRENT_VOLUME * 100))
        print("\n" + "=" * 65)
        print("  Raspberry Pi Sound- & TTS-Test (MAX98357A I2S Edition)")
        print("=" * 65)
        print(f"  Aktuelle Lautstärke : {format_volume_bar(vol_pct)}")
        print(f"  Speicherort Cache   : {AUDIO_CACHE_DIR.resolve()}")
        print("\nAktueller Cache-Status:")
        print_cache_status()
        print("\nBitte auswählen:")
        print("  [1] Deutsch vorlesen (DE)")
        print("  [2] Griechisch vorlesen (EL)")
        print("  [3] Beide nacheinander vorlesen")
        print("  [w] Lautstärke erhöhen (+5%)")
        print("  [s] Lautstärke verringern (-5%)")
        print("  [4] Neu generieren erzwingen (Google API erneut aufrufen)")
        print("  [5] Gespeicherte WAV-Dateien löschen (Cache leeren)")
        print("  [q] Beenden")
        print("=" * 65)
        print("  Tipp: Während des Vorlesens kannst du jederzeit mit [W] lauter und [S] leiser stellen!")

        try:
            choice = input("\nDeine Auswahl: ").strip().lower()
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
        elif choice in ("w", "+"):
            set_volume_relative(+5)
            v_pct = int(round(CURRENT_VOLUME * 100))
            print(f"-> Lautstärke erhöht: {format_volume_bar(v_pct)}")
        elif choice in ("s", "-"):
            set_volume_relative(-5)
            v_pct = int(round(CURRENT_VOLUME * 100))
            print(f"-> Lautstärke verringert: {format_volume_bar(v_pct)}")
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
            print("[Ungültige Eingabe] Bitte 1, 2, 3, w, s, 4, 5 oder q eingeben.")


def main():
    parser = argparse.ArgumentParser(
        description="Sound- und Sprachtest für Raspberry Pi mit Google Cloud TTS (optimiert für MAX98357A)"
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
    parser.add_argument(
        "--volume",
        type=int,
        default=80,
        help="Startlautstärke in Prozent (Standard: 80)"
    )

    args = parser.parse_args()

    # Startlautstärke setzen
    global CURRENT_VOLUME
    CURRENT_VOLUME = max(0.0, min(1.0, args.volume / 100.0))

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
