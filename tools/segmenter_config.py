"""
PlanMod Segmenter Configuration and Theme Management
"""
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any

CONFIG_FILE = Path.home() / ".planmod_segmenter.json"

@dataclass
class AppSettings:
    """Persistent application settings."""
    theme: str = "dark"  # "light" or "dark"
    tolerance: int = 5
    line_thickness: int = 3
    planform_opacity: float = 0.5
    snap_distance: int = 15
    last_workspace: str = ""
    window_width: int = 1900
    window_height: int = 1000

# Theme definitions
THEMES = {
    "dark": {
        "bg": "#1e1e2e",
        "fg": "#cdd6f4",
        "bg_secondary": "#313244",
        "bg_tertiary": "#45475a",
        "accent": "#89b4fa",
        "accent_hover": "#b4befe",
        "border": "#585b70",
        "canvas_bg": "#181825",
        "button_bg": "#45475a",
        "button_fg": "#cdd6f4",
        "entry_bg": "#313244",
        "entry_fg": "#cdd6f4",
        "select_bg": "#585b70",
        "tree_bg": "#1e1e2e",
        "tree_fg": "#cdd6f4",
        "tree_select": "#45475a",
        "warning": "#f9e2af",
        "error": "#f38ba8",
        "success": "#a6e3a1"
    },
    "light": {
        "bg": "#eff1f5",
        "fg": "#4c4f69",
        "bg_secondary": "#e6e9ef",
        "bg_tertiary": "#dce0e8",
        "accent": "#1e66f5",
        "accent_hover": "#7287fd",
        "border": "#9ca0b0",
        "canvas_bg": "#ffffff",
        "button_bg": "#dce0e8",
        "button_fg": "#4c4f69",
        "entry_bg": "#ffffff",
        "entry_fg": "#4c4f69",
        "select_bg": "#bcc0cc",
        "tree_bg": "#eff1f5",
        "tree_fg": "#4c4f69",
        "tree_select": "#dce0e8",
        "warning": "#df8e1d",
        "error": "#d20f39",
        "success": "#40a02b"
    }
}

def load_settings() -> AppSettings:
    """Load settings from config file."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return AppSettings(**{k: v for k, v in data.items() if hasattr(AppSettings, k)})
    except Exception as e:
        print(f"Failed to load settings: {e}")
    return AppSettings()

def save_settings(settings: AppSettings):
    """Save settings to config file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(asdict(settings), f, indent=2)
    except Exception as e:
        print(f"Failed to save settings: {e}")

def get_theme(name: str) -> Dict[str, str]:
    """Get theme colors by name."""
    return THEMES.get(name, THEMES["dark"])


