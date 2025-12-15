"""Export functionality for images and data."""

import json
from pathlib import Path
from typing import Dict, List
import cv2
import numpy as np

from tools.segmenter.models import PageTab, DynamicCategory
from tools.segmenter.core.rendering import Renderer


class ImageExporter:
    """Exports segmented images."""
    
    def __init__(self, renderer: Renderer = None):
        self.renderer = renderer or Renderer()
    
    def export_page(self,
                    path: str,
                    page: PageTab,
                    categories: Dict[str, DynamicCategory],
                    include_labels: bool = True) -> bool:
        """
        Export a segmented page as an image.
        
        Args:
            path: Output path
            page: Page to export
            categories: Category definitions
            include_labels: Whether to include labels
            
        Returns:
            True if successful
        """
        try:
            # Render at full resolution
            rendered = self.renderer.render_page(
                page, categories,
                zoom=1.0,
                show_labels=include_labels,
            )
            
            # Convert BGRA to BGR for saving
            if rendered.shape[2] == 4:
                rendered = cv2.cvtColor(rendered, cv2.COLOR_BGRA2BGR)
            
            cv2.imwrite(path, rendered)
            return True
            
        except Exception as e:
            print(f"Error exporting image: {e}")
            return False
    
    def export_masks(self,
                     output_dir: str,
                     page: PageTab,
                     separate_objects: bool = True) -> List[str]:
        """
        Export segmentation masks.
        
        Args:
            output_dir: Output directory
            page: Page to export
            separate_objects: Whether to create separate mask per object
            
        Returns:
            List of created file paths
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        created = []
        
        if page.original_image is None:
            return created
        
        h, w = page.original_image.shape[:2]
        
        if separate_objects:
            # One mask per object
            for obj in page.objects:
                mask = np.zeros((h, w), dtype=np.uint8)
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.mask is not None:
                            mask = np.maximum(mask, elem.mask)
                
                if np.any(mask):
                    filename = f"{page.model_name}_{page.page_name}_{obj.name}_mask.png"
                    filepath = out_path / filename
                    cv2.imwrite(str(filepath), mask)
                    created.append(str(filepath))
        else:
            # Single combined mask
            mask = np.zeros((h, w), dtype=np.uint8)
            for obj in page.objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.mask is not None:
                            mask = np.maximum(mask, elem.mask)
            
            filename = f"{page.model_name}_{page.page_name}_mask.png"
            filepath = out_path / filename
            cv2.imwrite(str(filepath), mask)
            created.append(str(filepath))
        
        return created


class DataExporter:
    """Exports segmentation data as JSON."""
    
    def export_page(self, path: str, page: PageTab) -> bool:
        """
        Export page data as JSON.
        
        Args:
            path: Output path
            page: Page to export
            
        Returns:
            True if successful
        """
        try:
            data = {
                "model": page.model_name,
                "page": page.page_name,
                "image_size": list(page.image_size) if page.image_size else None,
                "objects": [],
            }
            
            for obj in page.objects:
                obj_data = {
                    "id": obj.object_id,
                    "name": obj.name,
                    "category": obj.category,
                    "attributes": {
                        "material": obj.attributes.material,
                        "type": obj.attributes.obj_type,
                        "view": obj.attributes.view,
                        "size": {
                            "width": obj.attributes.width,
                            "height": obj.attributes.height,
                            "depth": obj.attributes.depth,
                        },
                        "description": obj.attributes.description,
                        "quantity": obj.attributes.quantity,
                    },
                    "instances": [],
                }
                
                for inst in obj.instances:
                    inst_data = {
                        "instance_num": inst.instance_num,
                        "view_type": inst.view_type,
                        "elements": [],
                    }
                    
                    for elem in inst.elements:
                        elem_data = {
                            "mode": elem.mode,
                            "points": elem.points,
                            "bounds": elem.bounds,
                            "centroid": elem.centroid,
                            "area": elem.area,
                        }
                        inst_data["elements"].append(elem_data)
                    
                    obj_data["instances"].append(inst_data)
                
                data["objects"].append(obj_data)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting data: {e}")
            return False
    
    def export_bom(self, path: str, pages: List[PageTab]) -> bool:
        """
        Export a Bill of Materials from all pages.
        
        Args:
            path: Output path
            pages: List of pages
            
        Returns:
            True if successful
        """
        try:
            bom = {
                "title": "Bill of Materials",
                "items": [],
            }
            
            # Collect unique objects
            seen = set()
            
            for page in pages:
                for obj in page.objects:
                    if obj.name in seen:
                        continue
                    seen.add(obj.name)
                    
                    item = {
                        "name": obj.name,
                        "category": obj.category,
                        "material": obj.attributes.material,
                        "type": obj.attributes.obj_type,
                        "quantity": obj.attributes.quantity,
                        "size": obj.attributes.size_string,
                        "description": obj.attributes.description,
                    }
                    bom["items"].append(item)
            
            # Sort by category then name
            bom["items"].sort(key=lambda x: (x["category"], x["name"]))
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(bom, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting BOM: {e}")
            return False


