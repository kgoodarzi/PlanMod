#!/usr/bin/env python3
"""
Local test script for PDF processing.

Tests the ingestion pipeline with PDF files.
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
from datetime import datetime


def test_pdf_processing():
    """Test PDF file processing locally."""
    print("=" * 60)
    print("PlanMod PDF Processing Test")
    print("=" * 60)
    print()
    
    # Initialize cost estimator
    from backend.shared.cost_estimator import CostEstimator
    cost_estimator = CostEstimator(job_id="test-pdf-001")
    
    # Find PDF file
    pdf_path = Path("samples/Aeronca_Defender_Plan_Vector.pdf")
    if not pdf_path.exists():
        print(f"[X] PDF file not found: {pdf_path}")
        return False
    
    print(f"[*] Input file: {pdf_path}")
    file_size = pdf_path.stat().st_size
    print(f"    Size: {file_size / 1024 / 1024:.2f} MB")
    print()
    
    # Track S3 upload cost (simulated)
    cost_estimator.add_s3_upload(file_size, num_requests=1)
    
    # Create output directory
    output_path = Path("output")
    output_path.mkdir(exist_ok=True)
    
    # Test 1: Read PDF and get page count
    print("[1] Testing PDF reading...")
    try:
        from backend.ingest.pdf_processor import PDFProcessor
        
        pdf_data = pdf_path.read_bytes()
        processor = PDFProcessor(dpi=150)  # Lower DPI for faster testing
        
        page_count = processor.get_page_count(pdf_data)
        print(f"    [OK] PDF loaded")
        print(f"    Pages: {page_count}")
        
        # Get metadata
        metadata = processor.get_metadata(pdf_data)
        if metadata:
            print(f"    Title: {metadata.get('title', 'N/A')}")
            print(f"    Author: {metadata.get('author', 'N/A')}")
        print()
        
        # Track Lambda invocation for PDF reading
        cost_estimator.add_lambda_invocation(duration_ms=500, memory_mb=1024)
        
    except ImportError as e:
        print(f"    [X] Missing dependency: {e}")
        print("    Run: pip install PyMuPDF pdf2image")
        return False
    except Exception as e:
        print(f"    [X] Failed to read PDF: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Rasterize PDF pages
    print("[2] Testing PDF rasterization...")
    try:
        images = processor.rasterize(pdf_data, dpi=150, pages=[0])  # First page only
        
        if not images:
            print("    [X] No pages rasterized")
            return False
        
        image = images[0]
        print(f"    [OK] Page 1 rasterized")
        print(f"    Image size: {image.shape[1]} x {image.shape[0]} pixels")
        print(f"    Channels: {image.shape[2] if len(image.shape) > 2 else 1}")
        
        # Save rasterized image
        from PIL import Image
        pil_image = Image.fromarray(image)
        raster_path = output_path / "pdf_page1_raster.png"
        pil_image.save(raster_path)
        print(f"    Saved: {raster_path}")
        print()
        
        # Track Lambda invocation for rasterization
        cost_estimator.add_lambda_invocation(duration_ms=2000, memory_mb=2048)
        
    except Exception as e:
        print(f"    [X] Failed to rasterize PDF: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Normalize image
    print("[3] Testing image normalization...")
    try:
        from backend.ingest.normalizer import ImageNormalizer
        
        normalizer = ImageNormalizer(max_dimension=2000)
        normalized = normalizer.normalize(image)
        
        print(f"    [OK] Image normalized")
        print(f"    Output size: {normalized.shape[1]} x {normalized.shape[0]} pixels")
        
        # Save normalized image
        pil_normalized = Image.fromarray(normalized)
        norm_path = output_path / "pdf_page1_normalized.png"
        pil_normalized.save(norm_path)
        print(f"    Saved: {norm_path}")
        print()
        
        # Track Lambda invocation for normalization
        cost_estimator.add_lambda_invocation(duration_ms=500, memory_mb=1024)
        
    except Exception as e:
        print(f"    [X] Failed to normalize image: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: CV-based detection
    print("[4] Testing CV detection...")
    detections = {}
    try:
        from backend.vision.cv_detector import CVDetector
        
        detector = CVDetector()
        detections = detector.detect(normalized)
        
        print(f"    [OK] CV detection complete")
        print(f"    Lines detected: {len(detections.get('lines', []))}")
        print(f"    Contours detected: {len(detections.get('contours', []))}")
        print(f"    Circles detected: {len(detections.get('circles', []))}")
        
        # Draw detections
        vis_image = detector.draw_detections(normalized, detections)
        vis_pil = Image.fromarray(vis_image)
        vis_path = output_path / "pdf_cv_detections.png"
        vis_pil.save(vis_path)
        print(f"    Saved visualization: {vis_path}")
        print()
        
        # Track Lambda invocation for CV detection
        cost_estimator.add_lambda_invocation(duration_ms=3000, memory_mb=2048)
        
    except Exception as e:
        print(f"    [X] CV detection failed: {e}")
        import traceback
        traceback.print_exc()
        # Continue anyway
    
    # Test 5: Region detection (without VLM)
    print("[5] Testing region detection...")
    regions = []
    try:
        regions = normalizer.detect_drawing_regions(normalized)
        
        print(f"    [OK] Region detection complete")
        print(f"    Regions found: {len(regions)}")
        
        for i, (x, y, w, h) in enumerate(regions[:5]):
            print(f"      Region {i+1}: ({x}, {y}) - {w}x{h} px")
        print()
        
    except Exception as e:
        print(f"    [!] Region detection failed: {e}")
        print()
    
    # Test 6: Create scene graph from image
    print("[6] Testing scene graph creation...")
    scene_graph = None
    try:
        from backend.shared.models import (
            SceneGraph, View, ViewType, Component, ComponentType,
            BoundingBox, GeometryEntity
        )
        
        scene_graph = SceneGraph(
            job_id="test-pdf-001",
            title="Aeronca Defender",
            source_file=str(pdf_path),
            image_width=normalized.shape[1],
            image_height=normalized.shape[0],
        )
        
        # Create main view
        main_view = View(
            name="Full Drawing",
            view_type=ViewType.UNKNOWN,
            bounds=BoundingBox(
                x=0,
                y=0,
                width=normalized.shape[1],
                height=normalized.shape[0],
            ),
            classification_confidence=1.0,
        )
        scene_graph.views.append(main_view)
        
        # Add detected regions as views
        for i, (x, y, w, h) in enumerate(regions[:5]):
            view = View(
                name=f"Region {i+1}",
                view_type=ViewType.UNKNOWN,
                bounds=BoundingBox(x=x, y=y, width=w, height=h),
                classification_confidence=0.5,
            )
            scene_graph.views.append(view)
        
        # Add some CV-detected elements as entities
        for line in detections.get('lines', [])[:50]:
            entity = GeometryEntity(
                entity_type="line",
                geometry={
                    "start": {"x": line["start"][0], "y": line["start"][1]},
                    "end": {"x": line["end"][0], "y": line["end"][1]},
                },
            )
            scene_graph.entities.append(entity)
        
        print(f"    [OK] Scene graph created")
        print(f"    Views: {len(scene_graph.views)}")
        print(f"    Entities: {len(scene_graph.entities)}")
        print()
        
        # Track DynamoDB write for scene graph
        cost_estimator.add_dynamodb_write(num_writes=1)
        
    except Exception as e:
        print(f"    [X] Scene graph creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 7: Generate DXF from scene graph
    print("[7] Testing DXF generation...")
    try:
        from backend.dxf_writer.writer import DXFWriter
        
        writer = DXFWriter()
        output_bytes = writer.write(scene_graph)
        
        dxf_path = output_path / "pdf_output.dxf"
        dxf_path.write_bytes(output_bytes)
        
        print(f"    [OK] DXF generated")
        print(f"    Output file: {dxf_path}")
        print(f"    Size: {len(output_bytes) / 1024:.1f} KB")
        
        # Verify
        import ezdxf
        doc_out = ezdxf.readfile(str(dxf_path))
        msp_out = doc_out.modelspace()
        out_count = sum(1 for _ in msp_out)
        print(f"    Entities in output: {out_count}")
        print()
        
        # Track S3 upload for output DXF
        cost_estimator.add_s3_upload(len(output_bytes), num_requests=1)
        cost_estimator.add_lambda_invocation(duration_ms=1000, memory_mb=1024)
        
    except Exception as e:
        print(f"    [X] DXF generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 8: Semantic layer visualization
    print("[8] Testing semantic layer visualization...")
    try:
        from backend.scene_graph.semantic_renderer import SemanticRenderer
        import cv2
        
        renderer = SemanticRenderer()
        
        # Create semantic visualization from CV detections
        semantic_vis = renderer.render_from_cv_detections(
            normalized,
            detections,
            show_legend=True,
        )
        
        # Save semantic visualization
        semantic_path = output_path / "pdf_semantic_layers.png"
        cv2.imwrite(str(semantic_path), semantic_vis)
        print(f"    [OK] Semantic layer visualization created")
        print(f"    Saved: {semantic_path}")
        print(f"    Image size: {semantic_vis.shape[1]} x {semantic_vis.shape[0]} pixels")
        
        # List detected semantic layers
        print(f"    Semantic layers defined:")
        for layer in renderer.layers[:10]:
            print(f"      - {layer.name}: {layer.color_rgb}")
        print()
        
    except Exception as e:
        print(f"    [!] Semantic visualization failed: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 9: Test VLM (if AWS credentials available)
    print("[9] Testing VLM integration (requires AWS Bedrock)...")
    try:
        from backend.shared.config import get_settings
        settings = get_settings()
        
        # Check if we have credentials
        has_creds = bool(
            settings.aws.access_key_id or 
            settings.aws.profile
        )
        
        if not has_creds:
            print("    [!] No AWS credentials configured, skipping VLM test")
            print()
        else:
            print(f"    AWS Region: {settings.aws.region}")
            print(f"    VLM Model: {settings.ai.bedrock.vlm_model_id}")
            
            # Try a simple VLM call
            from backend.vlm_client.bedrock_claude import BedrockClaudeVLM
            import asyncio
            
            vlm = BedrockClaudeVLM(settings)
            
            # Convert image to bytes
            img_buffer = io.BytesIO()
            pil_normalized.save(img_buffer, format='PNG')
            img_bytes = img_buffer.getvalue()
            
            async def test_vlm():
                response = await vlm.describe_drawing(img_bytes)
                return response
            
            print("    Calling VLM for drawing description...")
            response = asyncio.run(test_vlm())
            
            if response.success:
                print(f"    [OK] VLM response received")
                if response.structured_data:
                    data = response.structured_data
                    print(f"    Title: {data.get('title', 'N/A')}")
                    print(f"    Type: {data.get('drawing_type', 'N/A')}")
                    print(f"    Subject: {data.get('subject', 'N/A')}")
                    if data.get('views_identified'):
                        print(f"    Views: {', '.join(data['views_identified'])}")
                else:
                    print(f"    Raw response: {response.raw_response[:200]}...")
                print(f"    Tokens used: {response.tokens_used}")
                
                # Track Bedrock VLM cost
                cost_estimator.add_bedrock_call(
                    input_tokens=1500,  # Approximate for image
                    output_tokens=response.tokens_used or 300,
                    model="claude-3-5-sonnet",
                    includes_image=True,
                )
            else:
                print(f"    [!] VLM call failed: {response.error}")
            print()
            
    except Exception as e:
        print(f"    [!] VLM test failed: {e}")
        print()
    
    # Finalize cost estimation
    cost_estimator.finalize()
    cost_report = cost_estimator.get_report()
    
    # Print cost report
    print()
    print(cost_report.format_summary())
    print()
    
    # Save cost report
    cost_report_path = output_path / "pdf_cost_report.json"
    import json
    with open(cost_report_path, 'w') as f:
        json.dump(cost_report.to_dict(), f, indent=2)
    print(f"Cost report saved: {cost_report_path}")
    print()
    
    # Summary
    print("=" * 60)
    print("[OK] PDF Processing Test Complete!")
    print("=" * 60)
    print()
    print("Generated files:")
    print(f"  - {output_path / 'pdf_page1_raster.png'}")
    print(f"  - {output_path / 'pdf_page1_normalized.png'}")
    print(f"  - {output_path / 'pdf_cv_detections.png'}")
    print(f"  - {output_path / 'pdf_semantic_layers.png'}")
    print(f"  - {output_path / 'pdf_output.dxf'}")
    print(f"  - {output_path / 'pdf_cost_report.json'}")
    print()
    
    return True


if __name__ == "__main__":
    success = test_pdf_processing()
    sys.exit(0 if success else 1)
