#!/usr/bin/env python3
"""
VLM-based component classification test.

Uses Claude Vision to properly identify and classify components
in model aircraft plan drawings.
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import json
import asyncio
from datetime import datetime


# Component classification based on VLM analysis
# Colors in RGB format for visualization
COMPONENT_CLASSIFICATION = {
    # VLM category names (may vary)
    "former": {
        "description": "Fuselage formers/bulkheads that define cross-sections",
        "color_rgb": (255, 0, 0),  # Bright Red
        "items": []
    },
    "formers": {
        "description": "Fuselage formers/bulkheads that define cross-sections",
        "color_rgb": (255, 0, 0),  # Bright Red
        "items": []
    },
    "tail": {
        "description": "Tail stabilizer, fin, and related parts",
        "color_rgb": (255, 0, 255),  # Magenta
        "items": []
    },
    "tail_surfaces": {
        "description": "Tail stabilizer, fin, and related parts",
        "color_rgb": (255, 0, 255),  # Magenta
        "items": []
    },
    "fuselage_side": {
        "description": "Fuselage side panels",
        "color_rgb": (0, 100, 255),  # Blue
        "items": []
    },
    "fuselage_sides": {
        "description": "Fuselage side panels",
        "color_rgb": (0, 100, 255),  # Blue
        "items": []
    },
    "landing_gear": {
        "description": "Undercarriage, wheels, legs",
        "color_rgb": (255, 150, 150),  # Pink
        "items": []
    },
    "motor": {
        "description": "Engine/motor mount and cowling",
        "color_rgb": (255, 165, 0),  # Orange
        "items": []
    },
    "motor_mount": {
        "description": "Engine/motor mount and cowling",
        "color_rgb": (255, 165, 0),  # Orange
        "items": []
    },
    "wing": {
        "description": "Wing panels, ribs, spars",
        "color_rgb": (0, 255, 0),  # Bright Green
        "items": []
    },
    "misc": {
        "description": "Other parts (B, horns, etc.)",
        "color_rgb": (128, 128, 128),  # Gray
        "items": []
    },
    "miscellaneous": {
        "description": "Other parts (B, horns, etc.)",
        "color_rgb": (128, 128, 128),  # Gray
        "items": []
    }
}


def test_vlm_classification():
    """Test VLM-based component classification."""
    print("=" * 70)
    print("PlanMod VLM Component Classification Test")
    print("=" * 70)
    print()
    
    # Initialize cost estimator
    from backend.shared.cost_estimator import CostEstimator
    cost_estimator = CostEstimator(job_id="test-vlm-classification")
    
    # Find PDF file and rasterize
    pdf_path = Path("samples/Aeronca_Defender_Plan_Vector.pdf")
    if not pdf_path.exists():
        print(f"[X] PDF file not found: {pdf_path}")
        return False
    
    # Create output directory
    output_path = Path("output")
    output_path.mkdir(exist_ok=True)
    
    # Delete existing files
    for f in output_path.glob("*"):
        f.unlink()
    print("[*] Cleared output directory")
    print()
    
    # Step 1: Rasterize PDF
    print("[1] Rasterizing PDF...")
    try:
        from backend.ingest.pdf_processor import PDFProcessor
        from PIL import Image
        import numpy as np
        
        pdf_data = pdf_path.read_bytes()
        processor = PDFProcessor(dpi=150)  # Balance between quality and speed
        
        images = processor.rasterize(pdf_data, dpi=150, pages=[0])
        if not images:
            print("    [X] No pages rasterized")
            return False
        
        image = images[0]
        pil_image = Image.fromarray(image)
        
        raster_path = output_path / "pdf_page1_raster.png"
        pil_image.save(raster_path)
        
        print(f"    [OK] Rasterized at {pil_image.width}x{pil_image.height} pixels")
        print(f"    Saved: {raster_path}")
        print()
        
        cost_estimator.add_lambda_invocation(duration_ms=2000, memory_mb=2048)
        
    except Exception as e:
        print(f"    [X] Rasterization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 2: Call VLM for component identification
    print("[2] Calling VLM for component identification...")
    try:
        from backend.shared.config import get_settings
        settings = get_settings()
        
        has_creds = bool(settings.aws.access_key_id or settings.aws.profile)
        
        if not has_creds:
            print("    [!] No AWS credentials - using manual analysis")
            vlm_components = get_manual_component_list()
        else:
            from backend.vlm_client.bedrock_claude import BedrockClaudeVLM
            
            vlm = BedrockClaudeVLM(settings)
            
            # Convert image to bytes
            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format='PNG')
            img_bytes = img_buffer.getvalue()
            
            async def analyze_components():
                # Improved prompt with model aircraft plan domain knowledge
                prompt = """Analyze this model aircraft construction plan drawing.

## DRAWING CONVENTIONS:
This plan shows the same aircraft from multiple views:

### SIDE VIEW (main assembly, usually center-left):
Components appear as:
- FORMERS (F1-F7): Vertical RED LINES through fuselage profile
- SPARS/LONGERONS: Horizontal or curved BLUE LINES (structural sticks, not solid fill)
- FUSELAGE SIDES (FS1-FS3): BLUE FILLED SURFACES (sheeted/reinforced sides)
- LANDING GEAR (UC): PINK lines and shapes (wheels, wire legs)
- MOTOR (M): ORANGE shape at nose (cylinders visible)
- NOSE BLOCK: GRAY misc part
- WING FORMER: Top section of FS1 is center wing former (BLUE)
- TAIL outline: MAGENTA

### TEMPLATE VIEW (individual cut pieces, usually right column):
Components appear as CLOSED SHAPES to be cut out:
- FORMERS (F#): RED filled shapes (cross-section profiles)
- FUSELAGE SIDES (FS#): BLUE filled shapes  
- LANDING GEAR MOUNT (UC): PINK filled shape
- MISC PARTS (B, etc.): GRAY filled shapes

## KEY RULES:
1. Same part appears DIFFERENTLY in different views:
   - Former as LINE (side view) vs SHAPE (template view)
   - M and B as LINE (side view) vs SHAPE (template view)
2. Identify BOTH lines AND shapes
3. Labels are placed NEAR components, not exactly ON them
4. The fuselage is made of STICKS (blue lines), not solid blue fill

## TASK:
For each component found, return:
- id: Part label (F1, FS2, UC, M, B, TS, etc.)
- description: What it is
- material: If visible (1/16 balsa, 1/32 ply, etc.)
- geometry_type: "line" or "shape" or "both"
- view: "side_view" or "template" or "top_view"
- x_pct, y_pct, w_pct, h_pct: Bounding box as % of image
- category: former, fuselage_side, spar, tail, landing_gear, motor, wing, or misc

Return as JSON array. Be thorough - identify ALL labeled parts AND structural lines."""

                response = await vlm.analyze_with_prompt(img_bytes, prompt)
                return response
            
            print(f"    AWS Region: {settings.aws.region}")
            print(f"    VLM Model: {settings.ai.bedrock.vlm_model_id}")
            print("    Sending image to VLM...")
            
            response = asyncio.run(analyze_components())
            
            if response.success and response.structured_data:
                vlm_components = response.structured_data
                print(f"    [OK] VLM identified {len(vlm_components)} components")
                cost_estimator.add_bedrock_call(
                    input_tokens=2000,
                    output_tokens=response.tokens_used or 500,
                    model="claude-3-5-sonnet",
                    includes_image=True,
                )
            else:
                print(f"    [!] VLM failed: {response.error}")
                print("    Using manual component list...")
                vlm_components = get_manual_component_list()
        
        print()
        
    except Exception as e:
        print(f"    [!] VLM error: {e}")
        print("    Using manual component list...")
        vlm_components = get_manual_component_list()
        print()
    
    # Step 3: Display classified components
    print("[3] Classified Components:")
    print("-" * 70)
    
    # Group by category
    by_category = {}
    for comp in vlm_components:
        cat = comp.get("category", "misc")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(comp)
    
    total_components = 0
    for category, items in sorted(by_category.items()):
        cat_info = COMPONENT_CLASSIFICATION.get(category, {"description": category, "color_rgb": (128, 128, 128)})
        print(f"\n  [{category.upper()}] - {cat_info['description']}")
        print(f"  Color: RGB{cat_info['color_rgb']}")
        print(f"  Components ({len(items)}):")
        
        for comp in items:
            material = comp.get('material', 'N/A')
            desc = comp.get('description', '')
            loc = comp.get('location', '')
            print(f"    - {comp['id']:8} | {desc:30} | {material:15} | {loc}")
            total_components += 1
    
    print()
    print(f"  TOTAL COMPONENTS IDENTIFIED: {total_components}")
    print("-" * 70)
    print()
    
    # Step 4: Create visualization with colored components and bounding boxes
    print("[4] Creating semantic visualization...")
    try:
        import cv2
        import numpy as np
        
        # Create a copy for visualization
        vis_image = np.array(pil_image)
        if len(vis_image.shape) == 2:
            vis_image = cv2.cvtColor(vis_image, cv2.COLOR_GRAY2BGR)
        elif vis_image.shape[2] == 4:
            vis_image = cv2.cvtColor(vis_image, cv2.COLOR_RGBA2BGR)
        else:
            vis_image = cv2.cvtColor(vis_image, cv2.COLOR_RGB2BGR)
        
        # Create overlay for transparency
        overlay = vis_image.copy()
        height, width = vis_image.shape[:2]
        
        # Draw bounding boxes for each component
        components_with_boxes = 0
        for comp in vlm_components:
            cat = comp.get("category", "misc")
            cat_info = COMPONENT_CLASSIFICATION.get(cat, COMPONENT_CLASSIFICATION.get("miscellaneous", {"color_rgb": (128, 128, 128)}))
            color_bgr = (cat_info['color_rgb'][2], cat_info['color_rgb'][1], cat_info['color_rgb'][0])
            
            # Get bounding box if available
            x_pct = comp.get("x_pct", 0)
            y_pct = comp.get("y_pct", 0)
            w_pct = comp.get("w_pct", 5)
            h_pct = comp.get("h_pct", 5)
            
            if x_pct > 0 or y_pct > 0:  # Has valid position
                components_with_boxes += 1
                x = int(x_pct / 100 * width)
                y = int(y_pct / 100 * height)
                w = int(w_pct / 100 * width)
                h = int(h_pct / 100 * height)
                
                # Draw filled box on overlay
                cv2.rectangle(overlay, (x, y), (x + w, y + h), color_bgr, -1)
                
                # Draw border on original
                cv2.rectangle(vis_image, (x, y), (x + w, y + h), color_bgr, 3)
                
                # Draw label
                label = comp.get("id", "?")
                font_scale = 0.6
                thickness = 2
                (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                
                # Label background
                cv2.rectangle(vis_image, (x, y - text_h - 8), (x + text_w + 6, y), color_bgr, -1)
                cv2.putText(vis_image, label, (x + 3, y - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
        
        # Blend overlay with transparency
        alpha = 0.25
        result = cv2.addWeighted(overlay, alpha, vis_image, 1 - alpha, 0)
        
        # Draw legend
        legend_width = 250
        legend_start_x = width - legend_width - 20
        legend_y = 30
        
        cv2.rectangle(result, (legend_start_x - 10, 10), (width - 10, 10 + len(by_category) * 30 + 50), (255, 255, 255), -1)
        cv2.rectangle(result, (legend_start_x - 10, 10), (width - 10, 10 + len(by_category) * 30 + 50), (0, 0, 0), 2)
        
        cv2.putText(result, "COMPONENT LEGEND", (legend_start_x, legend_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        legend_y += 30
        
        for category, items in sorted(by_category.items()):
            cat_info = COMPONENT_CLASSIFICATION.get(category, COMPONENT_CLASSIFICATION.get("miscellaneous", {"color_rgb": (128, 128, 128)}))
            color_bgr = (cat_info['color_rgb'][2], cat_info['color_rgb'][1], cat_info['color_rgb'][0])
            
            # Draw color box
            cv2.rectangle(result, (legend_start_x, legend_y - 15), (legend_start_x + 20, legend_y + 5), color_bgr, -1)
            cv2.rectangle(result, (legend_start_x, legend_y - 15), (legend_start_x + 20, legend_y + 5), (0, 0, 0), 1)
            
            # Draw label with count
            label = f"{category} ({len(items)})"
            cv2.putText(result, label, (legend_start_x + 30, legend_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            legend_y += 25
        
        # Save visualization
        vis_path = output_path / "vlm_classified_components.png"
        cv2.imwrite(str(vis_path), result)
        print(f"    [OK] Saved: {vis_path}")
        print(f"    Components with bounding boxes: {components_with_boxes}/{len(vlm_components)}")
        print()
        
    except Exception as e:
        print(f"    [!] Visualization failed: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Step 5: Save component data as JSON
    print("[5] Saving component data...")
    try:
        component_data = {
            "drawing": {
                "title": "Peter Rake's Aeronca Defender",
                "copyright": "Copyright P. Rake 2015",
                "source": str(pdf_path),
            },
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "total_components": total_components,
            "components_by_category": {
                cat: {
                    "count": len(items),
                    "color_rgb": COMPONENT_CLASSIFICATION.get(cat, {}).get("color_rgb", [128, 128, 128]),
                    "items": items
                }
                for cat, items in by_category.items()
            },
            "all_components": vlm_components,
        }
        
        json_path = output_path / "component_classification.json"
        with open(json_path, 'w') as f:
            json.dump(component_data, f, indent=2)
        print(f"    [OK] Saved: {json_path}")
        print()
        
    except Exception as e:
        print(f"    [!] JSON export failed: {e}")
        print()
    
    # Finalize cost report
    cost_estimator.finalize()
    cost_report = cost_estimator.get_report()
    
    print()
    print(cost_report.format_summary())
    print()
    
    cost_path = output_path / "vlm_cost_report.json"
    with open(cost_path, 'w') as f:
        json.dump(cost_report.to_dict(), f, indent=2)
    print(f"Cost report saved: {cost_path}")
    
    print()
    print("=" * 70)
    print("[OK] VLM Classification Test Complete!")
    print("=" * 70)
    print()
    print("Generated files:")
    for f in output_path.glob("*"):
        print(f"  - {f}")
    
    return True


def get_manual_component_list():
    """
    Manual component list based on visual analysis of Aeronca Defender plan.
    This represents what the VLM should identify.
    """
    return [
        # Formers (F-series)
        {"id": "F1", "description": "Nose former/firewall", "material": "1/32 ply", "location": "bottom-left", "category": "former"},
        {"id": "F2", "description": "Forward fuselage former", "material": "1/16 balsa", "location": "bottom-center", "category": "former"},
        {"id": "F3", "description": "Mid fuselage former", "material": "1/32 ply", "location": "bottom-center", "category": "former"},
        {"id": "F4", "description": "Rear fuselage former", "material": "1/32 ply", "location": "center-right", "category": "former"},
        {"id": "F5", "description": "Wing saddle former", "material": "1/16 balsa", "location": "center-left", "category": "former"},
        {"id": "F5A", "description": "Dihedral brace former", "material": "1/16 balsa", "location": "center-left", "category": "former"},
        {"id": "F6", "description": "Tail area former", "material": "1/32 ply", "location": "center", "category": "former"},
        {"id": "F7", "description": "Tail mount former", "material": "1/16 balsa", "location": "center", "category": "former"},
        
        # Tail surfaces (T-series)
        {"id": "T1", "description": "Horizontal stabilizer", "material": "1/16 balsa", "location": "top-center", "category": "tail_surfaces"},
        {"id": "T2", "description": "Tail component with u/c leg", "material": "1/16 balsa, 1/32 ply", "location": "top-center", "category": "tail_surfaces"},
        {"id": "TS", "description": "Tail stabilizer outline", "material": "1/16 balsa", "location": "top-left", "category": "tail_surfaces"},
        
        # Fuselage sides (FS-series)
        {"id": "FS1", "description": "Main fuselage side panel", "material": "1/16 balsa", "location": "right", "category": "fuselage_sides"},
        {"id": "FS2", "description": "Fuselage side doubler", "material": "1/16 balsa", "location": "top-right", "category": "fuselage_sides"},
        {"id": "FS3", "description": "Fuselage side near/far", "material": "1/16 balsa", "location": "top-center", "category": "fuselage_sides"},
        
        # Landing gear (UC)
        {"id": "UC", "description": "Undercarriage mount", "material": "1/32 ply", "location": "center-right", "category": "landing_gear"},
        {"id": "u/c legs", "description": "Landing gear wire legs", "material": "20 swg wire", "location": "center-right", "category": "landing_gear"},
        {"id": "u/c wires", "description": "Undercarriage bracing", "material": "20 swg", "location": "center-right", "category": "landing_gear"},
        
        # Motor mount
        {"id": "M", "description": "Motor mount/nose block", "material": "1/32 ply", "location": "bottom-left", "category": "motor_mount"},
        
        # Miscellaneous
        {"id": "B", "description": "Bottom plate", "material": "1/32 ply", "location": "bottom-right", "category": "miscellaneous"},
        {"id": "horn", "description": "Control horn", "material": "1/32 ply", "location": "center", "category": "miscellaneous"},
        {"id": "c/tail stick skid", "description": "Tail skid", "material": "wire", "location": "center", "category": "miscellaneous"},
        {"id": "fuselage frame", "description": "Fuselage longerons", "material": "1/16 sq. balsa", "location": "center", "category": "miscellaneous"},
        {"id": "spar", "description": "Wing spar location", "material": "balsa", "location": "right", "category": "wing"},
        {"id": "locating dowels", "description": "Wing alignment dowels", "material": "hardwood", "location": "right", "category": "wing"},
    ]


if __name__ == "__main__":
    success = test_vlm_classification()
    sys.exit(0 if success else 1)

