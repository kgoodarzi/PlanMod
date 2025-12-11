"""Basic usage example for PlanMod."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.main import process_dxf, replace_component


def main():
    """Example usage of PlanMod pipeline."""
    
    # Example 1: Process a DXF file
    print("=" * 60)
    print("Example 1: Processing a DXF file")
    print("=" * 60)
    
    dxf_path = Path(__file__).parent.parent / "samples" / "wing.dxf"
    
    if dxf_path.exists():
        try:
            scene, mass_props = process_dxf(str(dxf_path), "output/example1")
            print(f"\n✓ Successfully processed {dxf_path}")
            print(f"  Components detected: {len(scene.components)}")
            print(f"  Total mass: {mass_props['total_mass_lb']:.4f} lb")
        except Exception as e:
            print(f"\n✗ Error processing DXF: {e}")
            print("  Make sure VLM API credentials are configured in .env")
    else:
        print(f"\n⚠ Sample DXF not found: {dxf_path}")
        print("  Run: python scripts/generate_samples.py")
    
    # Example 2: Replace a component
    print("\n" + "=" * 60)
    print("Example 2: Replacing a component")
    print("=" * 60)
    
    if dxf_path.exists():
        try:
            # First, process to get component IDs
            scene, _ = process_dxf(str(dxf_path), "output/example2")
            
            if scene.components:
                # Get first component ID
                first_comp_id = list(scene.components.keys())[0]
                print(f"\n  Replacing component: {first_comp_id}")
                
                # Replace with a different stick size
                scene, mass_props = replace_component(
                    str(dxf_path),
                    first_comp_id,
                    "stick_1_8_x_1_4",  # Replacement from database
                    "output/example2",
                )
                print(f"  ✓ Replacement complete")
                print(f"  New mass: {mass_props['total_mass_lb']:.4f} lb")
            else:
                print("  No components found to replace")
        except Exception as e:
            print(f"\n✗ Error replacing component: {e}")
    else:
        print(f"\n⚠ Sample DXF not found: {dxf_path}")
    
    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
    print("\nCheck output/example1/ and output/example2/ for results")


if __name__ == "__main__":
    main()

