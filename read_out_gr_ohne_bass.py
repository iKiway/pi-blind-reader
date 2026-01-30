import subprocess
from langdetect import detect

# Pfade zu den Modellen
PATH_PIPER = "/home/kimon/piper_tts/piper/piper"
MODEL_DE = "/home/kimon/piper_tts/de_DE-thorsten-medium.onnx"
MODEL_GR = "/home/kimon/piper_tts/el_GR-rapunzelina-medium.onnx"

def speak_offline_smart(text):
    """
    Erkennt die Sprache, wählt das Modell und spielt es mit Filtern ab (gegen Kratzen).
    """
    if not text or not text.strip():
        return

    try:
        # 1. Sprache erkennen
        try:
            language = detect(text)
        except:
            language = "de" # Fallback falls Erkennung scheitert
            
        print(f"Erkannte Sprache: {language}")

        # 2. Einstellungen wählen
        if language == 'el':
            model = MODEL_GR
            length_scale = "1.1"   # Etwas langsamer für Griechisch
            sample_rate = "22050"  # Rapunzelina Medium ist meist 22050Hz (bitte prüfen!)
            print(">> Modus: Griechisch (Rapunzelina)")
        else:
            model = MODEL_DE
            length_scale = "1.0"
            sample_rate = "22050"  # Thorsten Medium ist 22050Hz
            print(">> Modus: Deutsch (Thorsten)")

        # 3. Piper Prozess starten (Erzeugt das Audio)
        # Wir nutzen Popen statt os.system, das ist sicherer bei Sonderzeichen
        piper_process = subprocess.Popen(
            [PATH_PIPER, '--model', model, '--length-scale', length_scale, '--output-raw'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL # Unterdrückt Piper-Log-Müll
        )

        # 4. SoX Prozess starten (Filtert und spielt ab)
        # Das hier ist der "Gamechanger" für deinen Lautsprecher!
        sox_command = [
            'play',
            '-t', 'raw', 
            '-r', sample_rate, 
            '-e', 'signed-integer', 
            '-b', '16', 
            '-c', '1', 
            '-',                # Input kommt von Piper
            'vol', '0.5',       # <--- WICHTIG: Lautstärke halbieren, damit nix übersteuert!
            'highpass', '200',  # <--- WICHTIG: Bass raus (schützt den Lautsprecher)
            'lowpass', '3000',  # <--- WICHTIG: Scharfe S-Laute weichzeichnen
            'contrast', '10'    # Macht Sprache bei niedriger Lautstärke verständlicher
        ]

        sox_process = subprocess.Popen(
            sox_command,
            stdin=piper_process.stdout
        )

        # 5. Text an Piper senden
        piper_process.stdin.write(text.encode('utf-8'))
        piper_process.stdin.close() # Signalisiert Piper: "Text ist zu Ende"

        # Warten bis Audio fertig gespielt ist
        sox_process.wait()

    except Exception as e:
        print(f"Fehler bei der Sprachausgabe: {e}")

# --- TEST ---
if __name__ == "__main__":
    print("\n--- Test Deutsch ---")
    speak_offline_smart("Hallo Kimon, das Kratzen sollte jetzt weg sein.")
    
    print("\n--- Test Griechisch ---")
    # Dein langer griechischer Text
    text_gr = """Κάθομαι σε αναμμένα κάρβουνα. Στις έξι και μισή πρέπει να ήμαστε στην εκκλησία. Είναι ήδη έξι και τέταρτο, και η Αδριανή με την Κατερίνα βρίσκονται ακόμα κλεισμένες στην κρεβατοκάμαρα, για «κάτι τελειώματα» της τελευταίας στιγμής στο νυφικό. Τώρα, τι μερεμέτια μπορείς να κάνεις την τελευταία στιγμή σε ένα νυφικό που το έχεις χρυσοπληρώσει, άντε να το καταλάβω. «Ο Φάνης θα βαρεθεί και θα φύγει» ορύομαι από το καθιστικό. Φωνή βοώντος εν τη ερήμω. Ξαναρχίζω τις βόλτες με την επίσημη στολή μου. Μόνο που, αντί να παρελαύνω στο Σύνταγμα, βηματίζω άσκοπα στο καθιστικό, εν αναμονή της γαμήλιας τελετής, και προσπαθώ να σκοτώσω την ώρα μου και τον εκνευρισμό μου. Και σαν να μην έφτανε αυτό, η στολή μου κάθεται σαν κορσές γιατί τη φοράω σπάνια. Είμαι βέβαιος ότι όλη αυτή η καθυστέρηση γίνεται σκόπιμα, για να τηρηθεί η παράδοση που θέλει τη νύφη να αφήνει τον γαμπρό να περιμένει στην πόρτα της εκκλησίας. Και επειδή η Κατερίνα έχει μεσάνυχτα από κάτι τέτοια, η Αδριανή την έχει βάλει εν αγνοία της στο παιχνίδι. Το λέω εκ πείρας."""
    
    speak_offline_smart(text_gr)