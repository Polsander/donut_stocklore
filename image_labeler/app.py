import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import re
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

# Zoom / pan tuning
ZOOM_STEP = 1.15          # multiplier applied per wheel tick / button click
MAX_ZOOM = 10.0           # hard ceiling, further limited per-image below
MIN_ZOOM = 0.05
MAX_RENDER_DIM = 4500     # cap on the rendered width/height in pixels - keeps
                          # resizing fast and memory bounded no matter how far
                          # the user zooms in
WHEEL_DEBOUNCE_MS = 15    # coalesces bursts of wheel events (trackpads can
                          # fire dozens per second) into a single redraw

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # older Pillow versions
    RESAMPLE = Image.LANCZOS


# -----------------------------
# Main application
# -----------------------------

class ImageLabeler:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Labeler")
        self.root.geometry("1200x750")

        LABEL_DIR.mkdir(parents=True, exist_ok=True)

        def _natural_key(p: Path):
            parts = re.split(r"(\d+)", p.name)
            key = []
            for part in parts:
                if part.isdigit():
                    key.append(int(part))
                else:
                    key.append(part.lower())
            return key

        self.images = sorted(
            (p for p in IMAGE_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS),
            key=_natural_key,
        )

        self.index = 0
        self.current_image = None
        self.canvas_image_id = None
        self.tk_image = None

        self.zoom = 1.0
        self.min_zoom = MIN_ZOOM
        self.max_zoom = MAX_ZOOM
        self.img_offset = (0, 0)
        self.scroll_size = (0, 0)
        self._render_size = (0, 0)
        self.default_canvas_size = (900, 600)

        self._zoom_job = None
        self._pending_zoom = None
        self._pending_cursor = (0, 0)
        self._configure_job = None

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

        # Image display on the left (canvas with scrollbars for zoom/pan)
        left_panel.rowconfigure(0, weight=1)
        left_panel.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            left_panel,
            background="#222",
            highlightthickness=1,
            highlightbackground="#444",
            cursor="fleur",
        )
        self.v_scroll = ttk.Scrollbar(left_panel, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(left_panel, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        # mouse wheel zoom (debounced, zooms toward the cursor)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

        # click-and-drag panning
        self.canvas.bind("<ButtonPress-1>", self._pan_start)
        self.canvas.bind("<B1-Motion>", self._pan_move)

        # double-click resets to fit-to-window
        self.canvas.bind("<Double-Button-1>", lambda e: self.reset_view())

        # keep the image centered when the window/panel is resized
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Zoom controls row (centered under the image)
        zoom_frame = ttk.Frame(left_panel)
        zoom_frame.grid(row=2, column=0, columnspan=2, pady=(8, 0), sticky="ew")
        zoom_button_row = ttk.Frame(zoom_frame)
        zoom_button_row.pack()
        ttk.Button(zoom_button_row, text="Zoom −", command=self.zoom_out).pack(side="left", padx=6)
        ttk.Button(zoom_button_row, text="Fit", command=self.reset_view).pack(side="left", padx=6)
        ttk.Button(zoom_button_row, text="Zoom +", command=self.zoom_in).pack(side="left")

        hint = ttk.Label(
            left_panel,
            text="Scroll to zoom  ·  drag to pan  ·  double-click to reset",
            foreground="#888",
        )
        hint.grid(row=4, column=0, columnspan=2, pady=(4, 0))

        jump_frame = ttk.Frame(left_panel)
        jump_frame.grid(row=3, column=0, columnspan=2, pady=(8, 0), sticky="ew")

        ttk.Label(jump_frame, text="Image #:").pack(side="left")
        self.image_jump_var = tk.StringVar()
        self.image_jump_entry = ttk.Entry(jump_frame, textvariable=self.image_jump_var, width=8)
        self.image_jump_entry.pack(side="left", padx=(6, 8))
        self.image_jump_entry.bind("<Return>", lambda e: self.jump_to_image())

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

    # -----------------------------
    # Image loading / display
    # -----------------------------

    def show_image(self):
        if not self.images:
            self.status_label.config(text="No images found.")
            return

        # cancel any pending debounced work left over from the previous image
        if self._zoom_job is not None:
            self.root.after_cancel(self._zoom_job)
            self._zoom_job = None
        if self._configure_job is not None:
            self.root.after_cancel(self._configure_job)
            self._configure_job = None
        self._pending_zoom = None

        image_path = self.images[self.index]

        image = Image.open(image_path).convert("RGBA")
        self.current_image = image

        self.canvas.delete("all")
        self.canvas_image_id = None
        self.tk_image = None
        self._render_size = (0, 0)

        cw, ch = self._get_canvas_size()
        fit_scale = min(cw / image.width, ch / image.height, 1.0)

        # bound zoom so we never ask PIL to render an absurdly large image
        per_image_cap = min(MAX_ZOOM, MAX_RENDER_DIM / image.width, MAX_RENDER_DIM / image.height)
        self.max_zoom = max(fit_scale, per_image_cap)
        self.min_zoom = MIN_ZOOM

        self.zoom = fit_scale
        self.render_image()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

        self._update_status()
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

    # -----------------------------
    # Canvas geometry helpers
    # -----------------------------

    def _get_canvas_size(self):
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1 or h <= 1:
            w, h = self.default_canvas_size
        return w, h

    def _resize_and_cache(self):
        """Resize the source image to the current zoom level (once)."""
        w = max(1, int(self.current_image.width * self.zoom))
        h = max(1, int(self.current_image.height * self.zoom))
        resized = self.current_image.resize((w, h), RESAMPLE)
        self.tk_image = ImageTk.PhotoImage(resized)
        self._render_size = (w, h)

    def _position_on_canvas(self):
        """Place the cached PhotoImage on the canvas, centering it when it
        fits inside the viewport instead of leaving it pinned in the corner."""
        if self.tk_image is None:
            return

        cw, ch = self._get_canvas_size()
        w, h = self._render_size

        ox = max(0, (cw - w) // 2)
        oy = max(0, (ch - h) // 2)
        self.img_offset = (ox, oy)

        if self.canvas_image_id is None:
            self.canvas_image_id = self.canvas.create_image(ox, oy, anchor="nw", image=self.tk_image)
        else:
            self.canvas.itemconfig(self.canvas_image_id, image=self.tk_image)
            self.canvas.coords(self.canvas_image_id, ox, oy)

        scroll_w = max(cw, w + ox)
        scroll_h = max(ch, h + oy)
        self.scroll_size = (scroll_w, scroll_h)
        self.canvas.config(scrollregion=(0, 0, scroll_w, scroll_h))

    def render_image(self):
        if self.current_image is None:
            return
        self._resize_and_cache()
        self._position_on_canvas()

    def _on_canvas_configure(self, event):
        # window/pane resized: recenter the already-rendered image instead
        # of redoing the (comparatively expensive) PIL resize
        if self._configure_job is not None:
            self.root.after_cancel(self._configure_job)
        self._configure_job = self.root.after(100, self._position_on_canvas)

    # -----------------------------
    # Zoom
    # -----------------------------

    def zoom_at(self, cx, cy, new_zoom):
        """Zoom so the image point currently under (cx, cy) stays under the
        cursor, instead of the view jumping back to the top-left corner."""
        new_zoom = max(self.min_zoom, min(new_zoom, self.max_zoom))
        if self.current_image is None or abs(new_zoom - self.zoom) < 1e-6:
            return

        canvas_x = self.canvas.canvasx(cx)
        canvas_y = self.canvas.canvasy(cy)
        ox, oy = self.img_offset
        img_x = (canvas_x - ox) / self.zoom
        img_y = (canvas_y - oy) / self.zoom

        self.zoom = new_zoom
        self.render_image()

        new_ox, new_oy = self.img_offset
        target_x = img_x * self.zoom + new_ox
        target_y = img_y * self.zoom + new_oy

        scroll_w, scroll_h = self.scroll_size
        if scroll_w > 0:
            self.canvas.xview_moveto(max(0.0, min(1.0, (target_x - cx) / scroll_w)))
        if scroll_h > 0:
            self.canvas.yview_moveto(max(0.0, min(1.0, (target_y - cy) / scroll_h)))

        self._update_status()

    def zoom_in(self):
        cw, ch = self._get_canvas_size()
        self.zoom_at(cw / 2, ch / 2, self.zoom * ZOOM_STEP)

    def zoom_out(self):
        cw, ch = self._get_canvas_size()
        self.zoom_at(cw / 2, ch / 2, self.zoom / ZOOM_STEP)

    def reset_view(self):
        if self.current_image is None:
            return
        cw, ch = self._get_canvas_size()
        fit = min(cw / self.current_image.width, ch / self.current_image.height, 1.0)
        self.zoom = max(self.min_zoom, min(fit, self.max_zoom))
        self.render_image()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self._update_status()

    def _on_mousewheel(self, event):
        if self.current_image is None:
            return

        if getattr(event, "num", None) == 4:
            factor = ZOOM_STEP
        elif getattr(event, "num", None) == 5:
            factor = 1 / ZOOM_STEP
        else:
            factor = ZOOM_STEP if getattr(event, "delta", 0) > 0 else 1 / ZOOM_STEP

        # only remember the *latest* requested zoom + cursor position -
        # collapsing a fast burst of wheel events into a single redraw is
        # what stops the UI from freezing on trackpads / fast scrolling
        self._pending_zoom = (self._pending_zoom or self.zoom) * factor
        self._pending_cursor = (event.x, event.y)

        if self._zoom_job is not None:
            self.root.after_cancel(self._zoom_job)
        self._zoom_job = self.root.after(WHEEL_DEBOUNCE_MS, self._apply_pending_zoom)

    def _apply_pending_zoom(self):
        self._zoom_job = None
        if self._pending_zoom is None:
            return
        cx, cy = self._pending_cursor
        self.zoom_at(cx, cy, self._pending_zoom)
        self._pending_zoom = None

    # -----------------------------
    # Pan
    # -----------------------------

    def _pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _pan_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    # -----------------------------
    # Status / navigation
    # -----------------------------

    def _update_status(self):
        if not self.images:
            return
        image_path = self.images[self.index]
        self.status_label.config(
            text=f"{self.index + 1} / {len(self.images)}    {image_path.name}    Zoom: {int(self.zoom * 100)}%"
        )

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

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageLabeler(root)
    root.mainloop()