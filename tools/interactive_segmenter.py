#!/usr/bin/env python3
"""
PlanMod Interactive Segmenter v4.4

100% LOCAL - No cloud/Bedrock calls. All processing done on your machine.

v4.4 Changes:
- Full workspace save/load (images, objects, annotations)
- Dialog positioning relative to main window
- Group selection mode restored
- Label scan dialog restored
- Multi-select for merge operations
- Default tolerance = 5, snap distance = 15
- Universal object list across all pages
- Textbox category for descriptions
- Polyline snap feature
- Colored icons in object tree
- Modern sidebar design with themes
- Light/Dark mode with persistence

Usage:
    python tools/interactive_segmenter.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import base64
import io
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import json
import re
import math
import uuid

from tools.segmenter_config import load_settings, save_settings, get_theme, AppSettings, THEMES

try:
    import pytesseract
    # Set Tesseract path for Windows
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]
    for path in tesseract_paths:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            break
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    from backend.ingest.pdf_processor import PDFProcessor
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

VERSION = "4.4"

# Material options
MATERIALS = ["balsa", "basswood", "plywood", "spruce", "wire", "ply", "lite-ply", "foam", "complex", "other"]
# Type options  
TYPES = ["stick", "sheet", "block", "electrical", "hardware", "covering", "other"]
# View options
VIEWS = ["top", "side", "front", "isometric", "section", "detail", "template"]

# Default categories with textbox
DEFAULT_CATEGORIES = {
    "eraser": ("Eraser", (255, 255, 255), "flood"),
    "planform": ("Planform/View", (0, 255, 0), "polyline"),
    "longeron": ("Longeron", (0, 0, 255), "line"),
    "spar": ("Spar", (0, 100, 255), "line"),
    "textbox": ("Text/Description", (200, 200, 100), "polyline"),
}


@dataclass
class ObjectAttributes:
    """Attributes for a segmented object."""
    material: str = ""
    width: float = 0.0
    height: float = 0.0
    depth: float = 0.0
    obj_type: str = ""
    view: str = ""
    description: str = ""
    url: str = ""


@dataclass
class SegmentElement:
    """A single segmentation element (part of a group or instance)."""
    element_id: str
    category: str
    mode: str
    points: List[Tuple[int, int]]
    mask: np.ndarray
    color: Tuple[int, int, int]
    label_position: str = "center"
    
    def __post_init__(self):
        if not self.element_id:
            self.element_id = str(uuid.uuid4())[:8]


@dataclass
class ObjectInstance:
    """
    An instance of an object - the object appearing in a specific view/location.
    Contains grouped elements that together form this instance.
    
    Example: R1 (rib) might have:
      - Instance 1: side view on page 1 (3 elements forming the shape)
      - Instance 2: template view on page 2 (1 element)
    """
    instance_id: str
    instance_num: int  # 1, 2, 3...
    elements: List[SegmentElement] = field(default_factory=list)  # Grouped elements
    page_id: Optional[str] = None  # Which page this instance is on
    view_type: str = ""  # "side", "top", "template", etc.
    
    def __post_init__(self):
        if not self.instance_id:
            self.instance_id = str(uuid.uuid4())[:8]
    
    @property
    def is_grouped(self) -> bool:
        """Returns True if this instance has multiple grouped elements."""
        return len(self.elements) > 1


@dataclass
class SegmentedObject:
    """
    A named object that can have multiple instances across pages/views.
    
    Hierarchy:
      Object (R1)
        └── Instance 1 (side view)
              └── Element(s) - grouped elements forming this instance
        └── Instance 2 (template view)
              └── Element(s)
    """
    object_id: str
    name: str  # e.g., "R1", "F2"
    category: str
    instances: List[ObjectInstance] = field(default_factory=list)
    attributes: ObjectAttributes = field(default_factory=ObjectAttributes)
    
    def __post_init__(self):
        if not self.object_id:
            self.object_id = str(uuid.uuid4())[:8]
    
    @property
    def element_count(self) -> int:
        return sum(len(inst.elements) for inst in self.instances)
    
    @property
    def instance_count(self) -> int:
        return len(self.instances)
    
    @property
    def is_simple(self) -> bool:
        """True if just one instance with one element (no grouping)."""
        return len(self.instances) == 1 and len(self.instances[0].elements) == 1


# Alias for backward compatibility
ObjectGroup = SegmentedObject


@dataclass
class DynamicCategory:
    """A category for segmentation."""
    name: str
    prefix: str
    full_name: str
    color_rgb: Tuple[int, int, int]
    color_bgr: Tuple[int, int, int]
    instances: List[str] = field(default_factory=list)
    selection_mode: str = "flood"
    visible: bool = True  # Show/hide toggle


@dataclass
class PageTab:
    """Represents a single page/tab."""
    tab_id: str
    model_name: str
    page_name: str
    original_image: Optional[np.ndarray] = None
    segmentation_layer: Optional[np.ndarray] = None
    groups: List[ObjectGroup] = field(default_factory=list)
    source_path: Optional[str] = None
    rotation: int = 0
    active: bool = True
    
    @property
    def raster_filename(self) -> str:
        return f"{self.model_name}_{self.page_name}_raster.png"
    
    @property
    def segmented_filename(self) -> str:
        return f"{self.model_name}_{self.page_name}_segmented.png"
    
    @property
    def display_name(self) -> str:
        prefix = "" if self.active else "⏸ "
        return f"{prefix}{self.model_name} - {self.page_name}"


class CollapsibleFrame(ttk.Frame):
    """A frame that can be collapsed/expanded."""
    
    def __init__(self, parent, title="", collapsed=False, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.collapsed = collapsed
        self.title = title
        
        # Header
        self.header = ttk.Frame(self)
        self.header.pack(fill=tk.X)
        
        self.toggle_btn = ttk.Button(self.header, text="▼" if not collapsed else "▶", 
                                      width=2, command=self.toggle)
        self.toggle_btn.pack(side=tk.LEFT)
        
        self.title_label = ttk.Label(self.header, text=title, font=("Arial", 9, "bold"))
        self.title_label.pack(side=tk.LEFT, padx=5)
        
        # Content frame
        self.content = ttk.Frame(self)
        if not collapsed:
            self.content.pack(fill=tk.BOTH, expand=True)
    
    def toggle(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.content.pack_forget()
            self.toggle_btn.config(text="▶")
        else:
            self.content.pack(fill=tk.BOTH, expand=True)
            self.toggle_btn.config(text="▼")


class PDFLoaderDialog(tk.Toplevel):
    """Dialog for loading PDF and naming pages with rotation support."""
    
    def __init__(self, parent, pdf_path: str, pages: List[np.ndarray]):
        super().__init__(parent)
        self.title("PDF Page Setup")
        
        # Position relative to parent
        self.transient(parent)
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = 1000, 750
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.grab_set()
        
        self.pdf_path = pdf_path
        self.original_pages = pages
        self.pages = [p.copy() for p in pages]
        self.rotations = [0] * len(pages)
        self.page_names: List[str] = []
        self.model_name = ""
        self.result: Optional[List[Tuple[str, str, np.ndarray]]] = None
        
        self.default_model = Path(pdf_path).stem.split('_')[0].replace('-', ' ').title()
        
        self._setup_ui()
        if len(self.pages) > 0:
            self._update_preview(0)
        
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_window()
    
    def _setup_ui(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(top_frame, text="Model Name:", font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=self.default_model)
        ttk.Entry(top_frame, textvariable=self.model_var, width=30, font=("Arial", 11)).pack(side=tk.LEFT, padx=10)
        ttk.Label(top_frame, text=f"({len(self.pages)} pages)", foreground="gray").pack(side=tk.LEFT)
        
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        list_frame = ttk.LabelFrame(main_frame, text="Pages")
        list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        self.page_listbox = tk.Listbox(list_frame, width=25, height=15, font=("Arial", 10))
        self.page_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.page_listbox.bind("<<ListboxSelect>>", self._on_page_select)
        
        for i in range(len(self.pages)):
            name = f"Page_{i+1}"
            self.page_names.append(name)
            self.page_listbox.insert(tk.END, f"Page {i+1}: {name}")
        
        ctrl_frame = ttk.Frame(list_frame)
        ctrl_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(ctrl_frame, text="Rename", command=self._rename_page).pack(fill=tk.X, pady=2)
        
        rot_frame = ttk.LabelFrame(list_frame, text="Rotate Selected")
        rot_frame.pack(fill=tk.X, padx=5, pady=5)
        rot_btns = ttk.Frame(rot_frame)
        rot_btns.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(rot_btns, text="↺ 90°", width=6, command=lambda: self._rotate(-90)).pack(side=tk.LEFT, padx=2)
        ttk.Button(rot_btns, text="↻ 90°", width=6, command=lambda: self._rotate(90)).pack(side=tk.LEFT, padx=2)
        ttk.Button(rot_btns, text="180°", width=6, command=lambda: self._rotate(180)).pack(side=tk.LEFT, padx=2)
        
        preview_frame = ttk.LabelFrame(main_frame, text="Preview")
        preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.preview_canvas = tk.Canvas(preview_frame, bg="#333333", width=500, height=400)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.page_info_label = ttk.Label(preview_frame, text="", font=("Arial", 9))
        self.page_info_label.pack(pady=5)
        
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Load All Pages", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
        
        if len(self.pages) > 0:
            self.page_listbox.selection_set(0)
    
    def _rotate(self, degrees: int):
        selection = self.page_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        self.rotations[idx] = (self.rotations[idx] + degrees) % 360
        rot_count = self.rotations[idx] // 90
        self.pages[idx] = np.rot90(self.original_pages[idx], k=-rot_count)
        self._update_preview(idx)
    
    def _update_preview(self, page_idx: int):
        if not (0 <= page_idx < len(self.pages)):
            return
        page = self.pages[page_idx]
        if page is None or page.size == 0:
            return
        h, w = page.shape[:2]
        if h <= 0 or w <= 0:
            return
        self.update_idletasks()
        canvas_w = max(self.preview_canvas.winfo_width(), 400)
        canvas_h = max(self.preview_canvas.winfo_height(), 300)
        scale = min(canvas_w / w, canvas_h / h) * 0.9
        scale = max(0.01, scale)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        try:
            resized = cv2.resize(page, (new_w, new_h), interpolation=cv2.INTER_AREA)
            pil_img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
            self.preview_image = ImageTk.PhotoImage(pil_img)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(canvas_w//2, canvas_h//2, image=self.preview_image)
        except Exception as e:
            print(f"Preview error: {e}")
        rot_str = f" (rotated {self.rotations[page_idx]}°)" if self.rotations[page_idx] else ""
        self.page_info_label.config(text=f"Size: {w}x{h} pixels{rot_str}")
    
    def _on_page_select(self, event):
        selection = self.page_listbox.curselection()
        if selection:
            self._update_preview(selection[0])
    
    def _rename_page(self):
        selection = self.page_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        new_name = simpledialog.askstring("Rename Page", f"Enter name for Page {idx+1}:",
                                          initialvalue=self.page_names[idx], parent=self)
        if new_name:
            new_name = re.sub(r'[^\w\s-]', '', new_name).replace(' ', '_')
            self.page_names[idx] = new_name
            self.page_listbox.delete(idx)
            self.page_listbox.insert(idx, f"Page {idx+1}: {new_name}")
            self.page_listbox.selection_set(idx)
    
    def _on_ok(self):
        self.model_name = self.model_var.get().strip().replace(' ', '_')
        if not self.model_name:
            messagebox.showwarning("Warning", "Please enter a model name")
            return
        self.result = [(self.model_name, self.page_names[i], self.pages[i]) for i in range(len(self.pages))]
        self.destroy()
    
    def _on_cancel(self):
        self.result = None
        self.destroy()


class LabelScanDialog(tk.Toplevel):
    """Dialog showing scan progress and results."""
    
    KNOWN_PREFIXES = {
        "F": "Former", "R": "Rib", "FS": "Fuselage Side", "WT": "Wing Tip",
        "T": "Tail", "TS": "Tail Surface", "M": "Motor Mount", "UC": "Undercarriage",
        "B": "Misc Part", "L": "Longeron", "A": "Former A", "C": "Former C",
        "D": "Former D", "E": "Former E", "G": "Former G",
    }
    
    def __init__(self, parent, tabs: List[PageTab]):
        super().__init__(parent)
        self.title("Scan for Labels")
        
        # Position relative to parent
        self.transient(parent)
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = 600, 500
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.grab_set()
        
        self.tabs = tabs
        self.found_groups: Dict[str, List[str]] = {}
        self.result: Optional[Dict[str, str]] = None
        
        self._setup_ui()
        self.after(100, self._start_scan)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_window()
    
    def _setup_ui(self):
        self.progress_frame = ttk.LabelFrame(self, text="Scanning Progress")
        self.progress_frame.pack(fill=tk.X, padx=10, pady=10)
        self.progress_label = ttk.Label(self.progress_frame, text="Preparing...")
        self.progress_label.pack(padx=10, pady=5)
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate', length=400)
        self.progress_bar.pack(padx=10, pady=5)
        
        self.results_frame = ttk.LabelFrame(self, text="Found Labels - Select to Add")
        canvas_frame = ttk.Frame(self.results_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.results_canvas = tk.Canvas(canvas_frame, height=250)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.results_canvas.yview)
        self.checkbox_frame = ttk.Frame(self.results_canvas)
        self.checkbox_frame.bind("<Configure>", lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all")))
        self.results_canvas.create_window((0, 0), window=self.checkbox_frame, anchor="nw")
        self.results_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.check_vars: Dict[str, tk.BooleanVar] = {}
        self.name_entries: Dict[str, ttk.Entry] = {}
        
        self.btn_frame = ttk.Frame(self)
        ttk.Button(self.btn_frame, text="Select All", command=self._select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.btn_frame, text="Select None", command=self._select_none).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(self.btn_frame, text="Add Selected", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
    
    def _start_scan(self):
        if not HAS_TESSERACT:
            self.progress_label.config(text="Tesseract OCR not available!")
            return
        
        total_pages = len(self.tabs)
        self.progress_bar['maximum'] = total_pages
        all_found: Dict[str, set] = {}
        
        for i, tab in enumerate(self.tabs):
            self.progress_label.config(text=f"Scanning page {i+1}/{total_pages}: {tab.page_name}")
            self.progress_bar['value'] = i
            self.update()
            
            if tab.original_image is None:
                continue
            
            try:
                gray = cv2.cvtColor(tab.original_image, cv2.COLOR_BGR2GRAY)
                text = pytesseract.image_to_string(gray)
                
                patterns = [
                    (r'\b([RF])[-\s]?(\d+)\b', None), (r'\b(FS)[-\s]?(\d+)\b', None),
                    (r'\b(WT)(\d*)\b', None), (r'\b(TS)(\d*)\b', None),
                    (r'\b([T])[-\s]?(\d+)\b', None), (r'\b(UC)(\d*)\b', None),
                    (r'\b([LM])[-\s]?(\d+)\b', None), (r'\b(RIB)\s*([A-Z0-9]*)\b', 'R'),
                    (r'\bFORMER\s*([A-Z0-9]*)\b', 'F'), (r'\b([A-G])[-\s]?(\d*)\b(?=\s|$|[,.])', None),
                ]
                
                for pattern, force_prefix in patterns:
                    for match in re.findall(pattern, text, re.IGNORECASE):
                        if isinstance(match, tuple):
                            prefix = (force_prefix or match[0]).upper()
                            suffix = match[1] if len(match) > 1 else ""
                            instance = f"{prefix}{suffix}".strip()
                        else:
                            prefix = (force_prefix or match).upper()
                            instance = prefix
                        if prefix not in all_found:
                            all_found[prefix] = set()
                        if instance:
                            all_found[prefix].add(instance)
            except Exception as e:
                print(f"OCR error on {tab.page_name}: {e}")
        
        self.progress_bar['value'] = total_pages
        self.progress_label.config(text=f"Scan complete! Found {len(all_found)} category groups.")
        self.found_groups = {k: sorted(v) for k, v in all_found.items() if v}
        self._show_results()
    
    def _show_results(self):
        if not self.found_groups:
            self.progress_label.config(text="No labels found.")
            ttk.Button(self.progress_frame, text="Close", command=self._on_cancel).pack(pady=10)
            return
        
        self.results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        row = 0
        for prefix in sorted(self.found_groups.keys()):
            instances = self.found_groups[prefix]
            var = tk.BooleanVar(value=True)
            self.check_vars[prefix] = var
            
            cb = ttk.Checkbutton(self.checkbox_frame, variable=var)
            cb.grid(row=row, column=0, padx=5, pady=3, sticky="w")
            
            default_name = self.KNOWN_PREFIXES.get(prefix, prefix)
            entry = ttk.Entry(self.checkbox_frame, width=20)
            entry.insert(0, default_name)
            entry.grid(row=row, column=1, padx=5, pady=3, sticky="w")
            self.name_entries[prefix] = entry
            
            ttk.Label(self.checkbox_frame, text=f"({prefix})", foreground="gray").grid(row=row, column=2, padx=5, pady=3, sticky="w")
            instances_str = ", ".join(instances[:5]) + ("..." if len(instances) > 5 else "")
            ttk.Label(self.checkbox_frame, text=instances_str, foreground="blue").grid(row=row, column=3, padx=5, pady=3, sticky="w")
            row += 1
    
    def _select_all(self):
        for var in self.check_vars.values():
            var.set(True)
    
    def _select_none(self):
        for var in self.check_vars.values():
            var.set(False)
    
    def _on_ok(self):
        self.result = {prefix: self.name_entries[prefix].get().strip() 
                       for prefix, var in self.check_vars.items() if var.get()}
        self.destroy()
    
    def _on_cancel(self):
        self.result = None
        self.destroy()


class AttributeDialog(tk.Toplevel):
    """Dialog for editing object attributes."""
    
    def __init__(self, parent, group: ObjectGroup):
        super().__init__(parent)
        self.title(f"Attributes: {group.name}")
        
        # Position relative to parent
        self.transient(parent)
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = 400, 450
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.grab_set()
        
        self.group = group
        self.result: Optional[ObjectAttributes] = None
        
        self._setup_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_window()
    
    def _setup_ui(self):
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Material
        ttk.Label(main, text="Material:").grid(row=0, column=0, sticky="w", pady=5)
        self.material_var = tk.StringVar(value=self.group.attributes.material)
        mat_combo = ttk.Combobox(main, textvariable=self.material_var, values=MATERIALS, width=25)
        mat_combo.grid(row=0, column=1, pady=5)
        
        # Type
        ttk.Label(main, text="Type:").grid(row=1, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar(value=self.group.attributes.obj_type)
        type_combo = ttk.Combobox(main, textvariable=self.type_var, values=TYPES, width=25)
        type_combo.grid(row=1, column=1, pady=5)
        
        # View
        ttk.Label(main, text="View:").grid(row=2, column=0, sticky="w", pady=5)
        self.view_var = tk.StringVar(value=self.group.attributes.view)
        view_combo = ttk.Combobox(main, textvariable=self.view_var, values=VIEWS, width=25)
        view_combo.grid(row=2, column=1, pady=5)
        
        # Size
        size_frame = ttk.LabelFrame(main, text="Size")
        size_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=10)
        
        ttk.Label(size_frame, text="W:").grid(row=0, column=0, padx=5)
        self.width_var = tk.StringVar(value=str(self.group.attributes.width) if self.group.attributes.width else "")
        ttk.Entry(size_frame, textvariable=self.width_var, width=8).grid(row=0, column=1)
        
        ttk.Label(size_frame, text="H:").grid(row=0, column=2, padx=5)
        self.height_var = tk.StringVar(value=str(self.group.attributes.height) if self.group.attributes.height else "")
        ttk.Entry(size_frame, textvariable=self.height_var, width=8).grid(row=0, column=3)
        
        ttk.Label(size_frame, text="D:").grid(row=0, column=4, padx=5)
        self.depth_var = tk.StringVar(value=str(self.group.attributes.depth) if self.group.attributes.depth else "")
        ttk.Entry(size_frame, textvariable=self.depth_var, width=8).grid(row=0, column=5)
        
        # Description
        ttk.Label(main, text="Description:").grid(row=4, column=0, sticky="nw", pady=5)
        self.desc_text = tk.Text(main, width=30, height=4)
        self.desc_text.grid(row=4, column=1, pady=5)
        self.desc_text.insert("1.0", self.group.attributes.description)
        
        # URL
        ttk.Label(main, text="URL/Spec:").grid(row=5, column=0, sticky="w", pady=5)
        self.url_var = tk.StringVar(value=self.group.attributes.url)
        ttk.Entry(main, textvariable=self.url_var, width=28).grid(row=5, column=1, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Save", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
    
    def _on_ok(self):
        try:
            w = float(self.width_var.get()) if self.width_var.get() else 0.0
            h = float(self.height_var.get()) if self.height_var.get() else 0.0
            d = float(self.depth_var.get()) if self.depth_var.get() else 0.0
        except ValueError:
            w = h = d = 0.0
        
        self.result = ObjectAttributes(
            material=self.material_var.get(),
            width=w, height=h, depth=d,
            obj_type=self.type_var.get(),
            view=self.view_var.get(),
            description=self.desc_text.get("1.0", tk.END).strip(),
            url=self.url_var.get(),
        )
        self.destroy()
    
    def _on_cancel(self):
        self.result = None
        self.destroy()


class InteractiveSegmenter:
    """Multi-tab interactive segmentation tool with hierarchical object management."""
    
    CATEGORY_DEFINITIONS = {
        "R": ("Rib", (255, 0, 0), "flood"), "F": ("Former", (255, 0, 0), "flood"),
        "FS": ("Fuselage Side", (0, 0, 255), "flood"), "WT": ("Wing Tip", (0, 100, 255), "flood"),
        "T": ("Tail", (255, 0, 255), "flood"), "TS": ("Tail Surface", (255, 0, 255), "flood"),
        "M": ("Motor Mount", (255, 165, 0), "flood"), "UC": ("Undercarriage", (255, 180, 200), "flood"),
        "B": ("Misc Part", (128, 128, 128), "flood"), "L": ("Longeron", (0, 0, 255), "line"),
        "spar": ("Spar", (0, 0, 255), "line"), "longeron": ("Longeron", (0, 0, 255), "line"),
        "planform": ("Planform Region", (0, 255, 0), "polyline"), "view": ("View Region", (0, 255, 0), "polyline"),
        "textbox": ("Text/Description", (200, 200, 100), "polyline"),
    }
    
    MODES = {
        "select": "Select - Click to select existing objects",
        "flood": "Flood Fill - Click to fill region",
        "polyline": "Polyline - Click points, double-click to close",
        "freeform": "Freeform - Click and drag to draw",
        "line": "Line Segment - Click points, Enter to finish",
        "group": "Group - Select multiple objects to group",
    }
    
    def __init__(self):
        # Load persistent settings
        self.settings = load_settings()
        self.theme = get_theme(self.settings.theme)
        
        self.root = tk.Tk()
        self.root.title(f"PlanMod Segmenter v{VERSION}")
        self.root.geometry(f"{self.settings.window_width}x{self.settings.window_height}")
        
        self.tabs: Dict[str, PageTab] = {}
        self.current_tab_id: Optional[str] = None
        self.categories: Dict[str, DynamicCategory] = {}
        
        # Universal object list (shared across all pages)
        self.all_groups: List[ObjectGroup] = []
        
        self.current_mode = "flood"
        self.tolerance = self.settings.tolerance
        self.line_thickness = self.settings.line_thickness
        self.zoom_level = 1.0
        self.planform_opacity = self.settings.planform_opacity
        self.snap_distance = self.settings.snap_distance
        
        self.is_drawing = False
        self.current_points: List[Tuple[int, int]] = []
        self.temp_drawing_ids: List[int] = []
        
        # Multi-select support
        self.selected_group_ids: Set[str] = set()
        self.selected_instance_ids: Set[str] = set()
        self.selected_element_ids: Set[str] = set()
        
        # Group mode - collects elements being created
        self.group_mode_active = False
        self.group_mode_elements: List[SegmentElement] = []  # Elements created in group mode
        
        self.label_position = "center"
        self.show_labels = True
        
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
        self.workspace_file: Optional[str] = None
        self.workspace_modified = False
        
        self._apply_theme()
        self._init_default_categories()
        self._setup_ui()
        self._bind_events()
    
    def _apply_theme(self):
        """Apply theme colors to ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        t = self.theme
        
        # Configure main styles
        style.configure(".", background=t["bg"], foreground=t["fg"], 
                       fieldbackground=t["entry_bg"], bordercolor=t["border"])
        style.configure("TFrame", background=t["bg"])
        style.configure("TLabel", background=t["bg"], foreground=t["fg"])
        style.configure("TButton", background=t["button_bg"], foreground=t["button_fg"],
                       bordercolor=t["border"], focuscolor=t["accent"])
        style.map("TButton", background=[("active", t["accent"]), ("pressed", t["accent_hover"])])
        
        style.configure("TEntry", fieldbackground=t["entry_bg"], foreground=t["entry_fg"],
                       bordercolor=t["border"], insertcolor=t["fg"])
        style.configure("TCombobox", fieldbackground=t["entry_bg"], foreground=t["entry_fg"],
                       background=t["button_bg"], bordercolor=t["border"])
        
        style.configure("TNotebook", background=t["bg"], bordercolor=t["border"])
        style.configure("TNotebook.Tab", background=t["bg_secondary"], foreground=t["fg"],
                       padding=[10, 5])
        style.map("TNotebook.Tab", background=[("selected", t["accent"])],
                 foreground=[("selected", t["bg"])])
        
        style.configure("Treeview", background=t["tree_bg"], foreground=t["tree_fg"],
                       fieldbackground=t["tree_bg"], bordercolor=t["border"])
        style.map("Treeview", background=[("selected", t["tree_select"])])
        style.configure("Treeview.Heading", background=t["bg_secondary"], foreground=t["fg"])
        
        style.configure("TCheckbutton", background=t["bg"], foreground=t["fg"])
        style.configure("TRadiobutton", background=t["bg"], foreground=t["fg"])
        style.configure("TLabelframe", background=t["bg"], foreground=t["fg"], bordercolor=t["border"])
        style.configure("TLabelframe.Label", background=t["bg"], foreground=t["accent"])
        
        style.configure("TScale", background=t["bg"], troughcolor=t["bg_tertiary"])
        style.configure("TProgressbar", background=t["accent"], troughcolor=t["bg_tertiary"])
        
        style.configure("Horizontal.TScrollbar", background=t["bg_tertiary"], 
                       troughcolor=t["bg_secondary"], bordercolor=t["border"])
        style.configure("Vertical.TScrollbar", background=t["bg_tertiary"],
                       troughcolor=t["bg_secondary"], bordercolor=t["border"])
        
        # Custom styles
        style.configure("Accent.TButton", background=t["accent"], foreground=t["bg"])
        style.map("Accent.TButton", background=[("active", t["accent_hover"])])
        
        style.configure("Sidebar.TFrame", background=t["bg_secondary"])
        style.configure("Sidebar.TLabel", background=t["bg_secondary"], foreground=t["fg"])
        style.configure("Section.TLabel", background=t["bg_secondary"], foreground=t["accent"],
                       font=("Segoe UI", 9, "bold"))
        
        self.root.configure(bg=t["bg"])
    
    def _init_default_categories(self):
        for key, (full_name, color, mode) in DEFAULT_CATEGORIES.items():
            self.categories[key] = DynamicCategory(
                name=key, prefix=key, full_name=full_name,
                color_rgb=color, color_bgr=(color[2], color[1], color[0]),
                selection_mode=mode
            )
    
    def _setup_ui(self):
        t = self.theme
        
        menubar = tk.Menu(self.root, bg=t["bg_secondary"], fg=t["fg"], 
                         activebackground=t["accent"], activeforeground=t["bg"])
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0, bg=t["bg_secondary"], fg=t["fg"],
                           activebackground=t["accent"], activeforeground=t["bg"])
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New (Open PDF)...", command=self._open_pdf, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Workspace...", command=self._load_workspace, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Save Workspace", command=self._save_workspace, accelerator="Ctrl+S")
        file_menu.add_command(label="Save Workspace As...", command=self._save_workspace_as)
        file_menu.add_separator()
        file_menu.add_command(label="Export Page(s)...", command=self._export_pages)
        file_menu.add_command(label="Export Data (JSON)", command=self._export_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        
        view_menu = tk.Menu(menubar, tearoff=0, bg=t["bg_secondary"], fg=t["fg"],
                           activebackground=t["accent"], activeforeground=t["bg"])
        menubar.add_cascade(label="View", menu=view_menu)
        self.theme_var = tk.StringVar(value=self.settings.theme)
        view_menu.add_radiobutton(label="Dark Theme", variable=self.theme_var, value="dark",
                                  command=lambda: self._change_theme("dark"))
        view_menu.add_radiobutton(label="Light Theme", variable=self.theme_var, value="light",
                                  command=lambda: self._change_theme("light"))
        
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Left sidebar
        left_container = ttk.Frame(main_frame, width=280)
        left_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_container.pack_propagate(False)
        
        left_canvas = tk.Canvas(left_container, width=260)
        left_scroll = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        left_frame = ttk.Frame(left_canvas)
        left_frame.bind("<Configure>", lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
        left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(left_frame, text=f"PlanMod v{VERSION}", font=("Arial", 12, "bold")).pack(pady=5)
        
        # Mode section
        mode_section = CollapsibleFrame(left_frame, "Selection Mode")
        mode_section.pack(fill=tk.X, padx=5, pady=2)
        
        self.mode_var = tk.StringVar(value="flood")
        for mode, desc in self.MODES.items():
            rb = ttk.Radiobutton(mode_section.content, text=mode.capitalize(), 
                                 variable=self.mode_var, value=mode,
                                 command=lambda m=mode: self._set_mode(m))
            rb.pack(anchor=tk.W, padx=5)
        
        # Categories section
        cat_section = CollapsibleFrame(left_frame, "Categories")
        cat_section.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(cat_section.content, text="🔍 Scan Labels", 
                   command=self._scan_all_pages).pack(fill=tk.X, padx=5, pady=2)
        
        add_frame = ttk.Frame(cat_section.content)
        add_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(add_frame, text="Add:").pack(side=tk.LEFT)
        self.new_cat_entry = ttk.Entry(add_frame, width=8)
        self.new_cat_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(add_frame, text="+", width=2, command=self._add_manual_category).pack(side=tk.LEFT)
        
        # Category list with visibility toggles
        self.cat_list_frame = ttk.Frame(cat_section.content)
        self.cat_list_frame.pack(fill=tk.X, padx=5, pady=2)
        self.category_var = tk.StringVar(value="")
        self.cat_visibility_vars: Dict[str, tk.BooleanVar] = {}
        
        # Label position
        label_section = CollapsibleFrame(left_frame, "Label Position")
        label_section.pack(fill=tk.X, padx=5, pady=2)
        
        self.label_pos_var = tk.StringVar(value="center")
        pos_grid = ttk.Frame(label_section.content)
        pos_grid.pack(padx=5, pady=2)
        positions = [("↖", "top-left"), ("↑", "top-center"), ("↗", "top-right"),
                     ("←", "middle-left"), ("•", "center"), ("→", "middle-right"),
                     ("↙", "bottom-left"), ("↓", "bottom-center"), ("↘", "bottom-right")]
        for i, (sym, pos) in enumerate(positions):
            ttk.Radiobutton(pos_grid, text=sym, variable=self.label_pos_var, value=pos,
                           width=2, command=lambda p=pos: self._set_label_position(p)).grid(row=i//3, column=i%3)
        
        self.show_labels_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(label_section.content, text="Show labels", 
                        variable=self.show_labels_var, command=self._toggle_labels).pack(padx=5)
        
        # Group Mode section
        group_section = CollapsibleFrame(left_frame, "Group Selection")
        group_section.pack(fill=tk.X, padx=5, pady=2)
        
        self.group_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(group_section.content, text="Group Mode (multi-select)", 
                        variable=self.group_mode_var, command=self._toggle_group_mode).pack(anchor=tk.W, padx=5)
        ttk.Button(group_section.content, text="End Group & Create", 
                   command=self._finish_group_selection).pack(fill=tk.X, padx=5, pady=2)
        self.group_count_label = ttk.Label(group_section.content, text="Selected: 0", foreground=t["accent"])
        self.group_count_label.pack(anchor=tk.W, padx=5)
        
        # Settings
        settings_section = CollapsibleFrame(left_frame, "Settings", collapsed=True)
        settings_section.pack(fill=tk.X, padx=5, pady=2)
        
        tol_frame = ttk.Frame(settings_section.content)
        tol_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(tol_frame, text="Tolerance:").pack(side=tk.LEFT)
        self.tolerance_label = ttk.Label(tol_frame, text=str(self.tolerance), width=4)
        self.tolerance_label.pack(side=tk.RIGHT)
        ttk.Button(tol_frame, text="+", width=2, command=lambda: self._adjust_tolerance(1)).pack(side=tk.RIGHT)
        ttk.Button(tol_frame, text="-", width=2, command=lambda: self._adjust_tolerance(-1)).pack(side=tk.RIGHT)
        
        thick_frame = ttk.Frame(settings_section.content)
        thick_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(thick_frame, text="Line width:").pack(side=tk.LEFT)
        self.thickness_label = ttk.Label(thick_frame, text=str(self.line_thickness), width=4)
        self.thickness_label.pack(side=tk.RIGHT)
        ttk.Button(thick_frame, text="+", width=2, command=lambda: self._adjust_thickness(1)).pack(side=tk.RIGHT)
        ttk.Button(thick_frame, text="-", width=2, command=lambda: self._adjust_thickness(-1)).pack(side=tk.RIGHT)
        
        snap_frame = ttk.Frame(settings_section.content)
        snap_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(snap_frame, text="Snap dist:").pack(side=tk.LEFT)
        self.snap_label = ttk.Label(snap_frame, text=str(self.snap_distance), width=4)
        self.snap_label.pack(side=tk.RIGHT)
        ttk.Button(snap_frame, text="+", width=2, command=lambda: self._adjust_snap(5)).pack(side=tk.RIGHT)
        ttk.Button(snap_frame, text="-", width=2, command=lambda: self._adjust_snap(-5)).pack(side=tk.RIGHT)
        
        opacity_frame = ttk.Frame(settings_section.content)
        opacity_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(opacity_frame, text="Planform opacity:").pack(anchor=tk.W)
        self.opacity_var = tk.DoubleVar(value=self.planform_opacity)
        ttk.Scale(opacity_frame, from_=0.0, to=1.0, variable=self.opacity_var,
                  orient=tk.HORIZONTAL, command=self._on_opacity_change).pack(fill=tk.X)
        
        # Actions
        action_section = CollapsibleFrame(left_frame, "Actions")
        action_section.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(action_section.content, text="Undo (Z)", command=self._undo).pack(fill=tk.X, padx=5, pady=1)
        ttk.Button(action_section.content, text="Cancel (Esc)", command=self._cancel_drawing).pack(fill=tk.X, padx=5, pady=1)
        
        # Zoom
        zoom_frame = ttk.Frame(action_section.content)
        zoom_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(zoom_frame, text="-", width=2, command=self._zoom_out).pack(side=tk.LEFT)
        self.zoom_label = ttk.Label(zoom_frame, text="100%", width=6)
        self.zoom_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(zoom_frame, text="+", width=2, command=self._zoom_in).pack(side=tk.LEFT)
        ttk.Button(zoom_frame, text="Fit", width=4, command=self._zoom_fit).pack(side=tk.LEFT, padx=5)
        
        # Center - tabs
        center_frame = ttk.Frame(main_frame)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.notebook = ttk.Notebook(center_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        # Welcome tab
        welcome = ttk.Frame(self.notebook)
        self.notebook.add(welcome, text="Welcome")
        ttk.Label(welcome, text=f"PlanMod Segmenter v{VERSION}\n\nFile → New to open a PDF\nFile → Open Workspace to continue",
                  font=("Arial", 12), justify=tk.CENTER).pack(pady=100)
        
        # Right sidebar - Object tree
        right_frame = ttk.Frame(main_frame, width=280)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_frame.pack_propagate(False)
        
        obj_section = ttk.LabelFrame(right_frame, text="Objects")
        obj_section.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tree_frame = ttk.Frame(obj_section)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.object_tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, selectmode="extended")
        self.object_tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.object_tree.yview)
        
        self.object_tree.heading("#0", text="Objects")
        self.object_tree.column("#0", width=250)
        self.object_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.object_tree.bind("<Double-1>", self._on_tree_double_click)
        
        # Object actions
        btn_frame = ttk.Frame(obj_section)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Rename", command=self._rename_selected).pack(fill=tk.X, pady=1)
        ttk.Button(btn_frame, text="+ New Instance", command=self._new_instance).pack(fill=tk.X, pady=1)
        
        merge_frame = ttk.Frame(btn_frame)
        merge_frame.pack(fill=tk.X, pady=1)
        ttk.Button(merge_frame, text="Merge→Inst", width=10, 
                   command=self._merge_as_instances).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(merge_frame, text="Merge→Grp", width=10,
                   command=self._merge_as_group).pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        ttk.Button(btn_frame, text="Attributes", command=self._edit_attributes).pack(fill=tk.X, pady=1)
        ttk.Button(btn_frame, text="Delete", command=self._delete_selected).pack(fill=tk.X, pady=1)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN).pack(side=tk.BOTTOM, fill=tk.X)
        
        self._refresh_category_ui()
    
    def _bind_events(self):
        self.root.bind("<Control-n>", lambda e: self._open_pdf())
        self.root.bind("<Control-o>", lambda e: self._load_workspace())
        self.root.bind("<Control-s>", lambda e: self._save_workspace())
        self.root.bind("<Key>", self._on_key)
        self.root.bind("<Return>", self._on_enter)
        self.root.bind("<Escape>", lambda e: self._cancel_drawing())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_close(self):
        if self.workspace_modified:
            result = messagebox.askyesnocancel("Save Changes", "Save workspace before closing?")
            if result is None:
                return
            if result:
                self._save_workspace()
        
        # Save settings
        self.settings.tolerance = self.tolerance
        self.settings.line_thickness = self.line_thickness
        self.settings.planform_opacity = self.planform_opacity
        self.settings.snap_distance = self.snap_distance
        self.settings.window_width = self.root.winfo_width()
        self.settings.window_height = self.root.winfo_height()
        if self.workspace_file:
            self.settings.last_workspace = self.workspace_file
        save_settings(self.settings)
        
        self.root.quit()
    
    def _get_current_tab(self) -> Optional[PageTab]:
        return self.tabs.get(self.current_tab_id) if self.current_tab_id else None
    
    def _refresh_category_ui(self):
        for w in self.cat_list_frame.winfo_children():
            w.destroy()
        self.cat_visibility_vars.clear()
        
        for cat_name in sorted(self.categories.keys()):
            cat = self.categories[cat_name]
            f = ttk.Frame(self.cat_list_frame)
            f.pack(fill=tk.X, pady=1)
            
            vis_var = tk.BooleanVar(value=cat.visible)
            self.cat_visibility_vars[cat_name] = vis_var
            ttk.Checkbutton(f, variable=vis_var, 
                           command=lambda c=cat_name: self._toggle_category_visibility(c)).pack(side=tk.LEFT)
            
            color_hex = f"#{cat.color_rgb[0]:02x}{cat.color_rgb[1]:02x}{cat.color_rgb[2]:02x}"
            tk.Label(f, width=2, bg=color_hex).pack(side=tk.LEFT, padx=2)
            
            ttk.Radiobutton(f, text=cat.name, variable=self.category_var, value=cat_name,
                           command=lambda c=cat_name: self._select_category(c)).pack(side=tk.LEFT)
    
    def _toggle_category_visibility(self, cat_name: str):
        if cat_name in self.categories:
            self.categories[cat_name].visible = self.cat_visibility_vars[cat_name].get()
            self._update_display()
    
    def _set_mode(self, mode: str):
        self.current_mode = mode
        self.mode_var.set(mode)
        self._cancel_drawing()
        tab = self._get_current_tab()
        if tab and hasattr(tab, 'canvas'):
            cursors = {"select": "hand2", "flood": "crosshair", "polyline": "tcross", "freeform": "pencil", "line": "plus"}
            tab.canvas.config(cursor=cursors.get(mode, "crosshair"))
    
    def _select_category(self, cat_name: str):
        if cat_name in self.categories:
            self.category_var.set(cat_name)
            cat = self.categories[cat_name]
            if cat.selection_mode != "select":
                self._set_mode(cat.selection_mode)
    
    def _set_label_position(self, pos: str):
        self.label_position = pos
    
    def _toggle_labels(self):
        self.show_labels = self.show_labels_var.get()
        self._update_display()
    
    def _on_opacity_change(self, val):
        self.planform_opacity = float(val)
        self._update_display()
    
    def _adjust_tolerance(self, delta: int):
        self.tolerance = max(1, min(100, self.tolerance + delta))
        self.tolerance_label.config(text=str(self.tolerance))
    
    def _adjust_thickness(self, delta: int):
        self.line_thickness = max(1, min(20, self.line_thickness + delta))
        self.thickness_label.config(text=str(self.line_thickness))
    
    def _adjust_snap(self, delta: int):
        self.snap_distance = max(5, min(50, self.snap_distance + delta))
        self.snap_label.config(text=str(self.snap_distance))
    
    def _change_theme(self, theme_name: str):
        """Change and apply a new theme."""
        self.settings.theme = theme_name
        save_settings(self.settings)
        messagebox.showinfo("Theme Changed", f"Theme will be '{theme_name}' on next restart.")
    
    def _toggle_group_mode(self):
        """Toggle group creation mode - all new elements become part of one grouped instance."""
        self.group_mode_active = self.group_mode_var.get()
        if self.group_mode_active:
            self.group_mode_elements.clear()
            self.status_var.set("GROUP MODE: Create elements - they will be grouped together")
        else:
            if self.group_mode_elements:
                # Ask if user wants to save the group
                if messagebox.askyesno("Save Group?", f"Save {len(self.group_mode_elements)} elements as a group?"):
                    self._finish_group_selection()
                else:
                    self.group_mode_elements.clear()
        self._update_group_count()
    
    def _update_group_count(self):
        """Update the group selection count label."""
        count = len(self.group_mode_elements) if hasattr(self, 'group_mode_elements') else 0
        self.group_count_label.config(text=f"Elements: {count}")
    
    def _finish_group_selection(self):
        """Finish group creation - all collected elements become ONE instance of a new object."""
        if not hasattr(self, 'group_mode_elements') or len(self.group_mode_elements) < 1:
            messagebox.showinfo("Info", "Create at least 1 element in group mode first")
            return
        
        tab = self._get_current_tab()
        if not tab:
            return
        
        # Ask for object name
        cat_name = self.category_var.get() or "R"
        cat = self.categories.get(cat_name)
        prefix = cat.prefix if cat else cat_name[0].upper()
        
        # Count existing objects of this category
        count = sum(1 for g in tab.groups if g.category == cat_name) + 1
        default_name = f"{prefix}{count}"
        
        name = simpledialog.askstring("Object Name", 
                                      f"Name for this object ({len(self.group_mode_elements)} grouped elements):",
                                      initialvalue=default_name, parent=self.root)
        if not name:
            return
        
        # Create new object with ONE instance containing all grouped elements
        new_obj = SegmentedObject(
            object_id=str(uuid.uuid4())[:8],
            name=name,
            category=cat_name
        )
        new_inst = ObjectInstance(
            instance_id=str(uuid.uuid4())[:8], 
            instance_num=1,
            page_id=tab.tab_id,
            view_type="grouped"
        )
        new_inst.elements = list(self.group_mode_elements)
        new_obj.instances.append(new_inst)
        tab.groups.append(new_obj)
        
        # Reset group mode
        self.group_mode_elements.clear()
        self.group_mode_var.set(False)
        self.group_mode_active = False
        self._update_group_count()
        self.workspace_modified = True
        self._update_object_tree()
        self._update_display()
        self.status_var.set(f"Created object '{name}' with {len(new_inst.elements)} grouped elements")
    
    def _merge_as_instances(self):
        """Merge selected objects - each becomes a separate instance of the same object."""
        selection = self.object_tree.selection()
        if len(selection) < 2:
            messagebox.showinfo("Info", "Select at least 2 objects to merge as instances")
            return
        
        tab = self._get_current_tab()
        if not tab:
            return
        
        # Collect object IDs (from o_ prefix)
        obj_ids = set()
        for item_id in selection:
            if item_id.startswith("o_"):
                obj_ids.add(item_id[2:])
            elif item_id.startswith("i_"):
                parent = self.object_tree.parent(item_id)
                if parent.startswith("o_"):
                    obj_ids.add(parent[2:])
        
        if len(obj_ids) < 2:
            messagebox.showinfo("Info", "Select at least 2 different objects")
            return
        
        objs_to_merge = [g for g in tab.groups if g.object_id in obj_ids]
        if len(objs_to_merge) < 2:
            return
        
        # Ask for merged object name
        target = objs_to_merge[0]
        new_name = simpledialog.askstring("Merge as Instances", 
                                          "Name for merged object (each selection becomes an instance):",
                                          initialvalue=target.name, parent=self.root)
        if not new_name:
            return
        
        # Merge: each object's instances become instances of the target
        inst_num = len(target.instances)
        for other in objs_to_merge[1:]:
            for inst in other.instances:
                inst_num += 1
                inst.instance_num = inst_num
                target.instances.append(inst)
            tab.groups.remove(other)
        
        target.name = new_name
        self.workspace_modified = True
        self._update_object_tree()
        self._update_display()
        self.status_var.set(f"Merged {len(objs_to_merge)} objects into '{new_name}' ({len(target.instances)} instances)")
    
    def _merge_as_group(self):
        """Merge selected items - all elements become grouped elements of ONE instance."""
        selection = self.object_tree.selection()
        if len(selection) < 2:
            messagebox.showinfo("Info", "Select at least 2 items to merge as group")
            return
        
        tab = self._get_current_tab()
        if not tab:
            return
        
        # Collect all elements from selection
        elements_to_group = []
        obj_ids_to_remove = set()
        
        for item_id in selection:
            if item_id.startswith("o_"):
                obj_id = item_id[2:]
                for obj in tab.groups:
                    if obj.object_id == obj_id:
                        for inst in obj.instances:
                            elements_to_group.extend(inst.elements)
                        obj_ids_to_remove.add(obj_id)
            elif item_id.startswith("i_"):
                inst_id = item_id[2:]
                for obj in tab.groups:
                    for inst in obj.instances:
                        if inst.instance_id == inst_id:
                            elements_to_group.extend(inst.elements)
                            if len(obj.instances) == 1:
                                obj_ids_to_remove.add(obj.object_id)
            elif item_id.startswith("e_"):
                elem_id = item_id[2:]
                for obj in tab.groups:
                    for inst in obj.instances:
                        for elem in inst.elements:
                            if elem.element_id == elem_id:
                                elements_to_group.append(elem)
        
        if len(elements_to_group) < 2:
            messagebox.showinfo("Info", "Need at least 2 elements to group")
            return
        
        # Ask for object name
        cat_name = self.category_var.get() or "R"
        new_name = simpledialog.askstring("Merge as Group", 
                                          f"Name for new object ({len(elements_to_group)} grouped elements):",
                                          parent=self.root)
        if not new_name:
            return
        
        # Remove old objects
        tab.groups = [g for g in tab.groups if g.object_id not in obj_ids_to_remove]
        
        # Also remove elements that were individually selected
        elem_ids = {e.element_id for e in elements_to_group}
        for obj in tab.groups:
            for inst in obj.instances:
                inst.elements = [e for e in inst.elements if e.element_id not in elem_ids]
            obj.instances = [i for i in obj.instances if len(i.elements) > 0]
        tab.groups = [g for g in tab.groups if len(g.instances) > 0]
        
        # Create new object with one instance containing all elements
        new_obj = SegmentedObject(
            object_id=str(uuid.uuid4())[:8],
            name=new_name,
            category=cat_name
        )
        new_inst = ObjectInstance(
            instance_id=str(uuid.uuid4())[:8],
            instance_num=1,
            page_id=tab.tab_id
        )
        new_inst.elements = elements_to_group
        new_obj.instances.append(new_inst)
        tab.groups.append(new_obj)
        
        self.workspace_modified = True
        self._update_object_tree()
        self._update_display()
        self.status_var.set(f"Created '{new_name}' with {len(elements_to_group)} grouped elements")
    
    def _zoom_in(self):
        self.zoom_level = min(5.0, self.zoom_level * 1.25)
        self._update_display()
    
    def _zoom_out(self):
        self.zoom_level = max(0.1, self.zoom_level / 1.25)
        self._update_display()
    
    def _zoom_fit(self):
        tab = self._get_current_tab()
        if not tab or tab.original_image is None or not hasattr(tab, 'canvas'):
            return
        self.root.update_idletasks()
        h, w = tab.original_image.shape[:2]
        cw, ch = max(tab.canvas.winfo_width(), 100), max(tab.canvas.winfo_height(), 100)
        self.zoom_level = min(cw / w, ch / h) * 0.9
        self._update_display()
    
    def _create_tab_canvas(self, tab: PageTab):
        frame = ttk.Frame(self.notebook)
        h_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(frame, bg="#333", cursor="crosshair",
                          xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        canvas.pack(fill=tk.BOTH, expand=True)
        h_scroll.config(command=canvas.xview)
        v_scroll.config(command=canvas.yview)
        
        canvas.bind("<Button-1>", self._on_left_click)
        canvas.bind("<Double-Button-1>", self._on_double_click)
        canvas.bind("<Button-3>", self._on_right_click)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", self._on_release)
        canvas.bind("<Motion>", self._on_mouse_move)
        
        tab.canvas = canvas
        tab.frame = frame
    
    def _add_page_tab(self, tab: PageTab):
        if tab.original_image is None:
            return
        self.tabs[tab.tab_id] = tab
        self._create_tab_canvas(tab)
        self.notebook.add(tab.frame, text=tab.display_name)
        
        h, w = tab.original_image.shape[:2]
        tab.segmentation_layer = np.zeros((h, w, 4), dtype=np.uint8)
        
        self.notebook.select(tab.frame)
        self.current_tab_id = tab.tab_id
        self.workspace_modified = True
        
        self.root.update_idletasks()
        raster_path = self.output_dir / tab.raster_filename
        try:
            cv2.imwrite(str(raster_path), tab.original_image)
        except:
            pass
        
        self.root.after(200, lambda: (self._zoom_fit(), self._update_display()))
    
    def _on_tab_changed(self, event):
        try:
            selected = self.notebook.select()
            for tid, tab in self.tabs.items():
                if hasattr(tab, 'frame') and str(tab.frame) == selected:
                    self.current_tab_id = tid
                    self._update_display()
                    self._update_object_tree()
                    break
        except:
            pass
    
    def _update_display(self):
        tab = self._get_current_tab()
        if not tab or tab.original_image is None or not hasattr(tab, 'canvas'):
            return
        
        try:
            h, w = tab.original_image.shape[:2]
            if tab.segmentation_layer is None:
                tab.segmentation_layer = np.zeros((h, w, 4), dtype=np.uint8)
            
            # Rebuild segmentation layer from groups
            tab.segmentation_layer = np.zeros((h, w, 4), dtype=np.uint8)
            for group in tab.groups:
                if group.category in self.categories:
                    cat = self.categories[group.category]
                    if not cat.visible:
                        continue
                    
                    opacity = self.planform_opacity if group.category == "planform" else 0.7
                    
                    for inst in group.instances:
                        for elem in inst.elements:
                            if elem.mask is not None and elem.mask.shape == (h, w):
                                tab.segmentation_layer[elem.mask > 0, 0] = cat.color_bgr[0]
                                tab.segmentation_layer[elem.mask > 0, 1] = cat.color_bgr[1]
                                tab.segmentation_layer[elem.mask > 0, 2] = cat.color_bgr[2]
                                tab.segmentation_layer[elem.mask > 0, 3] = int(255 * opacity)
            
            # Blend
            original_rgba = cv2.cvtColor(tab.original_image, cv2.COLOR_BGR2RGBA)
            alpha = tab.segmentation_layer[:, :, 3:4] / 255.0
            blended = (original_rgba * (1 - alpha * 0.5) + tab.segmentation_layer * alpha * 0.5).astype(np.uint8)
            
            # Highlight selected elements
            for obj in tab.groups:
                is_obj_selected = obj.object_id in self.selected_group_ids
                for inst in obj.instances:
                    is_inst_selected = inst.instance_id in self.selected_instance_ids
                    for elem in inst.elements:
                        is_elem_selected = elem.element_id in self.selected_element_ids
                        if is_elem_selected or is_inst_selected or is_obj_selected:
                            if elem.mask is not None:
                                contours, _ = cv2.findContours(elem.mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                                cv2.drawContours(blended, contours, -1, (255, 255, 0, 255), 3)
            
            # Draw labels
            if self.show_labels:
                blended_bgr = cv2.cvtColor(blended, cv2.COLOR_RGBA2BGR)
                self._draw_labels(blended_bgr, tab)
                blended = cv2.cvtColor(blended_bgr, cv2.COLOR_BGR2RGBA)
            
            dw, dh = max(1, int(w * self.zoom_level)), max(1, int(h * self.zoom_level))
            resized = cv2.resize(blended, (dw, dh))
            pil_img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGRA2RGBA))
            tab.tk_image = ImageTk.PhotoImage(pil_img)
            
            tab.canvas.delete("all")
            tab.canvas.create_image(0, 0, anchor=tk.NW, image=tab.tk_image)
            tab.canvas.configure(scrollregion=(0, 0, dw, dh))
            
            self._redraw_temp_points()
        except Exception as e:
            print(f"Display error: {e}")
        
        self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
    
    def _draw_labels(self, image: np.ndarray, tab: PageTab):
        """Draw labels on the image."""
        for group in tab.groups:
            if group.category in self.categories and not self.categories[group.category].visible:
                continue
            for inst_idx, inst in enumerate(group.instances):
                for elem in inst.elements:
                    if elem.mask is not None:
                        ys, xs = np.where(elem.mask > 0)
                        if len(xs) > 0:
                            cx, cy = int(np.mean(xs)), int(np.mean(ys))
                            x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
                            pos = elem.label_position
                            if "top" in pos: ly = y0 - 5
                            elif "bottom" in pos: ly = y1 + 15
                            else: ly = cy
                            if "left" in pos: lx = x0
                            elif "right" in pos: lx = x1
                            else: lx = cx
                            
                            label = group.name
                            if len(group.instances) > 1:
                                label = f"{group.name}[{inst_idx+1}]"
                            cv2.putText(image, label, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 
                                      0.5, (0, 0, 0), 3)
                            cv2.putText(image, label, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 
                                      0.5, (255, 255, 255), 1)
    
    def _redraw_temp_points(self):
        tab = self._get_current_tab()
        if not tab or not hasattr(tab, 'canvas'):
            return
        for pid in self.temp_drawing_ids:
            try: tab.canvas.delete(pid)
            except: pass
        self.temp_drawing_ids.clear()
        
        if len(self.current_points) > 0:
            scaled = [(int(x * self.zoom_level), int(y * self.zoom_level)) for x, y in self.current_points]
            
            # Draw first point larger (snap target for polyline)
            if self.current_mode == "polyline" and len(scaled) >= 3:
                snap_radius = int(self.snap_distance * self.zoom_level)
                oid = tab.canvas.create_oval(scaled[0][0]-snap_radius, scaled[0][1]-snap_radius,
                                              scaled[0][0]+snap_radius, scaled[0][1]+snap_radius,
                                              outline="lime", width=2, dash=(4, 2))
                self.temp_drawing_ids.append(oid)
            
            for i, (x, y) in enumerate(scaled):
                color = "lime" if i == 0 else "yellow"
                oid = tab.canvas.create_oval(x-4, y-4, x+4, y+4, fill=color, outline="black")
                self.temp_drawing_ids.append(oid)
            if len(scaled) > 1:
                for i in range(len(scaled) - 1):
                    lid = tab.canvas.create_line(scaled[i][0], scaled[i][1], 
                                                  scaled[i+1][0], scaled[i+1][1], fill="yellow", width=2)
                    self.temp_drawing_ids.append(lid)
    
    def _update_object_tree(self):
        """Update the object tree with simplified hierarchy and colored icons.
        
        Hierarchy shown:
        - Simple object (1 instance, 1 element): Just "R1"
        - Object with grouped elements (1 instance, N elements): "R1" → elements
        - Object with instances: "R1" → "Instance 1" → elements, "Instance 2" → elements
        """
        self.object_tree.delete(*self.object_tree.get_children())
        
        # Create color icon images
        if not hasattr(self, 'tree_icons'):
            self.tree_icons = {}
        
        tab = self._get_current_tab()
        if not tab:
            return
        
        for obj in tab.groups:
            # Create or get color icon
            cat = self.categories.get(obj.category)
            if cat:
                color = cat.color_rgb
                icon_key = f"{color[0]}_{color[1]}_{color[2]}"
                if icon_key not in self.tree_icons:
                    img = Image.new('RGB', (12, 12), color)
                    ImageDraw.Draw(img).rectangle([0, 0, 11, 11], outline=(0, 0, 0))
                    self.tree_icons[icon_key] = ImageTk.PhotoImage(img)
                icon = self.tree_icons[icon_key]
            else:
                icon = None
            
            # Determine display mode
            is_simple = obj.is_simple if hasattr(obj, 'is_simple') else (
                len(obj.instances) == 1 and len(obj.instances[0].elements) == 1
            )
            has_multiple_instances = len(obj.instances) > 1
            
            if is_simple:
                # Simple: just show object name (no children)
                elem = obj.instances[0].elements[0]
                obj_text = f"{obj.name}"
                self.object_tree.insert("", "end", iid=f"o_{obj.object_id}", 
                                        text=obj_text, image=icon if icon else "")
            elif not has_multiple_instances:
                # Single instance with grouped elements: Object → Elements
                obj_text = f"{obj.name} ({obj.element_count} grouped)"
                obj_node = self.object_tree.insert("", "end", iid=f"o_{obj.object_id}",
                                                    text=obj_text, open=False, image=icon if icon else "")
                inst = obj.instances[0]
                for idx, elem in enumerate(inst.elements):
                    elem_text = f"├ element {idx+1}"
                    self.object_tree.insert(obj_node, "end", iid=f"e_{elem.element_id}", text=elem_text)
            else:
                # Multiple instances: Object → Instances → Elements
                obj_text = f"{obj.name} ({len(obj.instances)} instances)"
                obj_node = self.object_tree.insert("", "end", iid=f"o_{obj.object_id}",
                                                    text=obj_text, open=False, image=icon if icon else "")
                for inst_idx, inst in enumerate(obj.instances):
                    view_info = f" [{inst.view_type}]" if inst.view_type else ""
                    if len(inst.elements) > 1:
                        inst_text = f"Instance {inst_idx + 1}{view_info} ({len(inst.elements)} grouped)"
                    else:
                        inst_text = f"Instance {inst_idx + 1}{view_info}"
                    inst_node = self.object_tree.insert(obj_node, "end", iid=f"i_{inst.instance_id}",
                                                         text=inst_text, open=False)
                    for idx, elem in enumerate(inst.elements):
                        elem_text = f"├ element {idx+1}"
                        self.object_tree.insert(inst_node, "end", iid=f"e_{elem.element_id}", text=elem_text)
    
    def _on_tree_select(self, event):
        selection = self.object_tree.selection()
        
        # Multi-select support
        self.selected_group_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        
        for item_id in selection:
            if item_id.startswith("o_"):
                self.selected_group_ids.add(item_id[2:])
            elif item_id.startswith("i_"):
                self.selected_instance_ids.add(item_id[2:])
                parent = self.object_tree.parent(item_id)
                if parent.startswith("o_"):
                    self.selected_group_ids.add(parent[2:])
            elif item_id.startswith("e_"):
                self.selected_element_ids.add(item_id[2:])
                parent = self.object_tree.parent(item_id)
                if parent.startswith("i_"):
                    self.selected_instance_ids.add(parent[2:])
                    gp = self.object_tree.parent(parent)
                    if gp.startswith("o_"):
                        self.selected_group_ids.add(gp[2:])
                elif parent.startswith("o_"):
                    # Element directly under object (single instance case)
                    self.selected_group_ids.add(parent[2:])
        
        self._update_display()
    
    def _on_tree_double_click(self, event):
        self._edit_attributes()
    
    def _rename_selected(self):
        tab = self._get_current_tab()
        if not tab or not self.selected_group_ids:
            messagebox.showinfo("Info", "Select an object to rename")
            return
        obj_id = next(iter(self.selected_group_ids))
        for obj in tab.groups:
            if obj.object_id == obj_id:
                new_name = simpledialog.askstring("Rename", f"New name for {obj.name}:", 
                                                   initialvalue=obj.name, parent=self.root)
                if new_name:
                    obj.name = new_name
                    self.workspace_modified = True
                    self._update_object_tree()
                    self._update_display()
                break
    
    def _new_instance(self):
        """Add a new empty instance to the selected object."""
        tab = self._get_current_tab()
        if not tab or not self.selected_group_ids:
            messagebox.showinfo("Info", "Select an object to add an instance to")
            return
        obj_id = next(iter(self.selected_group_ids))
        for obj in tab.groups:
            if obj.object_id == obj_id:
                view_type = simpledialog.askstring("Instance View", 
                                                   "View type for this instance (e.g., side, top, template):",
                                                   parent=self.root) or ""
                new_inst = ObjectInstance(
                    instance_id=str(uuid.uuid4())[:8], 
                    instance_num=len(obj.instances) + 1,
                    page_id=tab.tab_id,
                    view_type=view_type
                )
                obj.instances.append(new_inst)
                self.workspace_modified = True
                self._update_object_tree()
                self.status_var.set(f"New instance added to {obj.name}")
                break
    
    def _edit_attributes(self):
        tab = self._get_current_tab()
        if not tab or not self.selected_group_ids:
            messagebox.showinfo("Info", "Select an object to edit attributes")
            return
        obj_id = next(iter(self.selected_group_ids))
        for obj in tab.groups:
            if obj.object_id == obj_id:
                dialog = AttributeDialog(self.root, obj)
                if dialog.result:
                    obj.attributes = dialog.result
                    self.workspace_modified = True
                break
    
    def _delete_selected(self):
        tab = self._get_current_tab()
        if not tab:
            return
        
        deleted = False
        
        # Delete selected elements
        for elem_id in self.selected_element_ids:
            for obj in tab.groups:
                for inst in obj.instances:
                    inst.elements = [e for e in inst.elements if e.element_id != elem_id]
                obj.instances = [i for i in obj.instances if len(i.elements) > 0]
            deleted = True
        
        # Delete selected instances
        for inst_id in self.selected_instance_ids:
            for obj in tab.groups:
                obj.instances = [i for i in obj.instances if i.instance_id != inst_id]
            deleted = True
        
        # Delete selected objects
        for obj_id in self.selected_group_ids:
            tab.groups = [g for g in tab.groups if g.object_id != obj_id]
            deleted = True
        
        # Clean up empty objects
        tab.groups = [g for g in tab.groups if len(g.instances) > 0]
        
        if deleted:
            self.selected_group_ids.clear()
            self.selected_instance_ids.clear()
            self.selected_element_ids.clear()
            self.workspace_modified = True
            self._update_object_tree()
            self._update_display()
            self.status_var.set("Deleted selected items")
    
    def _canvas_to_image(self, canvas_x: int, canvas_y: int) -> Tuple[int, int]:
        tab = self._get_current_tab()
        if not tab or not hasattr(tab, 'canvas'):
            return (0, 0)
        x = int(tab.canvas.canvasx(canvas_x) / self.zoom_level)
        y = int(tab.canvas.canvasy(canvas_y) / self.zoom_level)
        return (x, y)
    
    def _on_left_click(self, event):
        tab = self._get_current_tab()
        if not tab or tab.original_image is None:
            return
        
        x, y = self._canvas_to_image(event.x, event.y)
        h, w = tab.original_image.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return
        
        # Handle group mode
        if self.group_mode_active and self.current_mode == "select":
            elem_id = self._get_element_at_point(x, y)
            if elem_id and elem_id not in self.group_mode_selections:
                self.group_mode_selections.append(elem_id)
                self._update_group_count()
                self._update_display()
                self.status_var.set(f"Added to group. Total: {len(self.group_mode_selections)}")
            return
        
        if self.current_mode == "select":
            self._select_at_point(x, y)
        elif self.current_mode == "flood":
            self._flood_fill(x, y)
        elif self.current_mode in ["polyline", "line"]:
            # Snap to close polyline if near first point
            if self.current_mode == "polyline" and len(self.current_points) >= 3:
                first_pt = self.current_points[0]
                dist = math.sqrt((x - first_pt[0])**2 + (y - first_pt[1])**2)
                if dist < self.snap_distance:
                    # Snap to first point and close
                    self.status_var.set("Snapped to start - closing polygon")
                    self._finish_polyline()
                    return
            self.current_points.append((x, y))
            self._redraw_temp_points()
        elif self.current_mode == "freeform":
            self.is_drawing = True
            self.current_points = [(x, y)]
    
    def _get_element_at_point(self, x: int, y: int) -> Optional[str]:
        """Get element ID at the given point."""
        tab = self._get_current_tab()
        if not tab:
            return None
        for group in tab.groups:
            for inst in group.instances:
                for elem in inst.elements:
                    if elem.mask is not None and 0 <= y < elem.mask.shape[0] and 0 <= x < elem.mask.shape[1]:
                        if elem.mask[y, x] > 0:
                            return elem.element_id
        return None
    
    def _on_double_click(self, event):
        if self.current_mode == "polyline" and len(self.current_points) >= 3:
            self._finish_polyline()
    
    def _on_right_click(self, event):
        if len(self.current_points) > 0:
            self.current_points.pop()
            self._redraw_temp_points()
    
    def _on_drag(self, event):
        if self.current_mode == "freeform" and self.is_drawing:
            x, y = self._canvas_to_image(event.x, event.y)
            self.current_points.append((x, y))
            self._redraw_temp_points()
    
    def _on_release(self, event):
        if self.current_mode == "freeform" and self.is_drawing:
            self.is_drawing = False
            if len(self.current_points) >= 2:
                self._finish_freeform()
    
    def _on_mouse_move(self, event):
        x, y = self._canvas_to_image(event.x, event.y)
        self.status_var.set(f"Position: ({x}, {y}) | Mode: {self.current_mode}")
    
    def _on_key(self, event):
        pass
    
    def _on_enter(self, event):
        if self.current_mode == "line" and len(self.current_points) >= 2:
            self._finish_line()
        elif self.current_mode == "polyline" and len(self.current_points) >= 3:
            self._finish_polyline()
    
    def _cancel_drawing(self):
        self.current_points.clear()
        self.is_drawing = False
        self._redraw_temp_points()
    
    def _undo(self):
        tab = self._get_current_tab()
        if not tab or len(tab.groups) == 0:
            return
        last_group = tab.groups[-1]
        if last_group.instances and last_group.instances[-1].elements:
            last_group.instances[-1].elements.pop()
            if len(last_group.instances[-1].elements) == 0:
                last_group.instances.pop()
            if len(last_group.instances) == 0:
                tab.groups.pop()
        self.workspace_modified = True
        self._update_object_tree()
        self._update_display()
    
    def _select_at_point(self, x: int, y: int):
        tab = self._get_current_tab()
        if not tab:
            return
        for group in tab.groups:
            for inst in group.instances:
                for elem in inst.elements:
                    if elem.mask is not None and elem.mask[y, x] > 0:
                        self.selected_group_id = group.group_id
                        self.selected_instance_id = inst.instance_id
                        self.selected_element_id = elem.element_id
                        self.object_tree.selection_set(f"e_{elem.element_id}")
                        self._update_display()
                        return
        self.selected_element_id = None
        self._update_display()
    
    def _flood_fill(self, x: int, y: int):
        tab = self._get_current_tab()
        if not tab or not self.category_var.get():
            return
        
        cat_name = self.category_var.get()
        cat = self.categories.get(cat_name)
        if not cat:
            return
        
        gray = cv2.cvtColor(tab.original_image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        mask = np.zeros((h + 2, w + 2), np.uint8)
        
        if cat_name == "eraser":
            for group in tab.groups:
                for inst in group.instances:
                    inst.elements = [e for e in inst.elements if not (e.mask is not None and e.mask[y, x] > 0)]
                group.instances = [i for i in group.instances if len(i.elements) > 0]
            tab.groups = [g for g in tab.groups if len(g.instances) > 0]
            self.workspace_modified = True
            self._update_object_tree()
            self._update_display()
            return
        
        _, _, fill_mask, _ = cv2.floodFill(gray.copy(), mask, (x, y), 255, 
                                            self.tolerance, self.tolerance, cv2.FLOODFILL_MASK_ONLY)
        result_mask = (fill_mask[1:-1, 1:-1] > 0).astype(np.uint8) * 255
        
        self._add_element(cat_name, "flood", [(x, y)], result_mask)
    
    def _finish_polyline(self):
        if len(self.current_points) < 3:
            return
        tab = self._get_current_tab()
        if not tab:
            return
        
        cat_name = self.category_var.get() or "planform"
        h, w = tab.original_image.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        pts = np.array(self.current_points, dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
        
        self._add_element(cat_name, "polyline", list(self.current_points), mask)
        self.current_points.clear()
        self._redraw_temp_points()
    
    def _finish_freeform(self):
        if len(self.current_points) < 2:
            return
        tab = self._get_current_tab()
        if not tab:
            return
        
        cat_name = self.category_var.get() or "planform"
        h, w = tab.original_image.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        pts = np.array(self.current_points, dtype=np.int32)
        cv2.polylines(mask, [pts], False, 255, self.line_thickness * 3)
        
        self._add_element(cat_name, "freeform", list(self.current_points), mask)
        self.current_points.clear()
        self._redraw_temp_points()
    
    def _finish_line(self):
        if len(self.current_points) < 2:
            return
        tab = self._get_current_tab()
        if not tab:
            return
        
        cat_name = self.category_var.get() or "longeron"
        h, w = tab.original_image.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        pts = np.array(self.current_points, dtype=np.int32)
        cv2.polylines(mask, [pts], False, 255, self.line_thickness)
        
        self._add_element(cat_name, "line", list(self.current_points), mask)
        self.current_points.clear()
        self._redraw_temp_points()
    
    def _add_element(self, cat_name: str, mode: str, points: List[Tuple[int, int]], mask: np.ndarray):
        tab = self._get_current_tab()
        if not tab or cat_name not in self.categories:
            return
        
        cat = self.categories[cat_name]
        element = SegmentElement(
            element_id=str(uuid.uuid4())[:8],
            category=cat_name,
            mode=mode,
            points=points,
            mask=mask,
            color=cat.color_rgb,
            label_position=self.label_position
        )
        
        # If in group mode, collect elements without creating object yet
        if self.group_mode_active and cat_name not in ["eraser"]:
            self.group_mode_elements.append(element)
            self._update_group_count()
            self._update_display_with_pending()
            self.status_var.set(f"Added to group ({len(self.group_mode_elements)} elements)")
            return
        
        # Normal mode: create object with single instance containing single element
        prefix = cat.prefix if hasattr(cat, 'prefix') else cat_name[0].upper()
        count = sum(1 for g in tab.groups if g.category == cat_name) + 1
        name = f"{prefix}{count}"
        
        new_obj = SegmentedObject(
            object_id=str(uuid.uuid4())[:8],
            name=name,
            category=cat_name
        )
        new_inst = ObjectInstance(
            instance_id=str(uuid.uuid4())[:8], 
            instance_num=1,
            page_id=tab.tab_id
        )
        new_inst.elements.append(element)
        new_obj.instances.append(new_inst)
        tab.groups.append(new_obj)
        
        self.workspace_modified = True
        self._update_object_tree()
        self._update_display()
        self.status_var.set(f"Created {name}")
    
    def _update_display_with_pending(self):
        """Update display including pending group mode elements."""
        tab = self._get_current_tab()
        if not tab or tab.original_image is None or not hasattr(tab, 'canvas'):
            return
        
        # First do normal display
        self._update_display()
        
        # Then overlay pending group elements with dashed outline
        if self.group_mode_active and self.group_mode_elements:
            for elem in self.group_mode_elements:
                if elem.mask is not None:
                    contours, _ = cv2.findContours(elem.mask.astype(np.uint8), 
                                                   cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    # Draw dashed indicator on canvas
                    for contour in contours:
                        scaled_pts = [(int(p[0][0] * self.zoom_level), int(p[0][1] * self.zoom_level)) 
                                     for p in contour]
                        if len(scaled_pts) > 2:
                            for i in range(len(scaled_pts)):
                                x1, y1 = scaled_pts[i]
                                x2, y2 = scaled_pts[(i+1) % len(scaled_pts)]
                                tab.canvas.create_line(x1, y1, x2, y2, fill="cyan", 
                                                       width=2, dash=(4, 4))
    
    def _add_manual_category(self):
        prefix = self.new_cat_entry.get().strip().upper()
        if not prefix:
            return
        if prefix in self.categories:
            messagebox.showinfo("Info", f"Category {prefix} already exists")
            return
        
        full_name = simpledialog.askstring("Category Name", f"Full name for '{prefix}':", 
                                           initialvalue=prefix, parent=self.root)
        if not full_name:
            return
        
        colors = [(255,0,0), (0,255,0), (0,0,255), (255,165,0), (255,0,255),
                  (0,255,255), (128,0,128), (255,192,203), (165,42,42), (128,128,128)]
        color = colors[len(self.categories) % len(colors)]
        
        self.categories[prefix] = DynamicCategory(
            name=prefix, prefix=prefix, full_name=full_name,
            color_rgb=color, color_bgr=(color[2], color[1], color[0]),
            selection_mode="flood"
        )
        self.new_cat_entry.delete(0, tk.END)
        self._refresh_category_ui()
    
    def _scan_all_pages(self):
        active_tabs = [t for t in self.tabs.values() if t.active and t.original_image is not None]
        if not active_tabs:
            messagebox.showwarning("Warning", "No active pages to scan")
            return
        
        dialog = LabelScanDialog(self.root, active_tabs)
        if dialog.result:
            colors = [(255,0,0), (0,255,0), (0,0,255), (255,165,0), (255,0,255),
                      (0,255,255), (128,0,128), (255,192,203), (165,42,42), (128,128,128)]
            for prefix, full_name in dialog.result.items():
                if prefix not in self.categories:
                    color = colors[len(self.categories) % len(colors)]
                    self.categories[prefix] = DynamicCategory(
                        name=prefix, prefix=prefix, full_name=full_name,
                        color_rgb=color, color_bgr=(color[2], color[1], color[0]),
                        selection_mode="flood"
                    )
            self._refresh_category_ui()
            self.workspace_modified = True
            self.status_var.set(f"Added {len(dialog.result)} categories")
    
    def _open_pdf(self):
        if self.tabs and self.workspace_modified:
            result = messagebox.askyesnocancel("Save Changes", "Save current workspace before opening new PDF?")
            if result is None:
                return
            if result:
                self._save_workspace()
        
        path = filedialog.askopenfilename(
            title="Open PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not path:
            return
        
        self._load_pdf(path)
    
    def _load_pdf(self, path: str):
        try:
            import fitz
            doc = fitz.open(path)
            pages = []
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                else:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                pages.append(img)
            doc.close()
            
            dialog = PDFLoaderDialog(self.root, path, pages)
            if dialog.result:
                # Close existing tabs
                for tid in list(self.tabs.keys()):
                    if hasattr(self.tabs[tid], 'frame'):
                        idx = self.notebook.index(self.tabs[tid].frame)
                        self.notebook.forget(idx)
                    del self.tabs[tid]
                
                # Reset categories except defaults
                default_cats = ["eraser", "planform", "longeron", "spar"]
                self.categories = {k: v for k, v in self.categories.items() if k in default_cats}
                self._refresh_category_ui()
                
                self.workspace_file = None
                self.workspace_modified = True
                
                for model_name, page_name, img in dialog.result:
                    tab = PageTab(
                        tab_id=str(uuid.uuid4())[:8],
                        model_name=model_name,
                        page_name=page_name,
                        original_image=img,
                        source_path=path
                    )
                    self._add_page_tab(tab)
                
                self.status_var.set(f"Loaded {len(dialog.result)} pages from {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load PDF: {e}")
    
    def _save_workspace(self):
        if not self.workspace_file:
            self._save_workspace_as()
            return
        self._do_save_workspace(self.workspace_file)
    
    def _save_workspace_as(self):
        path = filedialog.asksaveasfilename(
            title="Save Workspace",
            defaultextension=".pmw",
            filetypes=[("PlanMod Workspace", "*.pmw"), ("All files", "*.*")]
        )
        if path:
            self._do_save_workspace(path)
    
    def _do_save_workspace(self, path: str):
        try:
            data = {
                "version": VERSION,
                "timestamp": datetime.now().isoformat(),
                "categories": {k: {"name": v.name, "prefix": v.prefix, "full_name": v.full_name,
                                   "color_rgb": v.color_rgb, "visible": v.visible}
                              for k, v in self.categories.items()},
                "tabs": []
            }
            
            # Save images alongside workspace
            workspace_dir = Path(path).parent
            
            for tid, tab in self.tabs.items():
                # Save image to file
                img_filename = f"{tab.model_name}_{tab.page_name}_raster.png"
                img_path = workspace_dir / img_filename
                if tab.original_image is not None:
                    cv2.imwrite(str(img_path), tab.original_image)
                
                tab_data = {
                    "tab_id": tab.tab_id,
                    "model_name": tab.model_name,
                    "page_name": tab.page_name,
                    "source_path": tab.source_path,
                    "rotation": tab.rotation,
                    "active": tab.active,
                    "image_file": img_filename,
                    "objects": []
                }
                
                for obj in tab.groups:
                    obj_data = {
                        "object_id": obj.object_id,
                        "name": obj.name,
                        "category": obj.category,
                        "attributes": {
                            "material": obj.attributes.material,
                            "width": obj.attributes.width,
                            "height": obj.attributes.height,
                            "depth": obj.attributes.depth,
                            "obj_type": obj.attributes.obj_type,
                            "view": obj.attributes.view,
                            "description": obj.attributes.description,
                            "url": obj.attributes.url
                        },
                        "instances": []
                    }
                    
                    for inst in obj.instances:
                        inst_data = {
                            "instance_id": inst.instance_id,
                            "instance_num": inst.instance_num,
                            "page_id": inst.page_id,
                            "view_type": inst.view_type,
                            "elements": []
                        }
                        for elem in inst.elements:
                            inst_data["elements"].append({
                                "element_id": elem.element_id,
                                "mode": elem.mode,
                                "points": elem.points,
                                "label_position": elem.label_position
                            })
                        obj_data["instances"].append(inst_data)
                    
                    tab_data["objects"].append(obj_data)
                
                data["tabs"].append(tab_data)
            
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.workspace_file = path
            self.workspace_modified = False
            self.status_var.set(f"Saved workspace to {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    def _load_workspace(self):
        if self.tabs and self.workspace_modified:
            result = messagebox.askyesnocancel("Save Changes", "Save current workspace first?")
            if result is None:
                return
            if result:
                self._save_workspace()
        
        path = filedialog.askopenfilename(
            title="Open Workspace",
            filetypes=[("PlanMod Workspace", "*.pmw"), ("All files", "*.*")]
        )
        if not path:
            return
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            # Close existing
            for tid in list(self.tabs.keys()):
                if hasattr(self.tabs[tid], 'frame'):
                    try:
                        idx = self.notebook.index(self.tabs[tid].frame)
                        self.notebook.forget(idx)
                    except: pass
                del self.tabs[tid]
            
            # Load categories
            self._init_default_categories()
            for k, v in data.get("categories", {}).items():
                if k not in self.categories:
                    color = tuple(v.get("color_rgb", (128, 128, 128)))
                    self.categories[k] = DynamicCategory(
                        name=v.get("name", k), prefix=v.get("prefix", k),
                        full_name=v.get("full_name", k),
                        color_rgb=color, color_bgr=(color[2], color[1], color[0]),
                        visible=v.get("visible", True)
                    )
            self._refresh_category_ui()
            
            # Load tabs
            workspace_dir = Path(path).parent
            for tab_data in data.get("tabs", []):
                # Try multiple locations for image file
                img_file = tab_data.get("image_file") or tab_data.get("raster_file", "")
                possible_paths = [
                    workspace_dir / img_file,
                    self.output_dir / img_file,
                    workspace_dir / tab_data.get("raster_file", ""),
                ]
                
                img = None
                for raster_path in possible_paths:
                    if raster_path and Path(raster_path).exists():
                        img = cv2.imread(str(raster_path))
                        if img is not None:
                            break
                
                if img is None:
                    continue
                
                tab = PageTab(
                    tab_id=tab_data.get("tab_id", str(uuid.uuid4())[:8]),
                    model_name=tab_data.get("model_name", "Unknown"),
                    page_name=tab_data.get("page_name", "Page"),
                    original_image=img,
                    source_path=tab_data.get("source_path"),
                    rotation=tab_data.get("rotation", 0),
                    active=tab_data.get("active", True)
                )
                
                # Rebuild objects/instances/elements
                h, w = img.shape[:2]
                # Support both old "groups" and new "objects" format
                objects_data = tab_data.get("objects", tab_data.get("groups", []))
                for odata in objects_data:
                    attrs_data = odata.get("attributes", {})
                    obj = SegmentedObject(
                        object_id=odata.get("object_id", odata.get("group_id", str(uuid.uuid4())[:8])),
                        name=odata.get("name", ""),
                        category=odata.get("category", ""),
                        attributes=ObjectAttributes(
                            material=attrs_data.get("material", ""),
                            width=attrs_data.get("width", 0),
                            height=attrs_data.get("height", 0),
                            depth=attrs_data.get("depth", 0),
                            obj_type=attrs_data.get("obj_type", ""),
                            view=attrs_data.get("view", ""),
                            description=attrs_data.get("description", ""),
                            url=attrs_data.get("url", "")
                        )
                    )
                    
                    for idata in odata.get("instances", []):
                        inst = ObjectInstance(
                            instance_id=idata.get("instance_id", str(uuid.uuid4())[:8]),
                            instance_num=idata.get("instance_num", 1),
                            page_id=idata.get("page_id"),
                            view_type=idata.get("view_type", "")
                        )
                        
                        for edata in idata.get("elements", []):
                            points = [tuple(p) for p in edata.get("points", [])]
                            mode = edata.get("mode", "flood")
                            mask = np.zeros((h, w), dtype=np.uint8)
                            
                            if mode == "flood" and points:
                                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                                flood_mask = np.zeros((h+2, w+2), np.uint8)
                                px, py = points[0]
                                if 0 <= px < w and 0 <= py < h:
                                    _, _, fm, _ = cv2.floodFill(gray.copy(), flood_mask, (px, py), 
                                                                255, self.tolerance, self.tolerance, cv2.FLOODFILL_MASK_ONLY)
                                    mask = (fm[1:-1, 1:-1] > 0).astype(np.uint8) * 255
                            elif mode == "polyline" and len(points) >= 3:
                                cv2.fillPoly(mask, [np.array(points, dtype=np.int32)], 255)
                            elif mode in ["line", "freeform"] and len(points) >= 2:
                                cv2.polylines(mask, [np.array(points, dtype=np.int32)], False, 255, self.line_thickness)
                            
                            cat = self.categories.get(obj.category)
                            color = cat.color_rgb if cat else (128, 128, 128)
                            
                            elem = SegmentElement(
                                element_id=edata.get("element_id", str(uuid.uuid4())[:8]),
                                category=obj.category,
                                mode=mode,
                                points=points,
                                mask=mask,
                                color=color,
                                label_position=edata.get("label_position", "center")
                            )
                            inst.elements.append(elem)
                        
                        if inst.elements:
                            obj.instances.append(inst)
                    
                    if obj.instances:
                        tab.groups.append(obj)
                
                self._add_page_tab(tab)
            
            self.workspace_file = path
            self.workspace_modified = False
            self.status_var.set(f"Loaded workspace: {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load workspace: {e}")
    
    def _export_pages(self):
        tab = self._get_current_tab()
        if not tab:
            return
        
        path = filedialog.asksaveasfilename(
            title="Export Segmented Image",
            defaultextension=".png",
            initialfile=tab.segmented_filename,
            filetypes=[("PNG", "*.png"), ("All files", "*.*")]
        )
        if not path:
            return
        
        try:
            h, w = tab.original_image.shape[:2]
            tab.segmentation_layer = np.zeros((h, w, 4), dtype=np.uint8)
            for group in tab.groups:
                if group.category in self.categories:
                    cat = self.categories[group.category]
                    for inst in group.instances:
                        for elem in inst.elements:
                            if elem.mask is not None:
                                tab.segmentation_layer[elem.mask > 0, 0] = cat.color_bgr[0]
                                tab.segmentation_layer[elem.mask > 0, 1] = cat.color_bgr[1]
                                tab.segmentation_layer[elem.mask > 0, 2] = cat.color_bgr[2]
                                tab.segmentation_layer[elem.mask > 0, 3] = 200
            
            original_rgba = cv2.cvtColor(tab.original_image, cv2.COLOR_BGR2RGBA)
            alpha = tab.segmentation_layer[:, :, 3:4] / 255.0
            blended = (original_rgba * (1 - alpha * 0.5) + tab.segmentation_layer * alpha * 0.5).astype(np.uint8)
            
            cv2.imwrite(path, cv2.cvtColor(blended, cv2.COLOR_RGBA2BGRA))
            self.status_var.set(f"Exported to {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
    
    def _export_data(self):
        tab = self._get_current_tab()
        if not tab:
            return
        
        path = filedialog.asksaveasfilename(
            title="Export Data",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        
        try:
            data = {"model": tab.model_name, "page": tab.page_name, "objects": []}
            for group in tab.groups:
                obj = {
                    "name": group.name,
                    "category": group.category,
                    "attributes": {
                        "material": group.attributes.material,
                        "size": {"w": group.attributes.width, "h": group.attributes.height, "d": group.attributes.depth},
                        "type": group.attributes.obj_type,
                        "view": group.attributes.view,
                        "description": group.attributes.description
                    },
                    "instances": []
                }
                for inst in group.instances:
                    inst_data = {"elements": [{"mode": e.mode, "points": e.points} for e in inst.elements]}
                    obj["instances"].append(inst_data)
                data["objects"].append(obj)
            
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            self.status_var.set(f"Exported data to {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
    
    def run(self):
        self.root.mainloop()


def main():
    app = InteractiveSegmenter()
    app.run()


if __name__ == "__main__":
    main()