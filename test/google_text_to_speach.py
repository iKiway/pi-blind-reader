import os
import winsound
from google.cloud import texttospeech

# Setze den Pfad zu den Anmeldedaten
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_cloud_credentials.json"

def synthesize_speech(text, use_wavenet=True):
    try:
        # Client instanziieren
        client = texttospeech.TextToSpeechClient()
    except Exception as e:
        print("Fehler beim Initialisieren des Google Cloud Clients. Bitte stelle sicher, dass 'google-cloud-texttospeech' installiert ist und die Credentials stimmen.")
        print(e)
        return

    # Text festlegen
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Stimme auswählen (Griechisch)
    if use_wavenet:
        # WaveNet-Stimmen sind qualitativ hochwertiger und klingen natürlicher
        voice_name = "el-GR-Wavenet-A" 
    else:
        # Standard-Stimmen sind günstiger/kostenlos, klingen aber roboterhafter
        voice_name = "el-GR-Standard-A"

    voice = texttospeech.VoiceSelectionParams(
        language_code="el-GR",
        name=voice_name
    )

    # Audio-Konfiguration festlegen (LINEAR16 = .wav Format, was für winsound auf Windows optimal ist)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    print(f"\nGeneriere Audio mit Stimme: {voice_name}...")
    
    try:
        # Anfrage an Google senden
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        # Die Antwort ist binär (Audio-Daten)
        output_file = "test_greek_output.wav"
        with open(output_file, "wb") as out:
            out.write(response.audio_content)
            print(f"Audio erfolgreich gespeichert als '{output_file}'")
            
        print("Spiele Audio ab...\n")
        winsound.PlaySound(output_file, winsound.SND_FILENAME)
        print("Abgeschlossen.")
        
    except Exception as e:
        print(f"Fehler bei der Google Text-to-Speech API: {e}")

if __name__ == "__main__":
    # Griechischer Testtext: "Hallo! Das ist ein Test für den Text-to-Speech-Dienst von Google. Ich hoffe, er klingt deutlich."
    greek_text = "Γεια σας! Αυτό είναι ένα δοκιμαστικό μήνυμα για την υπηρεσία μετατροπής κειμένου σε ομιλία της Google. Ελπίζω να ακούγεται καθαρά."
    
    print("=== Google Text-to-Speech Test (Griechisch) ===")
    print(f"Testtext: {greek_text}")
    print("\nMöchtest du eine WaveNet-Stimme verwenden? (Hochwertiger, aber evtl. kostenpflichtig bei hoher Nutzung)")
    print("[j] Ja (WaveNet)")
    print("[n] Nein (Standard)")
    
    choice = input("> ").strip().lower()
    
    use_wavenet = (choice == 'j' or choice == 'y')
    
    synthesize_speech(greek_text, use_wavenet)
