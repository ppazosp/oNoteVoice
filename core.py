#!/usr/bin/env python3
import threading
import io
import collections
import speech_recognition as sr
from faster_whisper import WhisperModel
from cmque import DataDeque, PairDeque, Queue
import asyncio
import websockets
import json
from concurrent.futures import ThreadPoolExecutor

models = ['tiny', 'base', 'small', 'medium', 'large-v1', 'large-v2', 'large-v3', 'large']

# Global WebSocket server state
websocket_server = None
connected_clients = set()
loop = None
executor = ThreadPoolExecutor(max_workers=3)


def get_mic_names():
    return sr.Microphone.list_microphone_names()


def get_mic_index(mic):
    if mic is None:
        return None
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        if mic in name:
            return index
    raise ValueError('Microphone device not found.')


# WebSocket handling functions
async def broadcast_message(message):
    if not connected_clients:
        print("No clients connected. Message not sent.")
        return

    print(f"Broadcasting message: {message}")  # Debugging output

    clients = connected_clients.copy()
    failed_clients = set()

    for client in clients:
        try:
            await client.send(message)
            print(f"Message sent to {client.remote_address}")  # Debugging output
        except websockets.exceptions.ConnectionClosed:
            print(f"Client {client.remote_address} disconnected.")  # Debugging output
            failed_clients.add(client)
        except Exception as e:
            print(f"Error sending message to {client.remote_address}: {e}")
            failed_clients.add(client)

    connected_clients.difference_update(failed_clients)


# Update your ws_handler to handle the case where path might be omitted
async def ws_handler(websocket, path=None):
    connected_clients.add(websocket)
    print(f"Client connected: {websocket.remote_address}")  # Add this line

    try:
        await websocket.send(json.dumps({"type": "connection", "status": "connected"}))
        # Keep the connection open and handle client messages if needed
        async for message in websocket:
            # Process incoming messages if needed
            pass
    finally:
        connected_clients.remove(websocket)


def start_websocket_server(host="100.87.246.86", port=8000):
    global websocket_server, loop

    # Define server start function for the event loop
    async def start_server():
        global websocket_server
        # Make sure we're using the handler function directly
        websocket_server = await websockets.serve(ws_handler, host, port)
        print(f"WebSocket server started at ws://{host}:{port}")
        return websocket_server

    # Create new event loop in the thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Start the server and run the event loop
    loop.run_until_complete(start_server())
    loop.run_forever()


def stop_websocket_server():
    global websocket_server, loop
    if websocket_server and loop:
        async def shutdown():
            # Close the server first
            websocket_server.close()
            await websocket_server.wait_closed()

            # Give connections a chance to close gracefully
            await asyncio.sleep(0.5)

            # Then cancel remaining tasks, but exclude the current task
            current_task = asyncio.current_task(loop)
            for task in asyncio.all_tasks(loop):
                if task is not current_task:
                    task.cancel()
                    try:
                        await asyncio.shield(task)
                    except asyncio.CancelledError:
                        pass

        try:
            future = asyncio.run_coroutine_threadsafe(shutdown(), loop)
            future.result(timeout=5)  # Wait up to 5 seconds for server to shut down
        except Exception as e:
            print(f"Error during WebSocket server shutdown: {e}")
        finally:
            loop.stop()
            print("WebSocket server stopped")


def send_transcription_via_websocket(done_text, current_text):
    global loop
    if loop:
        # Combine done_text and current_text to send the full text
        full_text = done_text + current_text

        message =  full_text

        asyncio.run_coroutine_threadsafe(broadcast_message(message), loop)


def process(index, model, vad, memory, patience, prompt, tsres_queue, ready,
            enable_websocket=True, ws_host="100.87.246.86", ws_port=8000):
    def ts():
        prompts = collections.deque([prompt], memory)
        window = bytearray()
        full_transcription = ""  # Keep track of the full transcription

        while frame := frame_queue.get():
            window.extend(frame)
            audio = sr.AudioData(window, mic.SAMPLE_RATE, mic.SAMPLE_WIDTH)
            with io.BytesIO(audio.get_wav_data()) as audio_file:
                segments, info = model.transcribe(audio_file, language='es', initial_prompt=''.join(prompts),
                                                  vad_filter=vad, word_timestamps=False,beam_size=5, without_timestamps=True)
            segments = [segment for segment in segments]
            start = max(len(window) // mic.SAMPLE_WIDTH / mic.SAMPLE_RATE - patience, 0.0)
            i = 0
            for segment in segments:
                if segment.end >= start:
                    if segment.start < start:
                        start = segment.start
                    break
                i += 1
            done_src = ''.join(segment.text for segment in segments[:i])
            curr_src = ''.join(segment.text for segment in segments[i:])

            # Update the full transcription
            full_transcription += done_src

            prompts.extend(segment.text for segment in segments[:i])
            del window[:int(start * mic.SAMPLE_RATE) * mic.SAMPLE_WIDTH]

            # Send to the transcription queue
            tsres_queue.put((done_src, curr_src))

            # Send transcription via WebSocket with full text
            if enable_websocket:
                send_transcription_via_websocket(full_transcription, curr_src)

        tsres_queue.put(None)

    try:
        # Start WebSocket server if enabled
        if enable_websocket:
            ws_thread = threading.Thread(target=start_websocket_server, args=(ws_host, ws_port), daemon=True)
            ws_thread.start()

        with sr.Microphone(index) as mic:
            model = WhisperModel(model)
            frame_queue = Queue(DataDeque())
            ts_thread = threading.Thread(target=ts)
            ts_thread.start()
            ready[0] = True
            while ready[0]:
                frame_queue.put(mic.stream.read(mic.CHUNK))
            frame_queue.put(None)
            ts_thread.join()

    finally:
        # Stop WebSocket server
        if enable_websocket:
            stop_websocket_server()
        ready[0] = None