"""Analyze planform boundaries to identify why objects outside polyline are being selected."""

import json
import sys
from pathlib import Path
import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent))

from tools.segmenter.io.workspace import WorkspaceManager
from tools.segmenter.core.segmentation import SegmentationEngine
from tools.segmenter.models import SegmentedObject, ObjectInstance, SegmentElement


def load_workspace(workspace_path: str):
    """Load workspace file."""
    manager = WorkspaceManager()
    workspace_dir = Path(workspace_path).parent
    
    # Load images first
    with open(workspace_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    page_images = {}
    for page_data in data.get("pages", []):
        img_file = page_data.get("image_file")
        if img_file:
            img_path = workspace_dir / img_file
            if img_path.exists():
                img = cv2.imread(str(img_path))
                if img is not None:
                    page_images[page_data["tab_id"]] = img
    
    # Load workspace
    result = manager.load(workspace_path)
    return result, page_images, data


def recreate_planform_mask(planform_elem: SegmentElement, image_shape: Tuple[int, int]) -> np.ndarray:
    """Recreate planform mask from its polyline points."""
    engine = SegmentationEngine()
    h, w = image_shape
    
    if planform_elem.mode == "polyline" and len(planform_elem.points) >= 3:
        # Create mask from polyline points
        mask = engine.create_polygon_mask((h, w), planform_elem.points, closed=True)
        return mask
    elif planform_elem.mask is not None:
        # Use stored mask if available
        return planform_elem.mask.copy()
    else:
        return np.zeros((h, w), dtype=np.uint8)


def check_object_overlap(obj: SegmentedObject, planform_mask: np.ndarray, 
                         page_id: str, image_shape: Tuple[int, int]) -> Dict:
    """Check if object overlaps with planform mask."""
    h, w = image_shape
    result = {
        "object_id": obj.object_id,
        "name": obj.name,
        "category": obj.category,
        "has_instance_on_page": False,
        "total_pixels": 0,
        "overlapping_pixels": 0,
        "overlap_percentage": 0.0,
        "is_inside": False,
        "is_outside": False,
        "bounding_box": None,
        "planform_bbox": None,
        "elements": []
    }
    
    # Get planform bounding box
    ys, xs = np.where(planform_mask > 0)
    if len(xs) > 0:
        result["planform_bbox"] = (int(np.min(xs)), int(np.min(ys)), 
                                   int(np.max(xs)), int(np.max(ys)))
    
    for inst in obj.instances:
        if inst.page_id != page_id:
            continue
        
        result["has_instance_on_page"] = True
        
        for elem in inst.elements:
            if elem.mask is None or elem.mask.shape != (h, w):
                continue
            
            elem_result = {
                "element_id": elem.element_id,
                "mode": elem.mode,
                "total_pixels": int(np.sum(elem.mask > 0)),
                "overlapping_pixels": 0,
                "overlap_percentage": 0.0,
                "bounding_box": None
            }
            
            # Get element bounding box
            elem_ys, elem_xs = np.where(elem.mask > 0)
            if len(elem_xs) > 0:
                elem_result["bounding_box"] = (int(np.min(elem_xs)), int(np.min(elem_ys)),
                                               int(np.max(elem_xs)), int(np.max(elem_ys)))
            
            # Check pixel overlap
            overlap_mask = (elem.mask > 0) & (planform_mask > 0)
            elem_result["overlapping_pixels"] = int(np.sum(overlap_mask))
            
            if elem_result["total_pixels"] > 0:
                elem_result["overlap_percentage"] = (elem_result["overlapping_pixels"] / 
                                                     elem_result["total_pixels"]) * 100
            
            result["total_pixels"] += elem_result["total_pixels"]
            result["overlapping_pixels"] += elem_result["overlapping_pixels"]
            result["elements"].append(elem_result)
    
    if result["total_pixels"] > 0:
        result["overlap_percentage"] = (result["overlapping_pixels"] / 
                                       result["total_pixels"]) * 100
    
    # Determine if inside or outside
    # Inside: any overlap with planform polyline
    # Outside: no overlap with planform polyline
    result["is_inside"] = result["overlapping_pixels"] > 0
    result["is_outside"] = result["overlapping_pixels"] == 0 and result["total_pixels"] > 0
    
    return result


def analyze_planform(workspace_path: str, planform_name: str = "Planform 4"):
    """Analyze a specific planform to see which objects are inside/outside."""
    print(f"Loading workspace: {workspace_path}")
    result, page_images, data = load_workspace(workspace_path)
    
    if not result:
        print("ERROR: Failed to load workspace")
        return
    
    print(f"Found {len(result.objects)} objects")
    print(f"Found {len(result.pages)} pages")
    
    # Find the planform object
    planform_obj = None
    for obj in result.objects:
        if obj.name == planform_name or planform_name.lower() in obj.name.lower():
            if obj.category == "planform":
                planform_obj = obj
                break
    
    if not planform_obj:
        print(f"ERROR: Could not find planform '{planform_name}'")
        print("Available planform objects:")
        for obj in result.objects:
            if obj.category == "planform":
                print(f"  - {obj.name} ({obj.object_id})")
        return
    
    print(f"\nFound planform: {planform_obj.name} ({planform_obj.object_id})")
    
    # Find the page this planform is on
    planform_page_id = None
    planform_elem = None
    for inst in planform_obj.instances:
        for elem in inst.elements:
            if elem.mode == "polyline":
                planform_page_id = inst.page_id
                planform_elem = elem
                break
        if planform_elem:
            break
    
    if not planform_elem or not planform_page_id:
        print("ERROR: Could not find planform element with polyline points")
        return
    
    # Get image for this page
    page_image = page_images.get(planform_page_id)
    if page_image is None:
        print(f"ERROR: Could not find image for page {planform_page_id}")
        return
    
    h, w = page_image.shape[:2]
    print(f"Page image shape: {h}x{w}")
    print(f"Planform has {len(planform_elem.points)} polyline points")
    
    # Recreate planform mask from points
    print("\nRecreating planform mask from polyline points...")
    planform_mask = recreate_planform_mask(planform_elem, (h, w))
    planform_pixels = np.sum(planform_mask > 0)
    print(f"Planform mask has {planform_pixels} non-white pixels")
    
    # Get planform bounding box for reference
    ys, xs = np.where(planform_mask > 0)
    planform_x_min = planform_x_max = planform_y_min = planform_y_max = 0
    if len(xs) > 0:
        planform_x_min, planform_x_max = int(np.min(xs)), int(np.max(xs)) + 1
        planform_y_min, planform_y_max = int(np.min(ys)), int(np.max(ys)) + 1
        bbox_area = (planform_x_max - planform_x_min) * (planform_y_max - planform_y_min)
        print(f"\nPlanform bounding box: ({planform_x_min}, {planform_y_min}) to ({planform_x_max}, {planform_y_max})")
        print(f"Planform bounding box size: {planform_x_max-planform_x_min}x{planform_y_max-planform_y_min} = {bbox_area:,} pixels")
        if bbox_area > 0:
            print(f"Planform mask fills {planform_pixels/bbox_area*100:.2f}% of bounding box")
    
    # Get stored planform_objects if available (note: this is not currently saved in workspace)
    stored_objects = data.get("planform_objects", {})
    stored_obj_ids = stored_objects.get(planform_obj.object_id, [])
    if stored_obj_ids:
        print(f"\nStored objects list for this planform: {len(stored_obj_ids)} objects")
        for obj_id in stored_obj_ids:
            # Try to find object name
            obj_name = obj_id
            for obj in result.objects:
                if obj.object_id == obj_id:
                    obj_name = f"{obj.name} ({obj_id})"
                    break
            print(f"  - {obj_name}")
    else:
        print(f"\nNOTE: No stored objects list found in workspace (planform_objects not saved)")
        print("      This means objects will be found at copy time, which may use incorrect logic")
    
    # Check all objects on this page
    print(f"\nAnalyzing all objects on page {planform_page_id}...")
    print("=" * 80)
    
    objects_inside = []
    objects_outside = []
    objects_in_stored_list = []
    objects_not_in_stored_list = []
    objects_outside_in_stored_list = []  # Objects that are outside but in stored list (PROBLEM!)
    
    mark_categories = {"mark_text", "mark_hatch", "mark_line"}
    
    for obj in result.objects:
        # Skip mark categories and other planforms
        if obj.category in mark_categories or obj.category == "planform":
            continue
        
        # Skip the planform itself
        if obj.object_id == planform_obj.object_id:
            continue
        
        # Check if object has instance on this page
        has_instance = any(inst.page_id == planform_page_id for inst in obj.instances)
        if not has_instance:
            continue
        
        overlap_info = check_object_overlap(obj, planform_mask, planform_page_id, (h, w))
        
        if overlap_info["is_inside"]:
            objects_inside.append(overlap_info)
            if obj.object_id in stored_obj_ids:
                objects_in_stored_list.append(overlap_info)
            else:
                objects_not_in_stored_list.append(overlap_info)
        elif overlap_info["is_outside"]:
            objects_outside.append(overlap_info)
            if obj.object_id in stored_obj_ids:
                objects_outside_in_stored_list.append(overlap_info)
                print(f"⚠ PROBLEM: Object {obj.name} ({obj.object_id}) is OUTSIDE planform but in stored list!")
    
    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Objects INSIDE planform polyline: {len(objects_inside)}")
    print(f"Objects OUTSIDE planform polyline: {len(objects_outside)}")
    print(f"\nStored objects list analysis:")
    print(f"  - Total objects in stored list: {len(stored_obj_ids)}")
    print(f"  - Inside objects correctly in stored list: {len(objects_in_stored_list)}")
    print(f"  - Inside objects MISSING from stored list: {len(objects_not_in_stored_list)}")
    print(f"  - Outside objects INCORRECTLY in stored list: {len(objects_outside_in_stored_list)} ⚠ PROBLEM")
    
    if objects_outside_in_stored_list:
        print(f"\n⚠ PROBLEMS FOUND:")
        print(f"  The following {len(objects_outside_in_stored_list)} objects are OUTSIDE the planform")
        print(f"  but are in the stored list (they will be incorrectly copied to new views):")
        for info in objects_outside_in_stored_list:
            print(f"    - {info['name']} ({info['object_id']})")
            print(f"      Total pixels: {info['total_pixels']:,}, Overlapping: {info['overlapping_pixels']:,}")
    
    if objects_not_in_stored_list:
        print(f"\n⚠ MISSING FROM STORED LIST:")
        print(f"  The following {len(objects_not_in_stored_list)} objects are INSIDE the planform")
        print(f"  but are NOT in the stored list (they will be missed when copying to new views):")
        for info in objects_not_in_stored_list:
            print(f"    - {info['name']} ({info['object_id']})")
            print(f"      Total pixels: {info['total_pixels']:,}, Overlapping: {info['overlapping_pixels']:,} ({info['overlap_percentage']:.2f}%)")
    
    # Print inside objects
    print(f"\n{'='*80}")
    print("OBJECTS INSIDE PLANFORM POLYLINE:")
    print(f"{'='*80}")
    for info in sorted(objects_inside, key=lambda x: x["name"]):
        in_stored = "✓ IN STORED" if info["object_id"] in stored_obj_ids else "✗ NOT IN STORED"
        print(f"\n{info['name']} ({info['object_id']}) [{info['category']}] {in_stored}")
        print(f"  Total pixels: {info['total_pixels']:,}")
        print(f"  Overlapping pixels: {info['overlapping_pixels']:,}")
        print(f"  Overlap percentage: {info['overlap_percentage']:.2f}%")
        if info["bounding_box"]:
            x1, y1, x2, y2 = info["bounding_box"]
            print(f"  Bounding box: ({x1}, {y1}) to ({x2}, {y2})")
        for elem_info in info["elements"]:
            print(f"    Element {elem_info['element_id']}: {elem_info['total_pixels']:,}px, "
                  f"{elem_info['overlapping_pixels']:,}px overlap ({elem_info['overlap_percentage']:.2f}%)")
    
    # Print outside objects
    print(f"\n{'='*80}")
    print("OBJECTS OUTSIDE PLANFORM POLYLINE:")
    print(f"{'='*80}")
    for info in sorted(objects_outside, key=lambda x: x["name"]):
        in_stored = "⚠ IN STORED (PROBLEM!)" if info["object_id"] in stored_obj_ids else ""
        print(f"\n{info['name']} ({info['object_id']}) [{info['category']}] {in_stored}")
        print(f"  Total pixels: {info['total_pixels']:,}")
        print(f"  Overlapping pixels: {info['overlapping_pixels']:,}")
        if info["bounding_box"]:
            x1, y1, x2, y2 = info["bounding_box"]
            print(f"  Bounding box: ({x1}, {y1}) to ({x2}, {y2})")
    
    # Print planform info
    print(f"\n{'='*80}")
    print("PLANFORM INFORMATION:")
    print(f"{'='*80}")
    print(f"Name: {planform_obj.name}")
    print(f"Object ID: {planform_obj.object_id}")
    print(f"Page ID: {planform_page_id}")
    print(f"Polyline points: {len(planform_elem.points)}")
    if planform_elem.points:
        print(f"First point: {planform_elem.points[0]}")
        print(f"Last point: {planform_elem.points[-1]}")
    print(f"Planform mask pixels: {planform_pixels:,}")
    if len(xs) > 0:
        print(f"Planform bounding box: ({planform_x_min}, {planform_y_min}) to ({planform_x_max}, {planform_y_max})")
        bbox_area = (planform_x_max - planform_x_min) * (planform_y_max - planform_y_min)
        print(f"Planform bounding box size: {planform_x_max-planform_x_min}x{planform_y_max-planform_y_min} = {bbox_area:,} pixels")
        if bbox_area > 0:
            print(f"Planform mask fills {planform_pixels/bbox_area*100:.2f}% of bounding box")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_planform_boundaries.py <workspace_file.pmw> [planform_name]")
        print("Example: python analyze_planform_boundaries.py 'Daddy-o-new for analysis.pmw' 'Planform 4'")
        sys.exit(1)
    
    workspace_path = sys.argv[1]
    planform_name = sys.argv[2] if len(sys.argv) > 2 else "Planform 4"
    
    if not Path(workspace_path).exists():
        print(f"ERROR: Workspace file not found: {workspace_path}")
        sys.exit(1)
    
    analyze_planform(workspace_path, planform_name)
