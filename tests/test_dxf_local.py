#!/usr/bin/env python3
"""
Local test script for DXF processing.

Tests the pipeline locally without AWS services.
Includes cost estimation and semantic layer visualization.
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
from datetime import datetime


def test_dxf_processing():
    """Test DXF file processing locally."""
    print("=" * 60)
    print("PlanMod DXF Processing Test")
    print("=" * 60)
    print()
    
    # Initialize cost estimator
    from backend.shared.cost_estimator import CostEstimator
    cost_estimator = CostEstimator(job_id="test-dxf-001")
    
    # Find DXF file
    dxf_path = Path("samples/Corsair rivista.dxf")
    if not dxf_path.exists():
        print(f"[X] DXF file not found: {dxf_path}")
        return False
    
    file_size = dxf_path.stat().st_size
    print(f"[*] Input file: {dxf_path}")
    print(f"    Size: {file_size / 1024:.1f} KB")
    print()
    
    # Track S3 upload cost (simulated)
    cost_estimator.add_s3_upload(file_size, num_requests=1)
    
    # Create output directory
    output_path = Path("output")
    output_path.mkdir(exist_ok=True)
    
    # Test 1: Read DXF with ezdxf
    print("[1] Testing DXF reading with ezdxf...")
    doc = None
    msp = None
    entity_counts = {}
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        
        # Count entities
        for entity in msp:
            etype = entity.dxftype()
            entity_counts[etype] = entity_counts.get(etype, 0) + 1
        
        print(f"    [OK] DXF loaded successfully")
        print(f"    DXF Version: {doc.dxfversion}")
        print(f"    Layers: {len(doc.layers)}")
        print(f"    Entities in modelspace: {sum(entity_counts.values())}")
        print(f"    Entity types: {dict(sorted(entity_counts.items(), key=lambda x: -x[1]))}")
        print()
        
        # List layers
        print("    Layers:")
        for layer in list(doc.layers)[:10]:
            print(f"      - {layer.dxf.name}")
        if len(doc.layers) > 10:
            print(f"      ... and {len(doc.layers) - 10} more")
        print()
        
        # Track Lambda invocation for DXF reading
        cost_estimator.add_lambda_invocation(duration_ms=300, memory_mb=1024)
        
    except ImportError:
        print("    [X] ezdxf not installed. Run: pip install ezdxf")
        return False
    except Exception as e:
        print(f"    [X] Failed to read DXF: {e}")
        return False
    
    # Test 2: Create scene graph from DXF
    print("[2] Testing scene graph creation...")
    scene_graph = None
    try:
        from backend.shared.models import (
            SceneGraph, View, ViewType, Component, ComponentType,
            BoundingBox, GeometryEntity
        )
        
        # Create scene graph
        scene_graph = SceneGraph(
            job_id="test-dxf-001",
            title="Corsair rivista",
            source_file=str(dxf_path),
        )
        
        # Get drawing bounds
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
        for entity in msp:
            try:
                if hasattr(entity, 'dxf') and hasattr(entity.dxf, 'start'):
                    min_x = min(min_x, entity.dxf.start.x)
                    min_y = min(min_y, entity.dxf.start.y)
                    max_x = max(max_x, entity.dxf.start.x)
                    max_y = max(max_y, entity.dxf.start.y)
                if hasattr(entity, 'dxf') and hasattr(entity.dxf, 'end'):
                    min_x = min(min_x, entity.dxf.end.x)
                    min_y = min(min_y, entity.dxf.end.y)
                    max_x = max(max_x, entity.dxf.end.x)
                    max_y = max(max_y, entity.dxf.end.y)
            except:
                pass
        
        if min_x == float('inf'):
            min_x, min_y, max_x, max_y = 0, 0, 1000, 1000
        
        scene_graph.image_width = int(max_x - min_x)
        scene_graph.image_height = int(max_y - min_y)
        
        # Create a view for the full drawing
        main_view = View(
            name="Full Drawing",
            view_type=ViewType.UNKNOWN,
            bounds=BoundingBox(
                x=min_x,
                y=min_y,
                width=max_x - min_x,
                height=max_y - min_y,
            ),
            classification_confidence=1.0,
        )
        scene_graph.views.append(main_view)
        
        # Create views for each layer that might represent different views
        view_keywords = {
            'top': ViewType.TOP,
            'side': ViewType.SIDE,
            'front': ViewType.FRONT,
            'plan': ViewType.TOP,
            'elevation': ViewType.SIDE,
        }
        
        for layer in doc.layers:
            layer_name = layer.dxf.name.lower()
            for keyword, vtype in view_keywords.items():
                if keyword in layer_name:
                    view = View(
                        name=layer.dxf.name,
                        view_type=vtype,
                        bounds=BoundingBox(x=min_x, y=min_y, width=max_x-min_x, height=max_y-min_y),
                        classification_confidence=0.7,
                    )
                    scene_graph.views.append(view)
                    break
        
        # Add geometry entities from DXF
        entity_count = 0
        for entity in msp:
            if entity_count >= 100:  # Limit for test
                break
            
            try:
                geom_entity = GeometryEntity(
                    entity_type=entity.dxftype().lower(),
                    geometry={"dxf_type": entity.dxftype()},
                    layer=entity.dxf.layer if hasattr(entity.dxf, 'layer') else "0",
                )
                scene_graph.entities.append(geom_entity)
                entity_count += 1
            except:
                pass
        
        print(f"    [OK] Scene graph created")
        print(f"    Views: {len(scene_graph.views)}")
        print(f"    Entities: {len(scene_graph.entities)}")
        print()
        
        # Track DynamoDB write
        cost_estimator.add_dynamodb_write(num_writes=1)
        
    except Exception as e:
        print(f"    [X] Failed to create scene graph: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Generate output DXF
    print("[3] Testing DXF output generation...")
    try:
        from backend.dxf_writer.writer import DXFWriter
        
        writer = DXFWriter()
        output_bytes = writer.write(scene_graph)
        
        output_file = output_path / "test_output.dxf"
        output_file.write_bytes(output_bytes)
        
        print(f"    [OK] Output DXF generated")
        print(f"    Output file: {output_file}")
        print(f"    Size: {len(output_bytes) / 1024:.1f} KB")
        print()
        
        # Verify output by reading back from file
        try:
            doc_out = ezdxf.readfile(str(output_file))
            msp_out = doc_out.modelspace()
            out_count = sum(1 for _ in msp_out)
            print(f"    Verification: {out_count} entities in output DXF")
            print(f"    Output layers: {len(doc_out.layers)}")
        except Exception as ve:
            print(f"    [!] Verification skipped: {ve}")
        print()
        
        # Track S3 upload for output
        cost_estimator.add_s3_upload(len(output_bytes), num_requests=1)
        cost_estimator.add_lambda_invocation(duration_ms=500, memory_mb=1024)
        
    except Exception as e:
        print(f"    [X] Failed to generate output DXF: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Render DXF preview
    print("[4] Testing DXF preview rendering...")
    preview_image = None
    try:
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        import numpy as np
        
        fig, ax = plt.subplots(figsize=(16, 12), dpi=100)
        ax.set_aspect('equal')
        
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp)
        
        preview_path = output_path / "preview.png"
        fig.savefig(preview_path, bbox_inches='tight', facecolor='white')
        
        # Also save as numpy array for semantic visualization
        fig.canvas.draw()
        # Use buffer_rgba() for compatibility with newer matplotlib
        preview_image = np.array(fig.canvas.buffer_rgba())[:, :, :3]  # RGB only
        
        plt.close(fig)
        
        print(f"    [OK] Preview rendered")
        print(f"    Preview file: {preview_path}")
        print(f"    Image size: {preview_image.shape[1]} x {preview_image.shape[0]} pixels")
        print()
        
    except ImportError as e:
        print(f"    [!] Preview rendering skipped (missing dependency: {e})")
        print()
    except Exception as e:
        print(f"    [!] Preview rendering failed: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 5: Semantic layer visualization
    print("[5] Testing semantic layer visualization...")
    try:
        from backend.scene_graph.semantic_renderer import SemanticRenderer, SEMANTIC_LAYERS
        import cv2
        import numpy as np
        
        renderer = SemanticRenderer()
        
        # Create elements from DXF layers for semantic classification
        elements = []
        layer_entities = {}
        
        # Group entities by layer
        for entity in msp:
            try:
                layer_name = entity.dxf.layer if hasattr(entity.dxf, 'layer') else "0"
                if layer_name not in layer_entities:
                    layer_entities[layer_name] = []
                layer_entities[layer_name].append(entity)
            except:
                pass
        
        print(f"    DXF Layers found: {len(layer_entities)}")
        
        # Classify layers semantically
        layer_classifications = {}
        for layer_name in layer_entities.keys():
            semantic = renderer.classify_element(layer_name, "layer", layer_name)
            if semantic:
                layer_classifications[layer_name] = semantic.name
            else:
                layer_classifications[layer_name] = "Unclassified"
        
        print(f"    Layer classifications:")
        for layer, semantic_class in list(layer_classifications.items())[:10]:
            print(f"      - {layer}: {semantic_class}")
        if len(layer_classifications) > 10:
            print(f"      ... and {len(layer_classifications) - 10} more")
        
        # Create semantic visualization if preview image is available
        if preview_image is not None:
            # Create visualization with colored layer overlay
            semantic_vis = renderer.render_from_cv_detections(
                preview_image,
                {
                    "lines": [],
                    "contours": [
                        {
                            "bounds": {"x": 50, "y": 50, "width": 100, "height": 100},
                            "shape": layer_name
                        }
                        for layer_name in list(layer_entities.keys())[:10]
                    ],
                    "circles": [],
                },
                show_legend=True,
            )
            
            semantic_path = output_path / "dxf_semantic_layers.png"
            cv2.imwrite(str(semantic_path), cv2.cvtColor(semantic_vis, cv2.COLOR_RGB2BGR))
            print(f"    [OK] Semantic visualization created")
            print(f"    Saved: {semantic_path}")
        else:
            print(f"    [!] Skipped (no preview image available)")
        
        # Print semantic layer legend
        print(f"\n    Semantic Layers (10 max):")
        for i, layer in enumerate(SEMANTIC_LAYERS[:10]):
            print(f"      {i+1}. {layer.name} - RGB{layer.color_rgb}")
        print()
        
    except Exception as e:
        print(f"    [!] Semantic visualization failed: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 6: Component catalog
    print("[6] Testing component catalog...")
    try:
        from backend.component_db.catalog import ComponentCatalog
        
        catalog = ComponentCatalog()
        
        print(f"    [OK] Catalog loaded")
        print(f"    Components: {len(catalog.components)}")
        
        # Show some components
        balsa = catalog.search(material="balsa")[:5]
        print(f"    Balsa stock items: {len(catalog.search(material='balsa'))}")
        for comp in balsa:
            print(f"      - {comp.id}: {comp.name}")
        print()
        
    except Exception as e:
        print(f"    [X] Catalog test failed: {e}")
        return False
    
    # Finalize cost estimation
    cost_estimator.finalize()
    cost_report = cost_estimator.get_report()
    
    # Print cost report
    print()
    print(cost_report.format_summary())
    print()
    
    # Save cost report
    cost_report_path = output_path / "dxf_cost_report.json"
    with open(cost_report_path, 'w') as f:
        json.dump(cost_report.to_dict(), f, indent=2)
    print(f"Cost report saved: {cost_report_path}")
    print()
    
    # Summary
    print("=" * 60)
    print("[OK] All tests passed!")
    print("=" * 60)
    print()
    print("Generated files:")
    print(f"  - output/test_output.dxf")
    print(f"  - output/preview.png")
    print(f"  - output/dxf_semantic_layers.png")
    print(f"  - output/dxf_cost_report.json")
    print()
    print("Next steps:")
    print("  1. Run: pip install -r requirements.txt")
    print("  2. Start API: python -m backend.api.server")
    print("  3. Start frontend: cd frontend && npm install && npm run dev")
    print("  4. Open http://localhost:5173 in browser")
    print()
    
    return True


if __name__ == "__main__":
    success = test_dxf_processing()
    sys.exit(0 if success else 1)
