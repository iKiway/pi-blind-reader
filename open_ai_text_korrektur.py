from openai import OpenAI
import json

def extract_letter_text_with_openai(raw_ocr_text):
    """
    Nimmt den rohen OCR-Text und filtert nur den eigentlichen Briefinhalt heraus.
    Entfernt Kopfzeilen, Adressen, Formularfelder, etc.
    """
    with open('api_key_open_ai.txt', 'r') as f:
        api_key = f.read().strip()
    client = OpenAI(api_key=api_key)

#     prompt = f"""Du bekommst einen von OCR erkannten Text eines Briefes. 
# Deine Aufgabe ist es, NUR den eigentlichen Brieftext zu extrahieren und zu korrigieren.

# WICHTIGSTE REGEL:
# - Antworte IMMER in der Sprache des Originalbriefes.
# - Übersetze NICHT.

# ENTFERNEN sollst du:
# - Kopfzeilen (z.B. "DVKG 79-01.25", Formular-IDs)
# - Absenderadressen
# - Empfängeradressen  
# - Kontaktdaten (Telefon, Fax, Internet, Öffnungszeiten)
# - Barcodes, Referenznummern
# - Fußnoten wie "Dieses Schreiben wurde maschinell erstellt"

# BEHALTEN sollst du:
# - Die Anrede (z.B. "Sehr geehrter Herr...")
# - Den kompletten Briefinhalt
# - Die Grußformel am Ende

# Korrigiere dabei auch OCR-Fehler und formatiere den Text gut lesbar.

# Korrigiere OCR-Fehler (besonders bei griechischen Akzenten/Sonderzeichen), aber verändere nicht den Inhalt.

# Hier ist der OCR-Text:

# {raw_ocr_text}

# Gib NUR den bereinigten und korrigierten Brieftext zurück, ohne zusätzliche Erklärungen."""


    prompt = f"""Du erhältst einen rohen OCR-Text. Das kann ein Brief, eine Buchseite, ein Artikel oder eine Notiz sein.
Deine Aufgabe: Identifiziere den Dokumententyp und extrahiere NUR den relevanten Hauptinhalt (lesbaren Text).

REGELN FÜR DEN INHALT:
1. SPRACHE: Behalte IMMER die Originalsprache bei (Deutsch, Griechisch, etc.). Übersetze NICHT.
2. BEI BRIEFEN: 
   - Entferne Adressfelder, Kopfzeilen, Metadaten, Telefonnummern.
   - Behalte Anrede, Textkörper und Grußformel.
3. BEI BUCHSEITEN / ARTIKELN: 
   - Entferne Seitenzahlen, Kopfzeilen (Running Headers), Fußnoten-Referenzen.
   - Verbinde getrennte Wörter am Zeilenende wieder korrekt.
4. ALLGEMEIN: 
   - Korrigiere OCR-Fehler (z.B. falsche Zeichen, 'l' statt '1'), aber verfälsche nicht den Inhalt.
   - Entferne "Rauschen" (einzelne sinnlose Zeichenfragmente).

Hier ist der OCR-Text:

{raw_ocr_text}

Gib NUR den bereinigten Text zurück, ohne Einleitung oder Erklärung."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Du bist ein Experte für Textrekonstruktion und OCR-Korrektur."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2000,
        temperature=0.2,
    )

    cleaned_text = response.choices[0].message.content.strip()
    return cleaned_text

# Vision API Response laden und verarbeiten
def process_vision_response():
    """
    Lädt vision_api_response.json, extrahiert den Text und filtert nur den Briefinhalt
    """
    with open('vision_api_response.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    # Vollständigen Text aus Google Vision API holen
    raw_text = ""
    if 'full_response' in data and 'textAnnotations' in data['full_response'] and len(data['full_response']['textAnnotations']) > 0:
        raw_text = data['full_response']['textAnnotations'][0]['description']
    elif 'filtered_text' in data:
        raw_text = data['filtered_text']
    
    if not raw_text:
        print("Kein Text in der JSON gefunden")
        return
    
    print("Roher OCR-Text gefunden, filtere Briefinhalt mit OpenAI...")
    print(f"Länge: {len(raw_text)} Zeichen\n")
    
    # Mit OpenAI den reinen Brieftext extrahieren
    letter_text = extract_letter_text_with_openai(raw_text)
    
    print("="*60)
    print("BEREINIGTER BRIEFTEXT:")
    print("="*60)
    print(letter_text)
    print("="*60)
    
    # Speichern in externer TXT-Datei
    with open('cleaned_text.txt', 'w', encoding='utf-8') as file:
        file.write(letter_text)
    
    print("\nBereinigter Text wurde in 'cleaned_text.txt' gespeichert")

if __name__ == "__main__":
    process_vision_response()

