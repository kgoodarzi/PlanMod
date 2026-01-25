"""
Nesting module for packing objects onto sheets.

Uses rectpack library for rectangle bin packing, with object bounding boxes.
Can optionally use more sophisticated polygon nesting if needed.
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import uuid

# Try to import rectpack for bin packing
try:
    import rectpack
    HAS_RECTPACK = True
except ImportError:
    HAS_RECTPACK = False
    print("Warning: rectpack not installed. Install with: pip install rectpack")


@dataclass
class NestedPart:
    """Represents a part placed on a sheet."""
    object_id: str
    instance_id: str
    name: str
    x: int  # Position on sheet (pixels)
    y: int
    width: int  # Bounding box size
    height: int
    rotated: bool  # True if rotated 90 degrees
    mask: Optional[np.ndarray] = None  # Original mask
    source_bbox: Tuple[int, int, int, int] = None  # (x, y, w, h) in source image
    
    def get_placed_mask(self, sheet_h: int, sheet_w: int) -> np.ndarray:
        """Get the mask positioned on the sheet."""
        if self.mask is None:
            return None
        
        result = np.zeros((sheet_h, sheet_w), dtype=np.uint8)
        
        # Get the mask content
        mask = self.mask
        if self.rotated:
            mask = cv2.rotate(mask, cv2.ROTATE_90_CLOCKWISE)
        
        # Extract just the bounding box region from the mask
        if self.source_bbox:
            sx, sy, sw, sh = self.source_bbox
            mask_region = mask[sy:sy+sh, sx:sx+sw]
        else:
            # Find bounding box from mask
            ys, xs = np.where(mask > 0)
            if len(ys) == 0:
                return result
            x1, y1 = xs.min(), ys.min()
            x2, y2 = xs.max() + 1, ys.max() + 1
            mask_region = mask[y1:y2, x1:x2]
        
        # Handle rotation effects on dimensions
        if self.rotated:
            # After 90° rotation, width and height are swapped
            mask_region = cv2.rotate(mask_region, cv2.ROTATE_90_CLOCKWISE)
        
        # Place on sheet
        mh, mw = mask_region.shape[:2]
        
        # Ensure we don't exceed sheet boundaries
        place_h = min(mh, sheet_h - self.y)
        place_w = min(mw, sheet_w - self.x)
        
        if place_h > 0 and place_w > 0:
            result[self.y:self.y+place_h, self.x:self.x+place_w] = mask_region[:place_h, :place_w]
        
        return result


@dataclass
class NestedSheet:
    """Represents a sheet with nested parts."""
    sheet_id: str
    width: int  # Sheet dimensions in pixels
    height: int
    material: str
    thickness: float
    parts: List[NestedPart] = field(default_factory=list)
    sheet_name: str = ""
    
    def __post_init__(self):
        if not self.sheet_id:
            self.sheet_id = str(uuid.uuid4())[:8]
    
    @property
    def utilization(self) -> float:
        """Calculate sheet utilization percentage."""
        if self.width == 0 or self.height == 0:
            return 0.0
        
        total_part_area = sum(p.width * p.height for p in self.parts)
        sheet_area = self.width * self.height
        return (total_part_area / sheet_area) * 100
    
    def render(self, include_masks: bool = True) -> np.ndarray:
        """
        Render the sheet with all placed parts.
        
        Returns:
            BGRA image of the sheet with parts
        """
        # Create white background
        image = np.ones((self.height, self.width, 4), dtype=np.uint8) * 255
        image[:, :, 3] = 255  # Full opacity
        
        # Draw each part
        for i, part in enumerate(self.parts):
            # Generate a color for this part (cycle through colors)
            colors = [
                (66, 133, 244),   # Blue
                (52, 168, 83),    # Green
                (251, 188, 5),    # Yellow
                (234, 67, 53),    # Red
                (156, 39, 176),   # Purple
                (0, 188, 212),    # Cyan
                (255, 152, 0),    # Orange
                (121, 85, 72),    # Brown
            ]
            color = colors[i % len(colors)]
            
            if include_masks and part.mask is not None:
                # Draw the actual mask
                placed_mask = part.get_placed_mask(self.height, self.width)
                if placed_mask is not None:
                    mask_region = placed_mask > 0
                    # Apply semi-transparent color
                    image[mask_region, 0] = color[2]  # BGR
                    image[mask_region, 1] = color[1]
                    image[mask_region, 2] = color[0]
            else:
                # Draw bounding box
                x, y = part.x, part.y
                w, h = part.width, part.height
                cv2.rectangle(image, (x, y), (x + w, y + h), (*color, 255), -1)
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 0, 255), 2)
            
            # Draw label
            label = part.name
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.4
            thickness = 1
            (text_w, text_h), _ = cv2.getTextSize(label, font, scale, thickness)
            
            label_x = part.x + (part.width - text_w) // 2
            label_y = part.y + (part.height + text_h) // 2
            
            # Draw text shadow
            cv2.putText(image, label, (label_x + 1, label_y + 1), font, scale, (0, 0, 0, 255), thickness)
            # Draw text
            cv2.putText(image, label, (label_x, label_y), font, scale, (255, 255, 255, 255), thickness)
        
        # Draw sheet border
        cv2.rectangle(image, (0, 0), (self.width - 1, self.height - 1), (0, 0, 0, 255), 2)
        
        return image


class NestingEngine:
    """
    Engine for nesting objects onto sheets.
    
    Uses rectpack for rectangle bin packing algorithm.
    """
    
    def __init__(self, spacing: int = 5, allow_rotation: bool = True):
        """
        Initialize the nesting engine.
        
        Args:
            spacing: Minimum spacing between parts (in pixels)
            allow_rotation: Whether to allow 90-degree rotation
        """
        self.spacing = spacing
        self.allow_rotation = allow_rotation
    
    def extract_part_info(self, obj, inst, page_image: np.ndarray) -> Optional[Dict]:
        """
        Extract part information from an object instance.
        
        Returns dict with:
            - mask: Combined mask of all elements
            - bbox: Bounding box (x, y, w, h)
            - name: Object name
        """
        h, w = page_image.shape[:2]
        
        # Combine all element masks
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        for elem in inst.elements:
            if elem.mask is not None and elem.mask.shape == (h, w):
                combined_mask = np.maximum(combined_mask, elem.mask)
        
        # Find bounding box
        ys, xs = np.where(combined_mask > 0)
        if len(ys) == 0:
            return None
        
        x1, y1 = xs.min(), ys.min()
        x2, y2 = xs.max() + 1, ys.max() + 1
        
        # Extract mask region
        mask_region = combined_mask[y1:y2, x1:x2]
        
        return {
            "mask": mask_region,
            "bbox": (x1, y1, x2 - x1, y2 - y1),
            "full_mask": combined_mask,
            "name": obj.name,
            "object_id": obj.object_id,
            "instance_id": inst.instance_id,
            "quantity": inst.attributes.quantity or 1,
        }
    
    def nest_parts(self, parts: List[Dict], sheet_sizes: List[Tuple[int, int]],
                   material: str, thickness: float) -> List[NestedSheet]:
        """
        Nest parts onto sheets.
        
        Args:
            parts: List of part info dicts from extract_part_info
            sheet_sizes: List of (width, height) tuples for available sheet sizes
            material: Material name for the sheets
            thickness: Material thickness
            
        Returns:
            List of NestedSheet objects with parts placed
        """
        if not HAS_RECTPACK:
            raise ImportError("rectpack library is required for nesting. Install with: pip install rectpack")
        
        if not parts or not sheet_sizes:
            return []
        
        # Prepare rectangles for packing
        # Each rectangle is (width, height, rid) where rid is a unique identifier
        rectangles = []
        part_lookup = {}
        
        for idx, part in enumerate(parts):
            bbox = part["bbox"]
            w = bbox[2] + self.spacing * 2
            h = bbox[3] + self.spacing * 2
            
            # Handle quantity - add multiple copies
            quantity = part.get("quantity", 1)
            for q in range(quantity):
                rid = f"{idx}_{q}"
                rectangles.append((w, h, rid))
                part_lookup[rid] = part
        
        # Create packer
        if self.allow_rotation:
            packer = rectpack.newPacker(
                mode=rectpack.PackingMode.Offline,
                pack_algo=rectpack.MaxRectsBssf,
                rotation=True
            )
        else:
            packer = rectpack.newPacker(
                mode=rectpack.PackingMode.Offline,
                pack_algo=rectpack.MaxRectsBssf,
                rotation=False
            )
        
        # Add rectangles to packer
        for w, h, rid in rectangles:
            packer.add_rect(w, h, rid)
        
        # Add bins (sheets) - we'll add sheets one at a time until all parts are packed
        sheet_idx = 0
        sheets = []
        
        # Sort sheet sizes by area (largest first for efficiency)
        sorted_sheets = sorted(sheet_sizes, key=lambda s: s[0] * s[1], reverse=True)
        
        # Keep adding sheets until all rectangles are packed
        remaining = len(rectangles)
        max_sheets = 100  # Safety limit
        
        while remaining > 0 and sheet_idx < max_sheets:
            # Use sheet sizes cyclically
            sw, sh = sorted_sheets[sheet_idx % len(sorted_sheets)]
            packer.add_bin(sw, sh, count=1)
            
            # Pack
            packer.pack()
            
            # Check how many are now packed
            packed_count = len(packer.all_rects())
            if packed_count == len(rectangles):
                remaining = 0
            elif packed_count == remaining:
                # No progress - parts might be too large
                break
            else:
                remaining = len(rectangles) - packed_count
            
            sheet_idx += 1
        
        # Convert packed results to NestedSheet objects
        for bin_idx, abin in enumerate(packer):
            sheet_w, sheet_h = abin.width, abin.height
            
            nested_sheet = NestedSheet(
                sheet_id="",
                width=sheet_w,
                height=sheet_h,
                material=material,
                thickness=thickness,
                sheet_name=f"{material} Sheet {bin_idx + 1}"
            )
            
            for rect in abin:
                b, x, y, w, h, rid = rect
                
                part = part_lookup.get(rid)
                if not part:
                    continue
                
                # Check if rotated (compare dimensions)
                orig_w = part["bbox"][2] + self.spacing * 2
                orig_h = part["bbox"][3] + self.spacing * 2
                rotated = (w != orig_w or h != orig_h)
                
                nested_part = NestedPart(
                    object_id=part["object_id"],
                    instance_id=part["instance_id"],
                    name=part["name"],
                    x=x + self.spacing,
                    y=y + self.spacing,
                    width=part["bbox"][2],
                    height=part["bbox"][3],
                    rotated=rotated,
                    mask=part["full_mask"],
                    source_bbox=part["bbox"]
                )
                nested_sheet.parts.append(nested_part)
            
            if nested_sheet.parts:
                sheets.append(nested_sheet)
        
        return sheets
    
    def nest_by_material(self, material_groups: List, sheet_configs: Dict,
                         pages: Dict, dpi: float = 150.0,
                         respect_quantity: bool = True) -> Dict[str, List[NestedSheet]]:
        """
        Nest all parts grouped by material.
        
        Args:
            material_groups: List of MaterialGroup objects
            sheet_configs: Dict mapping group key to list of SheetSize objects
            pages: Dict of PageTab objects
            dpi: DPI for converting sheet sizes to pixels
            respect_quantity: Whether to duplicate parts based on quantity attribute
            
        Returns:
            Dict mapping material to list of NestedSheet objects
        """
        results = {}
        
        for group in material_groups:
            group_key = f"{group.material}_{group.thickness}"
            sheet_sizes = sheet_configs.get(group_key, [])
            
            if not sheet_sizes:
                continue
            
            # Convert sheet sizes to pixels
            pixel_sheets = [s.to_pixels(dpi) for s in sheet_sizes]
            
            # Extract parts from this group
            parts = []
            for obj, inst in group.objects:
                # Find the page for this instance
                page = pages.get(inst.page_id)
                if not page or page.original_image is None:
                    continue
                
                part_info = self.extract_part_info(obj, inst, page.original_image)
                if part_info:
                    if not respect_quantity:
                        part_info["quantity"] = 1
                    parts.append(part_info)
            
            if parts:
                nested_sheets = self.nest_parts(
                    parts, pixel_sheets,
                    group.material, group.thickness
                )
                
                if nested_sheets:
                    results[group_key] = nested_sheets
        
        return results


def check_rectpack_available() -> bool:
    """Check if rectpack is available."""
    return HAS_RECTPACK
