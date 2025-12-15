"""
Main handler for the ingest module.

Orchestrates file ingestion, format detection, and normalization.
"""

import io
import logging
from pathlib import Path
from typing import Optional, Union

import numpy as np
from PIL import Image

from backend.shared.config import get_settings
from backend.shared.models import Job, JobStatus, S3Reference
from backend.shared.s3_client import S3Client, get_s3_client
from backend.ingest.normalizer import ImageNormalizer
from backend.ingest.pdf_processor import PDFProcessor
from backend.ingest.dwg_processor import DWGProcessor

logger = logging.getLogger(__name__)


class IngestHandler:
    """
    Handles file ingestion and normalization.
    
    Supports:
    - PDF: Rasterizes pages at configurable DPI
    - PNG/JPG: Direct image processing
    - DXF: Passes through (already vector format)
    - DWG: Converts to DXF
    """
    
    SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".dxf", ".dwg"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
    
    def __init__(
        self,
        s3_client: Optional[S3Client] = None,
        settings: Optional[any] = None,
    ):
        """
        Initialize ingest handler.
        
        Args:
            s3_client: Optional S3 client override
            settings: Optional settings override
        """
        self.s3_client = s3_client or get_s3_client()
        self.settings = settings or get_settings()
        
        self.normalizer = ImageNormalizer()
        self.pdf_processor = PDFProcessor()
        self.dwg_processor = DWGProcessor()
    
    def process(
        self,
        job: Job,
        input_path: Optional[Union[str, Path]] = None,
        input_bytes: Optional[bytes] = None,
    ) -> Job:
        """
        Process input file for a job.
        
        Either input_path or input_bytes must be provided.
        If neither, attempts to download from job.input.s3_reference.
        
        Args:
            job: Job to process
            input_path: Optional local file path
            input_bytes: Optional file bytes
            
        Returns:
            Updated job with normalized file references
        """
        logger.info(f"Processing job {job.id}")
        
        # Update job status
        job.update_status(JobStatus.INGESTING, "ingesting", 10)
        
        try:
            # Get input data
            if input_bytes is None:
                if input_path:
                    input_bytes = Path(input_path).read_bytes()
                elif job.input and job.input.s3_reference:
                    input_bytes = self.s3_client.download_bytes(
                        job.input.s3_reference.key
                    )
                else:
                    raise ValueError("No input file provided")
            
            # Detect file type
            file_type = self._detect_file_type(
                job.input.file_name if job.input else "unknown",
                input_bytes,
            )
            
            logger.info(f"Detected file type: {file_type}")
            
            # Process based on file type
            if file_type == "pdf":
                result = self._process_pdf(job, input_bytes)
            elif file_type in ("png", "jpg", "jpeg"):
                result = self._process_image(job, input_bytes, file_type)
            elif file_type == "dxf":
                result = self._process_dxf(job, input_bytes)
            elif file_type == "dwg":
                result = self._process_dwg(job, input_bytes)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
            
            # Update job with results
            job.output.normalized_image = result.get("normalized_image")
            job.update_status(JobStatus.INGESTING, "ingestion_complete", 20)
            
            logger.info(f"Ingestion complete for job {job.id}")
            return job
            
        except Exception as e:
            logger.error(f"Ingestion failed for job {job.id}: {e}")
            job.set_error(f"Ingestion failed: {str(e)}")
            raise
    
    def _detect_file_type(self, filename: str, data: bytes) -> str:
        """
        Detect file type from filename and magic bytes.
        
        Args:
            filename: Original filename
            data: File data
            
        Returns:
            File type string (pdf, png, jpg, dxf, dwg)
        """
        # Try extension first
        ext = Path(filename).suffix.lower()
        if ext in self.SUPPORTED_EXTENSIONS:
            return ext.lstrip(".")
        
        # Check magic bytes
        if data[:4] == b"%PDF":
            return "pdf"
        elif data[:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        elif data[:2] == b"\xff\xd8":
            return "jpg"
        elif data[:2] == b"AC":  # AutoCAD DWG
            return "dwg"
        elif b"SECTION" in data[:1000] or b"0\n" in data[:100]:
            return "dxf"
        
        raise ValueError(f"Could not detect file type for: {filename}")
    
    def _process_pdf(self, job: Job, data: bytes) -> dict:
        """
        Process PDF file.
        
        Rasterizes pages and normalizes the result.
        
        Args:
            job: Job being processed
            data: PDF file data
            
        Returns:
            Dictionary with processed file references
        """
        logger.info(f"Processing PDF for job {job.id}")
        
        # Rasterize PDF pages
        images = self.pdf_processor.rasterize(data, dpi=300)
        
        if not images:
            raise ValueError("PDF contains no pages")
        
        # For now, process first page only
        # TODO: Handle multi-page PDFs
        image = images[0]
        
        # Normalize image
        normalized = self.normalizer.normalize(image)
        
        # Save to S3
        normalized_key = S3Client.generate_temp_key(job.id, "normalized.png")
        
        # Convert to bytes
        img_bytes = self._image_to_bytes(normalized)
        
        s3_ref = self.s3_client.upload_bytes(
            img_bytes,
            normalized_key,
            content_type="image/png",
        )
        
        return {"normalized_image": s3_ref}
    
    def _process_image(self, job: Job, data: bytes, file_type: str) -> dict:
        """
        Process image file (PNG/JPG).
        
        Args:
            job: Job being processed
            data: Image file data
            file_type: Image format
            
        Returns:
            Dictionary with processed file references
        """
        logger.info(f"Processing {file_type.upper()} for job {job.id}")
        
        # Load image
        image = Image.open(io.BytesIO(data))
        
        # Convert to numpy array for OpenCV processing
        img_array = np.array(image)
        
        # Normalize
        normalized = self.normalizer.normalize(img_array)
        
        # Save to S3
        normalized_key = S3Client.generate_temp_key(job.id, "normalized.png")
        
        # Convert to bytes
        img_bytes = self._image_to_bytes(normalized)
        
        s3_ref = self.s3_client.upload_bytes(
            img_bytes,
            normalized_key,
            content_type="image/png",
        )
        
        return {"normalized_image": s3_ref}
    
    def _process_dxf(self, job: Job, data: bytes) -> dict:
        """
        Process DXF file.
        
        DXF is already a vector format, so we store it directly
        and optionally render a preview image.
        
        Args:
            job: Job being processed
            data: DXF file data
            
        Returns:
            Dictionary with processed file references
        """
        logger.info(f"Processing DXF for job {job.id}")
        
        # Store original DXF
        dxf_key = S3Client.generate_temp_key(job.id, "input.dxf")
        self.s3_client.upload_bytes(
            data,
            dxf_key,
            content_type="application/dxf",
        )
        
        # Render preview image from DXF
        preview_image = self._render_dxf_preview(data)
        
        if preview_image is not None:
            normalized = self.normalizer.normalize(preview_image)
            normalized_key = S3Client.generate_temp_key(job.id, "normalized.png")
            
            img_bytes = self._image_to_bytes(normalized)
            s3_ref = self.s3_client.upload_bytes(
                img_bytes,
                normalized_key,
                content_type="image/png",
            )
            
            return {"normalized_image": s3_ref}
        
        return {}
    
    def _process_dwg(self, job: Job, data: bytes) -> dict:
        """
        Process DWG file.
        
        Converts DWG to DXF, then processes as DXF.
        
        Args:
            job: Job being processed
            data: DWG file data
            
        Returns:
            Dictionary with processed file references
        """
        logger.info(f"Processing DWG for job {job.id}")
        
        # Convert DWG to DXF
        dxf_data = self.dwg_processor.convert_to_dxf(data)
        
        # Process as DXF
        return self._process_dxf(job, dxf_data)
    
    def _render_dxf_preview(self, data: bytes) -> Optional[np.ndarray]:
        """
        Render a preview image from DXF data.
        
        Args:
            data: DXF file data
            
        Returns:
            Preview image as numpy array, or None if rendering fails
        """
        try:
            import ezdxf
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import matplotlib.pyplot as plt
            
            # Parse DXF
            doc = ezdxf.read(io.BytesIO(data))
            msp = doc.modelspace()
            
            # Create figure
            fig, ax = plt.subplots(figsize=(20, 20), dpi=150)
            ax.set_aspect("equal")
            
            # Render
            ctx = RenderContext(doc)
            out = MatplotlibBackend(ax)
            Frontend(ctx, out).draw_layout(msp)
            
            # Convert to image
            fig.canvas.draw()
            img_array = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
            img_array = img_array.reshape(fig.canvas.get_width_height()[::-1] + (3,))
            
            plt.close(fig)
            
            return img_array
            
        except Exception as e:
            logger.warning(f"Failed to render DXF preview: {e}")
            return None
    
    def _image_to_bytes(self, image: np.ndarray, format: str = "PNG") -> bytes:
        """
        Convert numpy image array to bytes.
        
        Args:
            image: Image as numpy array
            format: Output format (PNG, JPEG)
            
        Returns:
            Image as bytes
        """
        pil_image = Image.fromarray(image)
        
        buffer = io.BytesIO()
        pil_image.save(buffer, format=format)
        buffer.seek(0)
        
        return buffer.read()


# Lambda handler entry point
def lambda_handler(event: dict, context: any) -> dict:
    """
    AWS Lambda entry point for ingest function.
    
    Args:
        event: Lambda event with job_id and optional input data
        context: Lambda context
        
    Returns:
        Result dictionary with status and output references
    """
    from backend.shared.dynamo_client import get_dynamo_client
    
    job_id = event.get("job_id")
    if not job_id:
        return {"status": "error", "message": "Missing job_id"}
    
    dynamo = get_dynamo_client()
    job = dynamo.get_job(job_id)
    
    if not job:
        return {"status": "error", "message": f"Job not found: {job_id}"}
    
    handler = IngestHandler()
    
    try:
        job = handler.process(job)
        dynamo.update_job(job)
        
        return {
            "status": "success",
            "job_id": job.id,
            "normalized_image": job.output.normalized_image.key if job.output.normalized_image else None,
        }
        
    except Exception as e:
        job.set_error(str(e))
        dynamo.update_job(job)
        
        return {
            "status": "error",
            "job_id": job.id,
            "message": str(e),
        }


