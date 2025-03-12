#!/usr/bin/env python3
import tkinter as tk
import tkinter.ttk as ttk
import threading
import core
from cmque import PairDeque, Queue


class Text(tk.Text):
    def __init__(self, master):
        super().__init__(master)
        self.res_queue = Queue(PairDeque())
        self.tag_config('done', foreground='black')
        self.tag_config('curr', foreground='blue', underline=True)
        self.insert('end', '  ', 'done')
        self.record = self.index('end-1c')
        self.see('end')
        self.config(state='disabled')
        self.update()

    def update(self):
        while self.res_queue:
            self.config(state='normal')
            if res := self.res_queue.get():
                done, curr = res
                self.delete(self.record, 'end')
                self.insert('end', done, 'done')
                self.record = self.index('end-1c')
                self.insert('end', curr, 'curr')
            else:
                done = self.get(self.record, 'end-1c')
                self.delete(self.record, 'end')
                self.insert('end', done, 'done')
                self.insert('end', '\n', 'done')
                self.insert('end', '  ', 'done')
                self.record = self.index('end-1c')
            self.see('end')
            self.config(state='disabled')
        self.after(100, self.update)  # avoid busy waiting


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Transcription')
        self.ts_text = Text(self)
        self.top_frame = ttk.Frame(self)
        self.mid_frame = ttk.Frame(self)  # Frame for WebSocket settings
        self.bot_frame = ttk.Frame(self)

        self.ts_text.grid(row=2, column=0, sticky='nsew')
        self.top_frame.grid(row=0, column=0, sticky='ew')
        self.mid_frame.grid(row=1, column=0, sticky='ew')
        self.bot_frame.grid(row=3, column=0, sticky='ew')

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # Top frame (existing controls)
        self.mic_label = ttk.Label(self.top_frame, text='Mic:')
        self.mic_combo = ttk.Combobox(self.top_frame, values=['default'], state='readonly')
        self.mic_combo.current(0)
        self.mic_button = ttk.Button(self.top_frame, text='Refresh',
                                     command=lambda: self.mic_combo.config(values=['default'] + core.get_mic_names()))

        self.model_label = ttk.Label(self.top_frame, text='Model size or path:')
        self.model_combo = ttk.Combobox(self.top_frame, values=core.models, state='normal')

        self.vad_check = ttk.Checkbutton(self.top_frame, text='VAD', onvalue=True, offvalue=False)
        self.vad_check.state(('!alternate', 'selected'))

        self.memory_label = ttk.Label(self.top_frame, text='Memory:')
        self.memory_spin = ttk.Spinbox(self.top_frame, from_=1, to=10, increment=1, state='readonly')
        self.memory_spin.set(3)

        self.patience_label = ttk.Label(self.top_frame, text='Patience:')
        self.patience_spin = ttk.Spinbox(self.top_frame, from_=1.0, to=20.0, increment=0.5, state='readonly')
        self.patience_spin.set(5.0)

        self.timeout_label = ttk.Label(self.top_frame, text='Timeout:')
        self.timeout_spin = ttk.Spinbox(self.top_frame, from_=1.0, to=20.0, increment=0.5, state='readonly')
        self.timeout_spin.set(5.0)

        self.mic_label.pack(side='left', padx=(5, 5))
        self.mic_combo.pack(side='left', padx=(0, 5))
        self.mic_button.pack(side='left', padx=(0, 5))
        self.model_label.pack(side='left', padx=(5, 5))
        self.model_combo.pack(side='left', padx=(0, 5), fill='x', expand=True)
        self.vad_check.pack(side='left', padx=(0, 5))
        self.memory_label.pack(side='left', padx=(5, 5))
        self.memory_spin.pack(side='left', padx=(0, 5))
        self.patience_label.pack(side='left', padx=(5, 5))
        self.patience_spin.pack(side='left', padx=(0, 5))
        self.timeout_label.pack(side='left', padx=(5, 5))
        self.timeout_spin.pack(side='left', padx=(0, 5))

        # Middle frame (WebSocket settings)
        self.ws_check = ttk.Checkbutton(self.mid_frame, text='Enable WebSocket Server', onvalue=True, offvalue=False)
        self.ws_check.state(('!alternate', 'selected'))

        self.ws_host_label = ttk.Label(self.mid_frame, text='WS Host:')
        self.ws_host_entry = ttk.Entry(self.mid_frame)
        self.ws_host_entry.insert(0, 'localhost')

        self.ws_port_label = ttk.Label(self.mid_frame, text='WS Port:')
        self.ws_port_spin = ttk.Spinbox(self.mid_frame, from_=1024, to=65535, increment=1, state='normal')
        self.ws_port_spin.set(8765)

        self.ws_status_label = ttk.Label(self.mid_frame, text='WebSocket Status: Not Started')

        self.ws_check.pack(side='left', padx=(5, 5))
        self.ws_host_label.pack(side='left', padx=(5, 5))
        self.ws_host_entry.pack(side='left', padx=(0, 5), fill='x', expand=True)
        self.ws_port_label.pack(side='left', padx=(5, 5))
        self.ws_port_spin.pack(side='left', padx=(0, 5))
        self.ws_status_label.pack(side='left', padx=(5, 5))

        # Bottom frame (modified controls - removed translation options)
        self.prompt_label = ttk.Label(self.bot_frame, text='Prompt:')
        self.prompt_entry = ttk.Entry(self.bot_frame, state='normal')

        self.control_button = ttk.Button(self.bot_frame, text='Start', command=self.start, state='normal')

        self.prompt_label.pack(side='left', padx=(5, 5))
        self.prompt_entry.pack(side='left', padx=(0, 5), fill='x', expand=True)
        self.control_button.pack(side='left', padx=(5, 5))

        self.ready = [None]

    def start(self):
        self.ready[0] = False
        self.control_button.config(text='Starting...', command=None, state='disabled')

        index = None if self.mic_combo.current() == 0 else self.mic_combo.current() - 1
        model = self.model_combo.get()
        vad = self.vad_check.instate(('selected',))
        memory = int(self.memory_spin.get())
        patience = float(self.patience_spin.get())
        timeout = float(self.timeout_spin.get())
        prompt = self.prompt_entry.get()

        # Removed source and target language settings
        # Using None for target to indicate no translation is needed
        source = None
        target = None

        # WebSocket settings
        enable_websocket = self.ws_check.instate(('selected',))
        ws_host = self.ws_host_entry.get()
        ws_port = int(self.ws_port_spin.get())

        if enable_websocket:
            self.ws_status_label.config(text=f"WebSocket Status: Starting on {ws_host}:{ws_port}")

        # Pass None for translation text queue since we're not using it
        threading.Thread(
            target=core.process,
            args=(index, model, vad, memory, patience, timeout, prompt, source, target,
                  self.ts_text.res_queue, None, self.ready,
                  enable_websocket, ws_host, ws_port),
            daemon=True
        ).start()

        self.starting()

    def starting(self):
        if self.ready[0] is True:
            self.control_button.config(text='Stop', command=self.stop, state='normal')
            if self.ws_check.instate(('selected',)):
                self.ws_status_label.config(
                    text=f"WebSocket Status: Running on {self.ws_host_entry.get()}:{self.ws_port_spin.get()}")
            return
        if self.ready[0] is None:
            self.control_button.config(text='Start', command=self.start, state='normal')
            self.ws_status_label.config(text="WebSocket Status: Not Started")
            return
        self.after(100, self.starting)

    def stop(self):
        self.ready[0] = False
        self.control_button.config(text='Stopping...', command=None, state='disabled')
        if self.ws_check.instate(('selected',)):
            self.ws_status_label.config(text="WebSocket Status: Stopping...")
        self.stopping()

    def stopping(self):
        if self.ready[0] is None:
            self.control_button.config(text='Start', command=self.start, state='normal')
            self.ws_status_label.config(text="WebSocket Status: Not Started")
            return
        self.after(100, self.stopping)


if __name__ == '__main__':
    App().mainloop()