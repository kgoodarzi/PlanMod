"""
FastAPI server for PlanMod API.

Provides REST endpoints for:
- Job creation and management
- File upload
- Scene graph inspection
- Component substitution
- Result download
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.shared.config import get_settings
from backend.shared.models import (
    Job,
    JobStatus,
    JobInput,
    CreateJobRequest,
    CreateJobResponse,
    JobStatusResponse,
    SubstitutionRequest,
    SubstitutionResponse,
    SubstitutionRule,
    S3Reference,
)
from backend.shared.s3_client import S3Client, get_s3_client
from backend.shared.dynamo_client import DynamoDBClient, get_dynamo_client
from backend.orchestration import OrchestrationHandler
from backend.scene_graph import SceneGraphHandler

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="PlanMod API",
        description="Drawing to DXF conversion pipeline with AI-powered component recognition",
        version="0.1.0",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


# Request/Response models
class UploadResponse(BaseModel):
    job_id: str
    status: str
    message: str


class SceneGraphResponse(BaseModel):
    job_id: str
    scene_graph_id: str
    views: list
    components: list
    visualization_url: Optional[str] = None


class ComponentListResponse(BaseModel):
    categories: list
    components: list


# Background task for processing
async def process_job_background(job_id: str):
    """Background task to process a job."""
    dynamo = get_dynamo_client()
    job = dynamo.get_job(job_id)
    
    if not job:
        logger.error(f"Job not found for background processing: {job_id}")
        return
    
    handler = OrchestrationHandler()
    
    try:
        await handler.process_job(job)
    except Exception as e:
        logger.error(f"Background job processing failed: {e}")
        job.set_error(str(e))
        dynamo.update_job(job)


# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "PlanMod API", "version": "0.1.0"}


@app.post("/jobs", response_model=CreateJobResponse)
async def create_job(request: CreateJobRequest):
    """
    Create a new processing job.
    
    Returns a pre-signed URL for uploading the input file.
    """
    settings = get_settings()
    s3 = get_s3_client()
    dynamo = get_dynamo_client()
    
    # Create job
    job = Job(
        input=JobInput(
            file_name=request.file_name,
            file_type=request.file_type,
            file_size=0,
        )
    )
    
    # Generate upload URL
    upload_key = S3Client.generate_upload_key(job.id, request.file_name)
    upload_url = s3.generate_presigned_upload_url(upload_key)
    
    # Set S3 reference
    job.input.s3_reference = S3Reference(
        bucket=s3.bucket_name,
        key=upload_key,
    )
    
    # Save job
    dynamo.create_job(job)
    
    return CreateJobResponse(
        job_id=job.id,
        upload_url=upload_url,
        status=job.status,
    )


@app.post("/jobs/{job_id}/upload")
async def upload_file(
    job_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Direct file upload endpoint.
    
    Alternative to pre-signed URL upload.
    """
    dynamo = get_dynamo_client()
    s3 = get_s3_client()
    
    job = dynamo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Read file
    content = await file.read()
    
    # Upload to S3
    upload_key = S3Client.generate_upload_key(job_id, file.filename)
    s3.upload_bytes(content, upload_key)
    
    # Update job
    job.input = JobInput(
        file_name=file.filename,
        file_type=file.filename.split(".")[-1].lower(),
        file_size=len(content),
        s3_reference=S3Reference(bucket=s3.bucket_name, key=upload_key),
    )
    job.update_status(JobStatus.UPLOADING, "file_uploaded", 5)
    dynamo.update_job(job)
    
    # Start processing in background
    if background_tasks:
        background_tasks.add_task(process_job_background, job_id)
    
    return UploadResponse(
        job_id=job_id,
        status="uploaded",
        message=f"File {file.filename} uploaded successfully. Processing started.",
    )


@app.post("/jobs/{job_id}/process")
async def start_processing(job_id: str, background_tasks: BackgroundTasks):
    """Start processing a job."""
    dynamo = get_dynamo_client()
    
    job = dynamo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in (JobStatus.PENDING, JobStatus.UPLOADING):
        raise HTTPException(
            status_code=400,
            detail=f"Job is already {job.status.value}",
        )
    
    # Start background processing
    background_tasks.add_task(process_job_background, job_id)
    
    return {"job_id": job_id, "status": "processing_started"}


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get job status and progress."""
    dynamo = get_dynamo_client()
    
    job = dynamo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        current_stage=job.current_stage,
        progress_percent=job.progress_percent,
        error_message=job.error_message,
    )


@app.get("/jobs/{job_id}/scene-graph")
async def get_scene_graph(job_id: str):
    """Get the scene graph for a job."""
    dynamo = get_dynamo_client()
    s3 = get_s3_client()
    
    job = dynamo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.scene_graph_id:
        raise HTTPException(status_code=404, detail="Scene graph not available yet")
    
    scene_graph = dynamo.get_scene_graph(job.scene_graph_id)
    if not scene_graph:
        raise HTTPException(status_code=404, detail="Scene graph not found")
    
    # Generate visualization URL if available
    vis_url = None
    if job.output.scene_graph_image:
        vis_url = s3.generate_presigned_download_url(
            job.output.scene_graph_image.key,
            expires_in=3600,
        )
    
    return SceneGraphResponse(
        job_id=job_id,
        scene_graph_id=scene_graph.id,
        views=[
            {
                "id": v.id,
                "name": v.name,
                "type": v.view_type.value,
                "confidence": v.classification_confidence,
            }
            for v in scene_graph.views
        ],
        components=[
            {
                "id": c.id,
                "name": c.name,
                "type": c.component_type.value,
                "confidence": c.classification_confidence,
            }
            for c in scene_graph.components
        ],
        visualization_url=vis_url,
    )


@app.post("/jobs/{job_id}/substitute", response_model=SubstitutionResponse)
async def apply_substitutions(
    job_id: str,
    request: SubstitutionRequest,
    background_tasks: BackgroundTasks,
):
    """Apply component substitutions and regenerate DXF."""
    dynamo = get_dynamo_client()
    
    job = dynamo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail="Job must be complete before applying substitutions",
        )
    
    # Update job with substitution rules
    job.substitution_rules = request.rules
    job.status = JobStatus.TRANSFORMING
    dynamo.update_job(job)
    
    # Process substitutions in background
    async def apply_subs():
        from backend.transform import TransformHandler
        
        scene_graph = dynamo.get_scene_graph_by_job(job_id)
        handler = TransformHandler()
        handler.transform(job, scene_graph, request.rules)
        dynamo.update_job(job)
    
    background_tasks.add_task(apply_subs)
    
    return SubstitutionResponse(
        job_id=job_id,
        status=JobStatus.TRANSFORMING,
    )


@app.get("/jobs/{job_id}/download/{file_type}")
async def download_output(job_id: str, file_type: str):
    """
    Download output files.
    
    file_type: base_dxf, final_dxf, scene_graph, report, visualization
    """
    dynamo = get_dynamo_client()
    s3 = get_s3_client()
    
    job = dynamo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Map file type to output reference
    file_map = {
        "base_dxf": job.output.base_dxf,
        "final_dxf": job.output.final_dxf,
        "scene_graph": job.output.scene_graph_json,
        "report": job.output.report,
        "visualization": job.output.scene_graph_image,
    }
    
    ref = file_map.get(file_type)
    if not ref:
        raise HTTPException(status_code=404, detail=f"File type '{file_type}' not available")
    
    # Generate download URL
    filename = ref.key.split("/")[-1]
    download_url = s3.generate_presigned_download_url(ref.key, filename=filename)
    
    return {"download_url": download_url, "filename": filename}


@app.get("/components", response_model=ComponentListResponse)
async def list_components(
    category: Optional[str] = None,
    component_type: Optional[str] = None,
):
    """List available components in the catalog."""
    from backend.component_db import ComponentCatalog
    
    catalog = ComponentCatalog()
    
    components = catalog.search(
        category=category,
        component_type=component_type,
    )
    
    # Get unique categories
    categories = list(set(c.category for c in catalog.components.values()))
    
    return ComponentListResponse(
        categories=categories,
        components=[
            {
                "id": c.id,
                "name": c.name,
                "type": c.component_type,
                "category": c.category,
                "material": c.material,
            }
            for c in components[:100]  # Limit results
        ],
    )


@app.get("/jobs")
async def list_jobs(status: Optional[str] = None, limit: int = 20):
    """List recent jobs."""
    dynamo = get_dynamo_client()
    
    status_filter = JobStatus(status) if status else None
    jobs = dynamo.list_jobs(status=status_filter, limit=limit)
    
    return {
        "jobs": [
            {
                "id": j.id,
                "status": j.status.value,
                "current_stage": j.current_stage,
                "created_at": j.created_at.isoformat(),
                "input_file": j.input.file_name if j.input else None,
            }
            for j in jobs
        ]
    }


def main():
    """Run the API server."""
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "backend.api.server:app",
        host="0.0.0.0",
        port=settings.local.api_port,
        reload=settings.local.debug,
    )


if __name__ == "__main__":
    main()


