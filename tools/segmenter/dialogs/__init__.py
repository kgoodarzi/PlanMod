"""Dialog windows for the segmenter."""

from tools.segmenter.dialogs.pdf_loader import PDFLoaderDialog
from tools.segmenter.dialogs.label_scan import LabelScanDialog
from tools.segmenter.dialogs.attributes import AttributeDialog
from tools.segmenter.dialogs.settings import SettingsDialog
from tools.segmenter.dialogs.rectangle_selection import RectangleSelectionDialog

__all__ = [
    "PDFLoaderDialog",
    "LabelScanDialog", 
    "AttributeDialog",
    "SettingsDialog",
    "RectangleSelectionDialog",
]


