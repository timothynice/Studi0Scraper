#!/usr/bin/env python3
"""Desktop UI for running the website crawler with appearance/accent theming."""

from __future__ import annotations

import json
import math
import queue
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw

from site_scraper import crawl_site

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("dark-blue")

# Neutral UI tokens (light, dark)
APP_BG = ("#F2F3F5", "#121212")
CARD_BG = ("#FFFFFF", "#1A1A1A")
CARD_BORDER = ("#D8DBE2", "#2B2B2B")
INPUT_BG = ("#FFFFFF", "#242424")
INPUT_BORDER = ("#C9CED8", "#3A3A3A")
LOG_BG = ("#F7F8FA", "#161616")
TEXT_PRIMARY = ("#161A22", "#F5F5F5")
TEXT_MUTED = ("#626B7F", "#B3B3B3")
SECONDARY_BG = ("#E8EAF0", "#2C2C2C")
SECONDARY_HOVER = ("#DCE0E8", "#383838")
DISABLED_BG = ("#D9DDE6", "#242424")
DISABLED_TEXT = ("#8A92A3", "#747D8D")
SCROLLBAR_BG = ("#B5BCCC", "#3A414E")
SCROLLBAR_HOVER = ("#98A1B3", "#4A5261")

CONTROL_HEIGHT = 40
BUTTON_RADIUS = 12
ENTRY_RADIUS = 10
CARD_RADIUS = 14
THEME_SETTINGS_PATH = Path.home() / ".studi0scraper-theme.json"
LEGACY_THEME_SETTINGS_PATH = Path.home() / ".webscraper-theme.json"
TITLE_LOGO_LIGHT_FILE = "studi0scraper-title-light.png"
TITLE_LOGO_DARK_FILE = "studi0scraper-title-dark.png"


@dataclass(frozen=True)
class AccentPreset:
    name: str
    dark_hex: str
    light_hex: str


ACCENT_PRESETS: tuple[AccentPreset, ...] = (
    AccentPreset("Solar Yellow", "FFFF82", "9B9B71"),
    AccentPreset("Amber", "FFB44C", "A17A4E"),
    AccentPreset("Mint", "58D6A3", "4D8D77"),
    AccentPreset("Ocean", "5BA8FF", "4E729B"),
    AccentPreset("Coral", "FF7F67", "A4685B"),
    AccentPreset("Rose", "FF6FA8", "A56583"),
    AccentPreset("Violet", "A88CFF", "7369A4"),
    AccentPreset("Slate Gray", "C2C7D0", "7C818B"),
)
ACCENT_PRESET_MAP = {preset.name: preset for preset in ACCENT_PRESETS}
APPEARANCE_OPTIONS = ("System", "Light", "Dark")
EDIT_HISTORY_WIDGET_CLASSES = frozenset({"Text", "Entry", "TEntry", "Spinbox", "TSpinbox"})
UNDO_SHORTCUTS = ("<Command-z>", "<Control-z>")
REDO_SHORTCUTS = (
    "<Command-Shift-z>",
    "<Command-Shift-Z>",
    "<Command-y>",
    "<Control-Shift-z>",
    "<Control-Shift-Z>",
    "<Control-y>",
)


def supports_edit_history(widget: object) -> bool:
    if not isinstance(widget, tk.Misc):
        return False
    try:
        return widget.winfo_class() in EDIT_HISTORY_WIDGET_CLASSES
    except tk.TclError:
        return False


def dispatch_edit_history_event(widget: object, event_name: str) -> bool:
    if not supports_edit_history(widget):
        return False
    target = widget
    try:
        target.event_generate(event_name)
    except tk.TclError:
        return False
    return True


def normalize_hex(value: str) -> str | None:
    text = value.strip().upper()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return None
    if any(ch not in "0123456789ABCDEF" for ch in text):
        return None
    return text


def hex_to_rgb(hex_value: str) -> tuple[float, float, float]:
    value = normalize_hex(hex_value) or "000000"
    number = int(value, 16)
    return ((number >> 16 & 0xFF) / 255.0, (number >> 8 & 0xFF) / 255.0, (number & 0xFF) / 255.0)


def rgb_to_hex(red: float, green: float, blue: float) -> str:
    r = int(round(min(max(red, 0.0), 1.0) * 255))
    g = int(round(min(max(green, 0.0), 1.0) * 255))
    b = int(round(min(max(blue, 0.0), 1.0) * 255))
    return f"{r:02X}{g:02X}{b:02X}"


def hue_component(red: float, green: float, blue: float, max_value: float, delta: float) -> float:
    if delta <= 0:
        return 0.0
    if max_value == red:
        hue = ((green - blue) / delta) % 6.0
    elif max_value == green:
        hue = ((blue - red) / delta) + 2.0
    else:
        hue = ((red - green) / delta) + 4.0
    normalized = hue / 6.0
    return normalized if normalized >= 0 else normalized + 1.0


def rgb_from_hsb(hue: float, saturation: float, brightness: float) -> tuple[float, float, float]:
    h = (hue * 6.0) % 6.0
    c = brightness * saturation
    x = c * (1.0 - abs((h % 2.0) - 1.0))
    m = brightness - c
    if 0.0 <= h < 1.0:
        values = (c, x, 0.0)
    elif 1.0 <= h < 2.0:
        values = (x, c, 0.0)
    elif 2.0 <= h < 3.0:
        values = (0.0, c, x)
    elif 3.0 <= h < 4.0:
        values = (0.0, x, c)
    elif 4.0 <= h < 5.0:
        values = (x, 0.0, c)
    else:
        values = (c, 0.0, x)
    return (values[0] + m, values[1] + m, values[2] + m)


def toned_down_hex_for_light_mode(dark_hex: str) -> str:
    red, green, blue = hex_to_rgb(dark_hex)
    max_value = max(red, green, blue)
    min_value = min(red, green, blue)
    delta = max_value - min_value
    saturation = 0.0 if max_value == 0 else delta / max_value
    brightness = max_value

    toned_saturation = saturation * 0.55
    toned_brightness = brightness * 0.62
    hue = hue_component(red, green, blue, max_value, delta)
    r, g, b = rgb_from_hsb(hue, toned_saturation, toned_brightness)
    return rgb_to_hex(r, g, b)


def adjust_hex_brightness(hex_value: str, factor: float) -> str:
    red, green, blue = hex_to_rgb(hex_value)
    return rgb_to_hex(red * factor, green * factor, blue * factor)


def hex_to_rgba_tuple(hex_value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    normalized = normalize_hex(hex_value) or "000000"
    number = int(normalized, 16)
    return (number >> 16 & 0xFF, number >> 8 & 0xFF, number & 0xFF, alpha)


class ScraperApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Studi0Scraper")
        self.geometry("980x700")
        self.minsize(860, 620)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.running = False
        self.stop_event = threading.Event()
        self.form_widgets: list[ctk.CTkBaseClass] = []
        self.theme_dropdown: ctk.CTkFrame | None = None
        self.theme_dropdown_accent_rows: dict[str, ctk.CTkButton] = {}
        self.theme_dropdown_appearance_rows: dict[str, ctk.CTkButton] = {}
        self.theme_dropdown_accent_base_text: dict[str, str | tuple[str, str]] = {}
        self.theme_dropdown_width = 252
        self.gear_icon: ctk.CTkImage | None = None
        self.gear_icon_loaded = False
        self.title_logo: ctk.CTkImage | None = None
        self.title_logo_loaded = False
        self.root_frame: ctk.CTkFrame | None = None

        self.url_var = tk.StringVar(value="https://www.timothynice.com")
        self.output_var = tk.StringVar(value=str(Path.home() / "site-export"))
        self.max_pages_var = tk.StringVar(value="500")
        self.delay_var = tk.StringVar(value="0.8")
        self.timeout_var = tk.StringVar(value="20")
        self.include_subdomains_var = tk.BooleanVar(value=False)
        self.ignore_robots_var = tk.BooleanVar(value=False)
        self.insecure_var = tk.BooleanVar(value=False)
        self.capture_images_var = tk.BooleanVar(value=True)
        self.capture_content_var = tk.BooleanVar(value=True)
        self.advanced_open = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")

        settings = self._load_theme_settings()
        self.appearance_var = tk.StringVar(value=settings["appearance"])
        self.accent_mode = settings["accent_mode"]
        self.accent_preset = settings["accent_preset"]
        self.custom_accent_hex = settings["custom_accent_hex"]

        self._apply_appearance()
        self._resolve_accent_colors()
        self._load_gear_icon()
        self._load_title_logo()
        self._build_ui()
        self._bind_shortcuts()
        self.after(120, self._pump_logs)

    def _load_theme_settings(self) -> dict[str, str]:
        defaults = {
            "appearance": "System",
            "accent_mode": "preset",
            "accent_preset": "Solar Yellow",
            "custom_accent_hex": "FFFF82",
        }
        settings_path = THEME_SETTINGS_PATH if THEME_SETTINGS_PATH.exists() else LEGACY_THEME_SETTINGS_PATH
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception:
            return defaults

        appearance = data.get("appearance", defaults["appearance"])
        if appearance not in APPEARANCE_OPTIONS:
            appearance = defaults["appearance"]

        accent_mode = data.get("accent_mode", defaults["accent_mode"])
        if accent_mode not in {"preset", "custom"}:
            accent_mode = defaults["accent_mode"]

        accent_preset = data.get("accent_preset", defaults["accent_preset"])
        if accent_preset not in ACCENT_PRESET_MAP:
            accent_preset = defaults["accent_preset"]

        custom = normalize_hex(str(data.get("custom_accent_hex", defaults["custom_accent_hex"])))
        if custom is None:
            custom = defaults["custom_accent_hex"]

        return {
            "appearance": appearance,
            "accent_mode": accent_mode,
            "accent_preset": accent_preset,
            "custom_accent_hex": custom,
        }

    def _save_theme_settings(self) -> None:
        payload = {
            "appearance": self.appearance_var.get(),
            "accent_mode": self.accent_mode,
            "accent_preset": self.accent_preset,
            "custom_accent_hex": self.custom_accent_hex,
        }
        try:
            THEME_SETTINGS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _apply_appearance(self) -> None:
        choice = self.appearance_var.get().strip().lower()
        if choice not in {"system", "light", "dark"}:
            choice = "system"
        ctk.set_appearance_mode(choice)

    def _resolve_accent_colors(self) -> None:
        if self.accent_mode == "preset":
            preset = ACCENT_PRESET_MAP.get(self.accent_preset, ACCENT_PRESET_MAP["Solar Yellow"])
            light_hex = preset.light_hex
            dark_hex = preset.dark_hex
        else:
            dark_hex = normalize_hex(self.custom_accent_hex) or "FFFF82"
            light_hex = toned_down_hex_for_light_mode(dark_hex)

        self.accent_fg = (f"#{light_hex}", f"#{dark_hex}")
        self.accent_hover = (
            f"#{adjust_hex_brightness(light_hex, 0.9)}",
            f"#{adjust_hex_brightness(dark_hex, 0.9)}",
        )

    def _asset_search_paths(self) -> list[Path]:
        base_paths: list[Path] = []
        script_base = Path(__file__).resolve().parent
        base_paths.append(script_base)
        base_paths.append(script_base.parent)

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            meipass_path = Path(meipass)
            base_paths.extend(
                [
                    meipass_path,
                    meipass_path.parent,
                    meipass_path.parent / "Resources",
                    meipass_path.parent.parent / "Resources",
                ]
            )

        exe_parent = Path(sys.executable).resolve().parent
        base_paths.extend([exe_parent, exe_parent.parent, exe_parent.parent / "Resources"])
        return list(dict.fromkeys(base_paths))

    def _find_asset_pair(self, dark_filename: str, light_filename: str) -> tuple[Path | None, Path | None]:
        dark_path: Path | None = None
        light_path: Path | None = None
        for base in self._asset_search_paths():
            candidate_dark = base / "assets" / dark_filename
            candidate_light = base / "assets" / light_filename
            if candidate_dark.exists() and candidate_light.exists():
                dark_path = candidate_dark
                light_path = candidate_light
                break
        return dark_path, light_path

    def _load_gear_icon(self) -> None:
        dark_path, light_path = self._find_asset_pair("gear-outline-dark.png", "gear-outline-light.png")

        light: Image.Image | None = None
        dark: Image.Image | None = None
        if dark_path is not None and light_path is not None:
            try:
                light = Image.open(light_path).convert("RGBA")
                dark = Image.open(dark_path).convert("RGBA")
            except Exception:
                light = None
                dark = None

        if light is None or dark is None:
            light = self._draw_gear_icon("1E222A")
            dark = self._draw_gear_icon("F4F6FA")

        self.gear_icon = ctk.CTkImage(light_image=light, dark_image=dark, size=(24, 24))
        self.gear_icon_loaded = True

    def _load_title_logo(self) -> None:
        dark_path, light_path = self._find_asset_pair(TITLE_LOGO_DARK_FILE, TITLE_LOGO_LIGHT_FILE)

        light: Image.Image | None = None
        dark: Image.Image | None = None
        if dark_path is not None and light_path is not None:
            try:
                light = Image.open(light_path).convert("RGBA")
                dark = Image.open(dark_path).convert("RGBA")
            except Exception:
                light = None
                dark = None

        if light is None or dark is None:
            self.title_logo = None
            self.title_logo_loaded = False
            return

        ratio = light.width / max(1, light.height)
        logo_height = 24
        logo_width = int(round(logo_height * ratio))
        max_width = 520
        if logo_width > max_width:
            logo_width = max_width
            logo_height = int(round(logo_width / ratio))

        self.title_logo = ctk.CTkImage(light_image=light, dark_image=dark, size=(logo_width, logo_height))
        self.title_logo_loaded = True

    def _draw_gear_icon(self, hex_color: str, size: int = 128) -> Image.Image:
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = hex_to_rgba_tuple(hex_color)

        center = size / 2.0
        outer_radius = size * 0.28
        inner_radius = size * 0.14
        tooth_start = size * 0.30
        tooth_end = size * 0.42
        stroke = max(3, int(round(size * 0.07)))

        for idx in range(8):
            angle = (math.pi * 2 * idx) / 8.0
            x1 = center + math.cos(angle) * tooth_start
            y1 = center + math.sin(angle) * tooth_start
            x2 = center + math.cos(angle) * tooth_end
            y2 = center + math.sin(angle) * tooth_end
            draw.line((x1, y1, x2, y2), fill=color, width=stroke)

        draw.ellipse(
            (
                center - outer_radius,
                center - outer_radius,
                center + outer_radius,
                center + outer_radius,
            ),
            outline=color,
            width=stroke,
        )
        draw.ellipse(
            (
                center - inner_radius,
                center - inner_radius,
                center + inner_radius,
                center + inner_radius,
            ),
            outline=color,
            width=stroke,
        )
        return image

    def _build_ui(self) -> None:
        if self.root_frame is not None:
            self.root_frame.destroy()

        self.configure(fg_color=APP_BG)
        self.form_widgets.clear()

        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=18, pady=16)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(3, weight=1)
        self.root_frame = root

        header = ctk.CTkFrame(root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.grid_columnconfigure(0, weight=1)
        if self.title_logo_loaded and self.title_logo is not None:
            ctk.CTkLabel(header, text="", image=self.title_logo).grid(row=0, column=0, sticky="w")
        else:
            ctk.CTkLabel(
                header,
                text="Studi0Scraper",
                text_color=self.accent_fg,
                font=ctk.CTkFont(size=28, weight="bold"),
            ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Export site content and images with a controlled crawl.",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=14),
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.theme_button = self._button(
            header,
            "" if self.gear_icon_loaded else "\u2699",
            self._toggle_theme_dropdown,
            variant="secondary",
            width=44,
            height=44,
            image=self.gear_icon,
            font_size=22,
            font_weight="normal",
        )
        self.theme_button.grid(row=0, column=1, rowspan=2, sticky="e")

        setup_card, setup_body = self._create_section(root, row=1, title="Crawl Setup", pady=(0, 12))
        setup_card.grid_columnconfigure(0, weight=1)
        setup_body.grid_columnconfigure(0, weight=1)
        setup_body.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            setup_body,
            text="Source URL",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.url_entry = self._entry(setup_body, self.url_var)
        self.url_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        self.form_widgets.append(self.url_entry)

        ctk.CTkLabel(
            setup_body,
            text="Destination Folder",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=2, column=0, columnspan=2, sticky="w")

        self.output_entry = self._entry(setup_body, self.output_var)
        self.output_entry.grid(row=3, column=0, sticky="ew", pady=(4, 12))
        self.form_widgets.append(self.output_entry)

        self.browse_btn = self._button(setup_body, "Browse", self._pick_output_folder, variant="secondary")
        self.browse_btn.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=(4, 12))
        self.form_widgets.append(self.browse_btn)

        capture_frame = ctk.CTkFrame(setup_body, fg_color="transparent")
        capture_frame.grid(row=4, column=0, columnspan=2, sticky="w")
        self.capture_images_check = self._checkbox(
            capture_frame,
            "Capture images",
            self.capture_images_var,
            command=lambda: self._on_capture_toggle("images"),
        )
        self.capture_images_check.grid(row=0, column=0, sticky="w")
        self.form_widgets.append(self.capture_images_check)

        self.capture_content_check = self._checkbox(
            capture_frame,
            "Capture content",
            self.capture_content_var,
            command=lambda: self._on_capture_toggle("content"),
        )
        self.capture_content_check.grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.form_widgets.append(self.capture_content_check)

        self.advanced_btn = self._button(
            setup_body,
            "Show Advanced Settings",
            self._toggle_advanced,
            variant="secondary",
        )
        self.advanced_btn.grid(row=5, column=0, sticky="w", pady=(10, 0))
        self.form_widgets.append(self.advanced_btn)

        self.advanced_panel = ctk.CTkFrame(setup_body, fg_color="transparent")
        self.advanced_panel.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.advanced_panel.grid_columnconfigure(0, weight=1)
        self.advanced_panel.grid_columnconfigure(1, weight=1)
        self.advanced_panel.grid_columnconfigure(2, weight=1)
        if self.advanced_open.get():
            self.advanced_btn.configure(text="Hide Advanced Settings")
        else:
            self.advanced_panel.grid_remove()

        self._labeled_small_entry(self.advanced_panel, "Max Pages", self.max_pages_var, 0)
        self._labeled_small_entry(self.advanced_panel, "Delay (sec)", self.delay_var, 1)
        self._labeled_small_entry(self.advanced_panel, "Timeout (sec)", self.timeout_var, 2)

        checks = ctk.CTkFrame(self.advanced_panel, fg_color="transparent")
        checks.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.include_subdomains_check = self._checkbox(checks, "Include subdomains", self.include_subdomains_var)
        self.include_subdomains_check.grid(row=0, column=0, sticky="w")
        self.form_widgets.append(self.include_subdomains_check)

        self.ignore_robots_check = self._checkbox(checks, "Ignore robots.txt", self.ignore_robots_var)
        self.ignore_robots_check.grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.form_widgets.append(self.ignore_robots_check)

        self.insecure_check = self._checkbox(checks, "Insecure TLS", self.insecure_var)
        self.insecure_check.grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.form_widgets.append(self.insecure_check)

        run_card, run_body = self._create_section(root, row=2, title=None, pady=(0, 12))
        run_card.grid_columnconfigure(0, weight=1)
        run_body.grid_columnconfigure(2, weight=1)

        self.start_btn = self._button(run_body, "\u25b6 Start Crawl", self._start, variant="primary")
        self.start_btn.grid(row=0, column=0, sticky="w")
        self.stop_btn = self._button(run_body, "\u25a0 Stop Crawl", self._stop, variant="secondary")
        self.stop_btn.grid(row=0, column=0, sticky="w")
        self.stop_btn.grid_remove()

        self.open_btn = self._button(run_body, "Open Output Folder", self._open_output, variant="secondary")
        self.open_btn.grid(row=0, column=1, sticky="w", padx=(10, 0))

        status_row = ctk.CTkFrame(run_body, fg_color="transparent")
        status_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        status_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            status_row,
            textvariable=self.status_var,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.progress = ctk.CTkProgressBar(
            status_row,
            mode="indeterminate",
            height=8,
            corner_radius=8,
            fg_color=INPUT_BG,
            progress_color=self.accent_fg,
            border_width=0,
        )
        self.progress.grid(row=0, column=1, sticky="e")
        self.progress.grid_remove()

        activity_card, activity_body = self._create_section(root, row=3, title="Activity")
        activity_body.grid_columnconfigure(0, weight=1)
        activity_body.grid_rowconfigure(1, weight=1)

        activity_actions = ctk.CTkFrame(activity_body, fg_color="transparent")
        activity_actions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        activity_actions.grid_columnconfigure(0, weight=1)
        self.clear_btn = self._button(activity_actions, "Clear Activity", self._clear_log, variant="secondary")
        self.clear_btn.grid(row=0, column=1, sticky="e")

        self.log = ctk.CTkTextbox(
            activity_body,
            wrap="word",
            fg_color=LOG_BG,
            border_width=1,
            border_color=CARD_BORDER,
            corner_radius=12,
            text_color=TEXT_PRIMARY,
            scrollbar_button_color=SCROLLBAR_BG,
            scrollbar_button_hover_color=SCROLLBAR_HOVER,
            font=ctk.CTkFont(family="Menlo", size=12),
        )
        self.log.grid(row=1, column=0, sticky="nsew")
        self.log.configure(state="disabled")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_running(self.running)

    def _create_section(
        self,
        parent: ctk.CTkFrame,
        row: int,
        title: str | None,
        pady: tuple[int, int] = (0, 0),
    ) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
            corner_radius=CARD_RADIUS,
        )
        card.grid(row=row, column=0, sticky="nsew", pady=pady)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        body = ctk.CTkFrame(card, fg_color="transparent")
        if title:
            ctk.CTkLabel(
                card,
                text=title,
                text_color=TEXT_PRIMARY,
                font=ctk.CTkFont(size=15, weight="bold"),
            ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))
            body.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
        else:
            body.grid(row=0, column=0, sticky="nsew", padx=14, pady=(12, 12))
        return card, body

    def _button(
        self,
        parent: ctk.CTkFrame,
        text: str,
        command: object,
        variant: str,
        width: int = 0,
        height: int = CONTROL_HEIGHT,
        font_size: int = 13,
        font_weight: str = "bold",
        image: ctk.CTkImage | None = None,
    ) -> ctk.CTkButton:
        if variant == "primary":
            fg_color = self.accent_fg
            hover_color = self.accent_hover
            text_color = ("#161A22", "#111111")
        else:
            fg_color = SECONDARY_BG
            hover_color = SECONDARY_HOVER
            text_color = TEXT_PRIMARY

        kwargs: dict[str, object] = {}
        if width > 0:
            kwargs["width"] = width

        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=height,
            corner_radius=BUTTON_RADIUS,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            text_color_disabled=DISABLED_TEXT,
            font=ctk.CTkFont(size=font_size, weight=font_weight),
            border_width=0,
            image=image,
            **kwargs,
        )

    def _entry(self, parent: ctk.CTkFrame, variable: tk.StringVar, width: int = 0) -> ctk.CTkEntry:
        kwargs: dict[str, object] = {}
        if width > 0:
            kwargs["width"] = width
        return ctk.CTkEntry(
            parent,
            textvariable=variable,
            height=CONTROL_HEIGHT,
            corner_radius=ENTRY_RADIUS,
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=13),
            **kwargs,
        )

    def _checkbox(
        self,
        parent: ctk.CTkFrame,
        text: str,
        variable: tk.BooleanVar,
        command: object | None = None,
    ) -> ctk.CTkCheckBox:
        return ctk.CTkCheckBox(
            parent,
            text=text,
            variable=variable,
            command=command,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=13),
            checkbox_width=20,
            checkbox_height=20,
            corner_radius=6,
            border_width=2,
            border_color=("#6E7585", "#5A6272"),
            fg_color=self.accent_fg,
            hover_color=self.accent_hover,
            checkmark_color=("#161A22", "#111111"),
        )

    def _labeled_small_entry(self, parent: ctk.CTkFrame, label: str, var: tk.StringVar, column: int) -> None:
        ctk.CTkLabel(
            parent,
            text=label,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=column, sticky="w", padx=(12 if column else 0, 0))

        entry = self._entry(parent, var, width=130)
        entry.grid(row=1, column=column, sticky="w", padx=(12 if column else 0, 0), pady=(4, 0))
        self.form_widgets.append(entry)

    def _bind_shortcuts(self) -> None:
        self.bind("<Command-r>", self._shortcut_toggle_run)
        self.bind("<Command-k>", self._shortcut_clear_log)
        self.bind("<Command-o>", self._shortcut_pick_output)
        for shortcut in UNDO_SHORTCUTS:
            self.bind_all(shortcut, self._shortcut_undo, add="+")
        for shortcut in REDO_SHORTCUTS:
            self.bind_all(shortcut, self._shortcut_redo, add="+")
        self.bind("<Escape>", self._shortcut_close_theme_dropdown)
        self.bind("<Button-1>", self._on_root_click, add="+")
        self.bind("<Configure>", self._on_window_configure, add="+")

    def _shortcut_toggle_run(self, _event: tk.Event) -> str:
        if self.running:
            self._stop()
        else:
            self._start()
        return "break"

    def _shortcut_clear_log(self, _event: tk.Event) -> str:
        self._clear_log()
        return "break"

    def _shortcut_pick_output(self, _event: tk.Event) -> str:
        self._pick_output_folder()
        return "break"

    def _dispatch_focus_history_event(self, event_name: str) -> bool:
        return dispatch_edit_history_event(self.focus_get(), event_name)

    def _shortcut_undo(self, _event: tk.Event) -> str | None:
        if self._dispatch_focus_history_event("<<Undo>>"):
            return "break"
        return None

    def _shortcut_redo(self, _event: tk.Event) -> str | None:
        if self._dispatch_focus_history_event("<<Redo>>"):
            return "break"
        return None

    def _shortcut_close_theme_dropdown(self, _event: tk.Event) -> str:
        self._close_theme_dropdown()
        return "break"

    def _widget_is_descendant(self, widget: tk.Misc | None, ancestor: tk.Misc | None) -> bool:
        if widget is None or ancestor is None:
            return False
        current: tk.Misc | None = widget
        while current is not None:
            if current == ancestor:
                return True
            current = current.master
        return False

    def _on_root_click(self, event: tk.Event) -> None:
        if self.theme_dropdown is None:
            return
        widget = event.widget if isinstance(event.widget, tk.Misc) else None
        if self._widget_is_descendant(widget, self.theme_dropdown):
            return
        if self._widget_is_descendant(widget, self.theme_button):
            return
        self._close_theme_dropdown()

    def _on_window_configure(self, _event: tk.Event) -> None:
        if self.theme_dropdown is not None:
            try:
                self._place_theme_dropdown()
            except tk.TclError:
                self._close_theme_dropdown()

    def _toggle_theme_dropdown(self) -> None:
        if self.theme_dropdown is not None:
            self._close_theme_dropdown()
            return
        self._open_theme_dropdown()

    def _open_theme_dropdown(self) -> None:
        if self.theme_dropdown is not None:
            return

        self.theme_dropdown = ctk.CTkFrame(
            self,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
            corner_radius=16,
            width=252,
        )
        self.theme_dropdown.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.theme_dropdown,
            text="Appearance",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))

        self.theme_dropdown_appearance_rows = {}
        self.theme_dropdown_accent_base_text = {}
        appearance_list = ctk.CTkFrame(self.theme_dropdown, fg_color="transparent")
        appearance_list.grid(row=1, column=0, sticky="ew", padx=10)
        appearance_list.grid_columnconfigure(0, weight=1)

        for row, option in enumerate(APPEARANCE_OPTIONS):
            btn = ctk.CTkButton(
                appearance_list,
                text=self._menu_row_label(option, self.appearance_var.get() == option),
                command=lambda value=option: self._on_appearance_selected(value),
                fg_color="transparent",
                hover_color=SECONDARY_HOVER,
                text_color=TEXT_PRIMARY,
                text_color_disabled=DISABLED_TEXT,
                anchor="w",
                height=34,
                corner_radius=10,
                border_width=0,
                font=ctk.CTkFont(size=15),
            )
            btn.grid(row=row, column=0, sticky="ew", padx=4, pady=1)
            self.theme_dropdown_appearance_rows[option] = btn

        ctk.CTkFrame(self.theme_dropdown, height=1, fg_color=CARD_BORDER).grid(
            row=2, column=0, sticky="ew", padx=14, pady=(12, 10)
        )

        ctk.CTkLabel(
            self.theme_dropdown,
            text="Accent Color",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=3, column=0, sticky="w", padx=14, pady=(0, 8))

        self.theme_dropdown_accent_rows = {}
        accent_list = ctk.CTkFrame(self.theme_dropdown, fg_color="transparent")
        accent_list.grid(row=4, column=0, sticky="ew", padx=10)
        accent_list.grid_columnconfigure(0, weight=1)

        for row, preset in enumerate(ACCENT_PRESETS):
            color = (f"#{preset.light_hex}", f"#{preset.dark_hex}")
            btn = ctk.CTkButton(
                accent_list,
                text=self._menu_row_label(preset.name, False),
                command=lambda name=preset.name: self._set_accent_preset(name),
                fg_color="transparent",
                hover_color=SECONDARY_HOVER,
                text_color=color,
                text_color_disabled=DISABLED_TEXT,
                anchor="w",
                height=32,
                corner_radius=10,
                border_width=0,
                font=ctk.CTkFont(size=16),
            )
            btn.grid(row=row, column=0, sticky="ew", padx=4, pady=1)
            self.theme_dropdown_accent_rows[preset.name] = btn
            self.theme_dropdown_accent_base_text[preset.name] = color

        ctk.CTkFrame(self.theme_dropdown, height=1, fg_color=CARD_BORDER).grid(
            row=5, column=0, sticky="ew", padx=14, pady=(10, 8)
        )

        custom_btn = ctk.CTkButton(
            self.theme_dropdown,
            text=self._menu_row_label("Custom...", False),
            command=self._pick_custom_accent,
            fg_color="transparent",
            hover_color=SECONDARY_HOVER,
            text_color=TEXT_PRIMARY,
            text_color_disabled=DISABLED_TEXT,
            anchor="w",
            height=34,
            corner_radius=10,
            border_width=0,
            font=ctk.CTkFont(size=16),
        )
        custom_btn.grid(row=6, column=0, sticky="ew", padx=14, pady=(0, 10))
        self.theme_dropdown_accent_rows["Custom..."] = custom_btn
        self.theme_dropdown_accent_base_text["Custom..."] = TEXT_PRIMARY

        self.theme_dropdown.update_idletasks()
        self.theme_dropdown_width = max(252, int(self.theme_dropdown.winfo_reqwidth()))
        self.theme_dropdown.configure(width=self.theme_dropdown_width)
        self._refresh_theme_dropdown_rows()
        self._place_theme_dropdown()

    def _place_theme_dropdown(self) -> None:
        if self.theme_dropdown is None:
            return
        if not self.theme_dropdown.winfo_exists():
            self.theme_dropdown = None
            return
        if not hasattr(self, "theme_button") or not self.theme_button.winfo_exists():
            self._close_theme_dropdown()
            return
        dropdown_width = int(self.theme_dropdown.winfo_width())
        if dropdown_width < 10:
            dropdown_width = int(self.theme_dropdown.winfo_reqwidth())
        if dropdown_width < 10:
            dropdown_width = max(self.theme_dropdown_width, int(self.theme_dropdown.cget("width") or 252))
        x = self.theme_button.winfo_x() + self.theme_button.winfo_width() - dropdown_width
        x = max(8, min(x, self.winfo_width() - dropdown_width - 8))
        y = self.theme_button.winfo_y() + self.theme_button.winfo_height() + 6
        self.theme_dropdown.place(x=x, y=y)
        self.theme_dropdown.lift()

    def _close_theme_dropdown(self) -> None:
        if self.theme_dropdown is not None and self.theme_dropdown.winfo_exists():
            self.theme_dropdown.destroy()
        self.theme_dropdown = None
        self.theme_dropdown_accent_rows = {}
        self.theme_dropdown_appearance_rows = {}
        self.theme_dropdown_accent_base_text = {}
        self.theme_dropdown_width = 252

    def _menu_row_label(self, name: str, selected: bool) -> str:
        return f"\u2713 {name}" if selected else f"  {name}"

    def _refresh_theme_dropdown_rows(self) -> None:
        selected_appearance = self.appearance_var.get()
        for name, row in self.theme_dropdown_appearance_rows.items():
            is_selected = name == selected_appearance
            row.configure(
                text=self._menu_row_label(name, is_selected),
                fg_color="transparent",
                hover_color=SECONDARY_HOVER,
                text_color=self.accent_fg if is_selected else TEXT_PRIMARY,
            )

        selected_name = self.accent_preset if self.accent_mode == "preset" else "Custom..."
        for name, row in self.theme_dropdown_accent_rows.items():
            is_selected = name == selected_name
            base_text = self.theme_dropdown_accent_base_text.get(name, TEXT_PRIMARY)
            row.configure(
                text=self._menu_row_label(name, is_selected),
                fg_color="transparent",
                hover_color=SECONDARY_HOVER,
                text_color=self.accent_fg if is_selected else base_text,
            )

    def _on_appearance_selected(self, selected: str) -> None:
        if selected not in APPEARANCE_OPTIONS:
            return
        self.appearance_var.set(selected)
        self._apply_appearance()
        self._save_theme_settings()
        self._refresh_theme_dropdown_rows()

    def _set_accent_preset(self, preset_name: str) -> None:
        if preset_name not in ACCENT_PRESET_MAP:
            return
        self.accent_mode = "preset"
        self.accent_preset = preset_name
        self._resolve_accent_colors()
        self._save_theme_settings()
        self._close_theme_dropdown()
        self._rebuild_ui_preserving_log()

    def _pick_custom_accent(self) -> None:
        self._close_theme_dropdown()
        initial = f"#{normalize_hex(self.custom_accent_hex) or 'FFFF82'}"
        chosen = colorchooser.askcolor(color=initial, title="Choose Custom Accent Color")
        if not chosen or chosen[1] is None:
            return
        normalized = normalize_hex(chosen[1])
        if normalized is None:
            return
        self.accent_mode = "custom"
        self.custom_accent_hex = normalized
        self._resolve_accent_colors()
        self._save_theme_settings()
        self._rebuild_ui_preserving_log()

    def _rebuild_ui_preserving_log(self) -> None:
        existing_log = ""
        if hasattr(self, "log"):
            try:
                existing_log = self.log.get("1.0", "end-1c")
            except Exception:
                existing_log = ""
        self._build_ui()
        if existing_log:
            self.log.configure(state="normal")
            self.log.insert("end", f"{existing_log}\n")
            self.log.see("end")
            self.log.configure(state="disabled")

    def _toggle_advanced(self) -> None:
        if self.advanced_open.get():
            self.advanced_panel.grid_remove()
            self.advanced_btn.configure(text="Show Advanced Settings")
            self.advanced_open.set(False)
            return

        self.advanced_panel.grid()
        self.advanced_btn.configure(text="Hide Advanced Settings")
        self.advanced_open.set(True)

    def _on_capture_toggle(self, source: str) -> None:
        if self.capture_images_var.get() or self.capture_content_var.get():
            return
        if source == "images":
            self.capture_images_var.set(True)
            return
        self.capture_content_var.set(True)

    def _pick_output_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Choose destination folder")
        if chosen:
            self.output_var.set(chosen)

    def _validate_inputs(self) -> bool:
        url = self.url_var.get().strip()
        if not url.startswith(("http://", "https://")):
            messagebox.showerror("Invalid URL", "URL must start with http:// or https://")
            return False

        if not self.output_var.get().strip():
            messagebox.showerror("Missing Destination", "Please choose a destination folder.")
            return False

        try:
            if int(self.max_pages_var.get()) <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Max Pages", "Max pages must be a positive integer.")
            return False

        try:
            if float(self.delay_var.get()) < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Delay", "Delay must be a number >= 0.")
            return False

        try:
            if int(self.timeout_var.get()) <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Timeout", "Timeout must be a positive integer.")
            return False

        if not self.capture_images_var.get() and not self.capture_content_var.get():
            messagebox.showerror("Select Output", "Enable at least one of: Capture images or Capture content.")
            return False

        return True

    def _set_running(self, running: bool) -> None:
        self.running = running
        if running:
            self.start_btn.grid_remove()
            self.stop_btn.grid()
            self.stop_btn.configure(state="normal")
            self.progress.grid()
            self.progress.start()
            self._set_form_enabled(False)
            self.status_var.set("Crawling in progress...")
            return

        self.stop_btn.grid_remove()
        self.start_btn.grid()
        self.progress.stop()
        self.progress.grid_remove()
        self._set_form_enabled(True)
        self.status_var.set("Ready")

    def _set_form_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in self.form_widgets:
            widget.configure(state=state)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _config(self) -> dict[str, object]:
        return {
            "base_url": self.url_var.get().strip(),
            "output_root": Path(self.output_var.get().strip()).expanduser().resolve(),
            "include_subdomains": self.include_subdomains_var.get(),
            "delay_seconds": float(self.delay_var.get().strip()),
            "timeout": int(self.timeout_var.get().strip()),
            "max_pages": int(self.max_pages_var.get().strip()),
            "respect_robots": not self.ignore_robots_var.get(),
            "verify_ssl": not self.insecure_var.get(),
            "capture_images": self.capture_images_var.get(),
            "capture_content": self.capture_content_var.get(),
        }

    def _worker_run(self, config: dict[str, object]) -> None:
        def log_fn(message: str) -> None:
            self.log_queue.put(f"{message}\n")

        try:
            summary = crawl_site(
                base_url=config["base_url"],
                output_root=config["output_root"],
                include_subdomains=config["include_subdomains"],
                delay_seconds=config["delay_seconds"],
                timeout=config["timeout"],
                max_pages=config["max_pages"],
                respect_robots=config["respect_robots"],
                verify_ssl=config["verify_ssl"],
                capture_images=config["capture_images"],
                capture_content=config["capture_content"],
                log=log_fn,
                should_stop=self.stop_event.is_set,
            )
            if self.stop_event.is_set():
                self.log_queue.put("\n[ui] Crawl stopped by user.\n")
            elif isinstance(summary, dict) and summary.get("failures"):
                self.log_queue.put("\n[ui] Crawl completed with some failures.\n")
            else:
                self.log_queue.put("\n[ui] Crawl finished successfully.\n")
        except Exception as exc:
            self.log_queue.put(f"\n[ui] Crawl failed: {exc}\n")
        finally:
            self.log_queue.put("__STATE:IDLE__")

    def _start(self) -> None:
        if self.running:
            return
        if not self._validate_inputs():
            return

        self.stop_event.clear()
        self._append_log("\n[ui] Starting crawl...\n\n")
        self._set_running(True)
        self.worker = threading.Thread(target=self._worker_run, args=(self._config(),), daemon=True)
        self.worker.start()

    def _stop(self) -> None:
        if not self.running:
            return
        self.stop_event.set()
        self.status_var.set("Stopping...")
        self.stop_btn.configure(state="disabled")
        self._append_log("\n[ui] Stop requested. Finishing current request...\n")

    def _open_output(self) -> None:
        output = self.output_var.get().strip()
        if not output:
            return
        try:
            subprocess.run(["open", output], check=False)
        except Exception as exc:
            messagebox.showerror("Open Folder Error", str(exc))

    def _pump_logs(self) -> None:
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if msg == "__STATE:IDLE__":
                self._set_running(False)
                continue
            self._append_log(msg)
        self.after(120, self._pump_logs)

    def _on_close(self) -> None:
        if self.running:
            if not messagebox.askyesno("Quit", "A crawl is still running. Stop and quit?"):
                return
            self.stop_event.set()
        self._close_theme_dropdown()
        self.destroy()


def main() -> None:
    app = ScraperApp()
    app.mainloop()


if __name__ == "__main__":
    main()
