"""
Report generation utilities.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from backend.shared.models import Job, SceneGraph
from backend.llm_client import BedrockClaudeLLM

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates human-readable reports from processing results.
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        self.llm_client = llm_client
    
    def generate_markdown_report(
        self,
        job: Job,
        scene_graph: SceneGraph,
    ) -> str:
        """
        Generate a Markdown report.
        
        Args:
            job: Completed job
            scene_graph: Final scene graph
            
        Returns:
            Markdown report string
        """
        report_lines = [
            "# PlanMod Processing Report",
            "",
            f"**Generated:** {datetime.utcnow().isoformat()}Z",
            "",
            "---",
            "",
            "## Job Summary",
            "",
            f"| Property | Value |",
            f"|----------|-------|",
            f"| Job ID | `{job.id}` |",
            f"| Status | {job.status.value} |",
            f"| Input File | {job.input.file_name if job.input else 'N/A'} |",
            f"| Processing Time | {job.processing_time_seconds:.1f}s |" if job.processing_time_seconds else "",
            "",
        ]
        
        # Views section
        report_lines.extend([
            "## Identified Views",
            "",
        ])
        
        if scene_graph.views:
            report_lines.append("| View | Type | Confidence |")
            report_lines.append("|------|------|------------|")
            
            for view in scene_graph.views:
                conf = f"{view.classification_confidence:.0%}"
                report_lines.append(f"| {view.name} | {view.view_type.value} | {conf} |")
            report_lines.append("")
        else:
            report_lines.append("*No views identified*")
            report_lines.append("")
        
        # Components section
        report_lines.extend([
            "## Identified Components",
            "",
        ])
        
        if scene_graph.components:
            # Group by type
            by_type: dict[str, list] = {}
            for comp in scene_graph.components:
                type_name = comp.component_type.value
                if type_name not in by_type:
                    by_type[type_name] = []
                by_type[type_name].append(comp)
            
            for type_name, comps in sorted(by_type.items()):
                report_lines.append(f"### {type_name.replace('_', ' ').title()} ({len(comps)})")
                report_lines.append("")
                
                for comp in comps[:10]:
                    name = comp.name or comp.id[:8]
                    conf = f"({comp.classification_confidence:.0%})"
                    report_lines.append(f"- {name} {conf}")
                
                if len(comps) > 10:
                    report_lines.append(f"- *...and {len(comps) - 10} more*")
                report_lines.append("")
        else:
            report_lines.append("*No components identified*")
            report_lines.append("")
        
        # Mass analysis
        if job.mass_kg:
            report_lines.extend([
                "## Mass Analysis",
                "",
                f"- **Total Mass:** {job.mass_kg * 1000:.1f} g ({job.mass_kg:.4f} kg)",
            ])
            
            if job.center_of_gravity:
                report_lines.append(
                    f"- **Center of Gravity:** ({job.center_of_gravity.x:.1f}, {job.center_of_gravity.y:.1f}) mm"
                )
            report_lines.append("")
        
        # Substitutions
        if job.substitution_rules:
            report_lines.extend([
                "## Applied Substitutions",
                "",
            ])
            
            for rule in job.substitution_rules:
                report_lines.append(f"- {rule.description or rule.id}")
            report_lines.append("")
        
        # Uncertainties
        if scene_graph.uncertainties:
            report_lines.extend([
                "## ⚠️ Items Requiring Review",
                "",
            ])
            
            for unc in scene_graph.uncertainties:
                report_lines.append(f"- {unc}")
            report_lines.append("")
        
        # Processing notes
        if scene_graph.processing_notes:
            report_lines.extend([
                "## Processing Notes",
                "",
            ])
            
            for note in scene_graph.processing_notes[-10:]:
                report_lines.append(f"- {note}")
            report_lines.append("")
        
        # Output files
        report_lines.extend([
            "## Output Files",
            "",
        ])
        
        if job.output.base_dxf:
            report_lines.append(f"- Base DXF: `{job.output.base_dxf.key}`")
        if job.output.final_dxf:
            report_lines.append(f"- Final DXF: `{job.output.final_dxf.key}`")
        if job.output.scene_graph_json:
            report_lines.append(f"- Scene Graph: `{job.output.scene_graph_json.key}`")
        if job.output.scene_graph_image:
            report_lines.append(f"- Visualization: `{job.output.scene_graph_image.key}`")
        
        report_lines.extend([
            "",
            "---",
            "",
            "*Generated by PlanMod*",
        ])
        
        return "\n".join(report_lines)
    
    async def generate_ai_enhanced_report(
        self,
        job: Job,
        scene_graph: SceneGraph,
    ) -> str:
        """
        Generate an AI-enhanced report using LLM.
        
        Args:
            job: Completed job
            scene_graph: Final scene graph
            
        Returns:
            Enhanced Markdown report
        """
        if not self.llm_client:
            self.llm_client = BedrockClaudeLLM()
        
        # Get base report
        base_report = self.generate_markdown_report(job, scene_graph)
        
        # Prepare summaries for LLM
        job_summary = {
            "id": job.id,
            "status": job.status.value,
            "input_file": job.input.file_name if job.input else None,
            "mass_kg": job.mass_kg,
            "substitutions_count": len(job.substitution_rules),
        }
        
        scene_summary = {
            "title": scene_graph.title,
            "views_count": len(scene_graph.views),
            "components_count": len(scene_graph.components),
            "uncertainties": scene_graph.uncertainties,
        }
        
        # Generate enhanced report
        enhanced = await self.llm_client.generate_report(
            job_summary,
            scene_summary,
            [r.model_dump() for r in job.substitution_rules],
        )
        
        return enhanced


