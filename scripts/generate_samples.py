"""Generate synthetic DXF sample files for testing."""

import sys
from pathlib import Path

import ezdxf

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.dxf_parser import DXFParser


def create_wing_dxf(output_path: Path):
    """Create a simple wing planform DXF."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    
    # Wing parameters
    root_chord = 8.0  # inches
    tip_chord = 4.0
    span = 24.0
    rib_spacing = 3.0
    
    # Leading edge
    msp.add_line((0, 0), (span, 0), dxfattribs={"layer": "WING"})
    
    # Trailing edge
    msp.add_line((0, root_chord), (span, tip_chord), dxfattribs={"layer": "WING"})
    
    # Root rib
    msp.add_line((0, 0), (0, root_chord), dxfattribs={"layer": "RIBS"})
    
    # Tip rib
    msp.add_line((span, 0), (span, tip_chord), dxfattribs={"layer": "RIBS"})
    
    # Intermediate ribs
    num_ribs = int(span / rib_spacing)
    for i in range(1, num_ribs):
        x = i * rib_spacing
        chord = root_chord - (root_chord - tip_chord) * (x / span)
        y_le = 0
        y_te = chord
        msp.add_line((x, y_le), (x, y_te), dxfattribs={"layer": "RIBS"})
    
    # Main spar (at 25% chord)
    spar_pos = 0.25
    msp.add_line(
        (0, root_chord * spar_pos),
        (span, tip_chord * spar_pos),
        dxfattribs={"layer": "SPARS"},
    )
    
    # Rear spar (at 70% chord)
    spar_pos = 0.70
    msp.add_line(
        (0, root_chord * spar_pos),
        (span, tip_chord * spar_pos),
        dxfattribs={"layer": "SPARS"},
    )
    
    # Add labels
    msp.add_text("WING PLANFORM", dxfattribs={"layer": "TEXT", "height": 0.5}).set_placement((span/2, -1))
    msp.add_text("FRONT VIEW", dxfattribs={"layer": "TEXT", "height": 0.3}).set_placement((span/2, -1.5))
    
    doc.saveas(str(output_path))
    print(f"Created wing DXF: {output_path}")


def create_fuselage_dxf(output_path: Path):
    """Create a simple fuselage side/top view DXF."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    
    # Fuselage parameters
    length = 20.0  # inches
    max_width = 2.0
    max_height = 3.0
    
    # Side view (left side of drawing)
    # Top line
    msp.add_line((0, 0), (length, 0), dxfattribs={"layer": "FUSELAGE_SIDE"})
    # Bottom line
    msp.add_line((0, -max_height), (length, -max_height), dxfattribs={"layer": "FUSELAGE_SIDE"})
    # Nose
    msp.add_line((0, 0), (0, -max_height), dxfattribs={"layer": "FUSELAGE_SIDE"})
    # Tail
    msp.add_line((length, 0), (length, -max_height), dxfattribs={"layer": "FUSELAGE_SIDE"})
    
    # Formers
    num_formers = 5
    for i in range(1, num_formers):
        x = (i / num_formers) * length
        height = max_height * (1 - abs((i / num_formers) - 0.5) * 0.5)
        msp.add_line(
            (x, 0),
            (x, -height),
            dxfattribs={"layer": "FORMERS"},
        )
    
    # Longerons (top and bottom)
    msp.add_line((0, 0), (length, 0), dxfattribs={"layer": "LONGERONS"})
    msp.add_line((0, -max_height), (length, -max_height), dxfattribs={"layer": "LONGERONS"})
    
    # Top view (right side of drawing, offset)
    offset_x = length + 2.0
    # Top line
    msp.add_line((offset_x, 0), (offset_x + length, 0), dxfattribs={"layer": "FUSELAGE_TOP"})
    # Bottom line
    msp.add_line((offset_x, -max_width), (offset_x + length, -max_width), dxfattribs={"layer": "FUSELAGE_TOP"})
    # Nose
    msp.add_line((offset_x, 0), (offset_x, -max_width), dxfattribs={"layer": "FUSELAGE_TOP"})
    # Tail
    msp.add_line((offset_x + length, 0), (offset_x + length, -max_width), dxfattribs={"layer": "FUSELAGE_TOP"})
    
    # Formers in top view
    for i in range(1, num_formers):
        x = offset_x + (i / num_formers) * length
        width = max_width * (1 - abs((i / num_formers) - 0.5) * 0.5)
        msp.add_line(
            (x, 0),
            (x, -width),
            dxfattribs={"layer": "FORMERS"},
        )
    
    # Labels
    msp.add_text("FUSELAGE", dxfattribs={"layer": "TEXT", "height": 0.5}).set_placement((length/2, 0.5))
    msp.add_text("SIDE VIEW", dxfattribs={"layer": "TEXT", "height": 0.3}).set_placement((length/2, 1.0))
    msp.add_text("TOP VIEW", dxfattribs={"layer": "TEXT", "height": 0.3}).set_placement((offset_x + length/2, 1.0))
    
    doc.saveas(str(output_path))
    print(f"Created fuselage DXF: {output_path}")


def main():
    """Generate all sample DXFs."""
    samples_dir = Path(__file__).parent.parent / "samples"
    samples_dir.mkdir(exist_ok=True)
    rendered_dir = samples_dir / "rendered"
    rendered_dir.mkdir(exist_ok=True)
    
    # Generate wing DXF
    wing_path = samples_dir / "wing.dxf"
    create_wing_dxf(wing_path)
    
    # Render wing to PNG
    parser = DXFParser(wing_path)
    images = parser.render_views(output_dir=rendered_dir)
    print(f"Rendered wing views: {list(images.keys())}")
    
    # Generate fuselage DXF
    fuselage_path = samples_dir / "fuselage.dxf"
    create_fuselage_dxf(fuselage_path)
    
    # Render fuselage to PNG
    parser = DXFParser(fuselage_path)
    images = parser.render_views(output_dir=rendered_dir)
    print(f"Rendered fuselage views: {list(images.keys())}")
    
    print("\nSample files generated successfully!")
    print(f"  Samples: {samples_dir}")
    print(f"  Rendered: {rendered_dir}")


if __name__ == "__main__":
    main()

