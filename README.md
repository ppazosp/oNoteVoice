# oNoteWhisper

In real time audio transcription service from a local microphone in the server using the [fast-whisper](https://github.com/SYSTRAN/faster-whisper) library. We use web sockets to send this transcription, because we want to use this transcription in a mobile application (Kotlin).

## Requirements

For the server side, you need to install the following packages:

- Python 3.8+
- [fast-whisper](https://github.com/SYSTRAN/faster-whisper)
- [SpeechRecognition](https://pypi.org/project/SpeechRecognition)
- [PyAudio](https://pypi.org/project/PyAudio) 0.2.11+
- [websocket-server](https://pypi.org/project/websocket-server)


## Usage

To start the server, run the `app.py` script. The server will listen on port 8765 by default.
The transcription will be in spanish and it will be sent to the client connected to the socket in real time.
We can change the model to use in the transcription by changing the `model` variable in the web.
## Q&A

- How does the program work?

  When the program starts working, it will take the audio stream in real time from the input device and transcribe it. After a piece of audio is transcribed, the corresponding text fragment will be sent to the client. In order to avoid inaccurate transcription results due to lack of context or speech being cut off in the middle, the program will temporarily place the segments that have been transcribed but have not yet been fully confirmed in a "transcription window" (displayed as underlined blue text in the gui of the app). When the next piece of audio comes, it will be concatenated to the window. The audio in the window is transcribed iteratively, and the transcription results are constantly revised and updated until a sentence is completed and has sufficient subsequent context (determined by the `patience` parameter) before it is moved out of the transcription window (turns into black text). The last few moved-out segments (the number is determined by the `memory` parameter) will be used as prompts for subsequent context to improve the accuracy of transcription.


- What is the effect of the `patience` and `memory` parameters on the program?

  The `patience` parameter determines the minimum time to wait for subsequent speech before moving a completed segment out of the transcription window. If the `patience` parameter is set too low, the program may move the segment out of the window too early, resulting in incomplete sentences or inaccurate transcription. If the `patience` parameter is set too high, the program may wait too long to move the segment out of the window, this will cause the transcription window to accumulate too much content, which may result in slower transcription speed.

  The `memory` parameter determines the maximum number of previous segments to be used as prompts for audio in the transcription window. If the `memory` parameter is set too low, the program may not have enough previous context used as prompts, which may result in inaccurate transcription. If the `memory` parameter is set too high, the prompts could be too long, which also could slow down the transcription speed.
