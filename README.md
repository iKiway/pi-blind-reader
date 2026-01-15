# pi-blind-reader
## Required libraries
- picamera2
- numpy
- flask
- gpiozero
- pytesseract
- Pillow
- opencv-python
- threading
- queue
- datetime
- os
- google-cloud-vision (optional, for Google OCR)

pytesseract requires Tesseract OCR to be installed on your system. You can install it using the following command:

```bash sudo apt-get install tesseract-ocr```

You have to install the different language packs separately. For example, for Spanish, you can use:

```bash sudo apt-get install tesseract-ocr-ell```