"""
PlanMod Segmenter Application - Main Coordinator

This is the main entry point that coordinates all modules.
Modern VS Code/Cursor-inspired UI with responsive layout.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from typing import Dict, Set, List, Optional
import uuid
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw

from tools.segmenter.config import (
    load_settings, save_settings, get_theme, get_theme_names, 
    AppSettings, Breakpoints, get_layout_mode
)
from tools.segmenter.models import (
    PageTab, SegmentedObject, ObjectInstance, SegmentElement,
    DynamicCategory, create_default_categories, get_next_color
)
from tools.segmenter.core import SegmentationEngine, Renderer
from tools.segmenter.io import WorkspaceManager, PDFReader
from tools.segmenter.dialogs import PDFLoaderDialog, LabelScanDialog, AttributeDialog, SettingsDialog
from tools.segmenter.widgets import (
    CollapsibleFrame, PositionGrid,
    ResizableLayout, StatusBar, PanelConfig, DockablePanel
)

VERSION = "6.0"


class SegmenterApp:
    """
    Main application coordinator.
    
    This class ties together all the modular components and handles
    high-level application logic.
    """
    
    MODES = {
        "select": "Select existing objects",
        "flood": "Flood fill region",
        "polyline": "Draw polygon",
        "freeform": "Freeform brush",
        "line": "Line segments",
    }
    
    def __init__(self):
        # Load settings
        self.settings = load_settings()
        self.theme = get_theme(self.settings.theme)
        
        # Core components
        self.engine = SegmentationEngine(self.settings.tolerance, self.settings.line_thickness)
        self.renderer = Renderer()
        self.workspace_mgr = WorkspaceManager(self.settings.tolerance, self.settings.line_thickness)
        self.pdf_reader = PDFReader()
        
        # Application state
        self.pages: Dict[str, PageTab] = {}
        self.current_page_id: Optional[str] = None
        self.categories: Dict[str, DynamicCategory] = {}
        self.all_objects: List[SegmentedObject] = []  # Global object list across all pages
        
        # Selection state
        self.selected_object_ids: Set[str] = set()
        self.selected_instance_ids: Set[str] = set()
        self.selected_element_ids: Set[str] = set()
        
        # Tool state
        self.current_mode = "flood"
        self.current_points: List[tuple] = []
        self.is_drawing = False
        self.group_mode_active = False
        self.group_mode_elements: List[SegmentElement] = []
        
        # Display state
        self.zoom_level = 1.0
        self.show_labels = True
        self.label_position = "center"
        
        # Workspace state
        self.workspace_file: Optional[str] = None
        self.workspace_modified = False
        
        # Create UI
        self.root = tk.Tk()
        self.root.title(f"PlanMod Segmenter v{VERSION}")
        # Restore window geometry including position
        geometry = f"{self.settings.window_width}x{self.settings.window_height}"
        if self.settings.window_x >= 0 and self.settings.window_y >= 0:
            geometry += f"+{self.settings.window_x}+{self.settings.window_y}"
        self.root.geometry(geometry)
        
        self._apply_theme()
        self._init_categories()
        self._setup_ui()
        self._bind_events()
    
    def _apply_theme(self):
        """Apply VS Code/Cursor-inspired theme to ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
        t = self.theme
        
        # Base styles
        style.configure(".", background=t["bg"], foreground=t["fg"], font=("Segoe UI", 9))
        style.configure("TFrame", background=t["bg"])
        style.configure("TLabel", background=t["bg"], foreground=t["fg"])
        
        # Primary button (accent color)
        style.configure("TButton", 
                       background=t["button_secondary_bg"], 
                       foreground=t["button_secondary_fg"],
                       padding=(12, 6),
                       borderwidth=0)
        style.map("TButton", 
                 background=[("active", t["button_secondary_hover"]), ("pressed", t["accent"])],
                 foreground=[("active", t["fg"]), ("pressed", t["button_fg"])])
        
        # Accent button
        style.configure("Accent.TButton",
                       background=t["accent"],
                       foreground=t["button_fg"],
                       padding=(12, 6))
        style.map("Accent.TButton",
                 background=[("active", t["accent_hover"]), ("pressed", t["accent_active"])])
        
        # Input fields
        style.configure("TEntry", 
                       fieldbackground=t["input_bg"], 
                       foreground=t["input_fg"],
                       bordercolor=t["input_border"],
                       lightcolor=t["input_border"],
                       darkcolor=t["input_border"],
                       padding=6)
        style.map("TEntry",
                 bordercolor=[("focus", t["input_focus"])],
                 lightcolor=[("focus", t["input_focus"])])
        
        style.configure("TCombobox", 
                       fieldbackground=t["input_bg"], 
                       foreground=t["input_fg"],
                       arrowcolor=t["fg_muted"],
                       padding=4)
        style.map("TCombobox",
                 fieldbackground=[("readonly", t["input_bg"])],
                 selectbackground=[("readonly", t["selection_bg"])])
        
        # Notebook (tabs)
        style.configure("TNotebook", background=t["tab_bg"], borderwidth=0)
        style.configure("TNotebook.Tab", 
                       background=t["tab_bg"], 
                       foreground=t["tab_fg"], 
                       padding=[16, 8],
                       borderwidth=0)
        style.map("TNotebook.Tab", 
                 background=[("selected", t["tab_active_bg"])], 
                 foreground=[("selected", t["tab_active_fg"])])
        
        # Treeview (lists)
        style.configure("Treeview", 
                       background=t["list_bg"], 
                       foreground=t["list_fg"], 
                       fieldbackground=t["list_bg"],
                       borderwidth=0,
                       rowheight=28)
        style.map("Treeview", 
                 background=[("selected", t["list_selected"])],
                 foreground=[("selected", t["selection_fg"])])
        style.configure("Treeview.Heading",
                       background=t["bg_secondary"],
                       foreground=t["fg_muted"],
                       borderwidth=0)
        
        # Checkbutton & Radiobutton
        style.configure("TCheckbutton", background=t["bg"], foreground=t["fg"])
        style.map("TCheckbutton", background=[("active", t["bg"])])
        style.configure("TRadiobutton", background=t["bg"], foreground=t["fg"])
        style.map("TRadiobutton", background=[("active", t["bg"])])
        
        # LabelFrame
        style.configure("TLabelframe", background=t["bg"], bordercolor=t["border"])
        style.configure("TLabelframe.Label", background=t["bg"], foreground=t["fg_muted"])
        
        # Scale (slider)
        style.configure("TScale", background=t["bg"], troughcolor=t["bg_tertiary"])
        
        # Scrollbar
        style.configure("TScrollbar",
                       background=t["scrollbar_thumb"],
                       troughcolor=t["bg"],
                       borderwidth=0,
                       arrowsize=0)
        style.map("TScrollbar",
                 background=[("active", t["scrollbar_thumb_hover"])])
        
        # Separator
        style.configure("TSeparator", background=t["border"])
        
        # Panel header style
        style.configure("PanelHeader.TLabel", 
                       background=t["panel_header_bg"], 
                       foreground=t["panel_header_fg"],
                       font=("Segoe UI", 9, "bold"),
                       padding=(12, 8))
        
        # Section header style
        style.configure("Section.TLabel", 
                       background=t["bg"], 
                       foreground=t["fg_muted"], 
                       font=("Segoe UI", 9, "bold"))
        
        self.root.configure(bg=t["bg_base"])
    
    def _init_categories(self):
        """Initialize default categories."""
        self.categories = create_default_categories()
    
    def _setup_ui(self):
        """Setup the modern VS Code/Cursor-inspired UI."""
        t = self.theme
        
        # Menu bar
        self._setup_menubar()
        
        # Main responsive layout
        self.layout = ResizableLayout(self.root, t, self.settings)
        self.layout.pack(fill=tk.BOTH, expand=True)
        
        # Add panels to layout
        self._setup_tools_panel()
        self._setup_object_panel()
        
        # Finalize panel layout
        self.layout.finalize_layout()
        
        # Setup center content (notebook)
        self._setup_center(self.layout.get_center_frame())
        
        # Add activity bar bottom buttons
        self.layout.activity_bar.add_spacer()
        self.layout.activity_bar.add_bottom_button("⚙", self._show_settings_dialog, "Settings")
        
        # Status bar
        self.status_bar = StatusBar(self.root, t)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar.add_item("status", "Ready - Open a PDF to begin")
        self.status_bar.add_separator()
        self.status_bar.add_item("zoom", "100%", side="right", click_command=self._zoom_fit)
        self.status_bar.add_item("mode", "Flood", side="right")
        
        # For backward compatibility
        self.status_var = type('obj', (object,), {'set': lambda s, x: self.status_bar.set_item_text("status", x)})()
    
    def _setup_menubar(self):
        """Setup the menu bar."""
        t = self.theme
        
        menubar = tk.Menu(self.root, bg=t["menu_bg"], fg=t["menu_fg"], 
                         activebackground=t["menu_hover"], activeforeground=t["selection_fg"],
                         borderwidth=0)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"],
                           activebackground=t["menu_hover"], activeforeground=t["selection_fg"])
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open PDF...", command=self._open_pdf, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Workspace...", command=self._load_workspace, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Save Workspace", command=self._save_workspace, accelerator="Ctrl+S")
        file_menu.add_command(label="Save Workspace As...", command=self._save_workspace_as)
        file_menu.add_separator()
        file_menu.add_command(label="Export Image...", command=self._export_image)
        file_menu.add_command(label="Export Data...", command=self._export_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        
        # Edit menu (with settings)
        edit_menu = tk.Menu(menubar, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"],
                           activebackground=t["menu_hover"], activeforeground=t["selection_fg"])
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self._undo, accelerator="Ctrl+Z")
        edit_menu.add_separator()
        edit_menu.add_command(label="Delete Selected", command=self._delete_selected, accelerator="Del")
        edit_menu.add_separator()
        edit_menu.add_command(label="Preferences...", command=self._show_settings_dialog)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"],
                           activebackground=t["menu_hover"], activeforeground=t["selection_fg"])
        menubar.add_cascade(label="View", menu=view_menu)
        
        self.view_menu = view_menu
        
        # Panel toggles
        view_menu.add_command(label="Toggle Tools Panel", command=lambda: self.layout._on_panel_toggle("tools"),
                             accelerator="Ctrl+B")
        view_menu.add_command(label="Toggle Objects Panel", command=lambda: self.layout._on_panel_toggle("objects"),
                             accelerator="Ctrl+J")
        view_menu.add_separator()
        
        # View options (per-page toggles)
        view_menu.add_command(label="Hide Background", command=self._toggle_hide_background)
        view_menu.add_command(label="Hide Text", command=self._toggle_hide_text)
        view_menu.add_command(label="Hide Hatching", command=self._toggle_hide_hatching)
        view_menu.add_separator()
        view_menu.add_command(label="Manage Mask Regions...", command=self._show_mask_regions_dialog)
        view_menu.add_separator()
        
        # Ruler options
        ruler_label = "Hide Ruler" if self.settings.show_ruler else "Show Ruler"
        view_menu.add_command(label=ruler_label, command=self._toggle_ruler)
        
        self.ruler_unit_var = tk.StringVar(value=self.settings.ruler_unit)
        ruler_menu = tk.Menu(view_menu, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"])
        view_menu.add_cascade(label="Ruler Unit", menu=ruler_menu)
        ruler_menu.add_radiobutton(label="Inches (1/16\" ticks)", variable=self.ruler_unit_var,
                                   value="inch", command=lambda: self._set_ruler_unit("inch"))
        ruler_menu.add_radiobutton(label="Centimeters (mm ticks)", variable=self.ruler_unit_var,
                                   value="cm", command=lambda: self._set_ruler_unit("cm"))
        view_menu.add_separator()
        
        # Theme submenu
        theme_menu = tk.Menu(view_menu, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"])
        view_menu.add_cascade(label="Theme", menu=theme_menu)
        for theme_name in get_theme_names():
            theme_menu.add_radiobutton(label=theme_name.replace("_", " ").title(), 
                                       command=lambda n=theme_name: self._change_theme(n))
        
        # Zoom submenu
        view_menu.add_separator()
        view_menu.add_command(label="Zoom In", command=self._zoom_in, accelerator="Ctrl++")
        view_menu.add_command(label="Zoom Out", command=self._zoom_out, accelerator="Ctrl+-")
        view_menu.add_command(label="Fit to Window", command=self._zoom_fit, accelerator="Ctrl+0")
    
    def _setup_tools_panel(self):
        """Setup the tools panel (left sidebar)."""
        t = self.theme
        
        config = PanelConfig(
            name="tools",
            icon="🔧",
            title="Tools",
            min_width=200,
            max_width=350,
            default_width=self.settings.sidebar_width,
            side="left"
        )
        
        tools_panel = self.layout.add_panel("tools", config)
        content = tools_panel.content
        
        # Scrollable content
        canvas = tk.Canvas(content, bg=t["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(content, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=t["bg"])
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind mousewheel only when mouse is over this canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        frame.bind("<Enter>", _bind_mousewheel)
        frame.bind("<Leave>", _unbind_mousewheel)
        
        # Mode section
        mode_section = CollapsibleFrame(frame, "Selection Mode", theme=t)
        mode_section.pack(fill=tk.X, padx=8, pady=4)
        
        self.mode_var = tk.StringVar(value="flood")
        for mode, desc in self.MODES.items():
            rb = ttk.Radiobutton(mode_section.content, text=mode.capitalize(), 
                                variable=self.mode_var, value=mode,
                                command=lambda m=mode: self._set_mode(m))
            rb.pack(anchor=tk.W, padx=8, pady=2)
        
        # Categories section
        cat_section = CollapsibleFrame(frame, "Categories", theme=t)
        cat_section.pack(fill=tk.X, padx=8, pady=4)
        
        ttk.Button(cat_section.content, text="🔍 Scan Labels", 
                   command=self._scan_labels).pack(fill=tk.X, padx=8, pady=4)
        
        self.cat_frame = tk.Frame(cat_section.content, bg=t["bg"])
        self.cat_frame.pack(fill=tk.X, padx=8, pady=4)
        self.category_var = tk.StringVar()
        self._refresh_categories()
        
        # Label position
        label_section = CollapsibleFrame(frame, "Label Position", theme=t)
        label_section.pack(fill=tk.X, padx=8, pady=4)
        
        self.position_grid = PositionGrid(label_section.content, self._set_label_position, "center")
        self.position_grid.pack(padx=8, pady=4)
        
        self.show_labels_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(label_section.content, text="Show labels", 
                        variable=self.show_labels_var, 
                        command=self._toggle_labels).pack(padx=8, anchor=tk.W)
        
        # Group mode section
        group_section = CollapsibleFrame(frame, "Group Selection", theme=t)
        group_section.pack(fill=tk.X, padx=8, pady=4)
        
        self.group_mode_var = tk.BooleanVar()
        ttk.Checkbutton(group_section.content, text="Group Mode", 
                        variable=self.group_mode_var,
                        command=self._toggle_group_mode).pack(anchor=tk.W, padx=8, pady=2)
        ttk.Button(group_section.content, text="End Group & Create",
                   command=self._finish_group).pack(fill=tk.X, padx=8, pady=4)
        self.group_count = tk.Label(group_section.content, text="Elements: 0", 
                                   fg=t["accent"], bg=t["bg"], font=("Segoe UI", 9))
        self.group_count.pack(anchor=tk.W, padx=8, pady=2)
        
        # Current view section
        view_section = CollapsibleFrame(frame, "Current View", theme=t)
        view_section.pack(fill=tk.X, padx=8, pady=4)
        
        view_frame = tk.Frame(view_section.content, bg=t["bg"])
        view_frame.pack(fill=tk.X, padx=8, pady=4)
        
        tk.Label(view_frame, text="Assign to view:", bg=t["bg"], fg=t["fg_muted"],
                font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        self.current_view_var = tk.StringVar(value="")
        self.view_combo = ttk.Combobox(view_frame, textvariable=self.current_view_var,
                                       values=["", "Plan", "Front", "Side", "Top", "Iso", "Detail"],
                                       width=10)
        self.view_combo.pack(side=tk.RIGHT)
        self.view_combo.bind("<<ComboboxSelected>>", self._on_view_changed)
        
        tk.Label(view_section.content, text="New objects will be assigned this view",
                bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 8)).pack(anchor=tk.W, padx=8)
        
        # Quick actions
        action_section = CollapsibleFrame(frame, "Quick Actions", theme=t)
        action_section.pack(fill=tk.X, padx=8, pady=4)
        
        ttk.Button(action_section.content, text="Undo", 
                   command=self._undo).pack(fill=tk.X, padx=8, pady=2)
        ttk.Button(action_section.content, text="Cancel",
                   command=self._cancel).pack(fill=tk.X, padx=8, pady=2)
        
        # Zoom controls
        zoom_frame = tk.Frame(action_section.content, bg=t["bg"])
        zoom_frame.pack(fill=tk.X, padx=8, pady=4)
        
        ttk.Button(zoom_frame, text="−", width=3, command=self._zoom_out).pack(side=tk.LEFT)
        self.zoom_label = tk.Label(zoom_frame, text="100%", width=6, bg=t["bg"], fg=t["fg"])
        self.zoom_label.pack(side=tk.LEFT, padx=8)
        ttk.Button(zoom_frame, text="+", width=3, command=self._zoom_in).pack(side=tk.LEFT)
        ttk.Button(zoom_frame, text="Fit", width=4, command=self._zoom_fit).pack(side=tk.LEFT, padx=8)
        
        # Store reference for theme changes
        self.tools_panel_frame = frame
    
    def _setup_center(self, parent):
        """Setup center notebook for pages."""
        t = self.theme
        
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        # Welcome tab with modern styling
        welcome = tk.Frame(self.notebook, bg=t["bg_base"])
        self.notebook.add(welcome, text="Welcome")
        
        # Center content
        center_frame = tk.Frame(welcome, bg=t["bg_base"])
        center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Logo/Title
        tk.Label(center_frame, text="🗺️", font=("Segoe UI", 48), 
                bg=t["bg_base"], fg=t["accent"]).pack(pady=(0, 10))
        tk.Label(center_frame, text=f"PlanMod Segmenter", font=("Segoe UI", 24, "bold"),
                bg=t["bg_base"], fg=t["fg"]).pack()
        tk.Label(center_frame, text=f"Version {VERSION}", font=("Segoe UI", 11),
                bg=t["bg_base"], fg=t["fg_muted"]).pack(pady=(0, 30))
        
        # Quick start buttons
        btn_frame = tk.Frame(center_frame, bg=t["bg_base"])
        btn_frame.pack()
        
        ttk.Button(btn_frame, text="📄 Open PDF", style="Accent.TButton",
                  command=self._open_pdf).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="📁 Open Workspace",
                  command=self._load_workspace).pack(side=tk.LEFT, padx=8)
        
        # Shortcuts hint
        tk.Label(center_frame, text="Ctrl+N: New PDF  •  Ctrl+O: Open Workspace  •  Ctrl+S: Save",
                font=("Segoe UI", 9), bg=t["bg_base"], fg=t["fg_subtle"]).pack(pady=(30, 0))
    
    def _setup_object_panel(self):
        """Setup right panel with object tree."""
        t = self.theme
        
        config = PanelConfig(
            name="objects",
            icon="📋",
            title="Objects",
            min_width=200,
            max_width=400,
            default_width=self.settings.tree_width,
            side="right"
        )
        
        objects_panel = self.layout.add_panel("objects", config)
        content = objects_panel.content
        
        # Grouping options
        group_frame = tk.Frame(content, bg=t["bg"])
        group_frame.pack(fill=tk.X, padx=8, pady=8)
        
        tk.Label(group_frame, text="Group by:", bg=t["bg"], fg=t["fg_muted"],
                font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.tree_grouping_var = tk.StringVar(value="none")
        group_combo = ttk.Combobox(group_frame, textvariable=self.tree_grouping_var,
                                   values=["none", "category", "view"], state="readonly", width=10)
        group_combo.pack(side=tk.LEFT, padx=8)
        group_combo.bind("<<ComboboxSelected>>", lambda e: self._update_tree())
        
        # Tree
        tree_frame = tk.Frame(content, bg=t["bg"])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.object_tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, selectmode="extended")
        self.object_tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.object_tree.yview)
        
        self.object_tree.heading("#0", text="Objects")
        self.object_tree.column("#0", width=250)
        self.object_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.object_tree.bind("<Button-1>", self._on_tree_click)
        self.object_tree.bind("<Double-1>", self._on_tree_double_click)
        self.object_tree.bind("<Button-3>", self._on_tree_right_click)
        
        # Mousewheel scrolling for tree only when mouse is over it
        def _tree_mousewheel(event):
            self.object_tree.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_tree_scroll(event):
            self.object_tree.bind_all("<MouseWheel>", _tree_mousewheel)
        
        def _unbind_tree_scroll(event):
            self.object_tree.unbind_all("<MouseWheel>")
        
        self.object_tree.bind("<Enter>", _bind_tree_scroll)
        self.object_tree.bind("<Leave>", _unbind_tree_scroll)
        
        self.tree_icons = {}
        
        # Checkbox to toggle auto-load image on selection
        options_frame = tk.Frame(content, bg=t["bg"])
        options_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
        
        self.auto_show_image_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Show image on select",
                       variable=self.auto_show_image_var).pack(anchor=tk.W)
        
        # Collapse/expand buttons
        expand_frame = tk.Frame(content, bg=t["bg"])
        expand_frame.pack(fill=tk.X, padx=8, pady=4)
        
        ttk.Button(expand_frame, text="Expand All", width=10,
                  command=self._expand_all_tree).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(expand_frame, text="Collapse All", width=10,
                  command=self._collapse_all_tree).pack(side=tk.LEFT)
        
        # Hint text
        hint_label = tk.Label(content, text="Right-click for actions",
                             bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 8))
        hint_label.pack(pady=(4, 8))
    
    def _bind_events(self):
        """Bind keyboard shortcuts."""
        self.root.bind("<Control-n>", lambda e: self._open_pdf())
        self.root.bind("<Control-o>", lambda e: self._load_workspace())
        self.root.bind("<Control-s>", lambda e: self._save_workspace())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Escape>", lambda e: self._cancel())
        self.root.bind("<Return>", lambda e: self._on_enter())
        
        # Panel toggles
        self.root.bind("<Control-b>", lambda e: self.layout._on_panel_toggle("tools"))
        self.root.bind("<Control-j>", lambda e: self.layout._on_panel_toggle("objects"))
        
        # Zoom shortcuts
        self.root.bind("<Control-plus>", lambda e: self._zoom_in())
        self.root.bind("<Control-equal>", lambda e: self._zoom_in())  # For keyboards without numpad
        self.root.bind("<Control-minus>", lambda e: self._zoom_out())
        self.root.bind("<Control-0>", lambda e: self._zoom_fit())
        
        # Window resize tracking
        self.root.bind("<Configure>", self._on_window_resize)
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_window_resize(self, event):
        """Handle window resize for responsive layout."""
        if event.widget == self.root:
            # Save window size to settings
            self.settings.window_width = self.root.winfo_width()
            self.settings.window_height = self.root.winfo_height()
    
    # ... (continuing with essential methods)
    
    def _get_current_page(self) -> Optional[PageTab]:
        return self.pages.get(self.current_page_id)
    
    def _get_working_image(self, page: PageTab) -> np.ndarray:
        """Get image with text/hatch hidden if those options are enabled."""
        image = page.original_image.copy()
        h, w = image.shape[:2]
        
        # Apply text mask if hiding text
        hide_text = getattr(page, 'hide_text', False)
        if hide_text:
            text_mask = getattr(page, 'combined_text_mask', None)
            if text_mask is not None:
                if text_mask.shape == (h, w):
                    mask_pixels = np.sum(text_mask > 0)
                    print(f"_get_working_image: Applying text mask with {mask_pixels} pixels")
                    image[text_mask > 0] = [255, 255, 255]
                else:
                    print(f"_get_working_image: Text mask shape mismatch {text_mask.shape} vs {(h, w)}")
            else:
                print(f"_get_working_image: hide_text=True but combined_text_mask is None")
        
        # Apply hatching mask if hiding hatching
        hide_hatching = getattr(page, 'hide_hatching', False)
        if hide_hatching:
            hatch_mask = getattr(page, 'combined_hatch_mask', None)
            if hatch_mask is not None:
                if hatch_mask.shape == (h, w):
                    mask_pixels = np.sum(hatch_mask > 0)
                    print(f"_get_working_image: Applying hatch mask with {mask_pixels} pixels")
                    image[hatch_mask > 0] = [255, 255, 255]
                else:
                    print(f"_get_working_image: Hatch mask shape mismatch {hatch_mask.shape} vs {(h, w)}")
            else:
                print(f"_get_working_image: hide_hatching=True but combined_hatch_mask is None")
        
        return image
    
    def _refresh_categories(self):
        """Refresh category list in sidebar."""
        for w in self.cat_frame.winfo_children():
            w.destroy()
        
        # Store visibility vars
        if not hasattr(self, 'cat_visibility_vars'):
            self.cat_visibility_vars = {}
        
        # Get set of categories in use
        used_categories = self._get_used_categories()
        
        # Protected categories that can never be deleted
        protected_categories = {"planform", "textbox", "mark_text", "mark_hatch"}
        
        for name in sorted(self.categories.keys()):
            cat = self.categories[name]
            f = ttk.Frame(self.cat_frame)
            f.pack(fill=tk.X, pady=1)
            
            # Visibility checkbox
            if name not in self.cat_visibility_vars:
                self.cat_visibility_vars[name] = tk.BooleanVar(value=cat.visible)
            else:
                self.cat_visibility_vars[name].set(cat.visible)
            
            ttk.Checkbutton(f, variable=self.cat_visibility_vars[name],
                           command=lambda n=name: self._toggle_category_visibility(n)).pack(side=tk.LEFT)
            
            # Color swatch
            color_hex = cat.color_hex
            tk.Label(f, width=2, bg=color_hex).pack(side=tk.LEFT, padx=2)
            
            # Radio button for selection
            ttk.Radiobutton(f, text=cat.name, variable=self.category_var, value=name,
                           command=lambda n=name: self._select_category(n)).pack(side=tk.LEFT)
            
            # Delete button - only show if category not in use and not protected
            if name not in used_categories and name not in protected_categories:
                del_btn = ttk.Button(f, text="🗑", width=2,
                                    command=lambda n=name: self._delete_category(n))
                del_btn.pack(side=tk.RIGHT, padx=2)
        
        # Add new category section
        add_frame = ttk.Frame(self.cat_frame)
        add_frame.pack(fill=tk.X, pady=(5, 2))
        
        self.new_cat_entry = ttk.Entry(add_frame, width=10)
        self.new_cat_entry.pack(side=tk.LEFT, padx=2)
        self.new_cat_entry.bind("<Return>", lambda e: self._add_custom_category())
        
        ttk.Button(add_frame, text="+", width=2, command=self._add_custom_category).pack(side=tk.LEFT)
    
    def _get_used_categories(self) -> set:
        """Get set of category names that are currently in use by objects."""
        used = set()
        for obj in self.all_objects:
            used.add(obj.category)
        return used
    
    def _delete_category(self, name: str):
        """Delete an unused category."""
        if name in self._get_used_categories():
            messagebox.showwarning("Cannot Delete", 
                                  f"Category '{name}' is in use by objects and cannot be deleted.",
                                  parent=self.root)
            return
        
        if messagebox.askyesno("Confirm Delete", 
                              f"Delete category '{name}'?", parent=self.root):
            del self.categories[name]
            if name in self.cat_visibility_vars:
                del self.cat_visibility_vars[name]
            self.workspace_modified = True
            self._refresh_categories()
            self.status_var.set(f"Deleted category: {name}")
    
    def _toggle_category_visibility(self, name: str):
        """Toggle visibility of a category."""
        if name in self.categories and name in self.cat_visibility_vars:
            self.categories[name].visible = self.cat_visibility_vars[name].get()
            self.renderer.invalidate_cache()
            self._update_display()
    
    def _add_custom_category(self):
        """Add a user-defined category."""
        name = self.new_cat_entry.get().strip()
        if not name:
            return
        
        if name in self.categories:
            messagebox.showinfo("Info", f"Category '{name}' already exists", parent=self.root)
            return
        
        color = get_next_color(len(self.categories))
        self.categories[name] = DynamicCategory(
            name=name, prefix=name[0].upper(), full_name=name,
            color_rgb=color, selection_mode="flood"
        )
        self.workspace_modified = True
        self._refresh_categories()
        self.category_var.set(name)  # Select the new category
        self.status_var.set(f"Added category: {name}")
    
    def _set_mode(self, mode: str):
        self.current_mode = mode
        self._cancel()
        # Update status bar
        self.status_bar.set_item_text("mode", mode.capitalize())
    
    def _select_category(self, name: str):
        """Select a category. Does NOT automatically change selection mode."""
        # Categories no longer auto-change mode - user controls mode separately
        # This allows using any mode (flood, polyline, freeform) with any category
        pass
    
    def _set_label_position(self, pos: str):
        self.label_position = pos
    
    def _toggle_labels(self):
        self.show_labels = self.show_labels_var.get()
        self.settings.show_labels = self.show_labels
        save_settings(self.settings)
        self._update_display()
    
    def _toggle_group_mode(self):
        self.group_mode_active = self.group_mode_var.get()
        if self.group_mode_active:
            self.group_mode_elements.clear()
            self.status_var.set("GROUP MODE: Create elements to group together")
        self._update_group_count()
    
    def _update_group_count(self):
        self.group_count.config(text=f"Elements: {len(self.group_mode_elements)}")
    
    def _finish_group(self):
        if len(self.group_mode_elements) < 1:
            messagebox.showinfo("Info", "Create at least 1 element first")
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        cat_name = self.category_var.get() or "R"
        cat = self.categories.get(cat_name)
        prefix = cat.prefix if cat else cat_name[0].upper()
        count = sum(1 for o in self.all_objects if o.category == cat_name) + 1
        
        # Get current view if set
        current_view = getattr(self, 'current_view_var', None)
        view_type = current_view.get() if current_view else ""
        
        name = simpledialog.askstring("Object Name", f"Name ({len(self.group_mode_elements)} elements):",
                                      initialvalue=f"{prefix}{count}", parent=self.root)
        if not name:
            return
        
        obj = SegmentedObject(name=name, category=cat_name)
        inst = ObjectInstance(instance_num=1, page_id=page.tab_id, view_type=view_type)
        inst.elements = list(self.group_mode_elements)
        obj.instances.append(inst)
        self.all_objects.append(obj)
        
        # Clear elements but keep group mode active - user can turn it off manually
        self.group_mode_elements.clear()
        # Don't turn off group mode automatically
        # self.group_mode_var.set(False)
        # self.group_mode_active = False
        self._update_group_count()
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._add_tree_item(obj)  # Incremental add
        self._update_display()
        self.status_var.set(f"Created: {name} - Group mode still active")
    
    def _adjust(self, setting: str, delta: int):
        if setting == "tolerance":
            self.settings.tolerance = max(1, min(100, self.settings.tolerance + delta))
            self.engine.tolerance = self.settings.tolerance
            self.tol_label.config(text=str(self.settings.tolerance))
        elif setting == "snap":
            self.settings.snap_distance = max(5, min(50, self.settings.snap_distance + delta))
            self.snap_label.config(text=str(self.settings.snap_distance))
    
    def _on_opacity(self, val):
        self.settings.planform_opacity = float(val)
        self._update_display()
    
    def _zoom_in(self):
        self.zoom_level = min(5.0, self.zoom_level * 1.25)
        self._update_display()
    
    def _zoom_out(self):
        self.zoom_level = max(0.1, self.zoom_level / 1.25)
        self._update_display()
    
    def _zoom_fit(self):
        page = self._get_current_page()
        if not page or page.original_image is None or not hasattr(page, 'canvas'):
            return
        h, w = page.original_image.shape[:2]
        cw = max(page.canvas.winfo_width(), 100)
        ch = max(page.canvas.winfo_height(), 100)
        self.zoom_level = min(cw / w, ch / h) * 0.9
        self._update_display()
        self._draw_rulers(page)
    
    def _scroll_with_rulers(self, page: PageTab, direction: str, *args):
        """Scroll canvas and update rulers."""
        if direction == 'h':
            page.canvas.xview(*args)
        else:
            page.canvas.yview(*args)
        self._draw_rulers(page)
    
    def _draw_rulers(self, page: PageTab = None):
        """Draw rulers for a page."""
        if page is None:
            page = self._get_current_page()
        if not page or not hasattr(page, 'h_ruler') or not hasattr(page, 'v_ruler'):
            return
        
        # Check if rulers should be shown
        if not self.settings.show_ruler:
            page.h_ruler.delete("all")
            page.v_ruler.delete("all")
            return
        
        # Get colors from theme
        bg_color = self.theme.get("bg_secondary", "#313244")
        fg_color = self.theme.get("fg", "#cdd6f4")
        tick_color = self.theme.get("fg_muted", "#a6adc8")
        
        # Get scale info
        ppi = page.pixels_per_inch  # Pixels per inch at 100% zoom
        ppi_zoomed = ppi * self.zoom_level  # Pixels per inch at current zoom
        
        unit = self.settings.ruler_unit
        
        # Draw horizontal ruler
        self._draw_h_ruler(page, ppi_zoomed, unit, bg_color, fg_color, tick_color)
        
        # Draw vertical ruler
        self._draw_v_ruler(page, ppi_zoomed, unit, bg_color, fg_color, tick_color)
    
    def _draw_h_ruler(self, page: PageTab, ppi: float, unit: str, bg: str, fg: str, tick_color: str):
        """Draw horizontal ruler."""
        ruler = page.h_ruler
        ruler.delete("all")
        
        # Get visible region
        ruler_w = ruler.winfo_width()
        ruler_h = page.ruler_size
        
        if ruler_w <= 1:
            return
        
        # Get scroll position
        x_offset = 0
        if hasattr(page, 'canvas'):
            try:
                x_view = page.canvas.xview()
                if page.original_image is not None:
                    img_w = page.original_image.shape[1] * self.zoom_level
                    x_offset = x_view[0] * img_w
            except:
                pass
        
        # Calculate unit intervals
        if unit == "inch":
            pixels_per_unit = ppi
            major_interval = 1.0  # 1 inch
            subdivisions = [(0.5, 0.6), (0.25, 0.4), (0.125, 0.25), (0.0625, 0.15)]  # (fraction, height_ratio)
        else:  # cm
            pixels_per_unit = ppi / 2.54
            major_interval = 1.0  # 1 cm
            subdivisions = [(0.5, 0.5), (0.1, 0.3)]  # 5mm and 1mm marks
        
        # Draw background
        ruler.create_rectangle(0, 0, ruler_w, ruler_h, fill=bg, outline="")
        
        # Draw ticks
        start_unit = int(x_offset / pixels_per_unit)
        end_unit = int((x_offset + ruler_w) / pixels_per_unit) + 2
        
        for i in range(start_unit, end_unit):
            x = i * pixels_per_unit - x_offset
            
            if 0 <= x <= ruler_w:
                # Major tick
                ruler.create_line(x, ruler_h, x, ruler_h * 0.2, fill=fg, width=1)
                # Label
                label = f"{i}" if unit == "inch" else f"{i}"
                ruler.create_text(x + 3, ruler_h * 0.4, text=label, anchor="w", 
                                 fill=fg, font=("TkDefaultFont", 7))
            
            # Subdivision ticks
            for frac, height_ratio in subdivisions:
                sub_x = x + frac * pixels_per_unit
                if 0 <= sub_x <= ruler_w:
                    tick_h = ruler_h * height_ratio
                    ruler.create_line(sub_x, ruler_h, sub_x, ruler_h - tick_h, fill=tick_color, width=1)
    
    def _draw_v_ruler(self, page: PageTab, ppi: float, unit: str, bg: str, fg: str, tick_color: str):
        """Draw vertical ruler."""
        ruler = page.v_ruler
        ruler.delete("all")
        
        ruler_w = page.ruler_size
        ruler_h = ruler.winfo_height()
        
        if ruler_h <= 1:
            return
        
        # Get scroll position
        y_offset = 0
        if hasattr(page, 'canvas'):
            try:
                y_view = page.canvas.yview()
                if page.original_image is not None:
                    img_h = page.original_image.shape[0] * self.zoom_level
                    y_offset = y_view[0] * img_h
            except:
                pass
        
        # Calculate unit intervals
        if unit == "inch":
            pixels_per_unit = ppi
            subdivisions = [(0.5, 0.6), (0.25, 0.4), (0.125, 0.25), (0.0625, 0.15)]
        else:  # cm
            pixels_per_unit = ppi / 2.54
            subdivisions = [(0.5, 0.5), (0.1, 0.3)]
        
        # Draw background
        ruler.create_rectangle(0, 0, ruler_w, ruler_h, fill=bg, outline="")
        
        # Draw ticks
        start_unit = int(y_offset / pixels_per_unit)
        end_unit = int((y_offset + ruler_h) / pixels_per_unit) + 2
        
        for i in range(start_unit, end_unit):
            y = i * pixels_per_unit - y_offset
            
            if 0 <= y <= ruler_h:
                # Major tick
                ruler.create_line(ruler_w, y, ruler_w * 0.2, y, fill=fg, width=1)
                # Label (rotated text approximation)
                label = f"{i}"
                ruler.create_text(ruler_w * 0.4, y + 3, text=label, anchor="n",
                                 fill=fg, font=("TkDefaultFont", 7))
            
            # Subdivision ticks
            for frac, height_ratio in subdivisions:
                sub_y = y + frac * pixels_per_unit
                if 0 <= sub_y <= ruler_h:
                    tick_w = ruler_w * height_ratio
                    ruler.create_line(ruler_w, sub_y, ruler_w - tick_w, sub_y, fill=tick_color, width=1)
    
    def _toggle_ruler(self):
        """Toggle ruler visibility."""
        self.settings.show_ruler = not self.settings.show_ruler
        save_settings(self.settings)
        self._update_view_menu_labels()
        page = self._get_current_page()
        if page:
            self._draw_rulers(page)
    
    def _set_ruler_unit(self, unit: str):
        """Set ruler measurement unit."""
        self.settings.ruler_unit = unit
        save_settings(self.settings)
        page = self._get_current_page()
        if page:
            self._draw_rulers(page)
    
    def _undo(self):
        page = self._get_current_page()
        if not page or not self.all_objects:
            return
        
        # Find last object with instance on current page
        last = None
        for obj in reversed(self.all_objects):
            for inst in obj.instances:
                if inst.page_id == page.tab_id:
                    last = obj
                    break
            if last:
                break
        
        if not last:
            return
            
        if last.instances and last.instances[-1].elements:
            last.instances[-1].elements.pop()
            if not last.instances[-1].elements:
                last.instances.pop()
            if not last.instances:
                self.all_objects.remove(last)
                self._remove_tree_item(last.object_id)
            else:
                self._update_tree_item(last)
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._update_display()
    
    def _cancel(self):
        self.current_points.clear()
        self.is_drawing = False
        self._redraw_points()
    
    def _on_enter(self):
        if self.current_mode == "line" and len(self.current_points) >= 2:
            self._finish_line()
        elif self.current_mode == "polyline" and len(self.current_points) >= 3:
            self._finish_polyline()
    
    def _change_theme(self, name: str):
        self.settings.theme = name
        save_settings(self.settings)
        messagebox.showinfo("Theme", f"Theme will be '{name}' on restart")
    
    def _toggle_hide_background(self):
        """Toggle hide background for current page."""
        page = self._get_current_page()
        if not page:
            return
        
        if not hasattr(page, 'hide_background'):
            page.hide_background = False
        page.hide_background = not page.hide_background
        
        self._update_view_menu_labels()
        self.renderer.invalidate_cache()
        self._update_display()
    
    def _toggle_hide_text(self):
        """Toggle hide text for current page."""
        page = self._get_current_page()
        if not page:
            return
        
        if not hasattr(page, 'hide_text'):
            page.hide_text = False
        
        # If turning on, detect text regions first
        if not page.hide_text:
            if not hasattr(page, 'auto_text_regions') or not page.auto_text_regions:
                self.status_var.set("Detecting text regions...")
                self.root.update()
                page.auto_text_regions = self._detect_text_regions(page)
                self._update_combined_text_mask(page)
                count = len(page.auto_text_regions)
                self.status_var.set(f"Found {count} text regions - use 'Manage Manual Regions' to review")
        
        page.hide_text = not page.hide_text
        
        self._update_view_menu_labels()
        self.renderer.invalidate_cache()
        self._update_display()
    
    def _toggle_hide_hatching(self):
        """Toggle hide hatching for current page."""
        page = self._get_current_page()
        if not page:
            return
        
        if not hasattr(page, 'hide_hatching'):
            page.hide_hatching = False
        
        # If turning on, detect hatching regions first
        if not page.hide_hatching:
            if not hasattr(page, 'auto_hatch_regions') or not page.auto_hatch_regions:
                self.status_var.set("Detecting hatching regions...")
                self.root.update()
                page.auto_hatch_regions = self._detect_hatching_regions(page)
                self._update_combined_hatch_mask(page)
                count = len(page.auto_hatch_regions)
                self.status_var.set(f"Found {count} hatching regions - use 'Manage Manual Regions' to review")
        
        page.hide_hatching = not page.hide_hatching
        
        self._update_view_menu_labels()
        self.renderer.invalidate_cache()
        self._update_display()
    
    def _update_view_menu_labels(self):
        """Update View menu labels based on current page state."""
        page = self._get_current_page()
        
        # Menu indices with new structure:
        # 0: Toggle Tools Panel
        # 1: Toggle Objects Panel
        # 2: separator
        # 3: Hide/Show Background
        # 4: Hide/Show Text
        # 5: Hide/Show Hatching
        # 6: separator
        # 7: Manage Mask Regions...
        # 8: separator
        # 9: Hide/Show Ruler
        
        # Background toggle (index 3)
        if page and getattr(page, 'hide_background', False):
            self.view_menu.entryconfig(3, label="Show Background")
        else:
            self.view_menu.entryconfig(3, label="Hide Background")
        
        # Text toggle (index 4)
        if page and getattr(page, 'hide_text', False):
            self.view_menu.entryconfig(4, label="Show Text")
        else:
            self.view_menu.entryconfig(4, label="Hide Text")
        
        # Hatching toggle (index 5)
        if page and getattr(page, 'hide_hatching', False):
            self.view_menu.entryconfig(5, label="Show Hatching")
        else:
            self.view_menu.entryconfig(5, label="Hide Hatching")
        
        # Ruler toggle (index 9)
        if self.settings.show_ruler:
            self.view_menu.entryconfig(9, label="Hide Ruler")
        else:
            self.view_menu.entryconfig(9, label="Show Ruler")
    
    def _show_settings_dialog(self):
        """Show the settings/preferences dialog."""
        old_theme = self.settings.theme
        
        def on_save(settings):
            # Apply settings
            self.settings = settings
            save_settings(settings)
            
            # Update engine settings
            self.engine.tolerance = settings.tolerance
            self.engine.line_thickness = settings.line_thickness
            
            # Update UI - sync show_labels with sidebar checkbox
            self.show_labels = settings.show_labels
            self.show_labels_var.set(settings.show_labels)
            
            if hasattr(self, 'opacity_var'):
                self.opacity_var.set(settings.planform_opacity)
            
            # Redraw
            self.renderer.invalidate_cache()
            self._update_display()
            self._draw_rulers()
            
            # Show restart message if theme changed
            if settings.theme != old_theme:
                messagebox.showinfo("Restart Required", 
                    "Theme changes will fully apply after restarting the application.")
        
        dialog = SettingsDialog(self.root, self.settings, self.theme, on_save)
        dialog.show()
    
    def _detect_text_regions(self, page: PageTab) -> list:
        """Detect text regions in image using OCR and return list of regions."""
        import pytesseract
        
        image = page.original_image
        h, w = image.shape[:2]
        regions = []
        
        try:
            # Configure tesseract path if needed
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            
            # Get bounding boxes for detected text - use word level only
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Use PSM 11 (sparse text) to find individual text elements
            custom_config = r'--oem 3 --psm 11'
            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT, config=custom_config)
            
            region_id = 1
            n_boxes = len(data['level'])
            for i in range(n_boxes):
                # Only consider actual text (level 5 = word)
                if data['level'][i] != 5:
                    continue
                    
                # Only consider words with high confidence
                conf = int(data['conf'][i]) if data['conf'][i] != '-1' else 0
                if conf < 60:  # Higher confidence threshold
                    continue
                
                # Only consider boxes with reasonable dimensions (not the whole image)
                x, y, bw, bh = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                
                # Skip if box is too large (> 10% of image) - likely false positive
                if bw * bh > (w * h * 0.1):
                    continue
                
                # Skip very small boxes (noise)
                if bw < 5 or bh < 5:
                    continue
                
                # Add small padding around text
                padding = 2
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(w, x + bw + padding)
                y2 = min(h, y + bh + padding)
                
                # Create mask for this region
                mask = np.zeros((h, w), dtype=np.uint8)
                mask[y1:y2, x1:x2] = 255
                
                # Get detected text
                text = data['text'][i] if data['text'][i].strip() else f"text_{region_id}"
                
                regions.append({
                    'id': f"auto_{region_id}",
                    'text': text,
                    'bbox': (x1, y1, x2, y2),
                    'confidence': conf,
                    'mode': 'auto',
                    'mask': mask
                })
                region_id += 1
            
        except Exception as e:
            print(f"Text detection error: {e}")
        
        return regions
        
        return mask
    
    def _detect_hatching_regions(self, page: PageTab) -> list:
        """Detect hatching/cross-hatch pattern regions in image and return list of regions."""
        image = page.original_image
        h, w = image.shape[:2]
        regions = []
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Use edge detection to find line patterns
            edges = cv2.Canny(gray, 50, 150)
            
            # Use Hough transform to detect lines
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, 
                                    minLineLength=20, maxLineGap=5)
            
            if lines is not None:
                # Find regions with high line density (hatching)
                line_density = np.zeros((h, w), dtype=np.float32)
                
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    # Calculate line length and angle
                    length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                    angle = np.arctan2(y2-y1, x2-x1)
                    
                    # Hatching typically has diagonal lines at ~45° or ~135°
                    angle_deg = np.abs(np.degrees(angle))
                    is_diagonal = (35 < angle_deg < 55) or (125 < angle_deg < 145)
                    
                    if is_diagonal and length < 100:  # Short diagonal lines = hatching
                        cv2.line(line_density, (x1, y1), (x2, y2), 1.0, 3)
                
                # Apply morphological operations to group nearby lines
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
                line_density = cv2.dilate(line_density, kernel)
                
                # Threshold to get hatching regions
                _, hatching = cv2.threshold(line_density, 0.3, 255, cv2.THRESH_BINARY)
                mask = hatching.astype(np.uint8)
                
                # Clean up with morphological closing
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (10, 10))
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                
                # Find connected components to create individual regions
                num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
                
                for i in range(1, num_labels):  # Skip background (0)
                    x, y, bw, bh, area = stats[i]
                    
                    # Skip very small regions
                    if area < 100:
                        continue
                    
                    # Create mask for this region
                    region_mask = np.zeros((h, w), dtype=np.uint8)
                    region_mask[labels == i] = 255
                    
                    cx, cy = centroids[i]
                    
                    regions.append({
                        'id': f"auto_{i}",
                        'bbox': (x, y, x + bw, y + bh),
                        'area': area,
                        'center': (int(cx), int(cy)),
                        'mode': 'auto',
                        'mask': region_mask
                    })
            
        except Exception as e:
            print(f"Hatching detection error: {e}")
        
        return regions
    
    # Manual text/hatching region management
    def _add_manual_text_region(self, page: PageTab, mask: np.ndarray, point: tuple, mode: str = "flood"):
        """Add a manually marked text region."""
        if not hasattr(page, 'manual_text_regions'):
            page.manual_text_regions = []
        
        # Store the region with its seed point and mode for reference
        region_id = len(page.manual_text_regions) + 1
        page.manual_text_regions.append({
            'id': region_id,
            'point': point,
            'mode': mode,
            'mask': mask.copy()
        })
        
        # Update combined text mask
        self._update_combined_text_mask(page)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._update_display()
        self.status_var.set(f"Added manual text region #{region_id} ({mode})")
    
    def _add_manual_hatch_region(self, page: PageTab, mask: np.ndarray, point: tuple, mode: str = "flood"):
        """Add a manually marked hatching region."""
        if not hasattr(page, 'manual_hatch_regions'):
            page.manual_hatch_regions = []
        
        region_id = len(page.manual_hatch_regions) + 1
        page.manual_hatch_regions.append({
            'id': region_id,
            'point': point,
            'mode': mode,
            'mask': mask.copy()
        })
        
        # Update combined hatching mask
        self._update_combined_hatch_mask(page)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._update_display()
        self.status_var.set(f"Added manual hatching region #{region_id} ({mode})")
    
    def _update_combined_text_mask(self, page: PageTab):
        """Combine auto-detected and manual text masks."""
        h, w = page.original_image.shape[:2]
        combined = np.zeros((h, w), dtype=np.uint8)
        
        auto_count = 0
        manual_count = 0
        auto_pixels = 0
        manual_pixels = 0
        
        # Add auto-detected regions
        if hasattr(page, 'auto_text_regions'):
            for region in page.auto_text_regions:
                mask = region.get('mask')
                if mask is not None:
                    if mask.shape == (h, w):
                        combined = np.maximum(combined, mask)
                        auto_count += 1
                        auto_pixels += np.sum(mask > 0)
                    else:
                        print(f"Text mask shape mismatch: {mask.shape} vs expected {(h, w)}")
        
        # Add manual regions
        if hasattr(page, 'manual_text_regions'):
            for region in page.manual_text_regions:
                mask = region.get('mask')
                if mask is not None:
                    if mask.shape == (h, w):
                        combined = np.maximum(combined, mask)
                        manual_count += 1
                        manual_pixels += np.sum(mask > 0)
                    else:
                        print(f"Manual text mask shape mismatch: {mask.shape} vs expected {(h, w)}")
        
        page.combined_text_mask = combined
        total_pixels = np.sum(combined > 0)
        print(f"_update_combined_text_mask: auto={auto_count} ({auto_pixels}px), "
              f"manual={manual_count} ({manual_pixels}px), combined={total_pixels}px")
    
    def _update_combined_hatch_mask(self, page: PageTab):
        """Combine auto-detected and manual hatching masks."""
        h, w = page.original_image.shape[:2]
        combined = np.zeros((h, w), dtype=np.uint8)
        
        auto_count = 0
        manual_count = 0
        auto_pixels = 0
        manual_pixels = 0
        
        # Add auto-detected regions
        if hasattr(page, 'auto_hatch_regions'):
            for region in page.auto_hatch_regions:
                mask = region.get('mask')
                if mask is not None:
                    if mask.shape == (h, w):
                        combined = np.maximum(combined, mask)
                        auto_count += 1
                        auto_pixels += np.sum(mask > 0)
                    else:
                        print(f"Hatch mask shape mismatch: {mask.shape} vs expected {(h, w)}")
        
        # Add manual regions
        if hasattr(page, 'manual_hatch_regions'):
            for region in page.manual_hatch_regions:
                mask = region.get('mask')
                if mask is not None:
                    if mask.shape == (h, w):
                        combined = np.maximum(combined, mask)
                        manual_count += 1
                        manual_pixels += np.sum(mask > 0)
                    else:
                        print(f"Manual hatch mask shape mismatch: {mask.shape} vs expected {(h, w)}")
        
        page.combined_hatch_mask = combined
        total_pixels = np.sum(combined > 0)
        print(f"_update_combined_hatch_mask: auto={auto_count} ({auto_pixels}px), "
              f"manual={manual_count} ({manual_pixels}px), combined={total_pixels}px")
    
    def _remove_manual_text_region(self, page: PageTab, region_id):
        """Remove a manual text region by ID."""
        if hasattr(page, 'manual_text_regions'):
            page.manual_text_regions = [r for r in page.manual_text_regions if r['id'] != region_id]
            self._update_combined_text_mask(page)
            self.workspace_modified = True
            self.renderer.invalidate_cache()
            self._update_display()
    
    def _remove_auto_text_region(self, page: PageTab, region_id: str):
        """Remove an auto-detected text region by ID."""
        if hasattr(page, 'auto_text_regions'):
            page.auto_text_regions = [r for r in page.auto_text_regions if r['id'] != region_id]
            self._update_combined_text_mask(page)
            self.workspace_modified = True
            self.renderer.invalidate_cache()
            self._update_display()
    
    def _remove_manual_hatch_region(self, page: PageTab, region_id):
        """Remove a manual hatching region by ID."""
        if hasattr(page, 'manual_hatch_regions'):
            page.manual_hatch_regions = [r for r in page.manual_hatch_regions if r['id'] != region_id]
            self._update_combined_hatch_mask(page)
            self.workspace_modified = True
            self.renderer.invalidate_cache()
            self._update_display()
    
    def _remove_auto_hatch_region(self, page: PageTab, region_id: str):
        """Remove an auto-detected hatching region by ID."""
        if hasattr(page, 'auto_hatch_regions'):
            page.auto_hatch_regions = [r for r in page.auto_hatch_regions if r['id'] != region_id]
            self._update_combined_hatch_mask(page)
            self.workspace_modified = True
            self.renderer.invalidate_cache()
            self._update_display()
    
    def _show_mask_regions_dialog(self):
        """Show dialog to manage text/hatching regions (auto-detected + manual)."""
        page = self._get_current_page()
        if not page:
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Mask Regions")
        dialog.geometry("500x550")
        dialog.transient(self.root)
        
        # Position relative to main window
        x = self.root.winfo_x() + 50
        y = self.root.winfo_y() + 50
        dialog.geometry(f"+{x}+{y}")
        
        # Store highlight state
        self._mask_highlight_masks = []
        
        def get_region_mask(source: str, region_id: str, region_type: str) -> np.ndarray:
            """Get mask for a region by source and ID."""
            if region_type == 'text':
                if source == 'auto' and hasattr(page, 'auto_text_regions'):
                    for r in page.auto_text_regions:
                        if r['id'] == region_id:
                            return r.get('mask')
                elif source == 'manual' and hasattr(page, 'manual_text_regions'):
                    for r in page.manual_text_regions:
                        if r['id'] == region_id:
                            return r.get('mask')
            else:  # hatching
                if source == 'auto' and hasattr(page, 'auto_hatch_regions'):
                    for r in page.auto_hatch_regions:
                        if r['id'] == region_id:
                            return r.get('mask')
                elif source == 'manual' and hasattr(page, 'manual_hatch_regions'):
                    for r in page.manual_hatch_regions:
                        if r['id'] == region_id:
                            return r.get('mask')
            return None
        
        def highlight_selected_regions(regions_data: list, listbox: tk.Listbox, region_type: str):
            """Highlight selected regions on the image."""
            self._mask_highlight_masks = []
            selections = listbox.curselection()
            for idx in selections:
                if idx < len(regions_data):
                    source, region_id = regions_data[idx]
                    mask = get_region_mask(source, region_id, region_type)
                    if mask is not None:
                        self._mask_highlight_masks.append(mask)
            self._update_display_with_mask_highlight()
        
        def clear_highlight():
            """Clear mask highlights."""
            self._mask_highlight_masks = []
            self._update_display()
        
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ===== Text regions tab =====
        text_frame = ttk.Frame(notebook)
        notebook.add(text_frame, text="Text Regions")
        
        # Store combined list with type tracking
        text_regions_data = []  # List of (source, region_id)
        
        text_listbox = tk.Listbox(text_frame, height=15, selectmode=tk.EXTENDED)
        text_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_listbox.yview)
        text_listbox.configure(yscrollcommand=text_scroll.set)
        
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
        text_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Populate: auto-detected first
        if hasattr(page, 'auto_text_regions'):
            for region in page.auto_text_regions:
                text = region.get('text', '?')[:20]
                conf = region.get('confidence', 0)
                bbox = region.get('bbox', (0, 0, 0, 0))
                display = f"[AUTO] \"{text}\" ({conf}% conf) at ({bbox[0]}, {bbox[1]})"
                text_listbox.insert(tk.END, display)
                text_regions_data.append(('auto', region['id']))
        
        # Then manual
        if hasattr(page, 'manual_text_regions'):
            for region in page.manual_text_regions:
                mode = region.get('mode', 'flood')
                pt = region.get('point', (0, 0))
                display = f"[MANUAL] #{region['id']} [{mode}] at ({pt[0]}, {pt[1]})"
                text_listbox.insert(tk.END, display)
                text_regions_data.append(('manual', region['id']))
        
        # Bind selection event for highlighting
        text_listbox.bind('<<ListboxSelect>>', 
                          lambda e: highlight_selected_regions(text_regions_data, text_listbox, 'text'))
        
        def delete_text_regions():
            selections = list(text_listbox.curselection())
            if not selections:
                return
            # Process in reverse order to maintain indices
            for idx in sorted(selections, reverse=True):
                if idx < len(text_regions_data):
                    source, region_id = text_regions_data[idx]
                    if source == 'auto':
                        self._remove_auto_text_region(page, region_id)
                    else:
                        self._remove_manual_text_region(page, region_id)
                    text_listbox.delete(idx)
                    text_regions_data.pop(idx)
            clear_highlight()
        
        btn_frame = ttk.Frame(text_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Delete Selected", command=delete_text_regions).pack(side=tk.LEFT, padx=5)
        ttk.Label(btn_frame, text=f"Total: {len(text_regions_data)} regions").pack(side=tk.RIGHT, padx=5)
        
        # ===== Hatching regions tab =====
        hatch_frame = ttk.Frame(notebook)
        notebook.add(hatch_frame, text="Hatching Regions")
        
        hatch_regions_data = []  # List of (source, region_id)
        
        hatch_listbox = tk.Listbox(hatch_frame, height=15, selectmode=tk.EXTENDED)
        hatch_scroll = ttk.Scrollbar(hatch_frame, orient=tk.VERTICAL, command=hatch_listbox.yview)
        hatch_listbox.configure(yscrollcommand=hatch_scroll.set)
        
        hatch_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
        hatch_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Populate: auto-detected first
        if hasattr(page, 'auto_hatch_regions'):
            for region in page.auto_hatch_regions:
                bbox = region.get('bbox', (0, 0, 0, 0))
                area = region.get('area', 0)
                display = f"[AUTO] #{region['id']} area={area}px at ({bbox[0]}, {bbox[1]})"
                hatch_listbox.insert(tk.END, display)
                hatch_regions_data.append(('auto', region['id']))
        
        # Then manual
        if hasattr(page, 'manual_hatch_regions'):
            for region in page.manual_hatch_regions:
                mode = region.get('mode', 'flood')
                pt = region.get('point', (0, 0))
                display = f"[MANUAL] #{region['id']} [{mode}] at ({pt[0]}, {pt[1]})"
                hatch_listbox.insert(tk.END, display)
                hatch_regions_data.append(('manual', region['id']))
        
        # Bind selection event for highlighting
        hatch_listbox.bind('<<ListboxSelect>>', 
                           lambda e: highlight_selected_regions(hatch_regions_data, hatch_listbox, 'hatch'))
        
        def delete_hatch_regions():
            selections = list(hatch_listbox.curselection())
            if not selections:
                return
            for idx in sorted(selections, reverse=True):
                if idx < len(hatch_regions_data):
                    source, region_id = hatch_regions_data[idx]
                    if source == 'auto':
                        self._remove_auto_hatch_region(page, region_id)
                    else:
                        self._remove_manual_hatch_region(page, region_id)
                    hatch_listbox.delete(idx)
                    hatch_regions_data.pop(idx)
            clear_highlight()
        
        hatch_btn_frame = ttk.Frame(hatch_frame)
        hatch_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(hatch_btn_frame, text="Delete Selected", command=delete_hatch_regions).pack(side=tk.LEFT, padx=5)
        ttk.Label(hatch_btn_frame, text=f"Total: {len(hatch_regions_data)} regions").pack(side=tk.RIGHT, padx=5)
        
        # Clear highlight when switching tabs
        notebook.bind('<<NotebookTabChanged>>', lambda e: clear_highlight())
        
        # Clear highlight when dialog closes
        dialog.protocol("WM_DELETE_WINDOW", lambda: (clear_highlight(), dialog.destroy()))
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    # Page management
    def _add_page(self, page: PageTab):
        self.pages[page.tab_id] = page
        
        # Create main frame with rulers
        frame = ttk.Frame(self.notebook)
        
        # Ruler dimensions
        ruler_size = 25
        
        # Create grid layout: [corner][h_ruler] / [v_ruler][canvas+scrolls]
        # Top row: corner + horizontal ruler
        top_frame = ttk.Frame(frame)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Corner (empty space where rulers meet)
        corner = tk.Canvas(top_frame, width=ruler_size, height=ruler_size, 
                          bg=self.theme.get("bg_secondary", "#313244"),
                          highlightthickness=0)
        corner.pack(side=tk.LEFT)
        
        # Horizontal ruler
        h_ruler = tk.Canvas(top_frame, height=ruler_size, 
                           bg=self.theme.get("bg_secondary", "#313244"),
                           highlightthickness=0)
        h_ruler.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Bottom row: vertical ruler + canvas area
        bottom_frame = ttk.Frame(frame)
        bottom_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Vertical ruler
        v_ruler = tk.Canvas(bottom_frame, width=ruler_size,
                           bg=self.theme.get("bg_secondary", "#313244"),
                           highlightthickness=0)
        v_ruler.pack(side=tk.LEFT, fill=tk.Y)
        
        # Canvas area with scrollbars
        canvas_frame = ttk.Frame(bottom_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        canvas = tk.Canvas(canvas_frame, bg=self.theme["canvas_bg"], cursor="crosshair",
                          xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        canvas.pack(fill=tk.BOTH, expand=True)
        h_scroll.config(command=lambda *args: self._scroll_with_rulers(page, 'h', *args))
        v_scroll.config(command=lambda *args: self._scroll_with_rulers(page, 'v', *args))
        
        canvas.bind("<Button-1>", self._on_click)
        canvas.bind("<Double-Button-1>", self._on_double_click)
        canvas.bind("<Button-3>", self._on_right_click)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", self._on_release)
        canvas.bind("<Motion>", self._on_motion)
        
        # Mouse wheel scrolling for canvas
        def _canvas_mousewheel(event):
            # Vertical scroll with mouse wheel
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            self._draw_rulers(page)
        
        def _canvas_mousewheel_horizontal(event):
            # Horizontal scroll with Shift+wheel or horizontal wheel
            canvas.xview_scroll(int(-1*(event.delta/120)), "units")
            self._draw_rulers(page)
        
        def _bind_canvas_scroll(event):
            canvas.bind_all("<MouseWheel>", _canvas_mousewheel)
            canvas.bind_all("<Shift-MouseWheel>", _canvas_mousewheel_horizontal)
            # For mice with horizontal scroll (tilt wheel)
            canvas.bind_all("<Shift-Button-4>", lambda e: canvas.xview_scroll(-1, "units"))
            canvas.bind_all("<Shift-Button-5>", lambda e: canvas.xview_scroll(1, "units"))
        
        def _unbind_canvas_scroll(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Shift-MouseWheel>")
            canvas.unbind_all("<Shift-Button-4>")
            canvas.unbind_all("<Shift-Button-5>")
        
        canvas.bind("<Enter>", _bind_canvas_scroll)
        canvas.bind("<Leave>", _unbind_canvas_scroll)
        
        # Store references
        page.canvas = canvas
        page.frame = frame
        page.h_ruler = h_ruler
        page.v_ruler = v_ruler
        page.ruler_size = ruler_size
        
        self.notebook.add(frame, text=page.display_name)
        self.notebook.select(frame)
        self.current_page_id = page.tab_id
        self.workspace_modified = True
        
        # Fit to screen after canvas is properly sized
        self.root.after(300, lambda: (self._zoom_fit(), self._update_display(), self._draw_rulers(page)))
    
    def _on_tab_changed(self, event):
        try:
            selected = self.notebook.select()
            for tid, page in self.pages.items():
                if hasattr(page, 'frame') and str(page.frame) == selected:
                    self.current_page_id = tid
                    self._update_view_menu_labels()  # Update menu for new page
                    self._update_display()
                    self._update_tree()
                    break
        except:
            pass
    
    # Canvas events
    def _canvas_to_image(self, x: int, y: int) -> tuple:
        page = self._get_current_page()
        if not page or not hasattr(page, 'canvas'):
            return (0, 0)
        ix = int(page.canvas.canvasx(x) / self.zoom_level)
        iy = int(page.canvas.canvasy(y) / self.zoom_level)
        return (ix, iy)
    
    def _on_click(self, event):
        page = self._get_current_page()
        if not page or page.original_image is None:
            return
        
        x, y = self._canvas_to_image(event.x, event.y)
        h, w = page.original_image.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return
        
        if self.current_mode == "select":
            self._select_at(x, y)
        elif self.current_mode == "flood":
            self._flood_fill(x, y)
        elif self.current_mode in ["polyline", "line"]:
            # Check snap
            if self.current_mode == "polyline" and len(self.current_points) >= 3:
                d = ((x - self.current_points[0][0])**2 + (y - self.current_points[0][1])**2)**0.5
                if d < self.settings.snap_distance:
                    self._finish_polyline()
                    return
            self.current_points.append((x, y))
            self._redraw_points()
        elif self.current_mode == "freeform":
            self.is_drawing = True
            self.current_points = [(x, y)]
    
    def _on_double_click(self, event):
        if self.current_mode == "polyline" and len(self.current_points) >= 3:
            self._finish_polyline()
    
    def _on_right_click(self, event):
        if self.current_points:
            self.current_points.pop()
            self._redraw_points()
    
    def _on_drag(self, event):
        if self.current_mode == "freeform" and self.is_drawing:
            x, y = self._canvas_to_image(event.x, event.y)
            self.current_points.append((x, y))
            self._redraw_points()
    
    def _on_release(self, event):
        if self.current_mode == "freeform" and self.is_drawing:
            self.is_drawing = False
            if len(self.current_points) >= 2:
                self._finish_freeform()
    
    def _on_motion(self, event):
        x, y = self._canvas_to_image(event.x, event.y)
        self.status_var.set(f"({x}, {y}) | Mode: {self.current_mode}")
    
    # Segmentation operations
    def _select_at(self, x: int, y: int):
        """Select object/instance/element at given image coordinates."""
        page = self._get_current_page()
        if not page:
            return
        
        # Search through all_objects for elements on this page
        result = None
        for obj in self.all_objects:
            for inst in obj.instances:
                # Only check instances on current page
                if inst.page_id != page.tab_id:
                    continue
                for elem in inst.elements:
                    if elem.contains_point(x, y):
                        result = (obj, inst, elem)
                        break
                if result:
                    break
            if result:
                break
        
        if result:
            obj, inst, elem = result
            self.selected_object_ids = {obj.object_id}
            self.selected_instance_ids = {inst.instance_id}
            self.selected_element_ids = {elem.element_id}
            
            # Select in tree view
            tree_id = f"o_{obj.object_id}"
            if self.object_tree.exists(tree_id):
                self.object_tree.selection_set(tree_id)
                self.object_tree.see(tree_id)
        else:
            self.selected_object_ids.clear()
            self.selected_instance_ids.clear()
            self.selected_element_ids.clear()
            self.object_tree.selection_remove(*self.object_tree.selection())
        
        self._update_display()
    
    def _flood_fill(self, x: int, y: int):
        page = self._get_current_page()
        cat_name = self.category_var.get()
        if not page or not cat_name:
            return
        
        cat = self.categories.get(cat_name)
        if not cat:
            return
        
        # Debug: Check page state before getting working image
        print(f"_flood_fill at ({x}, {y}): page.hide_text={getattr(page, 'hide_text', 'NOT SET')}, "
              f"page.hide_hatching={getattr(page, 'hide_hatching', 'NOT SET')}")
        text_mask = getattr(page, 'combined_text_mask', None)
        hatch_mask = getattr(page, 'combined_hatch_mask', None)
        print(f"  text_mask exists: {text_mask is not None}, "
              f"hatch_mask exists: {hatch_mask is not None}")
        if text_mask is not None:
            print(f"  text_mask pixels: {np.sum(text_mask > 0)}")
        
        # Get image with text/hatch hidden if those options are enabled
        working_image = self._get_working_image(page)
        
        mask = self.engine.flood_fill(working_image, (x, y))
        if np.sum(mask) == 0:
            return
        
        # Handle special marker categories - add to mask list, not objects
        if cat_name == "mark_text":
            self._add_manual_text_region(page, mask, (x, y), "flood")
            return
        elif cat_name == "mark_hatch":
            self._add_manual_hatch_region(page, mask, (x, y), "flood")
            return
        
        elem = SegmentElement(
            category=cat_name, mode="flood", points=[(x, y)],
            mask=mask, color=cat.color_rgb, label_position=self.label_position
        )
        self._add_element(elem)
    
    def _finish_polyline(self):
        if len(self.current_points) < 3:
            return
        page = self._get_current_page()
        if not page:
            return
        
        cat_name = self.category_var.get() or "planform"
        cat = self.categories.get(cat_name)
        h, w = page.original_image.shape[:2]
        mask = self.engine.create_polygon_mask((h, w), self.current_points)
        
        # Handle special marker categories
        if cat_name == "mark_text":
            self._add_manual_text_region(page, mask, self.current_points[0], "polyline")
            self.current_points.clear()
            self._redraw_points()
            return
        elif cat_name == "mark_hatch":
            self._add_manual_hatch_region(page, mask, self.current_points[0], "polyline")
            self.current_points.clear()
            self._redraw_points()
            return
        
        elem = SegmentElement(
            category=cat_name, mode="polyline", points=list(self.current_points),
            mask=mask, color=cat.color_rgb if cat else (128, 128, 128),
            label_position=self.label_position
        )
        self._add_element(elem)
        self.current_points.clear()
        self._redraw_points()
    
    def _finish_freeform(self):
        if len(self.current_points) < 2:
            return
        page = self._get_current_page()
        if not page:
            return
        
        cat_name = self.category_var.get() or "planform"
        cat = self.categories.get(cat_name)
        h, w = page.original_image.shape[:2]
        mask = self.engine.create_freeform_mask((h, w), self.current_points)
        
        # Handle special marker categories
        if cat_name == "mark_text":
            self._add_manual_text_region(page, mask, self.current_points[0], "freeform")
            self.current_points.clear()
            self._redraw_points()
            return
        elif cat_name == "mark_hatch":
            self._add_manual_hatch_region(page, mask, self.current_points[0], "freeform")
            self.current_points.clear()
            self._redraw_points()
            return
        
        elem = SegmentElement(
            category=cat_name, mode="freeform", points=list(self.current_points),
            mask=mask, color=cat.color_rgb if cat else (128, 128, 128),
            label_position=self.label_position
        )
        self._add_element(elem)
        self.current_points.clear()
        self._redraw_points()
    
    def _finish_line(self):
        if len(self.current_points) < 2:
            return
        page = self._get_current_page()
        if not page:
            return
        
        cat_name = self.category_var.get() or "longeron"
        cat = self.categories.get(cat_name)
        h, w = page.original_image.shape[:2]
        mask = self.engine.create_line_mask((h, w), self.current_points)
        
        # Handle special marker categories
        if cat_name == "mark_text":
            self._add_manual_text_region(page, mask, self.current_points[0], "line")
            self.current_points.clear()
            self._redraw_points()
            return
        elif cat_name == "mark_hatch":
            self._add_manual_hatch_region(page, mask, self.current_points[0], "line")
            self.current_points.clear()
            self._redraw_points()
            return
        
        elem = SegmentElement(
            category=cat_name, mode="line", points=list(self.current_points),
            mask=mask, color=cat.color_rgb if cat else (128, 128, 128),
            label_position=self.label_position
        )
        self._add_element(elem)
        self.current_points.clear()
        self._redraw_points()
    
    def _add_element(self, elem: SegmentElement):
        page = self._get_current_page()
        if not page:
            return
        
        # Group mode: collect elements without creating object yet
        if self.group_mode_active and elem.category != "eraser":
            self.group_mode_elements.append(elem)
            self._update_group_count()
            self._update_display()
            self.status_var.set(f"Added to group ({len(self.group_mode_elements)})")
            return
        
        # Check if anything is selected - add to that object's last instance
        # BUT only if the selected category matches the object's category
        selected_obj_id = self._get_selected_object_for_adding()
        if selected_obj_id and elem.category != "eraser":
            obj = self._get_object_by_id(selected_obj_id)
            if obj and obj.instances:
                # Only add to existing object if category matches
                if obj.category == elem.category:
                    # Add element to the last instance of the selected object
                    last_inst = obj.instances[-1]
                    last_inst.elements.append(elem)
                    self.workspace_modified = True
                    self.renderer.invalidate_cache()  # Objects changed
                    
                    # Ensure sequential instance numbering
                    self._renumber_instances(obj)
                    
                    # Preserve selection after tree update
                    old_selection = self.object_tree.selection()
                    self._update_tree_item(obj)  # Only update this object
                    # Re-select
                    for item in old_selection:
                        if self.object_tree.exists(item):
                            try:
                                self.object_tree.selection_add(item)
                            except:
                                pass
                    
                    self._update_display()
                    self.status_var.set(f"Added to {obj.name} instance {last_inst.instance_num}")
                    return
                # Category mismatch - fall through to create new object
        
        # No selection or eraser: create a new object
        cat = self.categories.get(elem.category)
        prefix = cat.prefix if cat else elem.category[0].upper()
        count = sum(1 for o in self.all_objects if o.category == elem.category) + 1
        
        # Assign current view if set
        current_view = getattr(self, 'current_view_var', None)
        view_type = current_view.get() if current_view else ""
        
        new_obj = SegmentedObject(name=f"{prefix}{count}", category=elem.category)
        inst = ObjectInstance(instance_num=1, page_id=page.tab_id, view_type=view_type)
        inst.elements.append(elem)
        new_obj.instances.append(inst)
        self.all_objects.append(new_obj)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()  # Objects changed
        self._add_tree_item(new_obj)  # Only add new item
        self._update_display()
        self.status_var.set(f"Created: {new_obj.name}")
    
    # Display
    def _get_objects_for_page(self, page_id: str) -> List[SegmentedObject]:
        """Get objects that have instances on a specific page."""
        result = []
        for obj in self.all_objects:
            # Check if any instance is on this page
            has_instance_on_page = any(inst.page_id == page_id for inst in obj.instances)
            if has_instance_on_page:
                result.append(obj)
        return result
    
    def _update_display(self):
        page = self._get_current_page()
        if not page or page.original_image is None or not hasattr(page, 'canvas'):
            return
        
        # Get objects for this page
        page_objects = self._get_objects_for_page(page.tab_id)
        
        # Get page-specific view settings
        hide_background = getattr(page, 'hide_background', False)
        
        # Get text mask if hiding text (use combined mask if available)
        text_mask = None
        if getattr(page, 'hide_text', False):
            if hasattr(page, 'combined_text_mask') and page.combined_text_mask is not None:
                text_mask = page.combined_text_mask
            elif hasattr(page, 'text_mask') and page.text_mask is not None:
                text_mask = page.text_mask
        
        # Get hatching mask if hiding hatching (use combined mask if available)
        hatching_mask = None
        if getattr(page, 'hide_hatching', False):
            if hasattr(page, 'combined_hatch_mask') and page.combined_hatch_mask is not None:
                hatching_mask = page.combined_hatch_mask
            elif hasattr(page, 'hatching_mask') and page.hatching_mask is not None:
                hatching_mask = page.hatching_mask
        
        rendered = self.renderer.render_page(
            page, self.categories, self.zoom_level, self.show_labels,
            self.selected_object_ids, self.selected_instance_ids, self.selected_element_ids,
            self.settings.planform_opacity, self.group_mode_elements,
            hide_background=hide_background,
            objects=page_objects,
            text_mask=text_mask,
            hatching_mask=hatching_mask
        )
        
        pil_img = Image.fromarray(cv2.cvtColor(rendered, cv2.COLOR_BGRA2RGBA))
        page.tk_image = ImageTk.PhotoImage(pil_img)
        
        page.canvas.delete("all")
        page.canvas.create_image(0, 0, anchor=tk.NW, image=page.tk_image)
        page.canvas.configure(scrollregion=(0, 0, rendered.shape[1], rendered.shape[0]))
        
        self._redraw_points()
        
        # Update zoom display
        zoom_text = f"{int(self.zoom_level * 100)}%"
        self.zoom_label.config(text=zoom_text)
        self.status_bar.set_item_text("zoom", zoom_text)
        
        # Update rulers
        self._draw_rulers(page)
    
    def _update_display_with_mask_highlight(self):
        """Update display with temporary mask region highlights."""
        page = self._get_current_page()
        if not page or page.original_image is None or not hasattr(page, 'canvas'):
            return
        
        # First do normal render
        page_objects = self._get_objects_for_page(page.tab_id)
        hide_background = getattr(page, 'hide_background', False)
        
        text_mask = None
        if getattr(page, 'hide_text', False):
            if hasattr(page, 'combined_text_mask') and page.combined_text_mask is not None:
                text_mask = page.combined_text_mask
        
        hatching_mask = None
        if getattr(page, 'hide_hatching', False):
            if hasattr(page, 'combined_hatch_mask') and page.combined_hatch_mask is not None:
                hatching_mask = page.combined_hatch_mask
        
        rendered = self.renderer.render_page(
            page, self.categories, self.zoom_level, self.show_labels,
            self.selected_object_ids, self.selected_instance_ids, self.selected_element_ids,
            self.settings.planform_opacity, self.group_mode_elements,
            hide_background=hide_background,
            objects=page_objects,
            text_mask=text_mask,
            hatching_mask=hatching_mask
        )
        
        # Now overlay highlight for selected mask regions
        if hasattr(self, '_mask_highlight_masks') and self._mask_highlight_masks:
            h, w = rendered.shape[:2]
            zoom = self.zoom_level
            
            for mask in self._mask_highlight_masks:
                if mask is None:
                    continue
                
                # Resize mask to match zoomed image
                mask_resized = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
                
                # Create yellow semi-transparent overlay
                overlay = np.zeros((h, w, 4), dtype=np.uint8)
                overlay[mask_resized > 0] = [0, 255, 255, 100]  # Yellow with alpha
                
                # Blend overlay
                alpha = overlay[:, :, 3:4] / 255.0
                rendered[:, :, :3] = (rendered[:, :, :3] * (1 - alpha) + 
                                      overlay[:, :, :3] * alpha).astype(np.uint8)
                
                # Draw contour in bright yellow
                contours, _ = cv2.findContours(mask_resized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(rendered, contours, -1, (0, 255, 255, 255), 2)
        
        pil_img = Image.fromarray(cv2.cvtColor(rendered, cv2.COLOR_BGRA2RGBA))
        page.tk_image = ImageTk.PhotoImage(pil_img)
        
        page.canvas.delete("all")
        page.canvas.create_image(0, 0, anchor=tk.NW, image=page.tk_image)
        page.canvas.configure(scrollregion=(0, 0, rendered.shape[1], rendered.shape[0]))
        
        self._redraw_points()
    
    def _redraw_points(self):
        page = self._get_current_page()
        if not page or not hasattr(page, 'canvas'):
            return
        
        page.canvas.delete("temp")
        
        if not self.current_points:
            return
        
        scaled = [(int(x * self.zoom_level), int(y * self.zoom_level)) for x, y in self.current_points]
        
        # Snap indicator for polyline
        if self.current_mode == "polyline" and len(scaled) >= 3:
            r = int(self.settings.snap_distance * self.zoom_level)
            page.canvas.create_oval(scaled[0][0]-r, scaled[0][1]-r, scaled[0][0]+r, scaled[0][1]+r,
                                   outline="lime", width=2, dash=(4, 2), tags="temp")
        
        for i, (x, y) in enumerate(scaled):
            color = "lime" if i == 0 else "yellow"
            page.canvas.create_oval(x-4, y-4, x+4, y+4, fill=color, outline="black", tags="temp")
        
        if len(scaled) > 1:
            for i in range(len(scaled) - 1):
                page.canvas.create_line(scaled[i][0], scaled[i][1], scaled[i+1][0], scaled[i+1][1],
                                        fill="yellow", width=2, tags="temp")
    
    # Tree management
    def _update_tree(self):
        """Full tree rebuild - shows ALL objects across all pages."""
        self.object_tree.delete(*self.object_tree.get_children())
        
        grouping = self.tree_grouping_var.get() if hasattr(self, 'tree_grouping_var') else "none"
        
        if grouping == "none":
            # Flat list - all objects
            for obj in self.all_objects:
                self._add_tree_item(obj)
        elif grouping == "category":
            # Group by category
            categories_used = {}
            for obj in self.all_objects:
                cat_name = obj.category or "Uncategorized"
                if cat_name not in categories_used:
                    categories_used[cat_name] = []
                categories_used[cat_name].append(obj)
            
            for cat_name in sorted(categories_used.keys()):
                icon = self._get_tree_icon(cat_name)
                cat_node = self.object_tree.insert("", "end", iid=f"cat_{cat_name}", 
                                                   text=f"📁 {cat_name} ({len(categories_used[cat_name])})",
                                                   image=icon, open=True)
                for obj in categories_used[cat_name]:
                    self._add_tree_item(obj, parent=cat_node)
        elif grouping == "view":
            # Group by view type - each instance under its own view
            # Structure: view -> (obj, instance) pairs
            views_used = {}
            
            for obj in self.all_objects:
                for inst in obj.instances:
                    # Get view from instance attributes or view_type
                    view_name = inst.attributes.view or inst.view_type or ""
                    if not view_name:
                        view_name = "Unassigned"
                    
                    if view_name not in views_used:
                        views_used[view_name] = []
                    views_used[view_name].append((obj, inst))
            
            # Sort views with "Unassigned" last
            sorted_views = sorted([v for v in views_used.keys() if v != "Unassigned"])
            if "Unassigned" in views_used:
                sorted_views.append("Unassigned")
            
            for view_name in sorted_views:
                items = views_used[view_name]
                view_node = self.object_tree.insert("", "end", iid=f"view_{view_name}",
                                                    text=f"👁 {view_name} ({len(items)})",
                                                    open=True)
                
                for obj, inst in items:
                    icon = self._get_tree_icon(obj.category)
                    # Show object name with instance number if multiple instances
                    if len(obj.instances) > 1:
                        label = f"{obj.name} [Inst {inst.instance_num}]"
                    else:
                        label = obj.name
                    
                    # Create unique ID combining object and instance
                    item_id = f"vi_{obj.object_id}_{inst.instance_id}"
                    
                    if len(inst.elements) == 1:
                        self.object_tree.insert(view_node, "end", iid=item_id, text=label, image=icon)
                    else:
                        node = self.object_tree.insert(view_node, "end", iid=item_id,
                                                       text=f"{label} ({len(inst.elements)} elem)", 
                                                       image=icon, open=False)
                        for i, elem in enumerate(inst.elements):
                            self.object_tree.insert(node, "end", iid=f"ve_{elem.element_id}", 
                                                    text=f"├ element {i+1}")
    
    def _get_tree_icon(self, category: str):
        """Get or create icon for a category."""
        cat = self.categories.get(category)
        if cat:
            key = f"{cat.color_rgb[0]}_{cat.color_rgb[1]}_{cat.color_rgb[2]}"
            if key not in self.tree_icons:
                img = Image.new('RGB', (12, 12), cat.color_rgb)
                ImageDraw.Draw(img).rectangle([0, 0, 11, 11], outline=(0, 0, 0))
                self.tree_icons[key] = ImageTk.PhotoImage(img)
            return self.tree_icons[key]
        return ""
    
    def _add_tree_item(self, obj: SegmentedObject, parent: str = ""):
        """Add a single object to the tree (incremental)."""
        grouping = self.tree_grouping_var.get() if hasattr(self, 'tree_grouping_var') else "none"
        icon = self._get_tree_icon(obj.category)
        
        # Handle grouping modes
        if grouping == "category" and not parent:
            # Ensure category group exists and add under it
            parent = self._ensure_category_group(obj.category)
        elif grouping == "view" and not parent:
            # View grouping needs special handling - add to _update_tree instead
            # For now, do a full rebuild
            self._update_tree()
            return
        
        parent_node = parent if parent else ""
        
        if obj.is_simple:
            self.object_tree.insert(parent_node, "end", iid=f"o_{obj.object_id}", text=obj.name, image=icon)
        elif not obj.has_multiple_instances:
            node = self.object_tree.insert(parent_node, "end", iid=f"o_{obj.object_id}",
                                           text=f"{obj.name} ({obj.element_count})", image=icon, open=False)
            for i, elem in enumerate(obj.instances[0].elements):
                self.object_tree.insert(node, "end", iid=f"e_{elem.element_id}", text=f"├ element {i+1}")
        else:
            node = self.object_tree.insert(parent_node, "end", iid=f"o_{obj.object_id}",
                                           text=f"{obj.name} ({len(obj.instances)} inst)", image=icon, open=False)
            for inst in obj.instances:
                inode = self.object_tree.insert(node, "end", iid=f"i_{inst.instance_id}",
                                                text=f"Instance {inst.instance_num}", open=False)
                for i, elem in enumerate(inst.elements):
                    self.object_tree.insert(inode, "end", iid=f"e_{elem.element_id}", text=f"├ elem {i+1}")
        
        # Update category group count if grouped by category
        if grouping == "category":
            self._update_category_group_count(obj.category)
    
    def _ensure_category_group(self, category: str) -> str:
        """Ensure category group exists in tree and return its ID."""
        group_id = f"cat_{category}"
        cat_name = category or "Uncategorized"
        
        # Check if group already exists
        if not self.object_tree.exists(group_id):
            icon = self._get_tree_icon(category)
            self.object_tree.insert("", "end", iid=group_id, 
                                   text=f"📁 {cat_name} (0)", image=icon, open=True)
        return group_id
    
    def _update_category_group_count(self, category: str):
        """Update the count in a category group header."""
        group_id = f"cat_{category}"
        cat_name = category or "Uncategorized"
        
        if self.object_tree.exists(group_id):
            # Count children
            children = self.object_tree.get_children(group_id)
            count = len(children)
            icon = self._get_tree_icon(category)
            self.object_tree.item(group_id, text=f"📁 {cat_name} ({count})", image=icon)
    
    def _update_tree_item(self, obj: SegmentedObject):
        """Update a single object in the tree (incremental)."""
        grouping = self.tree_grouping_var.get() if hasattr(self, 'tree_grouping_var') else "none"
        
        # For view grouping, do full rebuild (view can change)
        if grouping == "view":
            self._update_tree()
            return
        
        # Remove old item
        try:
            self.object_tree.delete(f"o_{obj.object_id}")
        except:
            pass
        
        # Determine parent for grouped modes
        parent = ""
        if grouping == "category":
            parent = self._ensure_category_group(obj.category)
        
        # Re-add with updated state
        self._add_tree_item(obj, parent=parent)
    
    def _remove_tree_item(self, object_id: str):
        """Remove a single object from the tree."""
        grouping = self.tree_grouping_var.get() if hasattr(self, 'tree_grouping_var') else "none"
        
        # Find the object to get its category before deletion
        category = None
        for obj in self.all_objects:
            if obj.object_id == object_id:
                category = obj.category
                break
        
        try:
            self.object_tree.delete(f"o_{object_id}")
        except:
            pass
        
        # Update category group count
        if grouping == "category" and category:
            self._update_category_group_count(category)
            # Remove empty category group
            group_id = f"cat_{category}"
            if self.object_tree.exists(group_id):
                if not self.object_tree.get_children(group_id):
                    self.object_tree.delete(group_id)
    
    def _on_tree_select(self, event):
        selection = self.object_tree.selection()
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        
        target_page_id = None  # Page to switch to
        
        # Track what's explicitly selected
        for item in selection:
            if item.startswith("o_"):
                self.selected_object_ids.add(item[2:])
            elif item.startswith("i_"):
                self.selected_instance_ids.add(item[2:])
            elif item.startswith("e_"):
                self.selected_element_ids.add(item[2:])
            elif item.startswith("vi_"):
                # View-grouped instance: vi_objid_instid
                parts = item[3:].split("_", 1)
                if len(parts) == 2:
                    self.selected_object_ids.add(parts[0])
                    self.selected_instance_ids.add(parts[1])
            elif item.startswith("ve_"):
                # View-grouped element: ve_elemid
                self.selected_element_ids.add(item[3:])
            elif item.startswith("cat_") or item.startswith("view_"):
                # Group header - select all children
                pass  # Could expand to select all in group
        
        # Only auto-switch pages if the checkbox is enabled
        if getattr(self, 'auto_show_image_var', None) and self.auto_show_image_var.get():
            # Determine which page to switch to based on selection
            target_page_id = self._get_page_for_selection()
            if target_page_id and target_page_id != self.current_page_id:
                self._switch_to_page(target_page_id)
            
            self._update_display()
        
        # Update current view selector based on selection
        self._update_view_from_selection()
    
    def _on_view_changed(self, event=None):
        """Handle current view combo change."""
        # Just store the value - it will be used when creating new objects
        pass
    
    def _update_view_from_selection(self):
        """Update current view combo based on selected object."""
        if not self.selected_object_ids:
            return
        
        # Get the first selected object
        obj_id = next(iter(self.selected_object_ids))
        obj = self._get_object_by_id(obj_id)
        if not obj:
            return
        
        # Check if all instances have the same view
        views = set()
        for inst in obj.instances:
            view = getattr(inst, 'view_type', '') or inst.attributes.view if hasattr(inst, 'attributes') else ''
            views.add(view)
        
        # Only update if there's a single consistent view
        if len(views) == 1:
            view = views.pop()
            if view and hasattr(self, 'current_view_var'):
                self.current_view_var.set(view)
    
    def _get_page_for_selection(self) -> Optional[str]:
        """
        Determine which page the selected items belong to.
        Returns None if selection spans multiple pages or has no page.
        """
        page_ids = set()
        
        # Check selected instances
        for inst_id in self.selected_instance_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    if inst.instance_id == inst_id and inst.page_id:
                        page_ids.add(inst.page_id)
        
        # Check selected elements
        for elem_id in self.selected_element_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.element_id == elem_id and inst.page_id:
                            page_ids.add(inst.page_id)
        
        # Check selected objects - use first instance's page
        for obj_id in self.selected_object_ids:
            obj = self._get_object_by_id(obj_id)
            if obj and obj.instances:
                # Check if all instances are on same page
                obj_pages = set(inst.page_id for inst in obj.instances if inst.page_id)
                if len(obj_pages) == 1:
                    page_ids.update(obj_pages)
                elif len(obj_pages) > 1:
                    # Object spans multiple pages - don't switch
                    return None
        
        # Return page if exactly one
        if len(page_ids) == 1:
            return page_ids.pop()
        return None
    
    def _switch_to_page(self, page_id: str):
        """Switch to a specific page tab."""
        if page_id in self.pages:
            page = self.pages[page_id]
            if hasattr(page, 'frame'):
                self.notebook.select(page.frame)
                self.current_page_id = page_id
    
    def _get_object_by_id(self, obj_id: str) -> Optional[SegmentedObject]:
        """Get object by ID from global list."""
        for obj in self.all_objects:
            if obj.object_id == obj_id:
                return obj
        return None
    
    def _get_element_at_point(self, page_id: str, x: int, y: int):
        """Find element at point on a specific page."""
        for obj in self.all_objects:
            for inst in obj.instances:
                if inst.page_id == page_id:
                    for elem in inst.elements:
                        if elem.mask is not None and elem.mask[y, x] > 0:
                            return (obj, inst, elem)
        return None
    
    def _get_selected_object_for_adding(self) -> Optional[str]:
        """Get the object ID to add elements to (from any selection type)."""
        page = self._get_current_page()
        if not page:
            return None
        
        # Direct object selection
        if self.selected_object_ids:
            return next(iter(self.selected_object_ids))
        
        # Instance selected - find parent object
        if self.selected_instance_ids:
            inst_id = next(iter(self.selected_instance_ids))
            for obj in self.all_objects:
                for inst in obj.instances:
                    if inst.instance_id == inst_id:
                        return obj.object_id
        
        # Element selected - find parent object
        if self.selected_element_ids:
            elem_id = next(iter(self.selected_element_ids))
            for obj in self.all_objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.element_id == elem_id:
                            return obj.object_id
        
        return None
    
    def _on_tree_click(self, event):
        """Handle click on tree - deselect if clicking empty area."""
        item = self.object_tree.identify_row(event.y)
        if not item:
            # Clicked on empty area - deselect all
            self.object_tree.selection_remove(*self.object_tree.selection())
            self.selected_object_ids.clear()
            self.selected_instance_ids.clear()
            self.selected_element_ids.clear()
            self._update_display()
            self.status_var.set("Deselected - new elements will create new objects")
    
    def _on_tree_right_click(self, event):
        """Show context menu on right-click."""
        item = self.object_tree.identify_row(event.y)
        
        # Select the item under cursor if not already selected
        if item and item not in self.object_tree.selection():
            self.object_tree.selection_set(item)
            self._on_tree_select(None)
        
        # Create context menu
        menu = tk.Menu(self.root, tearoff=0, bg=self.theme["menu_bg"], 
                      fg=self.theme["menu_fg"],
                      activebackground=self.theme["menu_hover"],
                      activeforeground=self.theme["selection_fg"])
        
        # Determine what's selected
        num_objects = len(self.selected_object_ids)
        num_instances = len(self.selected_instance_ids)
        num_elements = len(self.selected_element_ids)
        
        # Check if selected objects are same category (for merge)
        same_category = False
        if num_objects >= 2:
            categories = set()
            for obj_id in self.selected_object_ids:
                obj = self._get_object_by_id(obj_id)
                if obj:
                    categories.add(obj.category)
            same_category = len(categories) == 1
        
        # Object actions
        if num_objects >= 1:
            menu.add_command(label="Add Instance", command=self._add_instance,
                           state="normal" if num_objects == 1 else "disabled")
            menu.add_command(label="Duplicate", command=self._duplicate_object,
                           state="normal" if num_objects == 1 else "disabled")
            menu.add_command(label="Rename", command=lambda: self._start_inline_edit(f"o_{next(iter(self.selected_object_ids))}") if self.selected_object_ids else None,
                           state="normal" if num_objects == 1 else "disabled")
            menu.add_command(label="Edit Attributes", command=self._edit_attributes)
            menu.add_separator()
            
            # Merge options
            menu.add_command(label="Merge → Instances", command=self._merge_as_instances,
                           state="normal" if num_objects >= 2 and same_category else "disabled")
            menu.add_command(label="Merge → Group", command=self._merge_as_group,
                           state="normal" if num_objects >= 2 and same_category else "disabled")
            
            # Separate instances (if one object with multiple instances selected)
            if num_objects == 1 and num_instances >= 2:
                menu.add_command(label="Separate Instances", command=self._separate_instances)
            
            menu.add_separator()
        
        # Expand/collapse
        if item:
            menu.add_command(label="Expand", command=lambda: self.object_tree.item(item, open=True))
            menu.add_command(label="Collapse", command=lambda: self.object_tree.item(item, open=False))
            menu.add_separator()
        
        menu.add_command(label="Expand All", command=self._expand_all_tree)
        menu.add_command(label="Collapse All", command=self._collapse_all_tree)
        
        if num_objects >= 1 or num_instances >= 1 or num_elements >= 1:
            menu.add_separator()
            menu.add_command(label="Delete", command=self._delete_selected)
        
        # Show menu
        menu.tk_popup(event.x_root, event.y_root)
    
    def _expand_all_tree(self):
        """Expand all tree items."""
        def expand_children(item):
            self.object_tree.item(item, open=True)
            for child in self.object_tree.get_children(item):
                expand_children(child)
        
        for item in self.object_tree.get_children():
            expand_children(item)
    
    def _collapse_all_tree(self):
        """Collapse all tree items."""
        def collapse_children(item):
            for child in self.object_tree.get_children(item):
                collapse_children(child)
            self.object_tree.item(item, open=False)
        
        for item in self.object_tree.get_children():
            collapse_children(item)
    
    def _separate_instances(self):
        """Separate selected instances into individual objects."""
        if not self.selected_object_ids or len(self.selected_instance_ids) < 2:
            return
        
        obj_id = next(iter(self.selected_object_ids))
        obj = self._get_object_by_id(obj_id)
        if not obj:
            return
        
        # Find instances to separate
        instances_to_separate = []
        for inst in obj.instances:
            if inst.instance_id in self.selected_instance_ids:
                instances_to_separate.append(inst)
        
        if len(instances_to_separate) < 2:
            return
        
        # Keep first instance in original object, create new objects for rest
        for i, inst in enumerate(instances_to_separate[1:], start=1):
            # Remove from original
            obj.instances.remove(inst)
            
            # Create new object
            new_obj = SegmentedObject(
                name=f"{obj.name}_{i}",
                category=obj.category
            )
            inst.instance_num = 1
            new_obj.instances.append(inst)
            self.all_objects.append(new_obj)
        
        # Renumber remaining instances
        self._renumber_instances(obj)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._update_tree()
        self._update_display()
        self.status_var.set(f"Separated {len(instances_to_separate)} instances")
    
    def _on_tree_double_click(self, event):
        """Handle double-click on tree - start inline editing of object name."""
        item = self.object_tree.identify_row(event.y)
        if not item:
            return
        
        # Only allow editing object names (items starting with 'o_')
        if item.startswith("o_"):
            self._start_inline_edit(item)
        else:
            # For instances/elements, open attributes dialog
            self._edit_attributes()
    
    def _start_inline_edit(self, item_id: str):
        """Start inline editing of tree item."""
        if not item_id.startswith("o_"):
            return
            
        obj_id = item_id[2:]  # Remove 'o_' prefix
        obj = self._get_object_by_id(obj_id)
        if not obj:
            return
        
        # Ensure item is visible
        self.object_tree.see(item_id)
        self.object_tree.update_idletasks()
        
        # Get item bounding box
        bbox = self.object_tree.bbox(item_id)
        if not bbox:
            # Try again after a short delay
            self.root.after(100, lambda: self._do_inline_edit(item_id, obj))
            return
        
        self._do_inline_edit(item_id, obj, bbox)
    
    def _do_inline_edit(self, item_id: str, obj, bbox=None):
        """Actually perform inline editing."""
        if bbox is None:
            bbox = self.object_tree.bbox(item_id)
            if not bbox:
                return
        
        x, y, width, height = bbox
        
        # Destroy any existing edit entry
        if hasattr(self, '_inline_entry') and self._inline_entry:
            try:
                self._inline_entry.destroy()
            except:
                pass
        
        # Create entry widget for editing
        self._inline_entry = tk.Entry(self.object_tree, font=("Segoe UI", 9),
                                      bg=self.theme.get("input_bg", "#3c3c3c"),
                                      fg=self.theme.get("input_fg", "#cccccc"),
                                      insertbackground=self.theme.get("fg", "#cccccc"),
                                      relief="solid", borderwidth=1)
        self._inline_entry.insert(0, obj.name)
        self._inline_entry.select_range(0, tk.END)
        self._inline_entry.place(x=x + 20, y=y, width=max(width - 25, 100), height=height)
        self._inline_entry.focus_set()
        
        def finish_edit(event=None):
            if not hasattr(self, '_inline_entry') or not self._inline_entry:
                return
            try:
                new_name = self._inline_entry.get().strip()
                if new_name and new_name != obj.name:
                    obj.name = new_name
                    self.workspace_modified = True
                    self.renderer.invalidate_cache()
                    self._update_tree()
                    self._update_display()
                self._inline_entry.destroy()
                self._inline_entry = None
            except:
                pass
        
        def cancel_edit(event=None):
            if hasattr(self, '_inline_entry') and self._inline_entry:
                try:
                    self._inline_entry.destroy()
                    self._inline_entry = None
                except:
                    pass
        
        self._inline_entry.bind("<Return>", finish_edit)
        self._inline_entry.bind("<Escape>", cancel_edit)
        self._inline_entry.bind("<FocusOut>", finish_edit)
    
    # Object operations
    def _rename_object(self):
        if not self.selected_object_ids:
            return
        page = self._get_current_page()
        if not page:
            return
        
        obj_id = next(iter(self.selected_object_ids))
        obj = page.get_object_by_id(obj_id)
        if not obj:
            return
        
        name = simpledialog.askstring("Rename", f"New name:", initialvalue=obj.name, parent=self.root)
        if name:
            obj.name = name
            self.workspace_modified = True
            self._update_tree_item(obj)  # Incremental update
    
    def _add_instance(self):
        """Add a new empty instance to the selected object without prompting."""
        if not self.selected_object_ids:
            messagebox.showinfo("Info", "Select an object first")
            return
        page = self._get_current_page()
        if not page:
            return
        
        obj_id = next(iter(self.selected_object_ids))
        obj = self._get_object_by_id(obj_id)
        if not obj:
            return
        
        # Change category selector to match the object's category
        if obj.category and obj.category in self.categories:
            self.category_var.set(obj.category)
            # Also update mode if needed
            cat = self.categories[obj.category]
            if cat.selection_mode and cat.selection_mode != "select":
                self._set_mode(cat.selection_mode)
        
        # Renumber instances to ensure sequential numbering
        self._renumber_instances(obj)
        
        # Add instance silently - no dialog needed
        inst = obj.add_instance("", page.tab_id)
        self.workspace_modified = True
        # Note: empty instance doesn't need cache invalidate - no visual change
        self._update_tree_item(obj)  # Incremental update
        
        # Keep the object selected so subsequent elements go to this new instance
        self.selected_object_ids = {obj.object_id}
        self.selected_instance_ids = {inst.instance_id}
        self.selected_element_ids.clear()
        
        # Select in tree view
        tree_id = f"o_{obj.object_id}"
        if self.object_tree.exists(tree_id):
            self.object_tree.selection_set(tree_id)
        
        self._update_display()
        self.status_var.set(f"Instance {inst.instance_num} added to {obj.name} - now add elements")
    
    def _renumber_instances(self, obj: SegmentedObject):
        """Ensure instances have sequential numbering starting from 1."""
        for idx, inst in enumerate(obj.instances):
            inst.instance_num = idx + 1
    
    def _edit_attributes(self):
        """Edit attributes for selected instance (or first instance of selected object)."""
        page = self._get_current_page()
        if not page:
            return
        
        # Find target instance and object
        target_inst = None
        target_obj = None
        obj_name = ""
        
        # Priority: selected instance > selected object's first instance
        if self.selected_instance_ids:
            inst_id = next(iter(self.selected_instance_ids))
            for obj in self.all_objects:
                for inst in obj.instances:
                    if inst.instance_id == inst_id:
                        target_inst = inst
                        target_obj = obj
                        obj_name = obj.name
                        break
                if target_inst:
                    break
        elif self.selected_object_ids:
            obj_id = next(iter(self.selected_object_ids))
            target_obj = self._get_object_by_id(obj_id)
            if target_obj and target_obj.instances:
                target_inst = target_obj.instances[0]
                obj_name = target_obj.name
        
        if not target_inst or not target_obj:
            messagebox.showinfo("Info", "Select an object or instance first", parent=self.root)
            return
        
        dialog = AttributeDialog(self.root, target_inst, obj_name)
        result = dialog.show()
        if result:
            target_inst.attributes = result
            # Check if name was changed
            if hasattr(dialog, 'new_name') and dialog.new_name and dialog.new_name != target_obj.name:
                target_obj.name = dialog.new_name
                # Invalidate cache since name label will change
                self.renderer.invalidate_cache()
            self.workspace_modified = True
            self._update_tree()
            self._update_display()
    
    def _duplicate_object(self):
        """Create a duplicate of the selected object."""
        if not self.selected_object_ids:
            messagebox.showinfo("Info", "Select an object to duplicate")
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        obj_id = next(iter(self.selected_object_ids))
        obj = self._get_object_by_id(obj_id)
        if not obj:
            return
        
        import copy
        
        # Create new object with copied properties
        new_obj = SegmentedObject(
            name=f"{obj.name}_copy",
            category=obj.category
        )
        
        # Copy all instances
        for inst in obj.instances:
            new_inst = ObjectInstance(
                instance_num=inst.instance_num,
                page_id=inst.page_id,
                view_type=getattr(inst, 'view_type', ''),
                attributes=copy.deepcopy(inst.attributes) if hasattr(inst, 'attributes') else None
            )
            # Copy elements with new IDs
            for elem in inst.elements:
                new_elem = SegmentElement(
                    category=elem.category,
                    mask=elem.mask.copy() if elem.mask is not None else None,
                    seed_point=elem.seed_point,
                    points=elem.points.copy() if elem.points else None
                )
                new_inst.elements.append(new_elem)
            new_obj.instances.append(new_inst)
        
        self.all_objects.append(new_obj)
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._add_tree_item(new_obj)
        self._update_display()
        
        # Select the new object
        self.selected_object_ids = {new_obj.object_id}
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        tree_id = f"o_{new_obj.object_id}"
        if self.object_tree.exists(tree_id):
            self.object_tree.selection_set(tree_id)
        
        self.status_var.set(f"Duplicated: {new_obj.name}")
    
    def _delete_selected(self):
        modified_objs = set()
        deleted_objs = set()
        
        for elem_id in self.selected_element_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    old_len = len(inst.elements)
                    inst.elements = [e for e in inst.elements if e.element_id != elem_id]
                    if len(inst.elements) != old_len:
                        modified_objs.add(obj.object_id)
                obj.instances = [i for i in obj.instances if i.elements]
        
        for inst_id in self.selected_instance_ids:
            for obj in self.all_objects:
                old_len = len(obj.instances)
                obj.instances = [i for i in obj.instances if i.instance_id != inst_id]
                if len(obj.instances) != old_len:
                    modified_objs.add(obj.object_id)
        
        for obj_id in self.selected_object_ids:
            deleted_objs.add(obj_id)
        
        # Remove deleted objects
        self.all_objects = [o for o in self.all_objects if o.object_id not in deleted_objs]
        
        # Clean up empty objects
        for obj in self.all_objects[:]:
            if not obj.instances:
                deleted_objs.add(obj.object_id)
                self.all_objects.remove(obj)
        
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        self.workspace_modified = True
        self.renderer.invalidate_cache()  # Objects changed
        
        # Incremental tree update
        for obj_id in deleted_objs:
            self._remove_tree_item(obj_id)
        for obj_id in modified_objs - deleted_objs:
            obj = self._get_object_by_id(obj_id)
            if obj:
                self._update_tree_item(obj)
        
        self._update_display()
    
    def _merge_as_instances(self):
        if len(self.selected_object_ids) < 2:
            messagebox.showinfo("Info", "Select at least 2 objects")
            return
        
        objs = [self._get_object_by_id(oid) for oid in self.selected_object_ids]
        objs = [o for o in objs if o]
        if len(objs) < 2:
            return
        
        target = objs[0]
        name = simpledialog.askstring("Merge", "Merged name:", initialvalue=target.name, parent=self.root)
        if not name:
            return
        
        for other in objs[1:]:
            for inst in other.instances:
                inst.instance_num = len(target.instances) + 1
                target.instances.append(inst)
            self.all_objects.remove(other)
            self._remove_tree_item(other.object_id)
        
        target.name = name
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._update_tree_item(target)
        self._update_display()
    
    def _merge_as_group(self):
        if len(self.selected_object_ids) < 2 and len(self.selected_element_ids) < 2:
            messagebox.showinfo("Info", "Select at least 2 items")
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        # Collect all elements
        elements = []
        obj_ids_to_remove = set()
        
        for obj_id in self.selected_object_ids:
            obj = self._get_object_by_id(obj_id)
            if obj:
                for inst in obj.instances:
                    elements.extend(inst.elements)
                obj_ids_to_remove.add(obj_id)
        
        for elem_id in self.selected_element_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.element_id == elem_id and elem not in elements:
                            elements.append(elem)
        
        if len(elements) < 2:
            return
        
        cat_name = self.category_var.get() or "R"
        name = simpledialog.askstring("Merge", f"Name ({len(elements)} elements):", parent=self.root)
        if not name:
            return
        
        # Remove old objects
        for obj_id in obj_ids_to_remove:
            self._remove_tree_item(obj_id)
        self.all_objects = [o for o in self.all_objects if o.object_id not in obj_ids_to_remove]
        
        # Create new grouped object
        obj = SegmentedObject(name=name, category=cat_name)
        inst = ObjectInstance(instance_num=1, page_id=page.tab_id)
        inst.elements = elements
        obj.instances.append(inst)
        self.all_objects.append(obj)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._add_tree_item(obj)
        self._update_display()
    
    # File operations
    def _open_pdf(self):
        if self.pages and self.workspace_modified:
            r = messagebox.askyesnocancel("Save?", "Save workspace first?")
            if r is None:
                return
            if r:
                self._save_workspace()
        
        path = filedialog.askopenfilename(title="Open PDF", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        
        # Load with dimension information
        pages = self.pdf_reader.load_with_dimensions(path)
        if not pages:
            messagebox.showerror("Error", "Failed to load PDF")
            return
        
        dialog = PDFLoaderDialog(self.root, path, pages, dpi=self.settings.default_dpi)
        result = dialog.show()
        if not result:
            return
        
        # Close existing and reset workspace
        for tid in list(self.pages.keys()):
            if hasattr(self.pages[tid], 'frame'):
                self.notebook.forget(self.pages[tid].frame)
            del self.pages[tid]
        
        # Reset all workspace data
        self.all_objects = []  # Clear object list
        self.categories = create_default_categories()
        self._refresh_categories()
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        self._update_tree()  # Clear tree view
        self.workspace_file = None
        self.workspace_modified = True
        
        for page_data in result:
            page = PageTab(
                model_name=page_data['model_name'],
                page_name=page_data['page_name'],
                original_image=page_data['image'],
                source_path=path,
                rotation=page_data.get('rotation', 0),
                dpi=page_data.get('dpi', self.settings.default_dpi),
                pdf_width_inches=page_data.get('width_inches', 0),
                pdf_height_inches=page_data.get('height_inches', 0),
            )
            self._add_page(page)
        
        self.status_var.set(f"Loaded {len(result)} pages")
    
    def _save_workspace(self):
        if not self.workspace_file:
            self._save_workspace_as()
            return
        
        # Collect view state
        view_state = self._get_view_state()
        
        # Update page-level view state (zoom, scroll)
        for page in self.pages.values():
            page.zoom_level = self.zoom_level  # Current zoom
            if hasattr(page, 'canvas'):
                # Save scroll position
                page.scroll_x = page.canvas.xview()[0]
                page.scroll_y = page.canvas.yview()[0]
        
        if self.workspace_mgr.save(self.workspace_file, list(self.pages.values()), 
                                   self.categories, self.all_objects, view_state):
            self.workspace_modified = False
            self.status_var.set(f"Saved: {Path(self.workspace_file).name}")
    
    def _save_workspace_as(self):
        path = filedialog.asksaveasfilename(title="Save Workspace", defaultextension=".pmw",
                                            filetypes=[("PlanMod Workspace", "*.pmw")])
        if path:
            self.workspace_file = path
            self._save_workspace()
    
    def _load_workspace(self):
        if self.pages and self.workspace_modified:
            r = messagebox.askyesnocancel("Save?", "Save workspace first?")
            if r is None:
                return
            if r:
                self._save_workspace()
        
        path = filedialog.askopenfilename(title="Open Workspace", filetypes=[("PlanMod Workspace", "*.pmw")])
        if not path:
            return
        
        data = self.workspace_mgr.load(path)
        if not data:
            messagebox.showerror("Error", "Failed to load workspace")
            return
        
        # Close existing and reset workspace
        for tid in list(self.pages.keys()):
            if hasattr(self.pages[tid], 'frame'):
                self.notebook.forget(self.pages[tid].frame)
            del self.pages[tid]
        
        # Clear selections
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        
        self.categories = data.categories
        if not self.categories:
            self.categories = create_default_categories()
        
        # Ensure mark_text and mark_hatch exist for backwards compatibility
        if "mark_text" not in self.categories:
            self.categories["mark_text"] = DynamicCategory(
                name="mark_text", prefix="mark_text", full_name="Mark as Text",
                color_rgb=(255, 200, 0), selection_mode="flood"
            )
        if "mark_hatch" not in self.categories:
            self.categories["mark_hatch"] = DynamicCategory(
                name="mark_hatch", prefix="mark_hatch", full_name="Mark as Hatching",
                color_rgb=(200, 0, 255), selection_mode="flood"
            )
        
        self._refresh_categories()
        
        # Load global objects
        self.all_objects = data.objects if data.objects else []
        
        for page in data.pages:
            self._add_page(page)
            # ALWAYS rebuild combined masks to ensure they're initialized
            # This is critical for flood fill to work correctly after load
            self._update_combined_text_mask(page)
            self._update_combined_hatch_mask(page)
            
            # Debug: print mask status
            text_mask = getattr(page, 'combined_text_mask', None)
            hatch_mask = getattr(page, 'combined_hatch_mask', None)
            print(f"Page {page.display_name}: hide_text={getattr(page, 'hide_text', False)}, "
                  f"text_mask={(text_mask.shape if text_mask is not None else None)}, "
                  f"mask_sum={np.sum(text_mask) if text_mask is not None else 0}")
            print(f"  hide_hatch={getattr(page, 'hide_hatching', False)}, "
                  f"hatch_mask={(hatch_mask.shape if hatch_mask is not None else None)}, "
                  f"mask_sum={np.sum(hatch_mask) if hatch_mask is not None else 0}")
        
        self._update_tree()  # Rebuild tree with loaded objects
        
        # Update view menu to reflect loaded page's hide states
        self._update_view_menu_labels()
        
        self.workspace_file = path
        self.workspace_modified = False
        self.status_var.set(f"Loaded: {Path(path).name}")
        
        # Restore view state (current page, zoom, etc.)
        if data.view_state:
            self._restore_view_state(data.view_state)
        
        # Force a small delay to ensure all UI is settled, then redraw
        def _final_refresh():
            self.renderer.invalidate_cache()
            self._update_display()
            # Re-draw rulers for current page
            page = self._get_current_page()
            if page:
                self._draw_rulers(page)
                # Restore scroll position if available
                if hasattr(page, 'scroll_x') and hasattr(page, 'scroll_y'):
                    page.canvas.xview_moveto(page.scroll_x)
                    page.canvas.yview_moveto(page.scroll_y)
        
        self.root.after(400, _final_refresh)
    
    def _export_image(self):
        page = self._get_current_page()
        if not page:
            return
        
        path = filedialog.asksaveasfilename(title="Export Image", defaultextension=".png",
                                            initialfile=page.segmented_filename,
                                            filetypes=[("PNG", "*.png")])
        if path:
            from tools.segmenter.io.export import ImageExporter
            ImageExporter(self.renderer).export_page(path, page, self.categories)
            self.status_var.set(f"Exported: {Path(path).name}")
    
    def _export_data(self):
        page = self._get_current_page()
        if not page:
            return
        
        path = filedialog.asksaveasfilename(title="Export Data", defaultextension=".json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            from tools.segmenter.io.export import DataExporter
            DataExporter().export_page(path, page)
            self.status_var.set(f"Exported: {Path(path).name}")
    
    def _scan_labels(self):
        pages = [p for p in self.pages.values() if p.original_image is not None]
        if not pages:
            messagebox.showinfo("Info", "No pages to scan")
            return
        
        dialog = LabelScanDialog(self.root, pages)
        result = dialog.show()
        
        if result:
            for prefix, full_name in result.items():
                if prefix not in self.categories:
                    color = get_next_color(len(self.categories))
                    self.categories[prefix] = DynamicCategory(
                        name=prefix, prefix=prefix, full_name=full_name,
                        color_rgb=color, selection_mode="flood"
                    )
            self._refresh_categories()
            self.workspace_modified = True
            self.status_var.set(f"Added {len(result)} categories")
    
    def _get_view_state(self) -> dict:
        """Get current view state for workspace saving."""
        return {
            "current_page_id": self.current_page_id,
            "zoom_level": self.zoom_level,
            "group_by": self.group_by_var.get() if hasattr(self, 'group_by_var') else "none",
            "show_labels": self.show_labels,
            "current_view": self.current_view_var.get() if hasattr(self, 'current_view_var') else "",
            "sidebar_width": self.settings.sidebar_width,
            "tree_width": self.settings.tree_width,
        }
    
    def _restore_view_state(self, view_state: dict):
        """Restore view state from loaded workspace."""
        if not view_state:
            return
        
        # Restore zoom level
        self.zoom_level = view_state.get("zoom_level", 1.0)
        if hasattr(self, 'zoom_var'):
            self.zoom_var.set(f"{int(self.zoom_level * 100)}%")
        
        # Restore group by
        if hasattr(self, 'group_by_var'):
            self.group_by_var.set(view_state.get("group_by", "none"))
        
        # Restore show labels
        self.show_labels = view_state.get("show_labels", True)
        if hasattr(self, 'show_labels_var'):
            self.show_labels_var.set(self.show_labels)
        
        # Restore current view
        if hasattr(self, 'current_view_var'):
            self.current_view_var.set(view_state.get("current_view", ""))
        
        # Restore current page (done after all pages loaded)
        target_page_id = view_state.get("current_page_id")
        if target_page_id and target_page_id in self.pages:
            self._switch_to_page(target_page_id)
    
    def _on_close(self):
        if self.workspace_modified:
            r = messagebox.askyesnocancel("Save?", "Save workspace before closing?")
            if r is None:
                return
            if r:
                self._save_workspace()
        
        # Save window geometry
        self.settings.window_width = self.root.winfo_width()
        self.settings.window_height = self.root.winfo_height()
        self.settings.window_x = self.root.winfo_x()
        self.settings.window_y = self.root.winfo_y()
        save_settings(self.settings)
        self.root.quit()
    
    def run(self):
        """Run the application."""
        self.root.mainloop()

