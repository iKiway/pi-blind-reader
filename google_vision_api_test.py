from google.cloud import vision
import io

def detect_document_text(path):
    client = vision.ImageAnnotatorClient()

    with io.open(path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)

    # Wir nutzen document_text_detection (besser für Briefe als einfaches text_detection)
    response = client.document_text_detection(image=image)
    
    # Hier holen wir uns die erste Seite
    page = response.full_text_annotation.pages[0]
    
    # Bildabmessungen holen (um prozentual zu filtern)
    width = page.width
    height = page.height
    
    # GRENZWERTE DEFINIEREN (in Prozent des Bildes)
    # Alles oberhalb von 25% der Höhe wird ignoriert (Adresse/Kopfzeile)
    top_margin = height * 0.25 
    # Alles links von 10% der Breite wird ignoriert (Randnotiz wie dvkg...)
    left_margin = width * 0.10
    
    filtered_text = []

    for block in page.blocks:
        # Wir schauen uns die Bounding Box des Blocks an
        # vertices[0] ist meist die Ecke oben links des Blocks
        block_x = block.bounding_box.vertices[0].x
        block_y = block.bounding_box.vertices[0].y
        
        # DER FILTER:
        # Nur Blöcke nehmen, die UNTERHALB der Kopfzeile und RECHTS vom Rand liegen
        if block_y > top_margin and block_x > left_margin:
            
            # Text aus dem Block extrahieren
            block_text = ""
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    word_text = ''.join([symbol.text for symbol in word.symbols])
                    block_text += word_text + " "
                block_text += "\n"
            
            filtered_text.append(block_text)

    # Ergebnis zusammenfügen
    final_text = "\n".join(filtered_text)
    print(final_text)

# Aufruf
detect_document_text('captured_images/capture_20260115_210326.jpg')