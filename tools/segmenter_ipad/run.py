#!/usr/bin/env python3
"""
PlanMod iPad Segmenter - Run Script

This script handles the import path issues when running on iPad/Pyto.
Simply open this file in Pyto and tap the Play button.

Works on:
- Pyto (iOS)
- Pythonista (iOS)
- Desktop Python (for testing)
"""

import sys
import os

def setup_paths():
    """Set up Python paths for imports to work correctly."""
    # Get the directory containing this script
    if '__file__' in dir():
        script_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        # Fallback for some iOS environments
        script_dir = os.getcwd()
    
    # Add necessary paths
    paths_to_add = [
        script_dir,  # segmenter_ipad folder
        os.path.dirname(script_dir),  # tools folder
        os.path.dirname(os.path.dirname(script_dir)),  # PlanMod root
    ]
    
    for path in paths_to_add:
        if path and path not in sys.path:
            sys.path.insert(0, path)
    
    return script_dir

def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []
    
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")
    
    if missing:
        print("=" * 50)
        print("Missing dependencies!")
        print("Please install them in Pyto's terminal:")
        print()
        for pkg in missing:
            print(f"  pip install {pkg}")
        print()
        print("Then run this script again.")
        print("=" * 50)
        return False
    
    return True

def run_app():
    """Run the iPad Segmenter app."""
    print("=" * 50)
    print("PlanMod iPad Segmenter")
    print("=" * 50)
    print()
    
    # Set up import paths
    script_dir = setup_paths()
    print(f"Running from: {script_dir}")
    
    # Check dependencies
    if not check_dependencies():
        return
    
    print("Dependencies OK")
    print()
    
    # Try to import and run the main app
    try:
        # First try relative imports (when in segmenter_ipad folder)
        try:
            from config import load_settings, save_settings, get_theme, AppSettings
            from models import (
                PageTab, SegmentedObject, ObjectInstance, SegmentElement,
                DynamicCategory, create_default_categories, get_next_color
            )
            from core import SegmentationEngine, Renderer
            # Note: 'io' conflicts with built-in, so import specifically
            from io import WorkspaceManager, ImageExporter, DataExporter
            from services import PDFService, OCRService
            print("Using local imports")
        except ImportError as e:
            # Fall back to full path
            from tools.segmenter_ipad.config import load_settings, save_settings, get_theme, AppSettings
            from tools.segmenter_ipad.models import (
                PageTab, SegmentedObject, ObjectInstance, SegmentElement,
                DynamicCategory, create_default_categories, get_next_color
            )
            from tools.segmenter_ipad.core import SegmentationEngine, Renderer
            from tools.segmenter_ipad.io import WorkspaceManager, ImageExporter, DataExporter
            from tools.segmenter_ipad.services import PDFService, OCRService
            print("Using full path imports")
        
        # Check for Pyto UI
        try:
            import pyto_ui as ui
            print("Pyto UI available - launching graphical interface...")
            print()
            
            # Import and run the main app with UI
            try:
                from main import SegmenterApp, create_pyto_ui
            except ImportError:
                from tools.segmenter_ipad.main import SegmenterApp, create_pyto_ui
            
            app = SegmenterApp()
            main_view = create_pyto_ui(app)
            main_view.present()
            
        except ImportError:
            # No Pyto UI - run in console mode
            print("Pyto UI not available - running in console mode")
            print()
            run_console_mode()
            
    except Exception as e:
        print(f"Error starting app: {e}")
        print()
        import traceback
        traceback.print_exc()
        print()
        print("Falling back to console mode...")
        run_console_mode()

def run_console_mode():
    """Run in console mode for testing."""
    print()
    print("Console Mode")
    print("-" * 40)
    print()
    print("Available commands:")
    print("  load <path>   - Load an image or PDF")
    print("  save <path>   - Save workspace")
    print("  open <path>   - Open workspace")
    print("  info          - Show current state")
    print("  help          - Show this help")
    print("  quit          - Exit")
    print()
    
    # Try to create the app
    try:
        try:
            from main import SegmenterApp
        except ImportError:
            from tools.segmenter_ipad.main import SegmenterApp
        
        app = SegmenterApp()
        print("App initialized successfully!")
        print(f"Categories: {len(app.categories)}")
        print()
        
    except Exception as e:
        print(f"Could not initialize app: {e}")
        app = None
    
    # Simple command loop
    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if not cmd:
            continue
        
        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        if action in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        elif action == "help":
            print("Commands: load, save, open, info, quit")
        elif action == "info":
            if app:
                print(f"Pages: {len(app.pages)}")
                print(f"Objects: {len(app.all_objects)}")
                print(f"Categories: {len(app.categories)}")
            else:
                print("App not initialized")
        elif action == "load":
            if app and arg:
                if arg.lower().endswith('.pdf'):
                    success = app.load_pdf(arg)
                else:
                    success = app.load_image(arg)
                print("Loaded!" if success else "Failed to load")
            else:
                print("Usage: load <filepath>")
        elif action == "save":
            if app and arg:
                success = app.save_workspace(arg)
                print("Saved!" if success else "Failed to save")
            else:
                print("Usage: save <filepath>")
        elif action == "open":
            if app and arg:
                success = app.load_workspace(arg)
                print("Opened!" if success else "Failed to open")
            else:
                print("Usage: open <filepath>")
        else:
            print(f"Unknown command: {action}")
            print("Type 'help' for available commands")

# Entry point
if __name__ == "__main__":
    run_app()
else:
    # Also run when imported (for Pyto's "Run" button behavior)
    run_app()

