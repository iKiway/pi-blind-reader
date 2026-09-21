# sudo modprobe snd_bcm2835 muss geladen sein!!!!

import subprocess
import os

# Text aus cleaned_text.txt laden
text = ""
with open('cleaned_text.txt', 'r', encoding='utf-8') as file:
    text = file.read().strip()

# Text-to-Speech mit Piper
print(text)
if text:
    # Text direkt über subprocess.Popen an Piper senden (besser als echo)
    piper_process = subprocess.Popen(
        ['/home/kimon/piper_tts/piper/piper', '--model', '/home/kimon/piper_tts/de_DE-thorsten-medium.onnx', '--output-raw'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    aplay_process = subprocess.Popen(
        ['aplay', '-r', '22050', '-f', 'S16_LE', '-t', 'raw', '-'],
        stdin=piper_process.stdout
    )
    piper_process.stdin.write(text.encode('utf-8'))
    piper_process.stdin.close()
    aplay_process.wait()
    print(f"Text vorgelesen: {len(text)} Zeichen")
else:
    print("Kein Text in der JSON gefunden")