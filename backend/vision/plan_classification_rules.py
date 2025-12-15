"""
Model Aircraft Plan Classification Rules

Based on expert analysis of Peter Rake's Aeronca Defender plan
and general model aircraft construction conventions.

These rules encode domain knowledge for VLM prompts and CV classification.
"""

# =============================================================================
# COMPONENT CATEGORIES AND COLORS
# =============================================================================

CATEGORIES = {
    # === FUSELAGE COMPONENTS ===
    "former": {
        "color_rgb": (255, 0, 0),       # Red
        "color_bgr": (0, 0, 255),
        "description": "Fuselage cross-section bulkheads (F1, F2, F3, etc.)",
        "materials": ["balsa", "ply", "lite-ply"],
        "view_appearance": {
            "side_view": "vertical LINE",
            "template": "filled SHAPE",
        },
    },
    "fuselage_side": {
        "color_rgb": (0, 0, 255),       # Blue
        "color_bgr": (255, 0, 0),
        "description": "Fuselage side panels and reinforcements (FS1, FS2, FS3)",
        "materials": ["balsa sheet", "ply"],
    },
    "spar": {
        "color_rgb": (0, 0, 255),       # Blue
        "color_bgr": (255, 0, 0),
        "description": "Structural spars - longitudinal members (fuselage and wing)",
        "materials": ["balsa strip", "spruce", "bass"],
        "view_appearance": {
            "side_view": "horizontal/curved LINE",
            "wing_view": "outline LINES (leading/trailing edge)",
        },
    },
    
    # === WING COMPONENTS ===
    "rib": {
        "color_rgb": (255, 0, 0),       # Red (same as formers - cross-sections)
        "color_bgr": (0, 0, 255),
        "description": "Wing/tail ribs - airfoil cross-sections (R1, R2, R3, WT)",
        "materials": ["balsa sheet", "lite-ply"],
        "view_appearance": {
            "wing_planform": "perpendicular LINES inside wing outline",
            "template": "airfoil SHAPES with lightening holes",
        },
    },
    "strengthening": {
        "color_rgb": (0, 255, 255),     # Cyan
        "color_bgr": (255, 255, 0),
        "description": "Strengthening structures - lightening holes with reinforcement",
        "materials": ["balsa sheet", "ply"],
        "view_appearance": {
            "wing_planform": "oval shapes inside wing",
            "template": "cutout SHAPES",
        },
    },
    "wing_planform": {
        "color_rgb": (0, 255, 0),       # Green
        "color_bgr": (0, 255, 0),
        "description": "Wing plan view region indicator (LEFT WING, RIGHT WING)",
        "notes": "Green rectangle indicating wing top view region",
    },
    "elevator_planform": {
        "color_rgb": (0, 255, 0),       # Green
        "color_bgr": (0, 255, 0),
        "description": "Elevator plan view region indicator",
        "notes": "Green rectangle indicating elevator top view region",
    },
    
    # === TAIL COMPONENTS ===
    "tail": {
        "color_rgb": (255, 0, 255),     # Magenta
        "color_bgr": (255, 0, 255),
        "description": "Tail surfaces - stabilizer, fin, rudder (TS, T1-T5)",
        "materials": ["balsa sheet", "balsa strip"],
    },
    
    # === OTHER COMPONENTS ===
    "landing_gear": {
        "color_rgb": (255, 180, 200),   # Pink
        "color_bgr": (200, 180, 255),
        "description": "Undercarriage, wheels, legs, mounts (UC)",
        "materials": ["wire", "ply", "hardwood"],
    },
    "motor": {
        "color_rgb": (255, 165, 0),     # Orange
        "color_bgr": (0, 165, 255),
        "description": "Motor/engine mount and related (M)",
        "materials": ["ply", "hardwood", "aluminum"],
    },
    "misc": {
        "color_rgb": (128, 128, 128),   # Gray
        "color_bgr": (128, 128, 128),
        "description": "Other parts - nose block, dihedral guides, battery mount (B, N)",
        "materials": ["balsa block", "ply"],
        "examples": ["root rib angle guide", "dihedral jig", "nose block"],
    },
}


# =============================================================================
# VIEW CONTEXT RULES
# =============================================================================

VIEW_RULES = {
    "side_view": {
        "description": "Side profile view of assembled aircraft",
        "location": "Usually center-left of plan",
        "components": {
            "formers": {
                "appearance": "VERTICAL LINES",
                "color": "red",
                "notes": "F1-F7 shown as vertical cuts through fuselage profile",
            },
            "spars": {
                "appearance": "HORIZONTAL or CURVED LINES",
                "color": "blue",
                "notes": "Longerons and structural members, can follow fuselage curve",
            },
            "fuselage_sides": {
                "appearance": "FILLED SURFACE (when reinforced)",
                "color": "blue",
                "notes": "FS1, FS2, FS3 shown as surfaces when side is sheeted/reinforced",
            },
            "landing_gear": {
                "appearance": "LINES and SHAPES",
                "color": "pink",
                "notes": "UC mount, wire legs, wheels visible in profile",
            },
            "motor": {
                "appearance": "SHAPE at nose",
                "color": "orange",
                "notes": "Motor mount, cylinders, cowling at front of fuselage",
            },
            "nose": {
                "appearance": "SHAPE",
                "color": "gray",
                "notes": "Nose block, often carved/shaped balsa",
            },
            "wing_former": {
                "appearance": "SURFACE (top of fuselage)",
                "color": "blue",
                "notes": "Center wing section/former, often integrated with FS1 top",
            },
            "tail": {
                "appearance": "OUTLINE",
                "color": "magenta",
                "notes": "Tail surfaces shown in profile",
            },
        },
    },
    "top_view": {
        "description": "Plan view from above (fuselage top)",
        "location": "Usually shown integrated with side view or separate",
        "components": {
            "spars": {
                "appearance": "PARALLEL LINES on both sides",
                "color": "blue",
                "notes": "Same spars from side view seen from above - contour the fuselage top",
            },
            "formers": {
                "appearance": "LINES perpendicular to spars",
                "color": "red",
                "notes": "Former positions shown as cross-lines inside spar contour",
            },
            "motor_plate": {
                "appearance": "SHAPE at nose area",
                "color": "gray",
                "notes": "M plate for holding motor/electronics",
            },
            "uc_plate": {
                "appearance": "SHAPE",
                "color": "pink",
                "notes": "UC mounting plate visible from top",
            },
            "tail_section": {
                "appearance": "SHAPE at rear",
                "color": "pink or magenta",
                "notes": "TS or tail section visible in top view",
            },
            "elevator": {
                "appearance": "FILLED SURFACE (if shown)",
                "color": "magenta",
                "notes": "Elevator planform - not always shown",
            },
            "wing_section": {
                "appearance": "PARTIAL WING (if shown)",
                "color": "green",
                "notes": "Wing root or center section - not always shown",
            },
        },
    },
    "wing_view": {
        "description": "Wing plan view showing structure (usually page 2)",
        "location": "Page 2 - typically shows left wing, right wing, and elevator",
        "regions": {
            "left_wing": "Wing planform view - left panel",
            "right_wing": "Wing planform view - right/center panel", 
            "elevator": "Elevator planform view - usually smaller box",
        },
        "components_inside_planform": {
            "ribs": {
                "appearance": "RED LINES (perpendicular to spars)",
                "color": "red",
                "notes": "Rib positions shown as lines INSIDE wing planform (R3 positions)",
            },
            "spars": {
                "appearance": "BLUE LINES (leading edge, trailing edge, internal)",
                "color": "blue",
                "notes": "Form the wing outline and internal structure",
            },
            "strengthening": {
                "appearance": "CYAN shapes (lightening holes with structure)",
                "color": "cyan",
                "notes": "Oval cutouts with surrounding material for rigidity",
            },
            "strut_positions": {
                "appearance": "MARKERS labeled 'strut pos.'",
                "color": "misc",
                "notes": "Wing strut attachment points",
            },
        },
        "components_outside_planform": {
            "rib_templates": {
                "appearance": "RED SHAPES (R1, R2, R3, airfoil profiles)",
                "color": "red",
                "notes": "Rib cutout templates - outside the wing plan view",
            },
            "wing_tip": {
                "appearance": "BLUE SHAPE (WT)",
                "color": "blue",
                "notes": "Wing tip block template",
            },
            "strengthening_templates": {
                "appearance": "CYAN SHAPES",
                "color": "cyan",
                "notes": "Strengthening piece cutout templates",
            },
            "dihedral_guide": {
                "appearance": "GRAY SHAPE",
                "color": "gray",
                "notes": "'root rib angle guide' - used to set correct dihedral angle",
            },
        },
    },
    "elevator_view": {
        "description": "Elevator/horizontal stabilizer plan view",
        "location": "Usually in corner of wing page or with tail components",
        "components_inside_planform": {
            "ribs": {
                "appearance": "RED LINES",
                "color": "red",
                "notes": "Elevator rib positions",
            },
            "spars": {
                "appearance": "BLUE LINES (outline)",
                "color": "blue",
                "notes": "Elevator leading/trailing edge structure",
            },
        },
        "components_outside_planform": {
            "tail_templates": {
                "appearance": "BLUE/RED SHAPES (T3, T4, T5, TS)",
                "color": "blue or magenta",
                "notes": "Tail component cutout templates",
            },
        },
    },
    "template_view": {
        "description": "Individual cut-out templates for parts (SURFACES to be filled)",
        "location": "Usually right column, margins, or separate sheets by material",
        "notes": "All templates are CUTOUTS - closed shapes representing parts to cut from sheet material",
        "components": {
            "formers": {
                "appearance": "CLOSED SHAPES - FILL SURFACE RED",
                "color": "red",
                "notes": "Former templates (F1-F7) showing cross-section profiles to cut",
            },
            "fuselage_sides": {
                "appearance": "CLOSED SHAPES - FILL SURFACE BLUE",
                "color": "blue",
                "notes": "FS1, FS2, FS3 fuselage side sheet templates",
            },
            "landing_gear_mount": {
                "appearance": "CLOSED SHAPES - FILL SURFACE PINK",
                "color": "pink",
                "notes": "UC mount plate templates",
            },
            "tail_templates": {
                "appearance": "CLOSED SHAPES - FILL SURFACE MAGENTA",
                "color": "magenta",
                "notes": "T1, T2, T3, T4, T5, TS tail component templates",
            },
            "wing_ribs": {
                "appearance": "AIRFOIL SHAPES - FILL SURFACE GREEN",
                "color": "green",
                "notes": "R1, R2, R3, WT wing rib templates with lightening holes",
            },
            "misc_parts": {
                "appearance": "CLOSED SHAPES - FILL SURFACE GRAY",
                "color": "gray",
                "notes": "B (bottom), M (motor plate), nose block, horn, etc.",
            },
        },
        "organization": {
            "by_material": "Templates often grouped by material thickness",
            "examples": [
                "1/16 balsa sheet",
                "1/32 balsa sheet", 
                "1/32 ply sheet",
                "1/8 balsa sheet",
            ],
        },
    },
}


# =============================================================================
# SUMMARY: KEY CLASSIFICATION PRINCIPLES
# =============================================================================

CLASSIFICATION_PRINCIPLES = """
## Model Aircraft Plan Classification Principles

### 1. SAME PART, DIFFERENT VIEWS
A component appears differently depending on viewing angle:
- **Edge-on (side/top view)**: Appears as a LINE
- **Face-on (template/cutout)**: Appears as a filled SURFACE/SHAPE

Examples:
- Former F3: RED LINE in side view → RED SURFACE in template
- Motor plate M: LINE in side view → GRAY SURFACE in template
- Bottom plate B: LINE in side view → GRAY SURFACE in template

### 2. VIEW TYPES AND THEIR CONTENTS

**SIDE VIEW (assembly view):**
- Spars = BLUE LINES (horizontal, may curve)
- Formers = RED LINES (vertical cuts)
- Fuselage sides FS = BLUE SURFACES (if sheeted/reinforced)
- Landing gear = PINK shapes and lines
- Motor = ORANGE at nose
- Nose block = GRAY

**TOP VIEW (plan view of fuselage):**
- Spars = BLUE LINES (parallel, both sides)
- Formers = RED LINES (perpendicular to spars)
- Plates (M, UC, TS) = GRAY/PINK shapes inside spar contour

**TEMPLATE/CUTOUT VIEW:**
- ALL parts shown as FILLED SURFACES
- Color by category (Red=formers, Blue=FS, Pink=UC, etc.)
- Often organized by material (1/16 balsa, 1/32 ply, etc.)

### 3. WING STRUCTURE (usually page 2)
- Wing planform outline = GREEN
- Wing ribs (R1, R2, R3) = GREEN airfoil shapes
- Spars = BLUE lines through wing
- Wing tip (WT) = GREEN

### 4. TAIL STRUCTURE
- Tail templates (T1-T5, TS) = MAGENTA
- Often shown both as assembly and cutouts
"""


# =============================================================================
# HEURISTIC RULES FOR CLASSIFICATION
# =============================================================================

CLASSIFICATION_HEURISTICS = [
    {
        "rule": "former_as_line",
        "condition": "Component labeled F# appears as vertical line in side view",
        "action": "Color the LINE red (not the area)",
        "explanation": "Formers are cross-sections - in side view we see them edge-on",
    },
    {
        "rule": "former_as_shape",
        "condition": "Component labeled F# appears as closed shape (template area)",
        "action": "FILL the shape red",
        "explanation": "In template view, formers show their full cross-section profile",
    },
    {
        "rule": "spar_as_line",
        "condition": "Horizontal or curved structural line in side/top view",
        "action": "Color the LINE blue",
        "explanation": "Spars are longitudinal members - appear as lines in most views",
    },
    {
        "rule": "fuselage_side_reinforced",
        "condition": "FS# parts shown as filled surface in side view",
        "action": "FILL the surface blue",
        "explanation": "When fuselage has motor/reinforcement, sides are sheeted",
    },
    {
        "rule": "motor_misc_dual_view",
        "condition": "M or B appears as line in side view, shape in template",
        "action": "Color LINE in side view, FILL shape in template",
        "explanation": "These parts have thickness - line edge-on, shape head-on",
    },
    {
        "rule": "wing_center_section",
        "condition": "Top portion of FS1 at wing saddle area",
        "action": "Color blue (part of structural system)",
        "explanation": "Center wing former often integrated with fuselage side top",
    },
    {
        "rule": "label_near_component",
        "condition": "Text label (F1, FS2, UC, etc.) near a shape/line",
        "action": "Associate label with nearest matching geometry",
        "explanation": "Labels are placed close to but not exactly on components",
    },
    {
        "rule": "hatching_indicates_section",
        "condition": "Area filled with cross-hatching pattern",
        "action": "Hatched areas are cut sections or solid parts",
        "explanation": "Hatching shows material that would be cut through",
    },
]


# =============================================================================
# VLM PROMPT TEMPLATE
# =============================================================================

VLM_CLASSIFICATION_PROMPT = """
Analyze this model aircraft construction plan drawing.

## DRAWING CONVENTIONS:
This plan shows the same aircraft from multiple views:

### SIDE VIEW (main assembly, usually center-left):
Components appear as:
- FORMERS (F1-F7): Vertical RED LINES through fuselage profile
- SPARS/LONGERONS: Horizontal or curved BLUE LINES (structural sticks)
- FUSELAGE SIDES (FS1-FS3): BLUE FILLED SURFACES (when sheeted/reinforced)
- LANDING GEAR (UC): PINK lines and shapes (wheels, wire legs)
- MOTOR (M): ORANGE shape at nose
- NOSE BLOCK: GRAY misc part
- WING FORMER: BLUE surface at top of fuselage (center section)
- TAIL: MAGENTA outline

### TEMPLATE VIEW (individual cut pieces, usually right column):
Components appear as CLOSED SHAPES to be cut out:
- FORMERS (F#): RED filled shapes (cross-section profiles)
- FUSELAGE SIDES (FS#): BLUE filled shapes
- LANDING GEAR MOUNT (UC): PINK filled shape
- MISC PARTS (B, etc.): GRAY filled shapes

## KEY RULES:
1. Same part appears DIFFERENTLY in different views:
   - Former as LINE (side view) vs SHAPE (template)
   - M and B as LINE (side) vs SHAPE (template)
2. Color BOTH lines AND shapes appropriately
3. Labels are NEAR components, not exactly ON them
4. Hatched areas indicate solid/cut material

## TASK:
Identify ALL components with:
- Part ID (F1, FS2, UC, M, B, TS, etc.)
- Category (former, fuselage_side, spar, landing_gear, motor, tail, wing, misc)
- Geometry type (line, shape, or both)
- Bounding box (x_pct, y_pct, w_pct, h_pct as % of image)
- View context (side_view, top_view, or template)

Return as JSON array.
"""


# =============================================================================
# DETECTION PIPELINE
# =============================================================================

def get_detection_pipeline():
    """
    Return recommended detection pipeline steps.
    
    Combines VLM semantic understanding with CV precise geometry.
    """
    return [
        {
            "step": 1,
            "name": "Line Detection",
            "method": "Hough Transform",
            "purpose": "Detect structural lines (formers, spars)",
            "params": {
                "vertical_tolerance": 15,  # degrees from vertical = former
                "horizontal_tolerance": 15,  # degrees from horizontal = spar
            },
        },
        {
            "step": 2,
            "name": "Contour Detection", 
            "method": "findContours",
            "purpose": "Detect closed shapes (templates, filled areas)",
            "params": {
                "min_area": 500,
                "max_area_ratio": 0.3,
            },
        },
        {
            "step": 3,
            "name": "Region Segmentation",
            "method": "VLM or manual",
            "purpose": "Identify view regions (side, top, template)",
            "params": {},
        },
        {
            "step": 4,
            "name": "Label Detection",
            "method": "OCR (Textract or Tesseract)",
            "purpose": "Find component labels (F1, FS2, UC, etc.)",
            "params": {},
        },
        {
            "step": 5,
            "name": "Label-Geometry Association",
            "method": "Proximity matching",
            "purpose": "Match labels to nearest geometry",
            "params": {
                "max_distance": 50,  # pixels
            },
        },
        {
            "step": 6,
            "name": "Category Classification",
            "method": "Rule-based + VLM",
            "purpose": "Assign category based on label pattern and context",
            "params": {},
        },
        {
            "step": 7,
            "name": "Colorization",
            "method": "Flood fill + line coloring",
            "purpose": "Apply category colors to geometry",
            "params": {},
        },
    ]


# =============================================================================
# LABEL PATTERNS
# =============================================================================

LABEL_PATTERNS = {
    r"F\d+[A-Z]?": "former",           # F1, F2, F3A, F5A
    r"FS\d+": "fuselage_side",          # FS1, FS2, FS3
    r"TS\d*": "tail",                   # TS, TS1, TS2
    r"T\d+": "tail",                    # T1, T2
    r"UC|U/C|u/c": "landing_gear",      # UC, U/C
    r"M\d*": "motor",                   # M, M1
    r"W\d+|R\d+": "wing",               # W1, R1 (wing ribs)
    r"B\d*": "misc",                    # B, B1 (bottom/misc)
    r"N\d*": "misc",                    # N (nose)
}

