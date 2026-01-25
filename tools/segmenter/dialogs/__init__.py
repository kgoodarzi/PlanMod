"""Dialog windows for the segmenter."""

from tools.segmenter.dialogs.pdf_loader import PDFLoaderDialog
from tools.segmenter.dialogs.label_scan import LabelScanDialog
from tools.segmenter.dialogs.attributes import AttributeDialog
from tools.segmenter.dialogs.settings import SettingsDialog
from tools.segmenter.dialogs.rectangle_selection import RectangleSelectionDialog
from tools.segmenter.dialogs.delete_object import DeleteObjectDialog
from tools.segmenter.dialogs.page_selection import PageSelectionDialog
from tools.segmenter.dialogs.nesting import NestingConfigDialog, SheetSize, MaterialGroup
from tools.segmenter.dialogs.nesting_results import NestingResultsDialog

__all__ = [
    "PDFLoaderDialog",
    "LabelScanDialog",
    "AttributeDialog",
    "SettingsDialog",
    "RectangleSelectionDialog",
    "DeleteObjectDialog",
    "PageSelectionDialog",
    "NestingConfigDialog",
    "NestingResultsDialog",
    "SheetSize",
    "MaterialGroup",
]


