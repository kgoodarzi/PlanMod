"""
PlanMod Interactive Segmenter v5.0

A modular, professional-grade tool for annotating and segmenting 
model aircraft plans and technical drawings.

Usage:
    python -m tools.segmenter
    
Or:
    from tools.segmenter import main
    main()
"""

__version__ = "5.0.0"
__author__ = "PlanMod Team"

from tools.segmenter.app import SegmenterApp


def main():
    """Launch the segmenter application."""
    app = SegmenterApp()
    app.run()


__all__ = ["SegmenterApp", "main", "__version__"]


