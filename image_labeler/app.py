import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk


# -----------------------------
# Configuration
# -----------------------------

IMAGE_DIR = Path("./data/train/images")
LABEL_DIR = Path("./data/train/labels")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

DEFAULT_SCHEMA = {
    "merchant": "",
    "address": "",
    "items": [
        {
        "item": "",
        "qty": 0,
        "cost": 0
        }
    ],
    "total": 0,
    "tax": 0,
}


# -----------------------------
# Main application
# -----------------------------

class ImageLabeler:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Labeler")
        self.root.geometry("1200x750")

        LABEL_DIR.mkdir(parents=True, exist_ok=True)

        self.images = sorted(
            p for p in IMAGE_DIR.iterdir()
            if p.suffix.lower() in IMAGE_EXTENSIONS
        )

        self.index = 0

        self.build_ui()
        self.show_image()

    def build_ui(self):
        self.root.geometry("1200x750")

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(main_frame, padding=(0, 0, 10, 0))
        left_panel.grid(row=0, column=0, sticky="nsew")

        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=0, column=1, sticky="nsew")

        # Image display on the left
        self.image_label = ttk.Label(left_panel, anchor="center")
        self.image_label.pack(fill="both", expand=True)

        jump_frame = ttk.Frame(left_panel)
        jump_frame.pack(fill="x", pady=(8, 0))

        ttk.Label(jump_frame, text="Image #:").pack(side="left")
        self.image_jump_var = tk.StringVar()
        self.image_jump_entry = ttk.Entry(jump_frame, textvariable=self.image_jump_var, width=8)
        self.image_jump_entry.pack(side="left", padx=(6, 8))

        ttk.Button(jump_frame, text="Go", command=self.jump_to_image).pack(side="left")

        # Structured text schema on the right
        ttk.Label(
            right_panel,
            text="Receipt schema",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        self.label_entry = tk.Text(
            right_panel,
            width=40,
            height=20,
            wrap="word",
            padx=8,
            pady=8,
            font=("Segoe UI", 11),
        )
        self.label_entry.pack(fill="both", expand=True)

        button_frame = ttk.Frame(right_panel)
        button_frame.pack(fill="x", pady=(12, 0))

        ttk.Button(
            button_frame,
            text="← Previous",
            command=self.previous_image,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            button_frame,
            text="Format JSON",
            command=self.format_json,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            button_frame,
            text="Save & Next →",
            command=self.save_and_next,
        ).pack(side="left")

        self.status_label = ttk.Label(self.root)
        self.status_label.pack(pady=(0, 8))

    def default_schema_text(self):
        return json.dumps(DEFAULT_SCHEMA, indent=4, ensure_ascii=False)

    def show_image(self):
        if not self.images:
            self.status_label.config(text="No images found.")
            return

        image_path = self.images[self.index]

        image = Image.open(image_path)
        image.thumbnail((900, 600))
        self.tk_image = ImageTk.PhotoImage(image)
        self.image_label.config(image=self.tk_image)

        self.status_label.config(
            text=f"{self.index + 1} / {len(self.images)}    {image_path.name}"
        )
        self.image_jump_var.set(str(self.index + 1))

        label_path = LABEL_DIR / f"{image_path.stem}.json"
        self.label_entry.delete("1.0", tk.END)

        if label_path.exists():
            with open(label_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.label_entry.insert("1.0", json.dumps(data, indent=4, ensure_ascii=False))
        else:
            self.label_entry.insert("1.0", self.default_schema_text())

    def save(self):
        image_path = self.images[self.index]
        label_path = LABEL_DIR / f"{image_path.stem}.json"

        raw_text = self.label_entry.get("1.0", tk.END).strip()

        if not raw_text:
            self.label_entry.insert("1.0", self.default_schema_text())
            return

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            data = {"raw_text": raw_text}

        with open(label_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def save_and_next(self):
        self.save()

        if self.index < len(self.images) - 1:
            self.index += 1
            self.show_image()

    def previous_image(self):
        if self.index > 0:
            self.index -= 1
            self.show_image()

    def jump_to_image(self):
        try:
            index = int(self.image_jump_var.get()) - 1
            if 0 <= index < len(self.images):
                self.index = index
                self.show_image()
        except ValueError:
            pass

    def format_json(self):
        raw_text = self.label_entry.get("1.0", tk.END).strip()

        if not raw_text:
            self.label_entry.insert("1.0", self.default_schema_text())
            return

        try:
            data = json.loads(raw_text)
            formatted = json.dumps(data, indent=4, ensure_ascii=False)
            self.label_entry.delete("1.0", tk.END)
            self.label_entry.insert("1.0", formatted)
            self.status_label.config(text="JSON formatted successfully.")
        except json.JSONDecodeError as e:
            self.status_label.config(text=f"Invalid JSON: {e.msg} (line {e.lineno}, col {e.colno})")


# -----------------------------
# Start application
# -----------------------------

root = tk.Tk()
app = ImageLabeler(root)
root.mainloop()