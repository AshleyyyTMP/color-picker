import sys
import threading
import tkinter as tk
from tkinter import ttk
from PIL import ImageGrab
import pyperclip
import numpy as np
from pynput import mouse
from pynput.keyboard import Key, Listener as KeyListener

# ---------- Utility functions ----------
def rgb_to_hex(r, g, b):
    return "#{:02X}{:02X}{:02X}".format(r, g, b)

def normalize_hex(value):
    value = value.strip().lower()
    if value.startswith("#"):
        value = value[1:]
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return "#" + value if len(value) == 6 else None

# ---------- Screen sampling ----------
class ScreenColorPicker:
    def __init__(self, ui):
        self.ui = ui
        self.current_hex = "#000000"
        self.current_position = (0, 0)
        self.listening = False
        self._mouse_listener = None
        self._updating = False

    def sample_under_cursor(self):
        try:
            screenshot = ImageGrab.grab()
            x, y = self.current_position
            pix = screenshot.load()
            w, h = screenshot.size
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            r, g, b = pix[x, y][:3]  # Get only RGB, ignore alpha
            return rgb_to_hex(r, g, b)
        except Exception as e:
            print(f"Error sampling color: {e}")
            return "#000000"

    def start_listening(self):
        if self.listening:
            return
        self.listening = True

        def on_move(x, y):
            if not self.listening or self._updating:
                return
            self.current_position = (x, y)
            self._updating = True
            self.current_hex = self.sample_under_cursor()
            self.ui.root.after(0, lambda: self.ui.update_live_color(self.current_hex))
            self._updating = False

        def on_click(x, y, button, pressed):
            if pressed and self.listening:
                self.current_position = (x, y)
                self.current_hex = self.sample_under_cursor()
                self.ui.root.after(0, lambda: self.ui.add_color(self.current_hex))

        self._mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click)
        self._mouse_listener.start()

    def stop_listening(self):
        self.listening = False
        if self._mouse_listener:
            self._mouse_listener.stop()

# ---------- UI ----------
class ColorPickerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Color Picker")
        self.root.geometry("450x600")
        self.root.configure(bg="#f2f2f2")

        self.picker = ScreenColorPicker(self)
        self.selected_hex_var = tk.StringVar(value="#000000")
        self.live_hex_var = tk.StringVar(value="#000000")
        self.color_list = []
        self.picking_mode = False

        # Title
        title = ttk.Label(root, text="Screen Color Picker", font=("TkDefaultFont", 14, "bold"))
        title.pack(pady=(12, 8))

        # Live color display
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="x")

        self.live_color_box = tk.Label(frame, width=18, height=6, bg="#000000", relief="solid", borderwidth=2)
        self.live_color_box.pack(side="left", padx=(0, 12))

        info = ttk.Frame(frame)
        info.pack(side="left", fill="x", expand=True)

        ttk.Label(info, text="Current pixel:", font=("TkDefaultFont", 10)).pack(anchor="w")
        ttk.Label(info, textvariable=self.live_hex_var, font=("TkDefaultFont", 14, "bold")).pack(anchor="w")

        # Copy button
        copy_btn = ttk.Button(info, text="Copy current", command=self.copy_current_hex)
        copy_btn.pack(anchor="w", pady=(8, 0))

        # Control buttons
        controls = ttk.Frame(root)
        controls.pack(fill="x", padx=12, pady=(0, 10))

        self.pick_btn = ttk.Button(controls, text="🎯 Start Picking", command=self.toggle_picking_mode)
        self.pick_btn.pack(side="left", padx=(0, 8))

        ttk.Button(controls, text="Add current", command=self.add_color_from_live).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Clear all", command=self.clear_all).pack(side="left")

        # Instructions
        info_text = ttk.Label(
            root,
            text="When picking: move mouse to sample colors, click to add.\nDouble-click saved colors to copy.",
            font=("TkDefaultFont", 9),
            foreground="gray",
            justify="left"
        )
        info_text.pack(padx=12, pady=(0, 8))

        # Scrollable list
        list_frame = ttk.Frame(root)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.listbox = tk.Listbox(list_frame, height=15, font=("Consolas", 12), activestyle="none")
        self.listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

        self.listbox.bind("<Double-Button-1>", self.on_listbox_double_click)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def toggle_picking_mode(self):
        self.picking_mode = not self.picking_mode
        if self.picking_mode:
            self.pick_btn.config(text="🎯 Stop Picking")
            self.picker.start_listening()
        else:
            self.pick_btn.config(text="🎯 Start Picking")
            self.picker.stop_listening()

    def update_live_color(self, hex_value):
        self.live_hex_var.set(hex_value)
        try:
            self.live_color_box.configure(bg=hex_value)
        except tk.TclError:
            pass

    def add_color(self, hex_value):
        cleaned = normalize_hex(hex_value)
        if not cleaned:
            return
        if cleaned not in self.color_list:
            self.color_list.append(cleaned)
            self.listbox.insert(tk.END, cleaned)
            self.listbox.itemconfig(self.listbox.size() - 1, bg=cleaned, fg="white")

    def add_color_from_live(self):
        self.add_color(self.live_hex_var.get())

    def clear_all(self):
        self.color_list.clear()
        self.listbox.delete(0, tk.END)

    def copy_current_hex(self):
        current = self.live_hex_var.get()
        pyperclip.copy(current)
        print(f"Copied: {current}")

    def on_listbox_double_click(self, event):
        idx = self.listbox.curselection()
        if not idx:
            return
        value = self.listbox.get(idx)
        pyperclip.copy(value)
        print(f"Copied: {value}")

    def on_close(self):
        self.picker.stop_listening()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ColorPickerUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
