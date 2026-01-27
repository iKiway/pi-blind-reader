# pi-blind-reader
## 📦 Required Libraries

### Python Packages
- `picamera2`
- `numpy`
- `flask`
- `gpiozero`
- `pytesseract`
- `Pillow`
- `opencv-python`
- `google-cloud-vision` (optional)

### System Dependencies

**1. Tesseract OCR** (Required for OCR offline fallback)
```bash
sudo apt-get install tesseract-ocr
```
*For Greek support:*
```bash
sudo apt-get install tesseract-ocr-ell
```

**2. Audio Player** (Required for playback)
```bash
sudo apt update
sudo apt install mpg321 -y
```


# ⚙️ Installation & Setup

Führe folgende Schritte aus, um das System vollständig einzurichten.

## 🗣️ Text-to-Speech Installation (Piper)

Wir nutzen **Piper TTS**, eine schnelle und lokale Text-zu-Sprache Engine für den Raspberry Pi.

Führe folgende Schritte aus, um Piper sowie die deutsche und griechische Stimme zu installieren:

### 1. Piper herunterladen & installieren

```bash
# Ordner erstellen
mkdir -p ~/piper_tts
cd ~/piper_tts

# Piper für Raspberry Pi (64-bit) herunterladen
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_linux_aarch64.tar.gz

# Entpacken
tar -xvf piper_linux_aarch64.tar.gz
```

### 2. Stimmen herunterladen

### 🇩🇪 Deutsch (Thorsten)
```bash
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json
```

### 🇬🇷 Griechisch (Rapunzelina)
```bash
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/el/el_GR/rapunzelina/medium/el_GR-rapunzelina-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/el/el_GR/rapunzelina/medium/el_GR-rapunzelina-medium.onnx.json
```

### 3. Testen

Stelle sicher, dass du im Ordner `~/piper_tts` bist.

**Deutsch testen:**
```bash
echo "Hallo, das ist ein Test." | ./piper/piper --model de_DE-thorsten-medium.onnx --output_raw | aplay -r 22050 -f S16_LE -t raw -
```

**Griechisch testen:**
```bash
echo "Γεια σου, τι κάνεις;" | ./piper/piper --model el_GR-rapunzelina-medium.onnx --output_raw | aplay -r 22050 -f S16_LE -t raw -
```


## 🔊 Audio Setup (MAX98357A & Raspberry Pi)

Diese Anleitung beschreibt die Installation eines **MAX98357A I2S Mono-Verstärkers** an einem Raspberry Pi (getestet mit RPi 4).

### 1. Hardware-Verkabelung

Der Verstärker wird über den I2S-Bus (Digital Audio) angeschlossen.
**Wichtig:** Die Stiftleiste am Verstärker-Board muss verlötet sein, einfaches Einstecken reicht nicht für eine stabile Datenverbindung!

| MAX98357A Pin | Raspberry Pi Pin (Physisch) | GPIO | Funktion |
| --- | --- | --- | --- |
| **Vin** | Pin 4 | - | 5V Stromversorgung |
| **GND** | Pin 6 | - | Ground (Masse) |
| **DIN** | Pin 40 | GPIO 21 | Data In |
| **BCLK** | Pin 12 | GPIO 18 | Bit Clock |
| **LRC** | Pin 35 | GPIO 19 | LR Clock (Word Select) |

> **Hinweis:** Die Pins *SD* und *GAIN* am Verstärker bleiben leer (nicht verbunden).

### 2. Software-Konfiguration

#### A. Treiber aktivieren & Onboard-Sound deaktivieren

Öffne die Konfigurationsdatei:

```bash
sudo nano /boot/firmware/config.txt
# Bei älteren Raspbian-Versionen:
# sudo nano /boot/config.txt

```

1. Deaktiviere den Standard-Audioausgang, indem du ein `#` vor die Zeile setzt:
```text
#dtparam=audio=on

```


2. Füge am Ende der Datei den Treiber hinzu:
```text
dtoverlay=hifiberry-dac

```


*(Alternativ funktioniert oft auch `dtoverlay=max98357a`)*.

Speichern (`STRG+O`, `Enter`) und Beenden (`STRG+X`).
Führe danach einen Neustart durch:

```bash
sudo reboot

```

#### B. Soundkarte prüfen

Nach dem Neustart prüfen, ob die Karte erkannt wurde und welche Nummer sie hat:

```bash
aplay -l

```

Suche nach dem Eintrag `snd_rpi_hifiberry_dac`.

* Beim Raspberry Pi Zero/3 ist es oft **Card 0**.
* Beim Raspberry Pi 4 ist es oft **Card 2** (da HDMI Audio 0 und 1 belegt).

#### C. Software-Lautstärkeregler einrichten (/etc/asound.conf)

Da der Verstärker keinen Hardware-Mixer hat, muss ein virtueller Regler ("Softvol") erstellt werden.

Öffne die ALSA-Konfiguration:

```bash
sudo nano /etc/asound.conf

```

Füge folgenden Inhalt ein (**Ersetze `card 2` durch deine Kartennummer aus Schritt B!**):

```text
pcm.!default {
    type plug
    slave.pcm "softvol"
}

pcm.softvol {
    type softvol
    slave {
        pcm "plughw:2"       # <--- Hier Kartennummer anpassen (z.B. plughw:0 oder plughw:2)
    }
    control {
        name "Master"
        card 2               # <--- Hier Kartennummer anpassen
    }
}

ctl.!default {
    type hw
    card 2                   # <--- Hier Kartennummer anpassen
}

```

Speichern und schließen.

### 3. Lautstärke einstellen & Testen

#### Regler initialisieren

Der Lautstärkeregler erscheint erst, nachdem einmal Audio abgespielt wurde. Führe diesen Test kurz aus:

```bash
speaker-test -c2 -t wav -l 1

```

#### Lautstärke anpassen

Nun kannst du die Lautstärke regeln:

```bash
alsamixer

```

* Wähle mit `F6` die Soundkarte aus (sndrpihifiberry).
* Stelle den **Master**-Regler auf ca. **85-90%**.
* *Tipp:* 100% führt bei diesem 3W-Verstärker oft zu Verzerrungen (Clipping).
* Sollte unten "MM" stehen, drücke `M` um die Stummschaltung aufzuheben.



#### MP3 / Stream testen

Für einen echten Musik-Test installiere `mpg123`:

```bash
sudo apt-get install mpg123

```

Internetradio abspielen:

```bash
mpg123 http://wdr-1live-live.icecast.wdr.de/wdr/1live/live/mp3/128/stream.mp3

```

### 4. Troubleshooting

* **Nur Knacken/Rattern zu hören?**
* Prüfe die Verkabelung, insbesondere **Pin 40 (DIN)** und **Pin 12 (BCLK)**. Ein Wackelkontakt hier klingt wie ein Maschinengewehr.
* Stelle sicher, dass die Pins am Verstärker gelötet sind.


* **Sound klingt blechern/leise?**
* Der Lautsprecher benötigt zwingend ein **Gehäuse** (Resonanzkörper), um voll zu klingen. Ohne Gehäuse löschen sich die Bässe gegenseitig aus (akustischer Kurzschluss).


* **Verzerrter Sound (Kratzen)?**
* Lautstärke im `alsamixer` reduzieren (max 90%).
* Prüfen, ob die Stromversorgung des Pi stabil ist (offizielles Netzteil empfohlen).

## 🔑 API Setup

Dieses Projekt nutzt externe APIs für die Texterkennung und -verbesserung. Hier erfährst du, wie du die nötigen Schlüssel erhältst und einrichtest.

### 1. Google Cloud Vision API (für OCR)

Wir nutzen die Google Cloud Vision API für präzise Texterkennung.

1.  Gehe zur [Google Cloud Console](https://console.cloud.google.com/).
2.  Erstelle ein neues Projekt.
3.  Suche nach **"Cloud Vision API"** und aktiviere sie für dein Projekt.
4.  Gehe zu **IAM & Verwaltung** -> **Dienstkonten**.
5.  Erstelle ein neues Dienstkonto und gib ihm die Rolle **"Besitzer"** (oder spezifischer "Cloud Vision API Nutzer").
6.  Klicke auf das erstellte Dienstkonto -> **Schlüssel** -> **Schlüssel hinzufügen** -> **Neuen Schlüssel erstellen** -> **JSON**.
7.  Eine JSON-Datei wird automatisch heruntergeladen.
8.  Benenne diese Datei um in `google_cloud_credentials.json`.
9.  Kopiere sie in das Hauptverzeichnis dieses Projekts (z. B. `/home/kimon/pi-blind-reader/`).

### 2. OpenAI API (für Textkorrektur)

OpenAI wird genutzt, um fehlerhaften OCR-Text zu korrigieren und logisch zusammenzusetzen.

1.  Registriere dich bei [OpenAI Platform](https://platform.openai.com/).
2.  Gehe zu **API Keys** und erstelle einen neuen Schlüssel (`Create new secret key`).
3.  Kopiere den Schlüssel (er beginnt meist mit `sk-...`).
4.  Erstelle im Projektordner eine Textdatei namens `api_key_open_ai.txt`.
5.  Füge den Schlüssel in diese Datei ein (ohne Leerzeichen oder Anführungszeichen).

```bash
# Beispiel:
echo "sk-DEIN_KEY_HIER" > ~/pi-blind-reader/api_key_open_ai.txt
```

