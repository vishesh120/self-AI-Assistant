import speech_recognition as sr


def main():
    print("Available microphones:")
    for i, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"{i}: {name}")

    index = int(input("\nEnter your microphone index: "))
    recognizer = sr.Recognizer()

    try:
        with sr.Microphone(device_index=index) as source:
            print("\nAdjusting for background noise...")
            recognizer.adjust_for_ambient_noise(source, duration=2)
            print("Speak now: say 'Hello Jarvis'")
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=8)

        print("Recognized:", recognizer.recognize_google(audio))
    except Exception as e:
        print(type(e).__name__ + ":", e)


if __name__ == "__main__":
    main()
