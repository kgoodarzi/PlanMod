"""
Main handler for transform module.
"""

import io
import logging
from typing import Any, Optional

from backend.shared.config import get_settings
from backend.shared.models import Job, JobStatus, SceneGraph, S3Reference, SubstitutionRule
from backend.shared.s3_client import S3Client, get_s3_client
from backend.shared.dynamo_client import get_dynamo_client
from backend.transform.substitution_engine import SubstitutionEngine
from backend.transform.geometry_modifier import GeometryModifier
from backend.transform.mass_calculator import MassCalculator
from backend.component_db import ComponentCatalog

logger = logging.getLogger(__name__)


class TransformHandler:
    """
    Main handler for DXF transformations.
    
    Applies component substitutions and generates final DXF.
    """
    
    def __init__(
        self,
        s3_client: Optional[S3Client] = None,
        settings: Optional[Any] = None,
    ):
        self.s3_client = s3_client or get_s3_client()
        self.settings = settings or get_settings()
        
        self.catalog = ComponentCatalog()
        self.substitution_engine = SubstitutionEngine(self.catalog)
        self.geometry_modifier = GeometryModifier()
        self.mass_calculator = MassCalculator(self.catalog)
    
    def transform(
        self,
        job: Job,
        scene_graph: SceneGraph,
        rules: Optional[list[SubstitutionRule]] = None,
    ) -> Job:
        """
        Apply transformations to generate final DXF.
        
        Args:
            job: Associated job
            scene_graph: Scene graph with components
            rules: Substitution rules to apply
            
        Returns:
            Updated job with final DXF
        """
        logger.info(f"Transforming DXF for job {job.id}")
        
        job.update_status(JobStatus.TRANSFORMING, "applying_substitutions", 92)
        
        # Get rules from job if not provided
        rules = rules or job.substitution_rules
        
        # Load base DXF
        if not job.output.base_dxf:
            raise ValueError("No base DXF to transform")
        
        dxf_bytes = self.s3_client.download_bytes(job.output.base_dxf.key)
        
        # Apply substitutions
        if rules:
            logger.info(f"Applying {len(rules)} substitution rules")
            dxf_bytes, scene_graph = self.substitution_engine.apply_rules(
                dxf_bytes,
                scene_graph,
                rules,
            )
        
        # Calculate mass and CG
        job.update_status(JobStatus.TRANSFORMING, "calculating_mass", 95)
        
        mass_result = self.mass_calculator.calculate(scene_graph)
        job.mass_kg = mass_result.get("total_mass_kg", 0)
        
        if "center_of_gravity" in mass_result:
            from backend.shared.models import Point2D
            cg = mass_result["center_of_gravity"]
            job.center_of_gravity = Point2D(x=cg[0], y=cg[1])
        
        # Upload final DXF
        final_key = S3Client.generate_output_key(job.id, "final.dxf")
        self.s3_client.upload_bytes(
            dxf_bytes,
            final_key,
            content_type="application/dxf",
        )
        
        job.output.final_dxf = S3Reference(
            bucket=self.s3_client.bucket_name,
            key=final_key,
        )
        
        # Generate report
        report = self._generate_report(job, scene_graph, rules or [])
        report_key = S3Client.generate_output_key(job.id, "report.md")
        self.s3_client.upload_bytes(
            report.encode("utf-8"),
            report_key,
            content_type="text/markdown",
        )
        
        job.output.report = S3Reference(
            bucket=self.s3_client.bucket_name,
            key=report_key,
        )
        
        job.update_status(JobStatus.COMPLETE, "complete", 100)
        
        logger.info(f"Transform complete for job {job.id}")
        
        return job
    
    def _generate_report(
        self,
        job: Job,
        scene_graph: SceneGraph,
        rules: list[SubstitutionRule],
    ) -> str:
        """Generate processing report."""
        lines = [
            f"# PlanMod Processing Report",
            f"",
            f"**Job ID:** {job.id}",
            f"**Status:** {job.status.value}",
            f"",
            f"## Summary",
            f"",
            f"- **Input file:** {job.input.file_name if job.input else 'Unknown'}",
            f"- **Views detected:** {len(scene_graph.views)}",
            f"- **Components identified:** {len(scene_graph.components)}",
            f"- **Substitutions applied:** {len(rules)}",
            f"",
        ]
        
        if job.mass_kg:
            lines.extend([
                f"## Mass Analysis",
                f"",
                f"- **Total mass:** {job.mass_kg * 1000:.1f} grams ({job.mass_kg:.4f} kg)",
            ])
            
            if job.center_of_gravity:
                lines.append(f"- **Center of gravity:** ({job.center_of_gravity.x:.1f}, {job.center_of_gravity.y:.1f}) mm")
            
            lines.append("")
        
        if scene_graph.views:
            lines.extend([
                f"## Views",
                f"",
            ])
            for view in scene_graph.views:
                lines.append(f"- **{view.name}** ({view.view_type.value})")
            lines.append("")
        
        if scene_graph.components:
            lines.extend([
                f"## Components",
                f"",
            ])
            for comp in scene_graph.components[:20]:  # Limit to 20
                conf_str = f" ({comp.classification_confidence:.0%})" if comp.classification_confidence < 1 else ""
                lines.append(f"- {comp.name or comp.id[:8]}: {comp.component_type.value}{conf_str}")
            
            if len(scene_graph.components) > 20:
                lines.append(f"- ... and {len(scene_graph.components) - 20} more")
            lines.append("")
        
        if rules:
            lines.extend([
                f"## Substitutions Applied",
                f"",
            ])
            for rule in rules:
                lines.append(f"- {rule.description or rule.id}")
            lines.append("")
        
        if scene_graph.uncertainties:
            lines.extend([
                f"## ⚠️ Items Needing Human Review",
                f"",
            ])
            for unc in scene_graph.uncertainties:
                lines.append(f"- {unc}")
            lines.append("")
        
        lines.extend([
            f"---",
            f"*Generated by PlanMod*",
        ])
        
        return "\n".join(lines)


# Lambda handler
def lambda_handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point."""
    job_id = event.get("job_id")
    rules_data = event.get("rules", [])
    
    if not job_id:
        return {"status": "error", "message": "Missing job_id"}
    
    dynamo = get_dynamo_client()
    
    job = dynamo.get_job(job_id)
    if not job:
        return {"status": "error", "message": f"Job not found: {job_id}"}
    
    scene_graph = dynamo.get_scene_graph_by_job(job_id)
    if not scene_graph:
        return {"status": "error", "message": "Scene graph not found"}
    
    # Parse rules
    rules = []
    for rule_data in rules_data:
        rules.append(SubstitutionRule(**rule_data))
    
    try:
        handler = TransformHandler()
        job = handler.transform(job, scene_graph, rules)
        
        dynamo.update_job(job)
        dynamo.update_scene_graph(scene_graph)
        
        return {
            "status": "success",
            "job_id": job_id,
            "final_dxf_key": job.output.final_dxf.key if job.output.final_dxf else None,
            "mass_kg": job.mass_kg,
        }
        
    except Exception as e:
        job.set_error(str(e))
        dynamo.update_job(job)
        return {"status": "error", "message": str(e)}


