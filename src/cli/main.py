"""Main CLI entry point."""

import json
import sys
from pathlib import Path

from ..components.database import ComponentDatabase
from ..components.replacement import ReplacementEngine
from ..export.dxf_exporter import DXFExporter
from ..geometry.mass_properties import MassPropertiesCalculator
from ..ingestion.dxf_parser import DXFParser
from ..scene.scene_graph import SceneGraphBuilder
from ..vlm_client.client import VLMClient


def process_dxf(dxf_path: str, output_dir: str = "output"):
    """Process a DXF file through the full pipeline."""
    print(f"Processing DXF: {dxf_path}")
    
    # Step 1: Parse and render DXF
    print("  Parsing DXF...")
    parser = DXFParser(dxf_path)
    images = parser.render_views(output_dir=Path(output_dir) / "rendered")
    print(f"  Rendered {len(images)} view(s)")
    
    # Step 2: Call VLM
    print("  Calling VLM for analysis...")
    try:
        vlm = VLMClient()
        vlm_responses = vlm.analyze_drawing(images)
        print(f"  VLM analysis complete")
    except Exception as e:
        print(f"  Warning: VLM analysis failed: {e}")
        print("  Continuing with empty annotations...")
        from ..vlm_client.schema import VLMResponse
        vlm_responses = {name: VLMResponse() for name in images.keys()}
    
    # Step 3: Build scene graph
    print("  Building scene graph...")
    builder = SceneGraphBuilder(parser, vlm_responses)
    scene = builder.build()
    print(f"  Scene graph contains {len(scene.components)} components")
    
    # Step 4: Calculate mass properties
    print("  Calculating mass properties...")
    calc = MassPropertiesCalculator()
    mass_props = calc.calculate(scene)
    print(f"  Total mass: {mass_props['total_mass_lb']:.4f} lb")
    print(f"  CG: ({mass_props['cg'].x:.2f}, {mass_props['cg'].y:.2f}, {mass_props['cg'].z:.2f})")
    
    # Step 5: Export results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save scene graph JSON
    scene_json_path = output_path / "scene_graph.json"
    with open(scene_json_path, "w") as f:
        json.dump({
            "components": {k: v.dict() for k, v in scene.components.items()},
            "metadata": scene.metadata,
        }, f, indent=2, default=str)
    print(f"  Saved scene graph to {scene_json_path}")
    
    # Save mass properties
    mass_json_path = output_path / "mass_properties.json"
    with open(mass_json_path, "w") as f:
        json.dump({
            "total_mass_lb": mass_props["total_mass_lb"],
            "cg": {"x": mass_props["cg"].x, "y": mass_props["cg"].y, "z": mass_props["cg"].z},
            "component_masses": mass_props["component_masses"],
        }, f, indent=2)
    print(f"  Saved mass properties to {mass_json_path}")
    
    # Export regenerated DXF
    exporter = DXFExporter()
    output_dxf = output_path / "regenerated.dxf"
    exporter.export(scene, output_dxf)
    print(f"  Exported regenerated DXF to {output_dxf}")
    
    return scene, mass_props


def replace_component(
    dxf_path: str,
    component_id: str,
    replacement_id: str,
    output_dir: str = "output",
):
    """Replace a component and regenerate drawing."""
    print(f"Replacing component {component_id} with {replacement_id}")
    
    # Process original
    scene, _ = process_dxf(dxf_path, output_dir)
    
    # Replace component
    print(f"  Applying replacement...")
    db = ComponentDatabase()
    engine = ReplacementEngine(db)
    scene = engine.replace_component(scene, component_id, replacement_id)
    
    # Recalculate mass
    calc = MassPropertiesCalculator()
    mass_props = calc.calculate(scene)
    print(f"  New total mass: {mass_props['total_mass_lb']:.4f} lb")
    
    # Export updated DXF
    output_path = Path(output_dir)
    exporter = DXFExporter()
    output_dxf = output_path / "replaced.dxf"
    exporter.export(scene, output_dxf)
    print(f"  Exported updated DXF to {output_dxf}")
    
    return scene, mass_props


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.cli.main process <dxf_file> [output_dir]")
        print("  python -m src.cli.main replace <dxf_file> <component_id> <replacement_id> [output_dir]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "process":
        if len(sys.argv) < 3:
            print("Error: DXF file path required")
            sys.exit(1)
        dxf_path = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else "output"
        process_dxf(dxf_path, output_dir)
    
    elif command == "replace":
        if len(sys.argv) < 5:
            print("Error: DXF file, component ID, and replacement ID required")
            sys.exit(1)
        dxf_path = sys.argv[2]
        component_id = sys.argv[3]
        replacement_id = sys.argv[4]
        output_dir = sys.argv[5] if len(sys.argv) > 5 else "output"
        replace_component(dxf_path, component_id, replacement_id, output_dir)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

