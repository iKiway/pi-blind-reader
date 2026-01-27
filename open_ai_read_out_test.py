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
greek_text = "Κάθομαι σε αναμμένα κάρβουνα. Στις έξι και μισή πρέπει να ήμαστε στην εκκλησία. Είναι ήδη έξι και τέταρτο, και η Αδριανή με την Κατερίνα βρίσκονται ακόμα κλεισμένες στην κρεβατοκάμαρα, για «κάτι τελειώματα» της τελευταίας στιγμής στο νυφικό. Τώρα, τι μερεμέτια μπορείς να κάνεις την τελευταία στιγμή σε ένα νυφικό που το έχεις χρυσοπληρώσει, άντε να το καταλάβω. «Ο Φάνης θα βαρεθεί και θα φύγει» ορύομαι από το καθιστικό. Φωνή βοώντος εν τη ερήμω. Ξαναρχίζω τις βόλτες με την επίσημη στολή μου. Μόνο που, αντί να παρελαύνω στο Σύνταγμα, βηματίζω άσκοπα στο καθιστικό, εν αναμονή της γαμήλιας τελετής, και προσπαθώ να σκοτώσω την ώρα μου και τον εκνευρισμό μου. Και σαν να μην έφτανε αυτό, η στολή μου κάθεται σαν κορσές γιατί τη φοράω σπάνια. Είμαι βέβαιος ότι όλη αυτή η καθυστέρηση γίνεται σκόπιμα, για να τηρηθεί η παράδοση που θέλει τη νύφη να αφήνει τον γαμπρό να περιμένει στην πόρτα της εκκλησίας. Και επειδή η Κατερίνα έχει μεσάνυχτα από κάτι τέτοια, η Αδριανή την έχει βάλει εν αγνοία της στο παιχνίδι. Το λέω εκ πείρας."

# Ein gemischter Text
mixed_text = "Der Brief kommt aus Athen. Darin steht: Efharisto poli für die Einladung."

print("--- Deutsch ---")
# speak_text(german_text)

print("--- Griechisch ---")
speak_text(greek_text)

print("--- Gemischt ---")
# speak_text(mixed_text)