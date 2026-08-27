"""
Piper TTS Engine & Voice Manager
---------------------------------
Modulares, schnelles Text-to-Speech Framework für Piper TTS (.onnx) Modelle
auf dem PC (Windows, Linux, macOS) mit automatischem Modell-Download,
abbrechbarer Audio-Wiedergabe, intelligenter Spracherkennung und Audio-Filtern.
"""

import os
import json
import wave
import time
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Union

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Standard-Verzeichnis für heruntergeladene Stimmen
DEFAULT_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models_piper")

# Katalog bekannter, qualitativ hochwertiger Stimmen aus rhasspy/piper-voices
VOICE_CATALOG = {
    # Deutsch
    "de_DE-thorsten-medium": {
        "lang": "de",
        "name": "Thorsten (Männlich, Natürlich)",
        "quality": "medium",
        "sample_rate": 22050,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json",
    },
    "de_DE-thorsten_emotional-medium": {
        "lang": "de",
        "name": "Thorsten Emotional (Multi-Emotion)",
        "quality": "medium",
        "sample_rate": 22050,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten_emotional/medium/de_DE-thorsten_emotional-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten_emotional/medium/de_DE-thorsten_emotional-medium.onnx.json",
    },
    "de_DE-kerstin-low": {
        "lang": "de",
        "name": "Kerstin (Weiblich)",
        "quality": "low",
        "sample_rate": 16000,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/kerstin/low/de_DE-kerstin-low.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/kerstin/low/de_DE-kerstin-low.onnx.json",
    },
    # Griechisch
    "el_GR-joy-medium": {
        "lang": "el",
        "name": "Joy / Chara (Griechisch Weiblich, Sehr Natürlich)",
        "quality": "medium",
        "sample_rate": 22050,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/el/el_GR/joy/medium/el_GR-joy-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/el/el_GR/joy/medium/el_GR-joy-medium.onnx.json",
    },
    "el_GR-rapunzelina-medium": {
        "lang": "el",
        "name": "Rapunzelina (Griechisch Weiblich, Medium)",
        "quality": "medium",
        "sample_rate": 22050,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/el/el_GR/rapunzelina/medium/el_GR-rapunzelina-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/el/el_GR/rapunzelina/medium/el_GR-rapunzelina-medium.onnx.json",
    },
    "el_GR-rapunzelina-low": {
        "lang": "el",
        "name": "Rapunzelina (Griechisch Weiblich, Low)",
        "quality": "low",
        "sample_rate": 16000,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/el/el_GR/rapunzelina/low/el_GR-rapunzelina-low.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/el/el_GR/rapunzelina/low/el_GR-rapunzelina-low.onnx.json",
    },
    # Englisch
    "en_US-lessac-medium": {
        "lang": "en",
        "name": "Lessac (Englisch Weiblich, Medium)",
        "quality": "medium",
        "sample_rate": 22050,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
    },
    "en_US-amy-medium": {
        "lang": "en",
        "name": "Amy (Englisch Weiblich, Medium)",
        "quality": "medium",
        "sample_rate": 22050,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    },
}


def download_file(url: str, dest_path: str):
    """Lädt eine Datei mit Fortschrittsanzeige herunter."""
    import requests
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    temp_path = dest_path + ".tmp"
    logger.info(f"Download von {url}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    with open(temp_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\r  Fortschritt: {percent:.1f}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)", end="")
    print()
    if os.path.exists(dest_path):
        os.remove(dest_path)
    os.rename(temp_path, dest_path)
    logger.info(f"Gespeichert: {dest_path}")


def ensure_voice_downloaded(voice_key: str, models_dir: str = DEFAULT_MODELS_DIR) -> Tuple[str, str]:
    """
    Stellt sicher, dass das angegebene Modell im Verzeichnis models_dir existiert.
    Gibt (model_path, config_path) zurück.
    """
    # 1. Prüfe ob es ein lokaler Dateipfad ist
    if os.path.isfile(voice_key):
        onnx_path = voice_key
        json_path = voice_key + ".json" if not voice_key.endswith(".json") else voice_key
        return onnx_path, json_path

    # Prüfe ob im models_dir bereits vorhanden
    onnx_path = os.path.join(models_dir, f"{voice_key}.onnx")
    json_path = os.path.join(models_dir, f"{voice_key}.onnx.json")
    if os.path.exists(onnx_path) and os.path.exists(json_path):
        return onnx_path, json_path

    # 2. Im lokalen Katalog suchen
    if voice_key in VOICE_CATALOG:
        info = VOICE_CATALOG[voice_key]
        if not os.path.exists(onnx_path):
            logger.info(f"Modell '{voice_key}' nicht gefunden. Starte automatischen Download...")
            download_file(info["onnx_url"], onnx_path)
        if not os.path.exists(json_path):
            download_file(info["json_url"], json_path)
        return onnx_path, json_path

    # 3. Dynamische Suche in der offiziellen voices.json von Hugging Face
    try:
        import requests
        logger.info(f"Suche '{voice_key}' in der offiziellen Piper-Stimmendatenbank...")
        r = requests.get("https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json", timeout=10)
        if r.status_code == 200:
            voices_data = r.json()
            if voice_key in voices_data:
                files_info = voices_data[voice_key].get("files", {})
                onnx_rel = next((f for f in files_info if f.endswith(".onnx")), None)
                json_rel = next((f for f in files_info if f.endswith(".onnx.json")), None)
                if onnx_rel and json_rel:
                    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                    download_file(base_url + onnx_rel, onnx_path)
                    download_file(base_url + json_rel, json_path)
                    return onnx_path, json_path
    except Exception as e:
        logger.warning(f"Dynamische Suche fehlgeschlagen: {e}")

    raise ValueError(f"Unbekannte Stimme: '{voice_key}'. Verfügbar im Katalog: {list(VOICE_CATALOG.keys())}")


def list_local_voices(models_dir: str = DEFAULT_MODELS_DIR) -> List[Dict]:
    """Listet alle lokal im models_dir vorhandenen Stimmen auf."""
    voices = []
    if not os.path.isdir(models_dir):
        return voices

    for file in os.listdir(models_dir):
        if file.endswith(".onnx") and not file.endswith(".onnx.json"):
            name = file[:-5]
            onnx_path = os.path.join(models_dir, file)
            json_path = onnx_path + ".json"
            meta = {}
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    pass
            voices.append({
                "id": name,
                "onnx_path": onnx_path,
                "json_path": json_path,
                "language": meta.get("language", {}).get("code", "unbekannt") if isinstance(meta.get("language"), dict) else meta.get("language", "unbekannt"),
                "sample_rate": meta.get("audio", {}).get("sample_rate", 22050),
                "num_speakers": meta.get("num_speakers", 1),
            })
    return voices


def play_audio_interruptible(
    audio_np: np.ndarray,
    sample_rate: int,
    status_msg: str = ">> Wiedergabe läuft... [Beliebige Taste oder Strg+C zum Abbrechen]"
) -> bool:
    """
    Spielt Audiodaten ab und erlaubt sofortiges Abbrechen per Tastendruck oder Strg+C.
    Gibt True zurück wenn vollständig abgespielt, False bei Abbruch.
    """
    if len(audio_np) == 0:
        return True

    duration_sec = len(audio_np) / sample_rate
    print(f"\n{status_msg} ({duration_sec:.1f}s)", flush=True)

    try:
        import sounddevice as sd
        sd.stop()  # Vorherige Wiedergaben stoppen
        sd.play(audio_np, sample_rate)

        # Überwachungsschleife
        has_msvcrt = False
        if os.name == "nt":
            try:
                import msvcrt
                has_msvcrt = True
            except ImportError:
                has_msvcrt = False

        while True:
            # Prüfen ob Stream noch aktiv ist
            stream = sd.get_stream()
            if stream is None or not stream.active:
                break

            # Windows: Tastendruck abfangen (Enter, Leertaste, ESC, q etc.)
            if has_msvcrt and msvcrt.kbhit():
                msvcrt.getch()  # Taste aus Puffer lesen
                sd.stop()
                print("\n>> [STOP] Audio-Wiedergabe durch Tastendruck abgebrochen.")
                return False

            time.sleep(0.04)

        return True

    except KeyboardInterrupt:
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        print("\n>> [STOP] Audio-Wiedergabe durch Strg+C abgebrochen.")
        return False

    except Exception as e:
        logger.warning(f"sounddevice Fehler ({e}), wechsle zu Fallback...")
        import tempfile
        temp_wav = os.path.join(tempfile.gettempdir(), "piper_temp.wav")
        with wave.open(temp_wav, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_np.tobytes())

        if os.name == "nt":
            import winsound
            try:
                winsound.PlaySound(temp_wav, winsound.SND_FILENAME)
            except KeyboardInterrupt:
                winsound.PlaySound(None, winsound.SND_PURGE)
                return False
        else:
            import subprocess
            proc = subprocess.Popen(["aplay", temp_wav])
            try:
                proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
                return False
        return True


def clean_speech_text(text: str, remove_comma_pauses: bool = False) -> str:
    """
    Bereinigt Text vor der Sprachsynthese:
    - Entfernt störende Zeilenumbrüche und mehrfache Leerzeichen
    - Glättet doppelte Satzzeichen
    - Optional: Ersetzt Kommas durch Leerzeichen für unterbrechungsfreien Redefluss
    """
    if not text:
        return ""
    # Zeilenumbrüche und Tabs in Leerzeichen umwandeln
    cleaned = " ".join(text.split())
    # Doppelte Satzzeichen glätten
    cleaned = cleaned.replace("..", ".").replace("--", "-")
    if remove_comma_pauses:
        # Kommas und Semikolons entfernen, damit keine Atempause entsteht
        cleaned = cleaned.replace(",", " ").replace(";", " ").replace("·", " ")
        cleaned = " ".join(cleaned.split())
    return cleaned


def compress_audio_silence(
    audio_np: np.ndarray,
    sample_rate: int,
    threshold_db: float = -32.0,
    min_silence_ms: int = 60,
    target_silence_ms: int = 25,
    fade_ms: int = 4,
) -> np.ndarray:
    """
    Kürzt Stille-Phasen / Lücken zwischen Wörtern im Audiosignal präzise,
    OHNE die Sprechgeschwindigkeit der eigentlichen Wörter zu verändern.
    
    :param audio_np: 1D int16 Numpy Array mit Audiodaten
    :param sample_rate: Samplerate in Hz (z.B. 22050)
    :param threshold_db: Schwellenwert in dB relativ zum Spitzenpegel (unterhalb = Stille)
    :param min_silence_ms: Ab welcher Pausenlänge (in ms) gekürzt werden soll
    :param target_silence_ms: Auf welche Ziel-Pausenlänge (in ms) gestutzt werden soll
    :param fade_ms: Millisekunden für weiches Überblenden (verhindert Knackser)
    """
    if len(audio_np) == 0 or min_silence_ms <= target_silence_ms:
        return audio_np

    # 5ms Fenster für präzise Stille-Erkennung
    win_size = int(sample_rate * 0.005)
    if win_size == 0:
        return audio_np

    num_wins = len(audio_np) // win_size
    if num_wins == 0:
        return audio_np

    trimmed_len = num_wins * win_size
    reshaped = audio_np[:trimmed_len].reshape(num_wins, win_size).astype(np.float64)
    rms = np.sqrt(np.mean(reshaped ** 2, axis=1))

    max_rms = np.max(rms)
    if max_rms < 1e-6:
        return audio_np

    thresh_val = max_rms * (10 ** (threshold_db / 20.0))
    is_silent = rms < thresh_val

    min_sil_wins = max(1, int((min_silence_ms / 1000.0) * sample_rate / win_size))
    target_sil_wins = max(1, int((target_silence_ms / 1000.0) * sample_rate / win_size))
    fade_samples = max(1, int((fade_ms / 1000.0) * sample_rate))

    kept_chunks = []
    i = 0
    while i < num_wins:
        if not is_silent[i]:
            start_act = i
            while i < num_wins and not is_silent[i]:
                i += 1
            kept_chunks.append(audio_np[start_act * win_size : i * win_size])
        else:
            start_sil = i
            while i < num_wins and is_silent[i]:
                i += 1
            sil_wins = i - start_sil
            if sil_wins > min_sil_wins:
                # Stille auf target_silence_ms verkürzen
                keep_samples = target_sil_wins * win_size
                half = keep_samples // 2
                sil_chunk_start = audio_np[start_sil * win_size : start_sil * win_size + half]
                sil_chunk_end = audio_np[i * win_size - (keep_samples - half) : i * win_size]
                sil_merged = np.concatenate([sil_chunk_start, sil_chunk_end])
                
                # Sanftes Crossfade in der Mitte gegen Audio-Klicks
                if len(sil_merged) >= 2 * fade_samples:
                    fade_in = np.linspace(0.0, 1.0, fade_samples)
                    fade_out = np.linspace(1.0, 0.0, fade_samples)
                    mid = len(sil_merged) // 2
                    sil_merged[mid - fade_samples : mid] = (sil_merged[mid - fade_samples : mid] * fade_out).astype(np.int16)
                    sil_merged[mid : mid + fade_samples] = (sil_merged[mid : mid + fade_samples] * fade_in).astype(np.int16)
                
                kept_chunks.append(sil_merged)
            else:
                kept_chunks.append(audio_np[start_sil * win_size : i * win_size])

    if trimmed_len < len(audio_np):
        kept_chunks.append(audio_np[trimmed_len:])

    if not kept_chunks:
        return audio_np
    return np.concatenate(kept_chunks)


def trim_silence_edges(audio_np: np.ndarray, sample_rate: int, threshold_db: float = -32.0) -> np.ndarray:
    """Entfernt Stille am Anfang und Ende eines Audio-Abschnitts."""
    if len(audio_np) == 0:
        return audio_np
    win_size = int(sample_rate * 0.005)
    if win_size == 0:
        return audio_np
    num_wins = len(audio_np) // win_size
    if num_wins == 0:
        return audio_np
    trimmed_len = num_wins * win_size
    reshaped = audio_np[:trimmed_len].reshape(num_wins, win_size).astype(np.float64)
    rms = np.sqrt(np.mean(reshaped ** 2, axis=1))
    max_rms = np.max(rms)
    if max_rms < 1e-6:
        return audio_np
    thresh_val = max_rms * (10 ** (threshold_db / 20.0))
    is_silent = rms < thresh_val
    non_sil = np.where(~is_silent)[0]
    if len(non_sil) == 0:
        return audio_np
    start_idx = non_sil[0] * win_size
    end_idx = min(len(audio_np), (non_sil[-1] + 1) * win_size)
    return audio_np[start_idx:end_idx]


class PiperEngine:
    """
    Hauptklasse zur Audio-Synthese mit Piper-Modellen.
    """

    def __init__(
        self,
        model_path_or_key: str = "de_DE-thorsten-medium",
        models_dir: str = DEFAULT_MODELS_DIR,
        use_cuda: bool = False,
    ):
        """
        Lädt ein Piper-Modell (entweder aus dem Katalog oder von einem lokalen Pfad).
        """
        try:
            from piper import PiperVoice
        except ImportError:
            raise ImportError(
                "Das Paket 'piper-tts' ist nicht installiert. Installiere es mit:\n"
                "pip install -r requirements_piper.txt"
            )

        self.models_dir = models_dir
        self.use_cuda = use_cuda

        # Pfad auflösen oder herunterladen
        if os.path.isfile(model_path_or_key):
            self.model_path = model_path_or_key
            self.config_path = model_path_or_key + ".json" if not model_path_or_key.endswith(".json") else model_path_or_key
        else:
            self.model_path, self.config_path = ensure_voice_downloaded(model_path_or_key, self.models_dir)

        logger.info(f"Lade Piper-Stimme: {self.model_path} (CUDA: {use_cuda})...")
        self.voice = PiperVoice.load(self.model_path, config_path=self.config_path, use_cuda=use_cuda)
        self.sample_rate = self.voice.config.sample_rate
        logger.info(f"Stimme geladen! Sample-Rate: {self.sample_rate} Hz, Sprecher: {self.voice.config.num_speakers}")

    def synthesize(
        self,
        text: str,
        length_scale: float = 1.0,
        noise_scale: float = 0.667,
        noise_w_scale: float = 0.2,
        volume: float = 1.0,
        speaker_id: Optional[int] = None,
        apply_filter: bool = False,
        compress_pauses: bool = False,
        min_pause_ms: int = 60,
        target_pause_ms: int = 25,
        keep_sentence_pauses: bool = True,
        sentence_pause_ms: int = 250,
        clean_text: bool = True,
        remove_comma_pauses: bool = False,
    ) -> Tuple[np.ndarray, int]:
        """
        Synthetisiert den Text und gibt ein numpy int16-Audio-Array und die Samplerate zurück.
        
        :param noise_w_scale: Dauer-Varianz (0.1 - 0.3 erzeugt kompakte Wortabstände, 0.8 ist Standard)
        :param compress_pauses: Wenn True, werden Stillepausen zwischen Wörtern automatisch gestutzt
        :param min_pause_ms: Mindestdauer einer Wortpause in ms, ab der gekürzt wird
        :param target_pause_ms: Zieldauer der gekürzten Wortpausen in ms
        :param keep_sentence_pauses: True = natürliche Pause am Satzende behalten; False = auch Satzende-Pausen stutzen
        :param sentence_pause_ms: Dauer der Satzende-Pause in ms (falls keep_sentence_pauses=True)
        :param clean_text: Bereinigt Zeilenumbrüche vorab für flüssigen Satzbau
        :param remove_comma_pauses: Entfernt Kommapausen für unterbrechungsfreien Fluss
        """
        if not text or not text.strip():
            return np.zeros(0, dtype=np.int16), self.sample_rate

        if clean_text:
            text = clean_speech_text(text, remove_comma_pauses=remove_comma_pauses)

        try:
            from piper import SynthesisConfig
            syn_config = SynthesisConfig(
                length_scale=length_scale,
                noise_scale=noise_scale,
                noise_w_scale=noise_w_scale,
                volume=volume,
                speaker_id=speaker_id,
            )
        except Exception:
            syn_config = None

        # Piper synthetisiert satzweise (ein Chunk pro Satz)
        sentence_chunks = list(self.voice.synthesize(text, syn_config=syn_config))
        processed_chunks = []

        for i, chunk in enumerate(sentence_chunks):
            chunk_np = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16)
            if compress_pauses and len(chunk_np) > 0:
                chunk_np = compress_audio_silence(
                    chunk_np,
                    self.sample_rate,
                    min_silence_ms=min_pause_ms,
                    target_silence_ms=target_pause_ms,
                )
                chunk_np = trim_silence_edges(chunk_np, self.sample_rate)
            elif not keep_sentence_pauses and len(chunk_np) > 0:
                chunk_np = trim_silence_edges(chunk_np, self.sample_rate)

            processed_chunks.append(chunk_np)

            # Pause am Satzende einfügen (zwischen den Sätzen)
            if i < len(sentence_chunks) - 1:
                if keep_sentence_pauses:
                    pause_ms = sentence_pause_ms
                else:
                    pause_ms = target_pause_ms if compress_pauses else 30

                silence_samples = int((pause_ms / 1000.0) * self.sample_rate)
                if silence_samples > 0:
                    processed_chunks.append(np.zeros(silence_samples, dtype=np.int16))

        if not processed_chunks:
            audio_np = np.zeros(0, dtype=np.int16)
        else:
            audio_np = np.concatenate(processed_chunks)

        # Audio-Filter anwenden (optional)
        if apply_filter and len(audio_np) > 0:
            audio_np = self.filter_audio(audio_np, self.sample_rate)

        return audio_np, self.sample_rate

    @staticmethod
    def filter_audio(
        audio_np: np.ndarray,
        sample_rate: int,
        highpass_freq: float = 160.0,
        lowpass_freq: float = 4200.0,
        notch_low: float = 2700.0,
        notch_high: float = 3600.0,
        target_peak: float = 24000.0,
    ) -> np.ndarray:
        """
        Intelligenter Audio-Filter gegen metallischen Klang & Lautsprecher-Scheppern:
        - Entfernt Übersteuern / Scheppern durch Pegel-Headroom (24000 statt 32767 max)
        - Dämpft metallische Resonanzfrequenzen (z.B. bei Rapunzelina um 2.7 - 3.6 kHz)
        - Schneidet Membran-Rumpeln (< 160 Hz) und scharfes Zischeln (> 4.2 kHz) ab
        - Wendet sanfte Tanh-Sättigung an, um harte Spitzen abzurunden (wärmerer Klang)
        """
        if len(audio_np) == 0:
            return audio_np

        try:
            from scipy.signal import butter, sosfilt
            data = audio_np.astype(np.float32)

            # 1. Hochpass gegen Membran-Scheppern / Flattern
            sos_hp = butter(2, highpass_freq, btype='highpass', fs=sample_rate, output='sos')
            data = sosfilt(sos_hp, data)

            # 2. Tiefpass gegen Zischen & hochfrequentes Scheppern
            nyquist = sample_rate / 2.0
            lp_freq = min(lowpass_freq, nyquist - 200.0)
            if lp_freq > highpass_freq:
                sos_lp = butter(3, lp_freq, btype='lowpass', fs=sample_rate, output='sos')
                data = sosfilt(sos_lp, data)

            # 3. Notch-Filter gegen metallischen Dosenklang (2.7 - 3.6 kHz)
            if notch_high < nyquist:
                sos_notch = butter(2, [notch_low, notch_high], btype='bandstop', fs=sample_rate, output='sos')
                notch_filtered = sosfilt(sos_notch, data)
                data = 0.35 * data + 0.65 * notch_filtered

            # 4. Soft-Saturation (Tanh) zur Vermeidung harter Transienten & Scheppern
            max_val = np.max(np.abs(data))
            if max_val > 0:
                norm = data / max_val
                # Sanftes Ausrunden der Wellenspitzen
                saturated = np.tanh(norm * 1.15) / np.tanh(1.15)
                data = saturated * target_peak

            return data.astype(np.int16)
        except Exception as e:
            logger.warning(f"Filter konnte nicht angewendet werden: {e}")
            return audio_np

    def save_wav(
        self,
        text: str,
        output_path: str,
        length_scale: float = 1.0,
        apply_filter: bool = False,
        **kwargs
    ) -> str:
        """Synthetisiert Text und speichert das Ergebnis direkt in einer WAV-Datei."""
        audio_np, sr = self.synthesize(text, length_scale=length_scale, apply_filter=apply_filter, **kwargs)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with wave.open(output_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sr)
            wav_file.writeframes(audio_np.tobytes())
        logger.info(f"WAV-Datei gespeichert: {output_path}")
        return output_path

    def speak(
        self,
        text: str,
        length_scale: float = 1.0,
        apply_filter: bool = False,
        **kwargs
    ) -> bool:
        """
        Synthetisiert Text und gibt ihn sofort über Lautsprecher aus.
        Kann jederzeit mit beliebiger Taste oder Strg+C abgebrochen werden.
        Gibt True zurück bei vollständiger Wiedergabe, False bei Abbruch.
        """
        audio_np, sr = self.synthesize(text, length_scale=length_scale, apply_filter=apply_filter, **kwargs)
        if len(audio_np) == 0:
            return True

        return play_audio_interruptible(audio_np, sr)


class SmartPiper:
    """
    Intelligenter Piper-Manager:
    Erkennt automatisch die Sprache (Deutsch, Griechisch, Englisch)
    und wechselt zur passenden Stimme.
    """

    def __init__(
        self,
        voice_de: str = "de_DE-thorsten-medium",
        voice_el: str = "el_GR-joy-medium",
        voice_en: str = "en_US-lessac-medium",
        models_dir: str = DEFAULT_MODELS_DIR,
    ):
        self.models_dir = models_dir
        self.voice_names = {
            "de": voice_de,
            "el": voice_el,
            "en": voice_en,
        }
        self.loaded_engines: Dict[str, PiperEngine] = {}

    def _get_engine_for_lang(self, lang: str) -> PiperEngine:
        if lang not in self.voice_names:
            lang = "de"  # Fallback Deutsch

        if lang not in self.loaded_engines:
            voice_key = self.voice_names[lang]
            logger.info(f"Lade Stimme für Sprache '{lang}': {voice_key}")
            self.loaded_engines[lang] = PiperEngine(voice_key, models_dir=self.models_dir)

        return self.loaded_engines[lang]

    @staticmethod
    def detect_language(text: str) -> str:
        """
        Ermittelt Sprache des Textes. Erkennt Griechisch anhand von Unicode-Zeichen
        oder nutzt langdetect.
        """
        # Schnelle Griechisch-Prüfung über Zeichensatz
        greek_chars = sum(1 for c in text if '\u0370' <= c <= '\u03FF' or '\u1F00' <= c <= '\u1FFF')
        if greek_chars > len(text) * 0.15:
            return "el"

        try:
            from langdetect import detect
            lang = detect(text)
            if lang in ["de", "el", "en"]:
                return lang
            return "de"
        except Exception:
            return "de"

    def speak(self, text: str, **kwargs) -> bool:
        """
        Erkennt die Sprache und liest den Text mit der passenden Stimme vor.
        Kann jederzeit mit beliebiger Taste oder Strg+C abgebrochen werden.
        """
        lang = self.detect_language(text)
        logger.info(f"Erkannte Sprache: '{lang}'")
        engine = self._get_engine_for_lang(lang)

        # Griechisch oft minimal langsamer für bessere Verständlichkeit
        if lang == "el" and "length_scale" not in kwargs:
            kwargs["length_scale"] = 1.1

        return engine.speak(text, **kwargs)

    def save_wav(self, text: str, output_path: str, **kwargs) -> str:
        """Erkennt die Sprache und speichert das Audio in WAV."""
        lang = self.detect_language(text)
        engine = self._get_engine_for_lang(lang)
        if lang == "el" and "length_scale" not in kwargs:
            kwargs["length_scale"] = 1.1
        return engine.save_wav(text, output_path, **kwargs)
