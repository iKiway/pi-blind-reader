from openai import OpenAI
import os
import subprocess

# Ihr API Key
with open("api_key_open_ai.txt", "r") as f:
    openai_api_key = f.read().strip()
client = OpenAI(api_key=openai_api_key)

def speak_text(text):
    """
    Liest Text vor (Deutsch, Griechisch oder gemischt).
    Nutzt das günstigere 'tts-1' Modell (nicht tts-1-hd).
    """
    print(f"Generiere Audio für: {text[:30]}...")
    
    try:
        response = client.audio.speech.create(
            model="tts-1",    # Der Preis-Leistungs-Sieger ($15/1M chars)
            voice="onyx",    # 'alloy' und 'onyx' klingen sehr neutral und gut
            input=text
        )

        # Audio direkt an den Lautsprecher pipen (kein Speichern nötig)
        # Wir streamen die Daten in den 'mpg321' oder 'mpv' Player
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

# --- TEST ---

# Ein deutscher Text
german_text = "Die Rechnung über 50 Euro ist am Montag fällig."

# Ein griechischer Text (Hallo, wie geht es dir?)
greek_text = "Γεια σου, ti kanis? Ελπίζω να είσαι καλά."

# Ein gemischter Text
mixed_text = "Der Brief kommt aus Athen. Darin steht: Efharisto poli für die Einladung."

print("--- Deutsch ---")
speak_text(german_text)

print("--- Griechisch ---")
speak_text(greek_text)

print("--- Gemischt ---")
speak_text(mixed_text)