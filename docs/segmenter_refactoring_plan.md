# PlanMod Segmenter Refactoring Plan

## Current State

The `interactive_segmenter.py` file has grown to **~2,500 lines** and contains:
- Data models
- Configuration
- UI dialogs
- Custom widgets
- Core segmentation logic
- Event handling
- File I/O operations
- Rendering logic

This monolithic structure makes it difficult to:
- Test individual components
- Maintain and extend features
- Understand the codebase
- Reuse components

---

## Proposed Module Structure

```
tools/segmenter/
├── __init__.py              # Package init, exposes main entry point
├── __main__.py              # Entry point: python -m tools.segmenter
├── app.py                   # Main application class (slim coordinator)
├── config.py                # Settings, themes, constants (existing)
│
├── models/                  # Data structures
│   ├── __init__.py
│   ├── elements.py          # SegmentElement, masks
│   ├── objects.py           # SegmentedObject, ObjectInstance
│   ├── categories.py        # DynamicCategory
│   ├── page.py              # PageTab
│   └── attributes.py        # ObjectAttributes, materials, types
│
├── ui/                      # User interface components
│   ├── __init__.py
│   ├── main_window.py       # Main window setup, menu bar
│   ├── sidebar.py           # Left sidebar (tools, categories, settings)
│   ├── canvas.py            # Image canvas with zoom/scroll
│   ├── object_tree.py       # Right panel object tree view
│   └── status_bar.py        # Status bar component
│
├── widgets/                 # Reusable UI widgets
│   ├── __init__.py
│   ├── collapsible.py       # CollapsibleFrame
│   ├── color_picker.py      # Color selection widget
│   └── position_grid.py     # Label position 3x3 selector
│
├── dialogs/                 # Modal dialogs
│   ├── __init__.py
│   ├── pdf_loader.py        # PDFLoaderDialog
│   ├── label_scan.py        # LabelScanDialog
│   ├── attributes.py        # AttributeDialog
│   └── workspace.py         # Save/load workspace dialogs
│
├── core/                    # Core business logic
│   ├── __init__.py
│   ├── segmentation.py      # Flood fill, mask operations
│   ├── drawing.py           # Polyline, freeform, line tools
│   ├── selection.py         # Object selection, multi-select
│   ├── grouping.py          # Group mode, merge operations
│   └── rendering.py         # Display rendering, blending
│
├── io/                      # File I/O operations
│   ├── __init__.py
│   ├── workspace.py         # Save/load .pmw files
│   ├── pdf_reader.py        # PDF loading and rasterization
│   ├── image_export.py      # PNG/segmented image export
│   └── data_export.py       # JSON data export
│
└── utils/                   # Utilities
    ├── __init__.py
    ├── ocr.py               # Tesseract OCR wrapper
    ├── geometry.py          # Point/polygon utilities
    └── image.py             # Image processing helpers
```

---

## Module Responsibilities

### 1. `models/` - Data Structures (~200 lines)

**elements.py**
```python
@dataclass
class SegmentElement:
    element_id: str
    category: str
    mode: str  # "flood", "polyline", "freeform", "line"
    points: List[Tuple[int, int]]
    mask: np.ndarray
    color: Tuple[int, int, int]
    label_position: str = "center"
```

**objects.py**
```python
@dataclass
class ObjectInstance:
    instance_id: str
    instance_num: int
    elements: List[SegmentElement]
    page_id: Optional[str]
    view_type: str

@dataclass
class SegmentedObject:
    object_id: str
    name: str
    category: str
    instances: List[ObjectInstance]
    attributes: ObjectAttributes
```

**categories.py**
```python
@dataclass
class DynamicCategory:
    name: str
    prefix: str
    full_name: str
    color_rgb: Tuple[int, int, int]
    color_bgr: Tuple[int, int, int]
    selection_mode: str
    visible: bool = True

DEFAULT_CATEGORIES = {...}
```

**page.py**
```python
@dataclass
class PageTab:
    tab_id: str
    model_name: str
    page_name: str
    original_image: Optional[np.ndarray]
    segmentation_layer: Optional[np.ndarray]
    groups: List[SegmentedObject]
    # ... properties
```

---

### 2. `ui/` - User Interface (~400 lines)

**main_window.py**
```python
class MainWindow:
    """Coordinates all UI components."""
    
    def __init__(self, app: 'SegmenterApp'):
        self.app = app
        self.root = tk.Tk()
        self._setup_menu()
        self._setup_layout()
    
    def _setup_menu(self):
        # File, View, Help menus
    
    def _setup_layout(self):
        self.sidebar = Sidebar(self)
        self.canvas_manager = CanvasManager(self)
        self.object_tree = ObjectTreePanel(self)
```

**sidebar.py**
```python
class Sidebar:
    """Left sidebar with tools and settings."""
    
    def __init__(self, parent: MainWindow):
        self.mode_section = ModeSection(...)
        self.category_section = CategorySection(...)
        self.group_section = GroupSection(...)
        self.settings_section = SettingsSection(...)
```

**canvas.py**
```python
class SegmenterCanvas:
    """Image canvas with zoom, scroll, and drawing."""
    
    def __init__(self, parent, page: PageTab):
        self.page = page
        self.zoom_level = 1.0
        self._setup_canvas()
        self._bind_events()
    
    def render(self):
        # Blend original + segmentation + highlights
    
    def canvas_to_image(self, x, y) -> Tuple[int, int]:
        # Coordinate conversion
```

**object_tree.py**
```python
class ObjectTreePanel:
    """Right panel showing object hierarchy."""
    
    def __init__(self, parent: MainWindow):
        self.tree = ttk.Treeview(...)
        self._setup_buttons()
    
    def refresh(self, objects: List[SegmentedObject]):
        # Rebuild tree with simplified hierarchy
    
    def get_selected(self) -> Selection:
        # Return selected objects/instances/elements
```

---

### 3. `dialogs/` - Modal Dialogs (~400 lines)

**pdf_loader.py**
```python
class PDFLoaderDialog(tk.Toplevel):
    """Dialog for loading PDF and naming pages."""
    
    def __init__(self, parent, pdf_path: str, pages: List[np.ndarray]):
        self._center_on_parent(parent)
        self._setup_ui()
    
    def _center_on_parent(self, parent):
        # Position relative to parent window
    
    def get_result(self) -> Optional[List[PageConfig]]:
        # Return configured pages or None if cancelled
```

**label_scan.py**
```python
class LabelScanDialog(tk.Toplevel):
    """OCR scan progress and results."""
    
    def __init__(self, parent, pages: List[PageTab]):
        self._setup_ui()
        self.after(100, self._start_scan)
    
    def _start_scan(self):
        # Run OCR with progress updates
    
    def get_result(self) -> Optional[Dict[str, str]]:
        # Return selected categories
```

---

### 4. `core/` - Business Logic (~500 lines)

**segmentation.py**
```python
class SegmentationEngine:
    """Core segmentation operations."""
    
    def __init__(self, tolerance: int = 5):
        self.tolerance = tolerance
    
    def flood_fill(self, image: np.ndarray, seed: Tuple[int, int]) -> np.ndarray:
        # Return mask
    
    def create_polygon_mask(self, shape: Tuple[int, int], 
                            points: List[Tuple[int, int]]) -> np.ndarray:
        # Return filled polygon mask
    
    def create_line_mask(self, shape: Tuple[int, int],
                         points: List[Tuple[int, int]], 
                         thickness: int) -> np.ndarray:
        # Return line mask
```

**drawing.py**
```python
class DrawingTool:
    """Abstract base for drawing tools."""
    
    def on_click(self, x: int, y: int): ...
    def on_drag(self, x: int, y: int): ...
    def on_release(self): ...
    def on_double_click(self, x: int, y: int): ...
    def finish(self) -> Optional[SegmentElement]: ...
    def cancel(self): ...

class FloodFillTool(DrawingTool): ...
class PolylineTool(DrawingTool): ...
class FreeformTool(DrawingTool): ...
class LineTool(DrawingTool): ...
class SelectTool(DrawingTool): ...
```

**grouping.py**
```python
class GroupManager:
    """Manages object grouping and merging."""
    
    def __init__(self, page: PageTab):
        self.page = page
        self.pending_elements: List[SegmentElement] = []
    
    def start_group_mode(self): ...
    def add_to_group(self, element: SegmentElement): ...
    def finish_group(self, name: str, category: str) -> SegmentedObject: ...
    
    def merge_as_instances(self, objects: List[SegmentedObject], 
                           name: str) -> SegmentedObject: ...
    def merge_as_group(self, items: List[Any], 
                       name: str, category: str) -> SegmentedObject: ...
```

**rendering.py**
```python
class Renderer:
    """Renders segmentation overlays."""
    
    def render_page(self, page: PageTab, 
                    zoom: float,
                    show_labels: bool,
                    selected_ids: Set[str],
                    planform_opacity: float) -> np.ndarray:
        # Return blended image
    
    def _draw_labels(self, image: np.ndarray, 
                     objects: List[SegmentedObject]): ...
    
    def _highlight_selected(self, image: np.ndarray,
                            objects: List[SegmentedObject],
                            selected_ids: Set[str]): ...
```

---

### 5. `io/` - File Operations (~300 lines)

**workspace.py**
```python
class WorkspaceManager:
    """Save/load workspace files."""
    
    VERSION = "4.4"
    
    def save(self, path: str, 
             pages: List[PageTab],
             categories: Dict[str, DynamicCategory]): ...
    
    def load(self, path: str) -> WorkspaceData: ...
    
    def _serialize_object(self, obj: SegmentedObject) -> dict: ...
    def _deserialize_object(self, data: dict, 
                            image_shape: Tuple[int, int]) -> SegmentedObject: ...
```

**pdf_reader.py**
```python
class PDFReader:
    """Load and rasterize PDF files."""
    
    def __init__(self, dpi: int = 150):
        self.dpi = dpi
    
    def load(self, path: str) -> List[np.ndarray]:
        # Return list of page images
    
    def rotate_page(self, image: np.ndarray, degrees: int) -> np.ndarray: ...
```

---

### 6. `app.py` - Main Application (~200 lines)

```python
class SegmenterApp:
    """Main application coordinator."""
    
    def __init__(self):
        self.settings = load_settings()
        self.categories: Dict[str, DynamicCategory] = {}
        self.pages: Dict[str, PageTab] = {}
        self.current_page_id: Optional[str] = None
        
        self.segmentation = SegmentationEngine(self.settings.tolerance)
        self.workspace_mgr = WorkspaceManager()
        self.renderer = Renderer()
        
        self.window = MainWindow(self)
        self._init_default_categories()
    
    # High-level operations delegating to modules
    def open_pdf(self, path: str): ...
    def save_workspace(self, path: str): ...
    def add_element(self, element: SegmentElement): ...
    def delete_selected(self): ...
    
    def run(self):
        self.window.root.mainloop()
```

---

## Refactoring Steps

### Phase 1: Extract Data Models (Low Risk)
1. Create `tools/segmenter/models/` package
2. Move dataclasses to appropriate modules
3. Update imports in main file
4. Test: Verify app still runs

### Phase 2: Extract Utilities (Low Risk)
1. Create `tools/segmenter/utils/` package
2. Move OCR wrapper, geometry helpers
3. Update imports
4. Test

### Phase 3: Extract Dialogs (Medium Risk)
1. Create `tools/segmenter/dialogs/` package
2. Extract one dialog at a time (start with AttributeDialog)
3. Test each extraction
4. Handle parent window positioning

### Phase 4: Extract Core Logic (Medium Risk)
1. Create `tools/segmenter/core/` package
2. Extract SegmentationEngine (flood fill, masks)
3. Extract Renderer
4. Extract GroupManager
5. Test thoroughly

### Phase 5: Extract UI Components (Higher Risk)
1. Create `tools/segmenter/ui/` package
2. Extract ObjectTreePanel
3. Extract Sidebar
4. Extract CanvasManager
5. Wire up event communication

### Phase 6: Create App Coordinator (Final)
1. Create slim `app.py`
2. Move MainWindow setup to `ui/main_window.py`
3. Update entry point
4. Final integration testing

---

## Event Communication Pattern

Use an event bus pattern for loose coupling:

```python
# utils/events.py
class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event: str, handler: Callable):
        self._handlers.setdefault(event, []).append(handler)
    
    def emit(self, event: str, **data):
        for handler in self._handlers.get(event, []):
            handler(**data)

# Events:
# - "element_added" (element: SegmentElement)
# - "selection_changed" (selected_ids: Set[str])
# - "page_changed" (page_id: str)
# - "category_added" (category: DynamicCategory)
# - "mode_changed" (mode: str)
# - "workspace_modified" ()
```

---

## Testing Strategy

1. **Unit Tests** for each module:
   - `test_models.py` - Data serialization
   - `test_segmentation.py` - Mask generation
   - `test_grouping.py` - Merge operations
   - `test_workspace.py` - Save/load round-trip

2. **Integration Tests**:
   - Load PDF → Create elements → Save → Load → Verify

3. **Manual Testing Checklist**:
   - [ ] Open PDF, rename pages
   - [ ] Flood fill creates object
   - [ ] Group mode creates grouped object
   - [ ] Merge as instances works
   - [ ] Merge as group works
   - [ ] Save/load workspace preserves all data
   - [ ] Theme switching works

---

## Estimated Effort

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Models | 1-2 hours | Low |
| Phase 2: Utilities | 1 hour | Low |
| Phase 3: Dialogs | 2-3 hours | Medium |
| Phase 4: Core Logic | 3-4 hours | Medium |
| Phase 5: UI Components | 4-5 hours | Higher |
| Phase 6: App Coordinator | 2 hours | Medium |
| **Total** | **~15 hours** | |

---

## Benefits After Refactoring

1. **Maintainability**: Each file < 300 lines, single responsibility
2. **Testability**: Core logic can be unit tested without UI
3. **Reusability**: Components can be used in other tools
4. **Extensibility**: New tools/modes easy to add
5. **Collaboration**: Multiple developers can work in parallel
6. **Debugging**: Easier to isolate issues

---

## Migration Path

Keep `interactive_segmenter.py` working during refactoring:

```python
# tools/interactive_segmenter.py (during migration)
"""Legacy entry point - redirects to new modular version."""
from tools.segmenter import main
main()
```

This allows gradual migration while maintaining backward compatibility.


