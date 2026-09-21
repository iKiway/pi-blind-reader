"""
Piper TTS - Interaktives Testskript für den PC
-----------------------------------------------
Ermöglicht das einfache Testen, Anhören und Vergleichen verschiedener
Piper TTS-Stimmen (Deutsch, Griechisch, Englisch) direkt auf dem PC.
"""

import os
import sys

from piper_engine import (
    PiperEngine,
    SmartPiper,
    VOICE_CATALOG,
    list_local_voices,
    DEFAULT_MODELS_DIR,
)

# Liste der verfügbaren griechischen Stimmen für schnelles Umschalten
GREEK_VOICES = [
    ("el_GR-joy-medium", "Joy / Chara (Medium, 22kHz - Natürlichste Stimme, Empfohlen)"),
    ("el_GR-rapunzelina-medium", "Rapunzelina (Medium, 22kHz)"),
    ("el_GR-rapunzelina-low", "Rapunzelina (Low, 16kHz)"),
]

# Vordefinierte Testtexte (Kurz, Mittel, Lang)
PRESET_TEXTS = {
    "el": [
        (
            "Griechisch (Kurz - Begrüßung)",
            "Καλώς ήρθατε στο σύστημα ανάγνωσης κειμένου για άτομα με προβλήματα όρασης."
        ),
        (
            "Griechisch (Mittel - Alltag & Technologie)",
            "Η τεχνητή νοημοσύνη και η σύνθεση ομιλίας βοηθούν καθημερινά χιλιάδες ανθρώπους να διαβάζουν βιβλία, επιστολές και έντυπα έγγραφα με φυσικό και κατανοητό τρόπο."
        ),
        (
            "Griechisch (Lang - Original Roman-Ausschnitt)",
            "Κάθομαι σε αναμμένα κάρβουνα. Στις έξι και μισή πρέπει να ήμαστε στην εκκλησία. "
            "Είναι ήδη έξι και τέταρτο, και η Αδριανή με την Κατερίνα βρίσκονται ακόμα κλεισμένες στην κρεβατοκάμαρα, "
            "για «κάτι τελειώματα» της τελευταίας στιγμής στο νυφικό. Τώρα, τι μερεμέτια μπορείς να κάνεις την τελευταία στιγμή "
            "σε ένα νυφικό που το έχεις χρυσοπληρώσει, άντε να το καταλάβω. «Ο Φάνης θα βαρεθεί και θα φύγει» ορύομαι από το καθιστικό. "
            "Φωνή βοώντος εν τη ερήμω. Ξαναρχίζω τις βόλτες με την επίσημη στολή μου. Μόνο που, αντί να παρελαύνω στο Σύνταγμα, "
            "βηματίζω άσκοπα στο καθιστικό, εν αναμονή της γαμήλιας τελετής, και προσπαθώ να σκοτώσω την ώρα μου και τον εκνευρισμό μου. "
            "Και σαν να μην έφτανε αυτό, η στολή μου κάθεται σαν κορσές γιατί τη φοράω σπάνια. Είμαι βέβαιος ότι όλη αυτή η καθυστέρηση "
            "γίνεται σκόπιμα, για να τηρηθεί η παράδοση που θέλει τη νύφη να αφήνει τον γαμπρό να περιμένει στην πόρτα της εκκλησίας. "
            "Και επειδή η Κατερίνα έχει μεσάνυχτα από κάτι τέτοια, η Αδριανή την έχει βάλει εν αγνοία της στο παιχνίδι. Το λέω εκ πείρας."
        ),
        (
            "Griechisch (Zahlen & Laute - μπ, ντ, γκ, τσ, τζ, €)",
            "Στις 15 Μαΐου του 2024, ο λογαριασμός της Δ.Ε.Η. κόστιζε 19,50€ και πληρώθηκε μέσω τραπέζης. "
            "Ο μπαμπάς πήγε στην πλατεία και έφαγε τζατζίκι και τσάι."
        ),
    ],
    "de": [
        (
            "Deutsch (Kurz)",
            "Hallo Kimon, das ist ein Test der Piper Text-to-Speech Stimme."
        ),
        (
            "Deutsch (Mittel)",
            "Dies ist ein mobiles Vorlesegerät für Menschen mit Sehbehinderung. Das Schriftstück wurde per OCR erkannt und wird nun vorgelesen."
        ),
        (
            "Deutsch (Lang)",
            "Künstliche Intelligenz revolutioniert barrierefreie Technologien. Durch moderne neuronale Sprachsynthese "
            "können Texte in Echtzeit auf kleinen Geräten wie dem Raspberry Pi flüssig und ohne Internetverbindung vorgelesen werden."
        ),
    ],
    "en": [
        (
            "Englisch (Kurz)",
            "Hello! This is a test of the Piper neural text to speech synthesizer."
        ),
        (
            "Englisch (Mittel)",
            "Accessibility tools empower blind and visually impaired individuals around the world to read printed text independently."
        ),
    ]
}


def clear_screen():
    print("\n" + "-" * 60 + "\n")


def compare_greek_voices(
    text: str,
    length_scale: float = 1.0,
    volume: float = 1.0,
    apply_filter: bool = False,
    compress_pauses: bool = True,
    min_pause_ms: int = 60,
    target_pause_ms: int = 25,
    keep_sentence_pauses: bool = True,
    sentence_pause_ms: int = 250,
    noise_w_scale: float = 0.2,
    remove_comma_pauses: bool = False,
):
    """Liest denselben griechischen Text nacheinander mit allen griechischen Stimmen vor."""
    print("\n" + "=" * 60)
    print("        STIMMEN-VERGLEICH: GRIECHISCHE STIMMEN")
    print("=" * 60)
    print(f"Text: \"{text[:100]}...\"\n")

    for voice_key, desc in GREEK_VOICES:
        print(f"\n>> Spiele mit: {desc}...")
        try:
            engine = PiperEngine(voice_key)
            # Bei Rapunzelina: etwas wärmerer Noise-Scale und Anti-Schepper Filter
            is_rap = "rapunzelina" in voice_key
            curr_scale = 1.1 if is_rap and length_scale == 1.0 else length_scale
            curr_noise_scale = 0.75 if is_rap else 0.667
            curr_filter = True if is_rap else apply_filter
            curr_vol = min(volume, 0.85) if is_rap else volume

            engine.speak(
                text,
                length_scale=curr_scale,
                volume=curr_vol,
                noise_scale=curr_noise_scale,
                apply_filter=curr_filter,
                compress_pauses=compress_pauses,
                min_pause_ms=min_pause_ms,
                target_pause_ms=target_pause_ms,
                keep_sentence_pauses=keep_sentence_pauses,
                sentence_pause_ms=sentence_pause_ms,
                noise_w_scale=noise_w_scale,
                remove_comma_pauses=remove_comma_pauses,
            )
        except Exception as e:
            print(f"Fehler bei {voice_key}: {e}")
    print("\n[Vergleich abgeschlossen]")


def main():
    voice_de = "de_DE-thorsten-medium"
    voice_el = "el_GR-joy-medium"  # Standardmäßig die beste Stimme Joy
    voice_en = "en_US-lessac-medium"

    current_voice_key = voice_el
    current_engine = None
    smart_piper = None
    smart_mode = True  # Standardmäßig Smart-Modus aktiv

    # Sprech-Einstellungen
    length_scale = 1.0  # Normales Tempo (100%)
    volume = 0.9        # 90% für sauberen Headroom ohne Verzerrung
    apply_filter = True  # Warm- & Anti-Scheppern-Filter (Standard AN)

    # Pause- & Redefluss-Einstellungen
    pause_mode_name = "KOMPAKT (25ms)"  # "AUS", "LEICHT (50ms)", "KOMPAKT (25ms)", "MINIMAL (10ms)"
    compress_pauses = True
    min_pause_ms = 60
    target_pause_ms = 25
    keep_sentence_pauses = True  # True = Pause am Satzende lassen, False = auch am Satzende stutzen
    sentence_pause_ms = 250      # Dauer der Pause am Satzende in ms
    noise_w_scale = 0.2          # 0.2 verhindert Dehnen/Zögern zwischen Wörtern
    remove_comma_pauses = False  # Optional: Kommas für noch schnelleren Fluss überspringen

    while True:
        clear_screen()
        print("=" * 68)
        print("          Piper TTS - Modell Test- & Entwicklungsumgebung")
        print("=" * 68)
        if smart_mode:
            print(f"Modus: [SMART-MODUS] (DE: {voice_de} | EL: {voice_el} | EN: {voice_en})")
        else:
            print(f"Modus: [DIREKT-MODUS] (Stimme: {current_voice_key})")
        
        comma_status = "AUS (Keine Pausen)" if remove_comma_pauses else "AN"
        sent_status = f"AN ({sentence_pause_ms}ms)" if keep_sentence_pauses else "AUS (Gestutzt)"
        print(f"Wortpausen: {pause_mode_name} | Satzende-Pausen: {sent_status} | Komma: {comma_status}")
        print(f"Audio: Tempo={length_scale}x | Lautstärke={int(volume*100)}% | Warm-Filter={'AN (Anti-Scheppern)' if apply_filter else 'AUS'}")
        print("-" * 68)
        print("Menü:")
        print("  [1] Beispielsatz vorlesen (inkl. langer griechischer Roman-Text)")
        print("  [2] Eigenen Text eingeben oder Datei (.txt) vorlesen")
        print(f"  [G] Griechische Stimme wechseln (Aktuell: {voice_el})")
        print("  [V] Stimmen-Vergleich: Griechischen Text mit Joy vs. Rapunzelina vergleichen")
        print(f"  [P] Wort- & Satzpausen optimieren (Wort: {pause_mode_name} | Satzende: {sent_status})")
        print("  [3] Alle Stimmen verwalten / aus Katalog wählen")
        print("  [4] Modus umschalten (Smart Auto-Erkennung <-> Feste Stimme)")
        print("  [5] Einstellungen anpassen (Tempo, Lautstärke, Filter, etc.)")
        print("  [6] Lokale Modelle & Speicherort anzeigen")
        print("  [0] Beenden")

        choice = input("\nAuswahl: ").strip().upper()

        if choice == "0":
            print("\nAuf Wiedersehen!")
            break

        elif choice == "P":
            # Schnelleinstellung für Wort- und Satzpausen & Redefluss
            print("\n--- Wortpausen & Satzende-Pausen optimieren ---")
            print("  Wortpausen (innerhalb des Satzes):")
            print("    [1] KOMPAKT (Empfohlen) - Wortpausen auf ~25ms gestutzt")
            print("    [2] MINIMAL - Sehr zügig, Wortpausen auf ~10ms gestutzt")
            print("    [3] LEICHT - Sanfte Reduzierung auf ~50ms")
            print("    [4] AUS - Unbearbeitete Original-Wortpausen")
            print("\n  Satzende-Pausen (nach . ! ?):")
            sent_str = f"AN ({sentence_pause_ms}ms Pause)" if keep_sentence_pauses else "AUS (Direkt weiter wie nach Wort)"
            print(f"    [S] Satzende-Pause umschalten (Aktuell: {sent_str})")
            print("    [T] Satzende-Pausendauer manuell eingeben (in ms)")
            print("\n  Weitere Redefluss-Optionen:")
            print(f"    [5] Komma-Atempausen umschalten (Aktuell: {'Entfernen' if remove_comma_pauses else 'Beibehalten'})")
            print(f"    [6] Sprechvarianz noise_w anpassen (Aktuell: {noise_w_scale})")
            
            p_sub = input("\nWahl (1-6 / S / T, Enter für Zurück): ").strip().upper()
            if p_sub == "1":
                compress_pauses = True
                min_pause_ms = 60
                target_pause_ms = 25
                noise_w_scale = 0.2
                pause_mode_name = "KOMPAKT (25ms)"
                print("\n[OK] Wortpausen auf 'KOMPAKT' eingestellt.")
            elif p_sub == "2":
                compress_pauses = True
                min_pause_ms = 40
                target_pause_ms = 10
                noise_w_scale = 0.1
                pause_mode_name = "MINIMAL (10ms)"
                print("\n[OK] Wortpausen auf 'MINIMAL' eingestellt.")
            elif p_sub == "3":
                compress_pauses = True
                min_pause_ms = 80
                target_pause_ms = 50
                noise_w_scale = 0.4
                pause_mode_name = "LEICHT (50ms)"
                print("\n[OK] Wortpausen auf 'LEICHT' eingestellt.")
            elif p_sub == "4":
                compress_pauses = False
                noise_w_scale = 0.8
                pause_mode_name = "AUS (Original)"
                print("\n[OK] Pause-Kompression deaktiviert (Original-Pausen).")
            elif p_sub == "S":
                keep_sentence_pauses = not keep_sentence_pauses
                print(f"\n[OK] Satzende-Pausen sind nun: {'AKTIVIERT (' + str(sentence_pause_ms) + 'ms)' if keep_sentence_pauses else 'DEAKTIVIERT (Sätze gehen nahtlos ineinander über)'}")
            elif p_sub == "T":
                val = input(f"Dauer der Satzende-Pause in Millisekunden (z.B. 100 für kurz, 250 normal, 400 lang - aktuell {sentence_pause_ms}ms): ").strip()
                if val.isdigit():
                    sentence_pause_ms = int(val)
                    keep_sentence_pauses = True
                    print(f"[OK] Satzende-Pause auf {sentence_pause_ms}ms gesetzt und aktiviert.")
                else:
                    print("[FEHLER] Ungültige Zahl.")
            elif p_sub == "5":
                remove_comma_pauses = not remove_comma_pauses
                print(f"\n[OK] Komma-Atempausen sind nun: {'DEAKTIVIERT (Flüssiger Redefluss)' if remove_comma_pauses else 'AKTIVIERT'}")
            elif p_sub == "6":
                val = input("Neuer Wert für noise_w_scale (0.0 = extrem starr, 0.2 = empfohlen, 0.8 = Piper-Default): ").strip()
                try:
                    noise_w_scale = max(0.0, min(1.0, float(val)))
                    print(f"[OK] noise_w_scale auf {noise_w_scale} gesetzt.")
                except ValueError:
                    print("[FEHLER] Ungültige Eingabe.")
            input("\nDrücke Enter um fortzufahren...")

        elif choice == "G":
            # Schneller Wechsel der griechischen Stimme
            print("\n--- Griechische Stimme wählen ---")
            for idx, (vk, desc) in enumerate(GREEK_VOICES, 1):
                active = " <--- AKTIV" if vk == voice_el else ""
                print(f"  [{idx}] {desc}{active}")
            
            g_choice = input(f"\nNummer wählen (1-{len(GREEK_VOICES)}, Enter für Abbrechen): ").strip()
            if g_choice.isdigit() and 1 <= int(g_choice) <= len(GREEK_VOICES):
                voice_el = GREEK_VOICES[int(g_choice) - 1][0]
                if smart_piper:
                    smart_piper.voice_names["el"] = voice_el
                    smart_piper.loaded_engines.pop("el", None)
                if not smart_mode:
                    current_voice_key = voice_el
                    current_engine = PiperEngine(current_voice_key)
                print(f"\n[OK] Griechische Stimme erfolgreich auf '{voice_el}' gewechselt!")
            input("\nDrücke Enter um fortzufahren...")

        elif choice == "V":
            # Stimmen-Vergleich
            print("\nWähle Text für den Stimmen-Vergleich:")
            print("  [1] Kurzer Satz")
            print("  [2] Mittellanger Text")
            print("  [3] Langer Roman-Ausschnitt")
            print("  [4] Eigenen Text eingeben")
            v_sub = input("Wahl (1-4): ").strip()
            if v_sub == "1":
                cmp_text = PRESET_TEXTS["el"][0][1]
            elif v_sub == "2":
                cmp_text = PRESET_TEXTS["el"][1][1]
            elif v_sub == "3":
                cmp_text = PRESET_TEXTS["el"][2][1]
            elif v_sub == "4":
                cmp_text = input("Griechischen Text eingeben: ").strip()
            else:
                cmp_text = PRESET_TEXTS["el"][0][1]

            compare_greek_voices(
                cmp_text,
                length_scale=length_scale,
                volume=volume,
                apply_filter=apply_filter,
                compress_pauses=compress_pauses,
                min_pause_ms=min_pause_ms,
                target_pause_ms=target_pause_ms,
                keep_sentence_pauses=keep_sentence_pauses,
                sentence_pause_ms=sentence_pause_ms,
                noise_w_scale=noise_w_scale,
                remove_comma_pauses=remove_comma_pauses,
            )
            input("\nDrücke Enter um fortzufahren...")

        elif choice == "1":
            # Beispielsätze anzeigen
            print("\nVerfügbare Beispielsätze:")
            idx_map = []
            c = 1
            for lang, items in PRESET_TEXTS.items():
                print(f"\n--- {lang.upper()} ---")
                for title, text in items:
                    preview = text[:80] + ("..." if len(text) > 80 else "")
                    print(f"  [{c}] {title}: \"{preview}\"")
                    idx_map.append((lang, text))
                    c += 1

            sub_choice = input(f"\nNummer wählen (1-{len(idx_map)}): ").strip()
            if sub_choice.isdigit() and 1 <= int(sub_choice) <= len(idx_map):
                selected_lang, selected_text = idx_map[int(sub_choice) - 1]
                print(f"\n>> Lese vor ({len(selected_text)} Zeichen):\n{selected_text}\n")
                out_wav = os.path.join(DEFAULT_MODELS_DIR, "output_test.wav")

                tts_kwargs = {
                    "length_scale": length_scale,
                    "volume": volume,
                    "apply_filter": apply_filter,
                    "compress_pauses": compress_pauses,
                    "min_pause_ms": min_pause_ms,
                    "target_pause_ms": target_pause_ms,
                    "keep_sentence_pauses": keep_sentence_pauses,
                    "sentence_pause_ms": sentence_pause_ms,
                    "noise_w_scale": noise_w_scale,
                    "remove_comma_pauses": remove_comma_pauses,
                }

                if smart_mode:
                    if smart_piper is None:
                        smart_piper = SmartPiper(voice_de=voice_de, voice_el=voice_el, voice_en=voice_en)
                    smart_piper.speak(selected_text, **tts_kwargs)
                    smart_piper.save_wav(selected_text, out_wav, **tts_kwargs)
                else:
                    if current_engine is None or current_engine.model_path != current_voice_key:
                        current_engine = PiperEngine(current_voice_key)
                    current_engine.speak(selected_text, **tts_kwargs)
                    current_engine.save_wav(selected_text, out_wav, **tts_kwargs)

                print(f"[Gespeichert als {out_wav}]")
                input("\nDrücke Enter um fortzufahren...")

        elif choice == "2":
            print("\n[1] Text direkt im Terminal eintippen / einfügen")
            print("[2] Text aus einer Textdatei (.txt) laden")
            t_choice = input("Wahl (1-2, Standard: 1): ").strip()

            custom_text = ""
            if t_choice == "2":
                file_path = input("Pfad zur .txt Datei: ").strip().strip('"')
                if os.path.isfile(file_path):
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        custom_text = f.read().strip()
                else:
                    print("[FEHLER] Datei nicht gefunden.")
            else:
                custom_text = input("Text eingeben / einfügen: ").strip()

            if custom_text:
                print(f"\n>> Lese vor ({len(custom_text)} Zeichen)...\n")
                out_wav = os.path.join(DEFAULT_MODELS_DIR, "output_custom.wav")
                tts_kwargs = {
                    "length_scale": length_scale,
                    "volume": volume,
                    "apply_filter": apply_filter,
                    "compress_pauses": compress_pauses,
                    "min_pause_ms": min_pause_ms,
                    "target_pause_ms": target_pause_ms,
                    "keep_sentence_pauses": keep_sentence_pauses,
                    "sentence_pause_ms": sentence_pause_ms,
                    "noise_w_scale": noise_w_scale,
                    "remove_comma_pauses": remove_comma_pauses,
                }
                if smart_mode:
                    if smart_piper is None:
                        smart_piper = SmartPiper(voice_de=voice_de, voice_el=voice_el, voice_en=voice_en)
                    smart_piper.speak(custom_text, **tts_kwargs)
                    smart_piper.save_wav(custom_text, out_wav, **tts_kwargs)
                else:
                    if current_engine is None or current_engine.model_path != current_voice_key:
                        current_engine = PiperEngine(current_voice_key)
                    current_engine.speak(custom_text, **tts_kwargs)
                    current_engine.save_wav(custom_text, out_wav, **tts_kwargs)
                print(f"[Gespeichert als {out_wav}]")
                input("\nDrücke Enter um fortzufahren...")

        elif choice == "3":
            # Stimmenauswahl
            print("\n--- Stimmenverwaltung & Zuweisung ---")
            print(f"Aktuelle Griechisch-Stimme (Smart-Modus): {voice_el}")
            print(f"Aktuelle Deutsch-Stimme (Smart-Modus):    {voice_de}")
            print(f"Aktuelle Standard-Stimme (Direkt-Modus): {current_voice_key}")
            print("\nOptionen:")
            print("  [A] Griechische Stimme für Smart-Modus ändern")
            print("  [B] Deutsche Stimme für Smart-Modus ändern")
            print("  [C] Aktive Stimme für Direkt-Modus auswählen")
            print("  [D] Eigenen Dateipfad zu einem .onnx Modell eingeben")
            
            sub_opt = input("\nWahl (A-D, Enter für Zurück): ").strip().upper()
            
            if sub_opt in ["A", "B", "C"]:
                keys = list(VOICE_CATALOG.keys())
                print("\nVerfügbare Stimmen im Katalog:")
                for i, k in enumerate(keys, 1):
                    v = VOICE_CATALOG[k]
                    status = "LOKAL" if os.path.exists(os.path.join(DEFAULT_MODELS_DIR, f"{k}.onnx")) else "ONLINE (Auto-Download)"
                    print(f"  [{i}] {k} ({v['name']}) [{status}]")
                
                v_num = input(f"\nNummer wählen (1-{len(keys)}): ").strip()
                if v_num.isdigit() and 1 <= int(v_num) <= len(keys):
                    chosen_key = keys[int(v_num) - 1]
                    if sub_opt == "A":
                        voice_el = chosen_key
                        if smart_piper:
                            smart_piper.voice_names["el"] = voice_el
                            smart_piper.loaded_engines.pop("el", None)
                        print(f"\n[OK] Griechische Stimme auf '{voice_el}' gesetzt.")
                    elif sub_opt == "B":
                        voice_de = chosen_key
                        if smart_piper:
                            smart_piper.voice_names["de"] = voice_de
                            smart_piper.loaded_engines.pop("de", None)
                        print(f"\n[OK] Deutsche Stimme auf '{voice_de}' gesetzt.")
                    elif sub_opt == "C":
                        current_voice_key = chosen_key
                        smart_mode = False
                        current_engine = PiperEngine(current_voice_key)
                        print(f"\n[OK] Direkt-Modus auf '{current_voice_key}' gesetzt.")
                    input("\nDrücke Enter um fortzufahren...")

            elif sub_opt == "D":
                custom_path = input("Pfad zur .onnx Datei eingeben: ").strip().strip('"')
                if os.path.isfile(custom_path):
                    target_lang = input("Für welche Sprache zuweisen? (de / el / en / direkt): ").strip().lower()
                    if target_lang == "el":
                        voice_el = custom_path
                        if smart_piper:
                            smart_piper.voice_names["el"] = voice_el
                            smart_piper.loaded_engines.pop("el", None)
                        print(f"[OK] Benutzerdefiniertes Modell für Griechisch zugewiesen.")
                    elif target_lang == "de":
                        voice_de = custom_path
                        if smart_piper:
                            smart_piper.voice_names["de"] = voice_de
                            smart_piper.loaded_engines.pop("de", None)
                        print(f"[OK] Benutzerdefiniertes Modell für Deutsch zugewiesen.")
                    else:
                        current_voice_key = custom_path
                        smart_mode = False
                        current_engine = PiperEngine(current_voice_key)
                        print(f"[OK] Benutzerdefiniertes Modell für Direkt-Modus aktiv.")
                else:
                    print("[FEHLER] Datei nicht gefunden.")
                input("\nDrücke Enter um fortzufahren...")

        elif choice == "4":
            smart_mode = not smart_mode
            if smart_mode:
                print(f"\nSmart-Modus AKTIVIERT. Texte werden automatisch erkannt (Deutsch -> {voice_de}, Griechisch -> {voice_el}, Englisch -> {voice_en}).")
                if smart_piper is None:
                    smart_piper = SmartPiper(voice_de=voice_de, voice_el=voice_el, voice_en=voice_en)
            else:
                print(f"\nSmart-Modus DEAKTIVIERT. Feste Stimme: {current_voice_key}")
            input("\nDrücke Enter um fortzufahren...")

        elif choice == "5":
            print("\n--- Einstellungen anpassen ---")
            print(f"1. Tempo / Geschwindigkeit ändern (aktuell: {length_scale}x)")
            print(f"2. Lautstärke ändern (aktuell: {int(volume*100)}%)")
            print(f"3. Warm- & Anti-Scheppern-Filter umschalten (aktuell: {'AN' if apply_filter else 'AUS'})")
            print(f"4. Wortpausen-Kompression anpassen (aktuell: {pause_mode_name})")
            print(f"5. Satzende-Pausen umschalten (aktuell: {'AN (' + str(sentence_pause_ms) + 'ms)' if keep_sentence_pauses else 'AUS'})")
            print(f"6. Komma-Atempausen umschalten (aktuell: {'AUS' if remove_comma_pauses else 'AN'})")
            print(f"7. Sprechvarianz noise_w ändern (aktuell: {noise_w_scale})")
            set_choice = input("\nWahl (1-7, Enter für Zurück): ").strip()
            if set_choice == "1":
                val = input("Neues Tempo (z.B. 0.8 für schneller, 1.0 normal, 1.2 langsamer): ").strip()
                try:
                    length_scale = float(val)
                except ValueError:
                    print("Ungültige Zahl.")
            elif set_choice == "2":
                val = input("Neue Lautstärke (0.1 bis 1.0): ").strip()
                try:
                    volume = max(0.1, min(1.0, float(val)))
                except ValueError:
                    print("Ungültige Zahl.")
            elif set_choice == "3":
                apply_filter = not apply_filter
                print(f"Warm- & Anti-Scheppern-Filter ist nun: {'AN (Metallischer Klang gedämpft & Lautsprecher geschützt)' if apply_filter else 'AUS'}")
            elif set_choice == "4":
                print("  [1] KOMPAKT (25ms)")
                print("  [2] MINIMAL (10ms)")
                print("  [3] LEICHT (50ms)")
                print("  [4] AUS")
                p_c = input("Wahl (1-4): ").strip()
                if p_c == "1":
                    compress_pauses, min_pause_ms, target_pause_ms, pause_mode_name = True, 60, 25, "KOMPAKT (25ms)"
                elif p_c == "2":
                    compress_pauses, min_pause_ms, target_pause_ms, pause_mode_name = True, 40, 10, "MINIMAL (10ms)"
                elif p_c == "3":
                    compress_pauses, min_pause_ms, target_pause_ms, pause_mode_name = True, 80, 50, "LEICHT (50ms)"
                elif p_c == "4":
                    compress_pauses, pause_mode_name = False, "AUS"
            elif set_choice == "5":
                keep_sentence_pauses = not keep_sentence_pauses
                print(f"Satzende-Pausen sind nun: {'AN (' + str(sentence_pause_ms) + 'ms)' if keep_sentence_pauses else 'AUS (gestutzt)'}")
            elif set_choice == "6":
                remove_comma_pauses = not remove_comma_pauses
                print(f"Komma-Pausen sind nun: {'AUS (flüssiger)' if remove_comma_pauses else 'AN'}")
            elif set_choice == "7":
                val = input("Neuer Wert für noise_w_scale (0.0 bis 1.0): ").strip()
                try:
                    noise_w_scale = max(0.0, min(1.0, float(val)))
                except ValueError:
                    print("Ungültige Zahl.")
            input("\nDrücke Enter um fortzufahren...")

        elif choice == "6":
            print(f"\nModell-Verzeichnis: {DEFAULT_MODELS_DIR}")
            local_list = list_local_voices(DEFAULT_MODELS_DIR)
            if not local_list:
                print("Noch keine Modelle lokal heruntergeladen. Sie werden beim ersten Testen automatisch geladen.")
            else:
                print("Lokal vorhandene Modelle:")
                for m in local_list:
                    print(f"  - {m['id']} (Sprache: {m['language']}, {m['sample_rate']} Hz)")
            input("\nDrücke Enter um fortzufahren...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
