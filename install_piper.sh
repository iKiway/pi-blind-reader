# 1. Ordner erstellen und hineinwechseln
mkdir -p ~/piper_tts
cd ~/piper_tts

# 2. Piper herunterladen (für Pi 64-bit / aarch64)
# (Stand 2024 - dies ist die aktuell stabile Version)
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_linux_aarch64.tar.gz

# 3. Entpacken
tar -xvf piper_linux_aarch64.tar.gz

# 4. Die Deutsche Stimme "Thorsten" herunterladen (Modell + Config)
# Dies ist die beste deutsche Open-Source Stimme.
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json

# 5. Testen (Lautsprecher anschließen!)
# Wenn Sie "Hallo" hören, hat es geklappt.
echo "Hallo, das ist ein Test." | ./piper/piper --model de_DE-thorsten-medium.onnx --output_file test.wav
aplay test.wav
echo "Installation abgeschlossen!"