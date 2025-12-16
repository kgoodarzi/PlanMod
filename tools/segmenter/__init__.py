"""
PlanMod Interactive Segmenter v5.0

A modular, professional-grade tool for annotating and segmenting 
model aircraft plans and technical drawings.

Usage:
    python -m tools.segmenter
    python -m tools.segmenter --workspace path/to/workspace.pmw
    python -m tools.segmenter --pdf path/to/file.pdf
    
Or:
    from tools.segmenter import main
    main()
"""

import argparse

__version__ = "5.0.0"
__author__ = "PlanMod Team"

from tools.segmenter.app import SegmenterApp


def main():
    """Launch the segmenter application with optional file to open."""
    parser = argparse.ArgumentParser(
        description="PlanMod Interactive Segmenter - Annotate and segment technical drawings"
    )
    parser.add_argument(
        "--workspace", "-w",
        type=str,
        help="Path to workspace file (.pmw) to open on startup"
    )
    parser.add_argument(
        "--pdf", "-p",
        type=str,
        help="Path to PDF file to open on startup"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"PlanMod Segmenter {__version__}"
    )
    
    args = parser.parse_args()
    
    app = SegmenterApp(
        startup_workspace=args.workspace,
        startup_pdf=args.pdf
    )
    app.run()


__all__ = ["SegmenterApp", "main", "__version__"]


