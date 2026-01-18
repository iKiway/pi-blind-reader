import subprocess
from langdetect import detect

# Pfade zu den Modellen (Bitte anpassen, falls nötig)
PATH_PIPER = "/home/kimon/piper_tts/piper/piper"
MODEL_DE = "/home/kimon/piper_tts/de_DE-thorsten-medium.onnx"
MODEL_GR = "/home/kimon/piper_tts/el_GR-rapunzelina-medium.onnx"

def speak_offline_smart(text):
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

# --- TEST ---
if __name__ == "__main__":
    print("Test Deutsch:")
    speak_offline_smart("Hallo, hier ist dein Brief.")
    
    print("\nTest Griechisch:")
    text = """Αγαπητέ χρήστη,

Αυτό είναι ένα δοκιμαστικό μήνυμα για να ελέγξουμε την ποιότητα της φωνής στο σύστημα Raspberry Pi. Αν ακούτε αυτό το κείμενο καθαρά, σημαίνει ότι η εγκατάσταση του Piper TTS ολοκληρώθηκε με επιτυχία.

Είναι σημαντικό να ελέγξουμε πώς διαβάζονται οι αριθμοί και οι ημερομηνίες. Για παράδειγμα: Σήμερα είναι 17 Ιανουαρίου 2026. Το ποσό πληρωμής είναι 50,50 ευρώ. 

Το σύστημα αυτό σχεδιάστηκε για να βοηθάει στην ανάγνωση εγγράφων και βιβλίων. Ελπίζουμε να είναι ένα χρήσιμο εργαλείο για την καθημερινότητά σας.

Με εκτίμηση,
Η ομάδα υποστήριξης."""
    speak_offline_smart(text)