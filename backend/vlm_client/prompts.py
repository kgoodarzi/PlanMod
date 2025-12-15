"""
Prompt templates for VLM operations.

These prompts are optimized for analyzing technical drawings,
particularly model aircraft plans.
"""

SEGMENT_REGIONS_PROMPT = """Analyze this technical drawing and identify all distinct regions.

For each region, determine:
1. The type of view (top view, side view, front view, section view, detail view, title block, parts list, etc.)
2. The approximate bounding box as percentages of the image dimensions
3. A brief description of what the region shows
4. Your confidence in the identification (0.0 to 1.0)

This appears to be a model aircraft or engineering drawing. Look for:
- Orthographic projections (top, side, front views)
- Detail views showing enlarged areas
- Section views showing internal structure
- Title blocks with project information
- Parts lists or schedules
- Individual component drawings (ribs, formers, etc.)

Respond with a JSON object containing a "regions" array. Each region should have:
- label: A descriptive name (e.g., "Fuselage Side View", "Wing Top View")
- type: The view type (top_view, side_view, front_view, section, detail, title_block, parts_list, component)
- x_percent: X position of top-left corner as percentage (0-100)
- y_percent: Y position of top-left corner as percentage (0-100)
- width_percent: Width as percentage (0-100)
- height_percent: Height as percentage (0-100)
- confidence: Your confidence (0.0-1.0)
- description: Brief description of the region's content"""


CLASSIFY_COMPONENT_PROMPT = """Analyze this component from a technical drawing.

Context: {context}

Identify:
1. The component type (rib, former, bulkhead, spar, stringer, skin, fastener, hinge, motor mount, etc.)
2. The likely material (balsa, plywood, hardwood, carbon fiber, aluminum, etc.)
3. Any visible dimensions or specifications
4. A suggested name/ID for this component
5. Alternative interpretations if the identification is uncertain

For model aircraft components, common types include:
- Ribs: Airfoil-shaped parts that define wing cross-section
- Formers: Cross-section shapes for fuselage
- Bulkheads: Structural dividers in fuselage
- Spars: Longitudinal structural members
- Stringers/Longerons: Smaller longitudinal members
- Doublers: Reinforcement pieces

Respond with a JSON object containing:
- component_type: The identified type
- confidence: Your confidence (0.0-1.0)
- description: What you observe
- suggested_name: A name like "RIB_1" or "FORMER_F3"
- material: Likely material
- dimensions: Object with width, height, thickness if visible
- alternatives: Array of alternative classifications"""


EXTRACT_ANNOTATIONS_PROMPT = """Extract all text annotations from this technical drawing.

Look for:
1. Dimensions (measurements with units like inches, mm, etc.)
2. Part labels/IDs (like "RIB 1", "F3", "SPAR A")
3. Material notes (like "1/8 BALSA", "3mm PLY")
4. Scale indicators
5. Title block information
6. Assembly notes and instructions
7. Reference marks and symbols

For each annotation found, provide:
- text: The exact text content
- type: One of (dimension, label, material_note, scale, title, instruction, reference)
- x_percent: Approximate X position as percentage (0-100)
- y_percent: Approximate Y position as percentage (0-100)
- value: Numeric value if this is a dimension
- unit: Unit of measurement if applicable (in, mm, cm, etc.)

Respond with a JSON object containing an "annotations" array."""


DESCRIBE_DRAWING_PROMPT = """Provide a high-level description of this technical drawing.

Analyze the overall content and identify:
1. What is being depicted (aircraft, component, assembly, etc.)
2. The type of drawing (plan sheet, detail drawing, assembly drawing)
3. The main views present
4. Major components visible
5. Any scale information
6. Notable features or details

This appears to be a model aircraft plan. Consider:
- Is this a complete aircraft or a component (wing, fuselage, tail)?
- What construction method is shown (built-up, sheet, foam)?
- What size/scale is the model?
- Are there any special features (retractable gear, flaps, etc.)?

Respond with a JSON object containing:
- title: Apparent title or subject
- description: Overall description
- drawing_type: Type of drawing (plan_sheet, detail, assembly, parts)
- subject: What is depicted (e.g., "RC trainer aircraft", "wing panel")
- views_identified: Array of view types found
- main_components: Array of major components visible
- scale: Scale if identifiable (e.g., "full size", "1:4")
- notes: Any other notable observations"""


GROUP_VIEWS_PROMPT = """Analyze this drawing and group related components by their views.

For a model aircraft, typical groupings would be:
- Side view components: fuselage side, vertical stabilizer, wing root profile
- Top view components: wing planform, horizontal stabilizer planform
- Front view components: fuselage cross-sections, wing dihedral

For each group identified, provide:
1. The view type (side, top, front)
2. All components that belong to this view
3. How the components relate to each other
4. The spatial arrangement

Also identify any components that appear in multiple views or serve as references between views.

Respond with a JSON object containing:
- view_groups: Array of view group objects, each with:
  - view_type: side, top, front, or other
  - components: Array of component descriptions
  - relationships: How components in this view relate
- cross_references: Components that appear in multiple views
- assembly_sequence: Suggested order for assembly if apparent"""


IDENTIFY_MATERIALS_PROMPT = """Analyze this drawing to identify materials and stock sizes.

Look for:
1. Material callouts in annotations (e.g., "1/8 BALSA", "3mm PLY", "SPRUCE")
2. Standard stock sizes visible
3. Material symbols or hatching patterns
4. Assembly notes mentioning materials

Common materials in model aircraft:
- Balsa wood (various grades and sizes)
- Plywood (birch, lite-ply)
- Hardwood (spruce, bass)
- Carbon fiber/fiberglass
- Foam (EPP, EPS, Depron)
- Covering (tissue, film, fabric)

For each material identified:
- material_type: Base material
- specification: Size or grade (e.g., "1/8 x 1/4", "3mm", "medium grain")
- usage: What it's used for
- quantity_hint: Rough quantity if determinable
- location: Where on the drawing it's referenced

Respond with a JSON object containing:
- materials: Array of material specifications
- stock_list: Suggested materials to purchase
- notes: Additional observations about materials"""


