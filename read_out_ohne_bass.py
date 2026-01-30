import subprocess
import os

text = ""
file_path = 'cleaned_text.txt'

if os.path.exists(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read().strip()
else:
    print("Datei nicht gefunden.")

print(text)
if text:
    # 1. Piper Prozess
    piper_process = subprocess.Popen(
        ['/home/kimon/piper_tts/piper/piper', '--model', '/home/kimon/piper_tts/de_DE-thorsten-medium.onnx', '--output-raw'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE
    )

    # 2. SoX Prozess (Das Audio-Studio)
    sox_process = subprocess.Popen(
        [
            'play',
            '-t', 'raw',
            '-r', '22050',
            '-e', 'signed-integer',
            '-b', '16',
            '-c', '1',
            '-',                    # Input Pipe
            'vol', '0.4',           # <--- SCHRITT 1: Lautstärke auf 70% (verhindert Clipping)
            'highpass', '100',      # <--- SCHRITT 2: Nur ganz tiefes Rumpeln weg
            'equalizer', '400', '1.0q', '-5', # <--- SCHRITT 3: Die "Männertöne" (300Hz) um 5dB absenken
            'treble', '+3'          # <--- OPTIONAL: Höhen leicht anheben für Sprachverständlichkeit
        ],
        stdin=piper_process.stdout
    )

    piper_process.stdin.write(text.encode('utf-8'))
    piper_process.stdin.close()
    sox_process.wait()
    
    print(f"Text vorgelesen: {len(text)} Zeichen")
else:
    print("Kein Text gefunden")