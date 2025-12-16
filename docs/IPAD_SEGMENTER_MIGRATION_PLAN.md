# iPad Segmenter Migration Plan

## Executive Summary

This document outlines the plan to port the PlanMod Segmenter desktop application to iPad, making it runnable on iOS using one of the available Python environments (Pythonista, Pyto, or Carnets).

**Recommended Platform: Pyto**

After analyzing the Segmenter's requirements against available iPad Python environments, **Pyto** is recommended as the target platform due to its superior package support, pip integration, and modern SwiftUI-based UI framework.

---

## Current Segmenter Architecture

### Technology Stack (Desktop Version)

**GUI Framework:** `tkinter` (Python standard library)

**Key Dependencies:**
- `tkinter` / `ttk` - GUI framework
- `opencv-python-headless>=4.9.0` - Image processing (cv2)
- `Pillow>=10.2.0` - Image manipulation (PIL)
- `numpy>=1.26.0` - Array operations
- `PyMuPDF>=1.23.0` - PDF reading (fitz)
- `pdf2image>=1.17.0` - PDF to image conversion
- `pytesseract>=0.3.10` - OCR (Tesseract wrapper)

**Source:** [GitHub - kgoodarzi/PlanMod/tools/segmenter](https://github.com/kgoodarzi/PlanMod/tree/main/tools/segmenter)

### Module Structure

```
tools/segmenter/
├── app.py                 # Main tkinter application (3734 lines)
├── config.py              # Configuration management
├── __main__.py            # CLI entry point
│
├── core/
│   ├── drawing.py         # Drawing/annotation tools
│   ├── rendering.py       # Image rendering engine
│   └── segmentation.py    # Core segmentation logic (flood fill, contours)
│
├── dialogs/
│   ├── base.py            # Base dialog class (tkinter Toplevel)
│   ├── attributes.py      # Attribute editing dialog
│   ├── label_scan.py      # Label/text scanning dialog
│   ├── pdf_loader.py      # PDF import dialog
│   └── settings.py        # Application settings dialog
│
├── io/
│   ├── export.py          # Export to various formats
│   ├── pdf_reader.py      # PDF file reading (PyMuPDF)
│   └── workspace.py       # Project/workspace management (.pmw files)
│
├── models/
│   ├── attributes.py      # Attribute data models
│   ├── categories.py      # DynamicCategory definitions
│   ├── elements.py        # SegmentElement models
│   ├── objects.py         # SegmentedObject, ObjectInstance models
│   └── page.py            # PageTab document models
│
├── utils/
│   ├── geometry.py        # Geometric calculations
│   ├── image.py           # Image processing utilities (cv2, PIL)
│   └── ocr.py             # OCR via pytesseract
│
└── widgets/
    ├── collapsible.py     # CollapsibleFrame (tkinter)
    ├── position_grid.py   # PositionGrid widget
    └── responsive_layout.py # ResizableLayout, DockablePanel, StatusBar
```

### Core Features

| Feature | Description | Desktop Dependencies |
|---------|-------------|---------------------|
| PDF Import | Load multi-page PDF plans | PyMuPDF (fitz), pdf2image |
| Image Segmentation | Flood fill, polyline, freeform | OpenCV, PIL/Pillow, NumPy |
| OCR Text Extraction | Extract text/labels from images | Tesseract, pytesseract |
| Drawing Tools | Select, flood, polyline, freeform, line | tkinter Canvas |
| Attribute Editing | Assign metadata to segments | tkinter Toplevel dialogs |
| Export | Save segments, annotations, data | JSON, PNG, custom formats |
| Workspace Management | Save/load projects (.pmw files) | File system I/O |
| Settings/Config | User preferences, themes | JSON config files |
| Multi-page Support | Tab-based page navigation | tkinter Notebook |
| Zoom/Pan | Canvas zoom and pan | tkinter Canvas transforms |

---

## iPad Python Environment Comparison

### Platform Analysis

| Capability | Pythonista | Pyto | Carnets |
|------------|------------|------|---------|
| **UI Framework** | Custom `ui` module | SwiftUI-based | None (notebooks only) |
| **tkinter Support** | ❌ No | ❌ No | ❌ No |
| **pip Support** | ❌ No | ✅ Yes | Limited |
| **PIL/Pillow** | ✅ Built-in | ✅ Via pip | ✅ Built-in |
| **NumPy** | ✅ Built-in | ✅ Via pip | ✅ Built-in |
| **OpenCV** | ❌ No | ⚠️ Headless only | ❌ No |
| **PDF Reading** | ⚠️ Limited | ⚠️ Via packages | ❌ No |
| **OCR** | ❌ No native | ⚠️ Cloud API needed | ❌ No |
| **File Access** | ✅ Sandboxed | ✅ Files app integration | ✅ Limited |
| **Touch/Gesture** | ✅ Excellent | ✅ Good | N/A |
| **Apple Pencil** | ✅ Supported | ✅ Supported | N/A |
| **Active Development** | ⚠️ Slow updates | ✅ Active | ✅ Active |
| **Price** | $9.99 | $9.99 (Pro) | Free |

### Key Challenge: tkinter Not Available on iOS

The desktop Segmenter uses **tkinter**, which is NOT available on any iOS Python environment. The entire UI layer must be rewritten using the target platform's native UI framework.

### Recommendation: **Pyto**

**Why Pyto over Pythonista:**
1. **pip support** - Can install Pillow, NumPy, and other packages as needed
2. **Better file integration** - Works with iOS Files app and document picker
3. **Modern Python** - Python 3.10+ vs Pythonista's older version
4. **Active development** - Regular updates and bug fixes
5. **Shortcuts integration** - Automation possibilities
6. **SwiftUI foundation** - More native iOS feel
7. **PyObjC support** - Access iOS frameworks (Vision, PDFKit) via rubicon-objc

**Why Pythonista is still viable:**
- More mature `ui` module with better documentation
- Built-in `scene` module for 2D graphics
- Excellent touch handling
- If pip packages aren't critical, it's simpler

**Why not Carnets:**
- Designed for Jupyter notebooks, not standalone GUI applications
- No interactive UI framework

---

## Feature Compatibility Matrix

### ✅ Fully Supported Features (Green Light)

| Feature | Implementation Strategy |
|---------|------------------------|
| Image viewing/zooming | Pyto UI ImageView with gesture recognizers |
| Drawing rectangles | Custom canvas view with touch handling |
| Drawing polygons | Touch point collection, path rendering |
| Attribute assignment | Form-based UI dialogs |
| Category management | List views with CRUD operations |
| JSON export/import | Built-in `json` module |
| PNG image export | PIL/Pillow |
| Workspace save/load | iOS Files app integration |
| Settings/preferences | UserDefaults via PyObjC |
| Touch gestures | Native iOS gesture support |
| Apple Pencil support | Pressure/tilt data available |
| Pinch-to-zoom | Native gesture recognizers |

### ⚠️ Partially Supported Features (Requires Workarounds)

| Feature | Limitation | Workaround |
|---------|------------|------------|
| **PDF Import** | No PyMuPDF on iOS | Use `PyPDF2` for basic reading, or iOS native PDF rendering via PyObjC, or convert to images first |
| **OCR** | No Tesseract on iOS | Use Apple's Vision framework via PyObjC, or cloud API (Google Vision, AWS Textract) |
| **Multi-window** | iOS doesn't support true multi-window | Use tab-based or split-view navigation |
| **Drag & drop from desktop** | Limited cross-device | Use AirDrop, iCloud, or share sheet |
| **Large file handling** | iOS memory constraints | Implement pagination, lazy loading |
| **Background processing** | iOS limits background execution | Use iOS background tasks API |

### ❌ Not Supported Features (Red Light)

| Feature | Reason | Alternative |
|---------|--------|-------------|
| **System file dialogs** | iOS sandboxing | Use iOS document picker |
| **Global keyboard shortcuts** | No global shortcuts on iPad | Touch-based UI, toolbar buttons |
| **Multiple floating windows** | iPadOS limitation | Single window with navigation |
| **Direct printer access** | iOS print system different | Use iOS share sheet for printing |
| **Tesseract OCR (local)** | Binary not available | Must use Vision framework or cloud |
| **Advanced OpenCV features** | opencv-python-headless only | Limited to basic operations |
| **System tray/menu bar** | Desktop-only concept | N/A - not applicable |
| **Right-click context menus** | No right-click | Long-press menus instead |

---

## Migration Architecture

### Proposed iPad Architecture

```
segmenter_ipad/
├── main.py                    # Pyto app entry point (replaces __main__.py)
├── config.py                  # Configuration (port from desktop, use NSUserDefaults)
│
├── ui/                        # COMPLETE REWRITE (replaces tkinter)
│   ├── __init__.py
│   ├── main_view.py           # Main application view (replaces SegmenterApp class)
│   ├── canvas_view.py         # Drawing canvas (replaces tk.Canvas)
│   ├── toolbar.py             # Tool selection (replaces menubar + tool buttons)
│   ├── sidebar.py             # Objects/categories list (replaces TreeView)
│   ├── dialogs/
│   │   ├── __init__.py
│   │   ├── attributes.py      # Attribute editor (port from dialogs/attributes.py)
│   │   ├── categories.py      # Category manager (new for iOS)
│   │   ├── pdf_import.py      # PDF import (port from dialogs/pdf_loader.py)
│   │   ├── label_scan.py      # OCR dialog (port from dialogs/label_scan.py)
│   │   ├── export.py          # Export options (new for iOS share sheet)
│   │   └── settings.py        # Settings (port from dialogs/settings.py)
│   └── components/
│       ├── __init__.py
│       ├── collapsible.py     # Port from widgets/collapsible.py
│       ├── position_grid.py   # Port from widgets/position_grid.py
│       └── status_bar.py      # Port from widgets/responsive_layout.py
│
├── core/                      # MOSTLY PORTABLE (minor changes)
│   ├── __init__.py
│   ├── drawing.py             # Port from core/drawing.py (remove cv2 deps)
│   ├── rendering.py           # Port from core/rendering.py (use PIL)
│   └── segmentation.py        # Port from core/segmentation.py (PIL fallbacks)
│
├── io/                        # MAJOR CHANGES (iOS file system)
│   ├── __init__.py
│   ├── document_picker.py     # NEW: iOS UIDocumentPickerViewController
│   ├── pdf_reader.py          # REWRITE: Use iOS PDFKit instead of PyMuPDF
│   ├── export.py              # Port from io/export.py + iOS share sheet
│   └── workspace.py           # Port from io/workspace.py (use iOS Files)
│
├── models/                    # FULLY PORTABLE (pure Python dataclasses)
│   ├── __init__.py
│   ├── attributes.py          # Direct port from models/attributes.py
│   ├── categories.py          # Direct port from models/categories.py
│   ├── elements.py            # Direct port from models/elements.py
│   ├── objects.py             # Direct port from models/objects.py
│   └── page.py                # Direct port from models/page.py
│
├── services/                  # NEW: iOS-specific services
│   ├── __init__.py
│   ├── ocr_service.py         # NEW: Apple Vision OCR (replaces pytesseract)
│   └── image_service.py       # Image processing helpers
│
└── utils/                     # MOSTLY PORTABLE
    ├── __init__.py
    ├── geometry.py            # Direct port from utils/geometry.py
    ├── image.py               # Port from utils/image.py (remove cv2)
    ├── ocr.py                 # Port patterns/constants from utils/ocr.py
    └── ios_bridge.py          # NEW: PyObjC/rubicon-objc helpers
```

### Module Portability Assessment

| Desktop Module | iPad Status | Changes Required |
|----------------|-------------|------------------|
| `models/*` | ✅ 100% portable | None - pure Python dataclasses |
| `utils/geometry.py` | ✅ 100% portable | None - pure math |
| `config.py` | ⚠️ 90% portable | Replace file paths with iOS storage |
| `core/segmentation.py` | ⚠️ 70% portable | Add PIL fallbacks for cv2 functions |
| `core/rendering.py` | ⚠️ 60% portable | Replace cv2 rendering with PIL |
| `core/drawing.py` | ⚠️ 50% portable | Replace tk Canvas calls |
| `utils/image.py` | ⚠️ 50% portable | Replace cv2 with PIL equivalents |
| `utils/ocr.py` | 🔄 Rewrite | Replace pytesseract with Vision API |
| `io/pdf_reader.py` | 🔄 Rewrite | Replace PyMuPDF with iOS PDFKit |
| `io/workspace.py` | ⚠️ 70% portable | Adapt file paths for iOS sandbox |
| `io/export.py` | ⚠️ 60% portable | Add iOS share sheet integration |
| `dialogs/*` | 🔄 Rewrite | Replace tkinter dialogs with Pyto UI |
| `widgets/*` | 🔄 Rewrite | Replace tkinter widgets with Pyto UI |
| `app.py` | 🔄 Rewrite | Complete UI rewrite (3734 lines) |

### UI Framework Strategy

Using Pyto's UI system with custom drawing canvas:

```python
# Example: Main view structure
import pyto_ui as ui

class SegmenterApp:
    def __init__(self):
        self.window = ui.Window()
        self.setup_ui()
    
    def setup_ui(self):
        # Navigation with sidebar
        self.split_view = ui.SplitView()
        
        # Left: Tools and layers
        self.sidebar = self.create_sidebar()
        
        # Center: Canvas
        self.canvas = CanvasView()
        
        # Toolbar
        self.toolbar = self.create_toolbar()
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Goal:** Set up project structure and core portable modules

| Task | Priority | Effort |
|------|----------|--------|
| Create Pyto project structure | High | 2 hours |
| Port `models/` module (data classes) | High | 4 hours |
| Port `utils/geometry.py` | High | 2 hours |
| Port `config.py` for iOS | High | 3 hours |
| Set up iOS file access wrappers | High | 4 hours |
| Create basic app shell | High | 4 hours |

**Deliverable:** App launches, can load/save JSON configs

### Phase 2: Core Canvas (Week 2-3)

**Goal:** Implement drawing canvas with touch support

| Task | Priority | Effort |
|------|----------|--------|
| Create custom CanvasView class | High | 8 hours |
| Implement touch drawing (rectangles) | High | 6 hours |
| Implement polygon drawing | High | 6 hours |
| Add pinch-to-zoom/pan | High | 4 hours |
| Apple Pencil pressure support | Medium | 4 hours |
| Layer rendering system | High | 6 hours |

**Deliverable:** Can draw shapes on images with touch/pencil

### Phase 3: Image & PDF Import (Week 3-4)

**Goal:** Load images and PDFs into the canvas

| Task | Priority | Effort |
|------|----------|--------|
| iOS document picker integration | High | 4 hours |
| Image loading and display | High | 4 hours |
| PDF page rendering (via iOS) | High | 8 hours |
| Multi-page PDF navigation | Medium | 4 hours |
| Image preprocessing | Medium | 4 hours |

**Deliverable:** Can import PDF plans and images

### Phase 4: Segmentation UI (Week 4-5)

**Goal:** Full segmentation workflow

| Task | Priority | Effort |
|------|----------|--------|
| Object/segment list sidebar | High | 6 hours |
| Attribute editing sheets | High | 6 hours |
| Category management | High | 4 hours |
| Selection and editing tools | High | 6 hours |
| Undo/redo system | Medium | 4 hours |

**Deliverable:** Complete segmentation workflow

### Phase 5: OCR Integration (Week 5-6)

**Goal:** Text extraction capability

| Task | Priority | Effort |
|------|----------|--------|
| Apple Vision framework integration | High | 8 hours |
| Text region detection | High | 4 hours |
| OCR results UI | High | 4 hours |
| Cloud OCR fallback (optional) | Low | 6 hours |

**Deliverable:** Can extract text from plan images

### Phase 6: Export & Polish (Week 6-7)

**Goal:** Export functionality and UI polish

| Task | Priority | Effort |
|------|----------|--------|
| JSON export | High | 2 hours |
| PNG segment export | High | 4 hours |
| Workspace save/load | High | 4 hours |
| iCloud sync support | Medium | 6 hours |
| Share sheet integration | Medium | 4 hours |
| UI polish and animations | Medium | 8 hours |
| Error handling | High | 4 hours |

**Deliverable:** Production-ready iPad app

### Phase 7: Testing & Documentation (Week 7-8)

| Task | Priority | Effort |
|------|----------|--------|
| User testing | High | 8 hours |
| Bug fixes | High | 8 hours |
| Performance optimization | Medium | 6 hours |
| User documentation | Medium | 4 hours |

---

## Technical Implementation Details

### Current Desktop Implementation Analysis

From the source code at [github.com/kgoodarzi/PlanMod/tools/segmenter](https://github.com/kgoodarzi/PlanMod/tree/main/tools/segmenter):

**Segmentation Modes (from `app.py`):**
```python
MODES = {
    "select": "Select existing objects",
    "flood": "Flood fill region",
    "polyline": "Draw polygon", 
    "freeform": "Freeform brush",
    "line": "Line segments",
}
```

**Core Segmentation Engine (from `core/segmentation.py`):**
- `flood_fill()` - Uses `cv2.floodFill()` with tolerance
- `create_polygon_mask()` - Uses `cv2.fillPoly()`
- `create_line_mask()` - Uses `cv2.polylines()`
- `create_freeform_mask()` - Thick polylines for brush effect
- Morphological operations: erode, dilate, smooth

**OCR System (from `utils/ocr.py`):**
- Uses `pytesseract` (Tesseract OCR wrapper)
- Looks for model aircraft component labels: R1, F1, FS1, WT, etc.
- Has `KNOWN_PREFIXES` dictionary for component naming

**PDF Reading (from `io/pdf_reader.py`):**
- Uses `PyMuPDF (fitz)` for PDF rendering
- Configurable DPI (default 150)
- Extracts page dimensions in inches

---

### OCR Strategy (Apple Vision Framework)

Replace pytesseract with Apple's Vision framework via PyObjC:

```python
# iOS OCR using Vision framework
from rubicon.objc import ObjCClass
from rubicon.objc.api import NSData, NSURL
import re

VNRecognizeTextRequest = ObjCClass('VNRecognizeTextRequest')
VNImageRequestHandler = ObjCClass('VNImageRequestHandler')

# Port the KNOWN_PREFIXES from desktop version
KNOWN_PREFIXES = {
    "F": "Former", "R": "Rib", "FS": "Fuselage Side",
    "WT": "Wing Tip", "T": "Tail", "M": "Motor Mount",
    "UC": "Undercarriage", "W": "Wing", "E": "Elevator",
    "S": "Spar", "N": "Nose", "L": "Longeron",
}

class OCRService:
    def extract_text(self, image_path: str) -> str:
        """Extract text using Apple Vision framework"""
        url = NSURL.fileURLWithPath_(image_path)
        handler = VNImageRequestHandler.alloc().initWithURL_options_(url, None)
        
        request = VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(1)  # Accurate
        
        handler.performRequests_error_([request], None)
        
        results = request.results()
        text_parts = []
        for observation in results:
            text_parts.append(observation.topCandidates_(1)[0].string())
        
        return '\n'.join(text_parts)
    
    def find_labels(self, image_path: str) -> dict:
        """Port of utils/ocr.py find_labels()"""
        text = self.extract_text(image_path)
        # Use same regex patterns from desktop version
        # ... pattern matching logic ...
```

### PDF Reading Strategy

**Option A: iOS PDFKit (Recommended)**
```python
# Use iOS PDFKit via PyObjC - mirrors desktop PDFReader class
from rubicon.objc import ObjCClass
from PIL import Image
import numpy as np

PDFDocument = ObjCClass('PDFDocument')
PDFPage = ObjCClass('PDFPage')
NSData = ObjCClass('NSData')
NSURL = ObjCClass('NSURL')

class PDFReader:
    """Port of io/pdf_reader.py PDFReader class"""
    
    def __init__(self, dpi: int = 150):
        self.dpi = dpi
    
    def load(self, path: str) -> list:
        """Load PDF and return page images (like desktop version)"""
        url = NSURL.fileURLWithPath_(path)
        doc = PDFDocument.alloc().initWithURL_(url)
        
        pages = []
        for i in range(doc.pageCount()):
            page = doc.pageAtIndex_(i)
            # Render to image using Core Graphics
            # ... rendering code ...
            pages.append(img_array)
        
        return pages
    
    def get_page_count(self, path: str) -> int:
        url = NSURL.fileURLWithPath_(path)
        doc = PDFDocument.alloc().initWithURL_(url)
        return doc.pageCount() if doc else 0
```

**Option B: Pre-convert PDFs**
- User converts PDFs to images before importing
- Simpler but less convenient

### Segmentation Engine Port

The `SegmentationEngine` class can be partially ported:

```python
# core/segmentation.py - iPad version
import numpy as np
from PIL import Image, ImageDraw

class SegmentationEngine:
    """
    iPad port of core/segmentation.py
    
    Note: OpenCV headless has limited flood fill on iOS
    Using PIL/NumPy alternatives where possible
    """
    
    def __init__(self, tolerance: int = 5, line_thickness: int = 3):
        self.tolerance = tolerance
        self.line_thickness = line_thickness
    
    def create_polygon_mask(self, shape: tuple, points: list, 
                            closed: bool = True) -> np.ndarray:
        """Create filled polygon mask using PIL (no OpenCV needed)"""
        h, w = shape
        mask = Image.new('L', (w, h), 0)
        draw = ImageDraw.Draw(mask)
        
        if len(points) >= 3:
            if closed:
                draw.polygon(points, fill=255)
            else:
                draw.line(points, fill=255, width=self.line_thickness)
        
        return np.array(mask)
    
    def flood_fill(self, image: np.ndarray, seed: tuple) -> np.ndarray:
        """
        Flood fill - requires opencv-python-headless
        May need cloud fallback if not available
        """
        try:
            import cv2
            # Original implementation
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # ... flood fill logic ...
        except ImportError:
            # PIL-based fallback (less accurate)
            return self._pil_flood_fill(image, seed)
```

### Canvas Drawing Implementation

```python
# Pyto UI canvas for touch drawing
import pyto_ui as ui
from PIL import Image
import numpy as np

class CanvasView(ui.View):
    """
    Touch-based drawing canvas
    Replaces tkinter Canvas from desktop app.py
    """
    
    def __init__(self):
        super().__init__()
        self.image = None
        self.segments = []  # List of SegmentElement
        self.current_mode = 'flood'  # select, flood, polyline, freeform, line
        self.current_points = []
        self.is_drawing = False
        self.zoom_level = 1.0
        self.pan_offset = (0, 0)
        
    def touch_began(self, touch):
        if self.current_mode in ['polyline', 'freeform', 'line']:
            self.is_drawing = True
            self.current_points = [self._screen_to_image(touch.location)]
        elif self.current_mode == 'flood':
            # Single tap flood fill
            pt = self._screen_to_image(touch.location)
            self._do_flood_fill(pt)
            
    def touch_moved(self, touch):
        if self.is_drawing and self.current_mode in ['freeform', 'line']:
            self.current_points.append(self._screen_to_image(touch.location))
            self.set_needs_display()
            
    def touch_ended(self, touch):
        if self.is_drawing:
            if self.current_mode == 'polyline':
                self.current_points.append(self._screen_to_image(touch.location))
                # Double-tap to close polygon
            else:
                self._finalize_segment()
        self.is_drawing = False
        
    def _screen_to_image(self, point):
        """Convert screen coords to image coords (accounting for zoom/pan)"""
        x = (point[0] - self.pan_offset[0]) / self.zoom_level
        y = (point[1] - self.pan_offset[1]) / self.zoom_level
        return (int(x), int(y))
```

---

## Risk Assessment

### High Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| OCR accuracy lower than Tesseract | Medium | Apple Vision is good for printed text; offer cloud fallback |
| Performance with large PDFs | High | Implement page-by-page loading, caching |
| Pyto API changes | Medium | Abstract UI layer for easier updates |
| Memory constraints | High | Aggressive image downsampling, pagination |

### Medium Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| Apple Pencil latency | Low | Use native drawing APIs |
| File sync issues | Medium | Robust conflict resolution |
| Touch precision vs mouse | Medium | Add precision mode, zoom assist |

---

## Feature Parity Summary

### What WILL Work on iPad ✅

1. ✅ Load and view plan images (PNG, JPEG)
2. ✅ Load and navigate multi-page PDFs
3. ✅ Draw rectangular segments
4. ✅ Draw polygon segments
5. ✅ Freeform selection (with Apple Pencil)
6. ✅ Assign attributes to segments
7. ✅ Manage categories
8. ✅ Export segments as JSON
9. ✅ Export segment images as PNG
10. ✅ Save/load workspace projects
11. ✅ Pinch-to-zoom and pan
12. ✅ Apple Pencil drawing support
13. ✅ OCR text extraction (via Vision framework)
14. ✅ Touch-optimized UI
15. ✅ Dark mode support

### What Will Work DIFFERENTLY ⚠️

| Desktop Feature | iPad Adaptation |
|-----------------|-----------------|
| Keyboard shortcuts | Toolbar buttons + iPad keyboard shortcuts |
| Right-click menus | Long-press context menus |
| File browser dialog | iOS document picker |
| Multi-window editing | Tab-based navigation |
| Drag files from desktop | Share sheet / AirDrop |
| Mouse hover tooltips | Tap-and-hold hints |
| Window resizing | iPad split-view support |

### What Will NOT Work on iPad ❌

1. ❌ **Tesseract OCR** - pytesseract cannot run on iOS; must use Apple Vision framework or cloud API
2. ❌ **PyMuPDF (fitz)** - Not available on iOS; must use iOS PDFKit via PyObjC
3. ❌ **tkinter GUI** - Entire UI must be rewritten using Pyto/Pythonista UI framework
4. ❌ **cv2.floodFill()** - May not work in opencv-python-headless; need PIL fallback
5. ❌ **Direct filesystem browsing** - iOS sandboxing requires document picker
6. ❌ **Background processing** - iOS limits background execution time
7. ❌ **Multi-window editing** - iPadOS doesn't support floating windows like tkinter Toplevel
8. ❌ **System file dialogs** - tkinter.filedialog not available; use iOS document picker
9. ❌ **Custom themes** - tkinter ttk themes won't work; use iOS native styling
10. ❌ **Keyboard shortcuts** - Global keyboard shortcuts not available; use toolbar buttons

---

## Estimated Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Foundation | 1 week | Week 1 |
| Phase 2: Core Canvas | 1.5 weeks | Week 2-3 |
| Phase 3: Import | 1 week | Week 3-4 |
| Phase 4: Segmentation UI | 1.5 weeks | Week 4-5 |
| Phase 5: OCR | 1 week | Week 5-6 |
| Phase 6: Export & Polish | 1 week | Week 6-7 |
| Phase 7: Testing | 1 week | Week 7-8 |

**Total Estimated Time: 7-8 weeks**

---

## Prerequisites

### Required Software
- iPad with iPadOS 15+ 
- Pyto app ($9.99 from App Store)
- Mac for development/testing (optional but recommended)

### Required Accounts (for cloud OCR fallback)
- Google Cloud Vision API key (optional)
- AWS account for Textract (optional)

### Files Needed
- Original Segmenter source code (currently only .pyc files exist)
- Asset files (icons, default configs)

---

## Next Steps

1. **Recover Source Code**: The original `.py` source files need to be recovered or the app needs to be reverse-engineered from `.pyc` files
2. **Install Pyto**: Set up development environment on iPad
3. **Prototype Canvas**: Build proof-of-concept drawing canvas
4. **Validate PDF Loading**: Test PDF rendering approach
5. **Begin Phase 1**: Start foundation work

---

## Appendix A: Pyto Installation & Setup

```bash
# On iPad:
# 1. Install Pyto from App Store
# 2. Open Pyto, go to Settings > Pip
# 3. Install required packages:

pip install pillow
pip install numpy
pip install PyPDF2
```

## Appendix B: Required Packages

| Package | Version | Purpose |
|---------|---------|---------|
| pillow | 10.0+ | Image processing |
| numpy | 1.24+ | Array operations |
| PyPDF2 | 3.0+ | PDF reading fallback |
| rubicon-objc | 0.4+ | iOS framework bridge |

---

*Document created: December 2024*
*Last updated: December 2024*
*Version: 1.0*

