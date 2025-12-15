"""
DWG processing for PlanMod.

Handles DWG to DXF conversion.
"""

import io
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DWGProcessor:
    """
    Processes DWG files for the ingestion pipeline.
    
    DWG is a proprietary AutoCAD format. This processor
    converts DWG to DXF for further processing.
    
    Conversion methods (in order of preference):
    1. ODA File Converter (if available)
    2. LibreDWG (if available)
    3. Fallback to ezdxf (limited support)
    """
    
    def __init__(self, oda_converter_path: Optional[str] = None):
        """
        Initialize DWG processor.
        
        Args:
            oda_converter_path: Path to ODA File Converter executable
        """
        self.oda_converter_path = oda_converter_path
        self._converter_available: Optional[bool] = None
    
    def convert_to_dxf(self, dwg_data: bytes) -> bytes:
        """
        Convert DWG to DXF format.
        
        Args:
            dwg_data: DWG file as bytes
            
        Returns:
            DXF file as bytes
        """
        logger.info("Converting DWG to DXF")
        
        # Try ODA converter first
        if self._check_oda_converter():
            try:
                return self._convert_with_oda(dwg_data)
            except Exception as e:
                logger.warning(f"ODA conversion failed: {e}")
        
        # Try LibreDWG
        if self._check_libredwg():
            try:
                return self._convert_with_libredwg(dwg_data)
            except Exception as e:
                logger.warning(f"LibreDWG conversion failed: {e}")
        
        # Try ezdxf (very limited support)
        try:
            return self._convert_with_ezdxf(dwg_data)
        except Exception as e:
            logger.warning(f"ezdxf conversion failed: {e}")
        
        raise RuntimeError(
            "DWG conversion failed. Please install ODA File Converter or LibreDWG. "
            "Alternatively, convert the DWG file to DXF manually before uploading."
        )
    
    def _check_oda_converter(self) -> bool:
        """Check if ODA File Converter is available."""
        if self._converter_available is not None:
            return self._converter_available
        
        if self.oda_converter_path:
            self._converter_available = Path(self.oda_converter_path).exists()
        else:
            # Check common locations
            common_paths = [
                "/opt/ODAFileConverter/ODAFileConverter",
                "C:\\Program Files\\ODA\\ODAFileConverter\\ODAFileConverter.exe",
                "/usr/local/bin/ODAFileConverter",
            ]
            
            for path in common_paths:
                if Path(path).exists():
                    self.oda_converter_path = path
                    self._converter_available = True
                    return True
            
            self._converter_available = False
        
        return self._converter_available
    
    def _check_libredwg(self) -> bool:
        """Check if LibreDWG is available."""
        try:
            result = subprocess.run(
                ["dwg2dxf", "--version"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _convert_with_oda(self, dwg_data: bytes) -> bytes:
        """
        Convert DWG using ODA File Converter.
        
        Args:
            dwg_data: DWG file as bytes
            
        Returns:
            DXF file as bytes
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir) / "input"
            output_dir = Path(tmpdir) / "output"
            input_dir.mkdir()
            output_dir.mkdir()
            
            # Write input file
            input_file = input_dir / "input.dwg"
            input_file.write_bytes(dwg_data)
            
            # Run ODA converter
            # ODA File Converter args: input_folder output_folder output_version output_format recurse audit
            result = subprocess.run(
                [
                    self.oda_converter_path,
                    str(input_dir),
                    str(output_dir),
                    "ACAD2018",  # Output version
                    "DXF",  # Output format
                    "0",  # Don't recurse
                    "1",  # Audit
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"ODA conversion failed: {result.stderr}")
            
            # Read output file
            output_file = output_dir / "input.dxf"
            if not output_file.exists():
                raise RuntimeError("ODA converter did not produce output file")
            
            return output_file.read_bytes()
    
    def _convert_with_libredwg(self, dwg_data: bytes) -> bytes:
        """
        Convert DWG using LibreDWG's dwg2dxf.
        
        Args:
            dwg_data: DWG file as bytes
            
        Returns:
            DXF file as bytes
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.dwg"
            output_file = Path(tmpdir) / "output.dxf"
            
            input_file.write_bytes(dwg_data)
            
            result = subprocess.run(
                ["dwg2dxf", "-o", str(output_file), str(input_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"LibreDWG conversion failed: {result.stderr}")
            
            if not output_file.exists():
                raise RuntimeError("LibreDWG did not produce output file")
            
            return output_file.read_bytes()
    
    def _convert_with_ezdxf(self, dwg_data: bytes) -> bytes:
        """
        Attempt conversion using ezdxf (very limited support).
        
        Note: ezdxf has very limited DWG support and may not
        work for most files.
        
        Args:
            dwg_data: DWG file as bytes
            
        Returns:
            DXF file as bytes
        """
        import ezdxf
        
        # ezdxf can read some DWG files directly
        with io.BytesIO(dwg_data) as stream:
            try:
                doc = ezdxf.read(stream)
            except Exception as e:
                raise RuntimeError(
                    f"ezdxf cannot read this DWG file: {e}. "
                    "Please install ODA File Converter for full DWG support."
                )
        
        # Write as DXF
        output = io.BytesIO()
        doc.write(output)
        output.seek(0)
        
        return output.read()
    
    def get_dwg_version(self, dwg_data: bytes) -> Optional[str]:
        """
        Get the AutoCAD version of a DWG file.
        
        Args:
            dwg_data: DWG file as bytes
            
        Returns:
            Version string or None
        """
        # DWG version is in first 6 bytes
        version_bytes = dwg_data[:6].decode("ascii", errors="ignore")
        
        version_map = {
            "AC1015": "AutoCAD 2000",
            "AC1018": "AutoCAD 2004",
            "AC1021": "AutoCAD 2007",
            "AC1024": "AutoCAD 2010",
            "AC1027": "AutoCAD 2013",
            "AC1032": "AutoCAD 2018",
        }
        
        return version_map.get(version_bytes, f"Unknown ({version_bytes})")


