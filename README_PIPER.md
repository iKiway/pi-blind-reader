# Piper TTS Test- und Entwicklungsumgebung

Eine vollständige, extrem schnelle und lokale Text-to-Speech Testumgebung für **Piper TTS** (.onnx) Modelle auf dem PC (Windows, Linux, macOS).

---

## 1. Installation

Installiere die benötigten Pakete mit pip:

```powershell
pip install -r requirements_piper.txt
```

*(Hinweis: Piper TTS benötigt keine GPU und läuft extrem ressourcensparend direkt auf der CPU).*

---

## 2. Interaktives Test-Tool ausführen

Starte das interaktive CLI-Menü:

```powershell
python pc_test.py
```

### Neue Features im CLI-Menü:
- **`[G]` Griechische Stimme schnell wechseln:**
  - `el_GR-joy-medium` (Joy / Chara - Natürlichste Stimme, 22kHz)
  - `el_GR-rapunzelina-medium` (Rapunzelina Medium, 22kHz)
  - `el_GR-rapunzelina-low` (Rapunzelina Low, 16kHz)
- **`[V]` Stimmen-Direktvergleich:**
  - Spielt denselben Text nacheinander mit **Joy** und **Rapunzelina** vor, um Unterschiede direkt herauszuhören.
- **`[1]` Beispielsätze & lange Texte:**
  - Enthält kurze Begrüßungen, mittellange Texte sowie den **vollständigen langen Roman-Ausschnitt** ("Κάθομαι σε αναμμένα κάρβουνα...").
- **`[2]` Freie Texteingabe / Textdatei (.txt):**
  - Eigene Texte im Terminal eingeben oder eine `.txt`-Datei zum Vorlesen laden.
- **`[5]` Feinjustierung:**
  - Tempo/Geschwindigkeit (`length_scale`), Lautstärke und optionaler Lautsprecher-Filter (Highpass/Lowpass gegen Kratzen an kleinen Lautsprechern).

---

## 3. Verwendung im eigenen Code

```python
from piper_engine import PiperEngine, SmartPiper

# 1. Griechische Joy-Stimme direkt laden
engine = PiperEngine("el_GR-joy-medium")
engine.speak("Καλώς ήρθατε στο σύστημα ανάγνωσης.")

# 2. Smart-Modus (Automatische Spracherkennung DE/EL/EN)
smart = SmartPiper(
    voice_de="de_DE-thorsten-medium",
    voice_el="el_GR-joy-medium",
    voice_en="en_US-lessac-medium"
)

smart.speak("Guten Tag! Wie kann ich helfen?")
smart.speak("Καλημέρα! Πώς μπορώ να σας βοηθήσω;")
```
