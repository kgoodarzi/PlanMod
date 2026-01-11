# Planform Boundary Check Improvements

This document lists potential improvements to the planform boundary checking logic based on analysis of the workspace file.

## Issues Identified

### 1. **planform_objects Not Persisted**
- **Problem**: The `planform_objects` dictionary is not saved to the workspace file, so when a workspace is loaded, this data is lost.
- **Impact**: When creating a view from a planform, the system falls back to `_find_objects_within_planform`, which may use incorrect logic or stale data.
- **Solution**: Save `planform_objects` to the workspace file so it persists across sessions.

### 2. **Mask Recreation from Points May Be Inaccurate**
- **Problem**: When recreating the planform mask from polyline points, the mask may not exactly match the original mask used during planform creation.
- **Impact**: Objects that were correctly identified during creation may be incorrectly identified when copying to a new view.
- **Solution**: Store the original planform mask in the workspace file, or ensure mask recreation is pixel-perfect.

### 3. **Bounding Box Pre-check May Be Too Permissive**
- **Problem**: The bounding box pre-check in `_find_objects_within_planform` filters objects, but if the planform has a complex shape (e.g., L-shaped), many objects outside the polyline may still have overlapping bounding boxes.
- **Impact**: Objects outside the polyline may pass the bounding box check and then incorrectly pass the pixel overlap check due to edge cases.
- **Solution**: Use a more sophisticated pre-check, such as checking if the object's centroid is within the planform, or using a tighter bounding box approximation.

### 4. **ROI Overlap Check May Have Edge Cases**
- **Problem**: The ROI (Region of Interest) overlap check uses `roi_x_min = max(0, min(elem_x_min, planform_x_min))`, which may not correctly handle all edge cases, especially when objects are partially outside the image bounds.
- **Impact**: Incorrect pixel overlap calculations for objects near image boundaries.
- **Solution**: Ensure ROI bounds are correctly calculated and handle edge cases explicitly.

### 5. **Visibility Check May Not Be Applied Consistently**
- **Problem**: The visibility check in `_find_objects_within_planform` checks `cat.visible`, but this may not be applied when using stored `planform_objects`.
- **Impact**: Objects from invisible categories may be included in the stored list and copied to new views.
- **Solution**: Re-validate visibility when using stored `planform_objects`, or ensure visibility is checked when storing the list.

### 6. **Pixel Overlap Threshold**
- **Problem**: The current logic uses "any overlap" (`pixels_overlap > 0`) to determine if an object is inside the planform. This may include objects that only touch the boundary by a single pixel.
- **Impact**: Objects that are essentially outside the planform may be included if they have minimal boundary contact.
- **Solution**: Consider using a minimum overlap threshold (e.g., 1% of object pixels) or a minimum pixel count (e.g., 10 pixels) to be considered "inside".

### 7. **Element-Level vs Object-Level Overlap**
- **Problem**: The logic checks element-level overlap, but an object is considered "inside" if ANY element overlaps. This may include objects where only a small part overlaps.
- **Impact**: Objects that are mostly outside the planform may be included if a small element overlaps.
- **Solution**: Consider requiring a minimum percentage of the object's total pixels to overlap, or require all elements to have some overlap.

### 8. **Mask Filtering During Copy May Not Be Complete**
- **Problem**: During copy, element masks are filtered to the planform polyline, but if the stored mask is incorrect or the planform mask is recreated incorrectly, filtering may not work as expected.
- **Impact**: Objects copied to new views may include pixels outside the planform boundary.
- **Solution**: Double-check that filtered masks are correct, and add validation to ensure no pixels outside the planform are included.

### 9. **Point Filtering May Miss Edge Cases**
- **Problem**: Point filtering checks if points are within the bounding box and planform mask, but points may be on the boundary or slightly outside due to rounding.
- **Impact**: Some points may be incorrectly included or excluded.
- **Solution**: Use a small tolerance for point-in-polygon checks, or use a more robust point-in-polygon algorithm.

### 10. **Deferred Execution May Cause Stale Data**
- **Problem**: `_find_objects_within_planform` is deferred when a planform is created, which means it may run after objects have been added, removed, or modified.
- **Impact**: The stored `planform_objects` list may become stale if objects are modified after planform creation.
- **Solution**: Re-validate the stored list when it's used, or update it when objects are modified.

## Recommended Improvements (Priority Order)

### High Priority

1. **Save planform_objects to workspace file**
   - Modify `WorkspaceManager.save()` to include `planform_objects` in the saved data
   - Modify `WorkspaceManager.load()` to restore `planform_objects` from the saved data
   - This ensures consistency between creation and copy operations

2. **Store original planform mask in workspace**
   - Save the original planform mask (or a hash) when the planform is created
   - Use this stored mask when copying to new views instead of recreating from points
   - This ensures pixel-perfect accuracy

3. **Re-validate stored planform_objects when used**
   - When using stored `planform_objects`, re-check visibility and actual overlap
   - Remove objects that no longer overlap or are now invisible
   - This prevents stale data from causing incorrect copies

### Medium Priority

4. **Improve bounding box pre-check**
   - Use object centroid check in addition to bounding box overlap
   - For complex planform shapes, use a tighter approximation (e.g., convex hull)
   - This reduces false positives in the pre-check phase

5. **Add minimum overlap threshold**
   - Require at least 1% of object pixels to overlap with planform
   - Or require at least 10 pixels of overlap
   - This prevents objects that only touch the boundary from being included

6. **Fix ROI calculation edge cases**
   - Explicitly handle cases where objects are partially outside image bounds
   - Ensure ROI bounds are always valid (non-negative, within image dimensions)
   - This prevents incorrect pixel overlap calculations

### Low Priority

7. **Improve point filtering**
   - Use a small tolerance (e.g., 1 pixel) for point-in-polygon checks
   - Use a more robust point-in-polygon algorithm (e.g., ray casting)
   - This ensures points on boundaries are handled correctly

8. **Add validation during copy**
   - After filtering element masks, verify no pixels outside planform are included
   - Log warnings if validation fails
   - This helps catch issues early

9. **Update planform_objects when objects change**
   - When objects are modified, check if they affect any planform's stored list
   - Update the stored list if needed
   - This keeps stored data in sync with actual object state

10. **Add debug visualization**
    - Create a visualization mode that shows which objects are considered "inside" a planform
    - Highlight objects that pass/fail each check (bounding box, pixel overlap, etc.)
    - This helps debug boundary checking issues

## Testing Recommendations

1. **Create test cases with various planform shapes**
   - Simple rectangle
   - L-shaped planform
   - U-shaped planform
   - Complex polyline with many points
   - Planform with holes (if supported)

2. **Test edge cases**
   - Objects exactly on the boundary
   - Objects partially overlapping
   - Objects with elements both inside and outside
   - Objects from invisible categories
   - Objects added after planform creation

3. **Test workspace save/load**
   - Create planform, save workspace, load workspace, create view
   - Verify that the same objects are included in the view
   - This ensures persistence works correctly

4. **Performance testing**
   - Test with large numbers of objects (100+)
   - Test with large planform masks
   - Measure time for `_find_objects_within_planform`
   - Ensure deferred execution doesn't cause UI freezes
