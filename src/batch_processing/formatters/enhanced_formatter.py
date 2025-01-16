from pathlib import Path
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import markdown
from weasyprint import HTML, CSS
import logging
from dataclasses import dataclass

from src.location.location_processor import LocationProcessor
from src.construction.expert import ConstructionExpert
from src.timing.analyser import TaskAnalyzer
from src.timing.chronogram import ChronogramVisualizer
from src.report_generation.llm_service import LLMService
from src.timing.models import ScheduleGraph

@dataclass
class ReportSection:
    """Represents a section of the report with its content and metadata"""
    title: str
    content: str
    order: int
    type: str = "markdown"  # markdown, mermaid, etc.
    metadata: Dict[str, Any] = None

class EnhancedReportFormatter:
    """Enhanced report formatter that integrates all specialized agents"""
    
    def __init__(self):
        """Initialize formatter with all required agents"""
        self.logger = logging.getLogger(__name__)
        self.location_processor = LocationProcessor()
        self.construction_expert = ConstructionExpert()
        self.task_analyzer = TaskAnalyzer()
        self.llm_service = LLMService()
        self.chronogram_visualizer = ChronogramVisualizer()

    def _format_header(self, location_data: Dict) -> str:
        """Format the report header with site information"""
        try:
            # Get main_site data
            main_site = location_data.get('main_site')
            if not main_site:
                self.logger.warning("No main_site data found")
                company = "Unknown Company"
                site = "Unknown Site"
            else:
                # Handle both object and dictionary formats
                if hasattr(main_site, 'company'):
                    company = main_site.company
                    site = main_site.site
                else:
                    company = main_site.get('company', 'Unknown Company')
                    site = main_site.get('site', 'Unknown Site')

            # Format the header
            return f"""# Construction Site Visit Report

    ## Site Information
    - **Company:** {company}
    - **Location:** {site}
    - **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

    ---
    """
        except Exception as e:
            self.logger.error(f"Error formatting header: {str(e)}")
            # Return a default header rather than failing
            return f"""# Construction Site Visit Report

    ## Site Information
    - **Company:** Error retrieving company
    - **Location:** Error retrieving location
    - **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

    ---
    """

    def _format_executive_summary(self, analysis: Dict) -> str:
        """Format the executive summary section"""
        summary = analysis.get('executive_summary', 'No summary available')
        vision_general = analysis.get('vision_general', {})

        # Include confidence score if available
        confidence = analysis.get("confidence_scores", {}).get("overall", None)
        confidence_text = f"\n\n**Nivel de confianza:** {confidence * 100:.1f}%" if confidence is not None else ""

        # Format areas visited
        areas_section = []
        for area in vision_general.get('areas_visitadas', []):
            areas_section.append(f"\n### {area['area']}\n")

            if area.get('observaciones_clave'):
                areas_section.append("**Observaciones Clave:**")
                for obs in area['observaciones_clave']:
                    areas_section.append(f"- {obs}")

            if area.get('problemas_identificados'):
                areas_section.append("\n**Problemas Identificados:**")
                for prob in area['problemas_identificados']:
                    areas_section.append(f"- {prob}")

            areas_section.append("\n")

        areas_text = "\n".join(areas_section) if areas_section else "No se visitaron áreas"

        return f"""## Resumen Ejecutivo

        {summary}

        ### Áreas Visitadas
        {areas_text}

        {confidence_text}

        ---"""

    
    def _format_problems_section(self, analysis: Dict) -> str:
        """Format the problems and solutions section"""
        sections = ["## Problemas y Soluciones\n"]
        
        # Process technical findings
        for finding in analysis.get('hallazgos_tecnicos', []):
            sections.append(f"### Problem in {finding['ubicacion']}")
            sections.append(f"**Severity:** {finding['severidad']}")
            sections.append(f"**Description:** {finding['hallazgo']}")
            sections.append(f"**Recommended Action:** {finding['accion_recomendada']}\n")
        
        # Process safety concerns
        if analysis.get('preocupaciones_seguridad'):
            sections.append("### Safety Concerns")
            for concern in analysis['preocupaciones_seguridad']:
                sections.append(f"**Location:** {concern['ubicacion']}")
                sections.append(f"**Concern:** {concern['preocupacion']}")
                sections.append(f"**Priority:** {concern['prioridad']}")
                sections.append(f"**Mitigation:** {concern['mitigacion']}\n")
        
        return "\n".join(sections)
    
    def _format_follow_up_section(self, data: Dict) -> str:
        """Format the follow-up items section"""
        sections = ["## Tareas Pendientes\n"]

        # Ensure we access the correct key in the construction analysis
        construction_analysis = data.get("construction_analysis", {})
        tasks = construction_analysis.get("tareas_pendientes", [])

        if tasks:
            for item in tasks:
                sections.append(f"### {item['tarea']}")
                sections.append(f"- **Ubicación:** {item['ubicacion']}")
                sections.append(f"- **Asignado a:** {item['asignado_a']}")
                sections.append(f"- **Prioridad:** {item['prioridad']}")
                sections.append(f"- **Plazo:** {item['plazo']}\n")

            # Add general observations if present
            if construction_analysis.get('observaciones_generales'):
                sections.append("### Observaciones Generales")
                for obs in construction_analysis['observaciones_generales']:
                    sections.append(f"- {obs}\n")
        else:
            sections.append("No hay tareas pendientes registradas.\n")

        return "\n".join(sections)

    def _format_location_analysis(self, location_data: Dict) -> str:
        """Format the location analysis section"""
        sections = ["## Location Analysis\n"]

        # Add movement tracking
        if location_data.get('location_changes'):
            sections.append("### Movement Timeline")
            for change in location_data['location_changes']:
                # Handle both dictionary and object formats
                if hasattr(change, 'timestamp'):
                    time = change.timestamp.strftime('%H:%M:%S')
                    area = change.area
                    subloc = getattr(change, 'sublocation', '')
                    notes = getattr(change, 'notes', '')
                else:
                    time = change.get('timestamp', datetime.now()).strftime('%H:%M:%S')
                    area = change.get('area', 'Unknown Area')
                    subloc = change.get('sublocation', '')
                    notes = change.get('notes', '')
                
                # Format location entry
                location_str = f"- **{time}** - {area}"
                if subloc:
                    location_str += f" ({subloc})"
                if notes:
                    location_str += f" - {notes}"
                sections.append(location_str)
        
        return "\n".join(sections)

    def _create_report_sections(self, **data) -> List[ReportSection]:
        """Create all report sections from analyzed data"""
        sections = []
        
        # Header section
        sections.append(ReportSection(
            title="Información de la Obra",
            content=self._format_header(data['location_data']),
            order=1
        ))
        
        # Executive summary
        sections.append(ReportSection(
            title="Resumen Ejecutivo",
            content=self._format_executive_summary(data['construction_analysis']),
            order=2
        ))
        
        # Location analysis
        sections.append(ReportSection(
            title="Análisis de Ubicación",
            content=self._format_location_analysis(data['location_data']),
            order=3
        ))
        
        # Problems and solutions
        sections.append(ReportSection(
            title="Problemas y Soluciones",
            content=self._format_problems_section(data['construction_analysis']),
            order=4
        ))
        
        # Chronogram
        sections.append(ReportSection(
            title="Cronograma del Proyecto",
            content=data['chronogram'],
            type="mermaid",
            order=5
        ))
        
        # Follow-up items
        sections.append(ReportSection(
            title="Tareas Pendientes",
            content=self._format_follow_up_section(data),
            order=6
        ))
        return sorted(sections, key=lambda s: s.order)
    
    def _convert_to_schedule_graph(self, timing_data: Dict) -> ScheduleGraph:
        """Convert timing analysis data to ScheduleGraph"""
        from src.timing.models import Task, TaskRelationship, TaskRelationType, Duration, ScheduleGraph
        

        if isinstance(timing_data, ScheduleGraph):
            return timing_data  # No need to convert if it's already correct

        # Otherwise, proceed with conversion from dict to ScheduleGraph

        # Create schedule graph
        schedule = ScheduleGraph(tasks={}, relationships=[])
        task_ids = {}  # Store mapping of task names to IDs
        
        # First pass: Create all tasks
        for task_data in timing_data.get('tasks', []):
            task = Task(
                name=task_data['name'],
                description=task_data.get('description', ''),
                duration=Duration(**task_data['duration'])
            )
            schedule.add_task(task)
            task_ids[task.name] = task.id
        
        # Second pass: Create relationships
        for task_data in timing_data.get('tasks', []):
            for dep_name in task_data.get('dependencies', []):
                if dep_name in task_ids and task_data['name'] in task_ids:
                    relationship = TaskRelationship(
                        from_task_id=task_ids[dep_name],
                        to_task_id=task_ids[task_data['name']],
                        relation_type=TaskRelationType.SEQUENTIAL
                    )
                    schedule.add_relationship(relationship)
        
        return schedule
    

    async def _generate_report_files(
        self,
        sections: List[ReportSection],
        output_dir: Path,
        metadata: Dict[str, Any]
    ) -> Dict[str, Path]:
        """Generate all report file formats"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate markdown
        markdown_path = output_dir / "report.md"
        markdown_content = self._generate_markdown(sections)
        markdown_path.write_text(markdown_content)
        
        # Generate PDF
        pdf_path = output_dir / "report.pdf"
        await self._generate_pdf(markdown_content, pdf_path)
        
        # Save metadata
        metadata_path = output_dir / "report_metadata.json"
        metadata.update({
            "sections": [
                {
                    "title": section.title,
                    "type": section.type,
                    "order": section.order
                }
                for section in sections
            ]
        })
        metadata_path.write_text(json.dumps(metadata, indent=2))
        
        return {
            "markdown": markdown_path,
            "pdf": pdf_path,
            "metadata": metadata_path
        }


    async def generate_comprehensive_report(
        self,
        transcript_text: str,
        visit_id: uuid.UUID,
        location_id: uuid.UUID,
        output_dir: Path,
        analysis_data: Optional[Dict[str, Any]] = None,
        start_date: Optional[datetime] = None
    ) -> Dict[str, Path]:
        """Generate a comprehensive report integrating all analyses."""
        try:
            logger = logging.getLogger(__name__)
            # Process location data
            self.logger.info("Processing location data...")
            location_data = self.location_processor.process_transcript(transcript_text)
        
            logger.debug(f"Generating report for visit {visit_id}, location {location_id}")

            # Use provided analysis data or generate new analysis
            if analysis_data:
                construction_analysis = analysis_data
                logger.debug(f"Analysis Data: {analysis_data}")
            else:
                # Get construction analysis
                self.logger.info("Analyzing construction aspects...")
                analysis_result = self.construction_expert.analyze_visit(
                    visit_id=visit_id,
                    transcript_text=transcript_text,
                    location_id=location_id
                )

                construction_analysis = {
                    'executive_summary': analysis_result.metadata.get('executive_summary', 'No summary available'),                    'problems': analysis_result.problems,
                    'solutions': analysis_result.solutions,
                    'confidence_scores': analysis_result.confidence_scores,
                    'metadata': analysis_result.metadata
                }
            
            # Get timing analysis
            self.logger.info("Analyzing timing and tasks...")
            timing_data = self.task_analyzer.analyze_transcript(
                transcript_text=transcript_text,
                location_id=location_id
            )
            
            # Convert timing data to ScheduleGraph
            timing_analysis = self._convert_to_schedule_graph(timing_data)
            
            # Generate chronogram
            self.logger.info("Generating chronogram visualization...")
            chronogram = self.chronogram_visualizer.generate_mermaid_gantt(
                timing_analysis,
                start_date or datetime.now()
            )
            
            # Create report sections
            sections = self._create_report_sections(
                location_data=location_data,
                construction_analysis=construction_analysis,
                timing_analysis=timing_analysis,
                chronogram=chronogram
            )
            
            

            # Generate report files
            print("Final Report Markdown:")
            print(self._generate_markdown(sections))

            return await self._generate_report_files(
                sections=sections,
                output_dir=output_dir,
                metadata={
                    "visit_id": str(visit_id),
                    "location_id": str(location_id),
                    "generated_at": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error generating report: {str(e)}")
            raise


    def _generate_markdown(self, sections: List[ReportSection]) -> str:
        """Generate complete markdown content from sections"""
        parts = []
        
        for section in sections:
            if section.type == "markdown":
                parts.append(section.content)
            elif section.type == "mermaid":
                parts.append("```mermaid")
                parts.append(section.content)
                parts.append("```")
            
            parts.append("")  # Add spacing between sections
            
        return "\n".join(parts)

    async def _generate_pdf(self, markdown_content: str, output_path: Path) -> None:
        """Generate PDF from markdown content"""
        try:
            # Convert markdown to HTML
            html_content = markdown.markdown(
                markdown_content,
                extensions=['tables', 'fenced_code']
            )
            
            # Add CSS styling
            css = CSS(string="""
                @page {
                    margin: 2.5cm;
                    @top-right {
                        content: counter(page);
                    }
                }
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    font-size: 11pt;
                }
                h1, h2, h3 {
                    color: #2c3e50;
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 1em 0;
                }
                th, td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                pre {
                    background-color: #f8f9fa;
                    padding: 1em;
                    border-radius: 4px;
                    overflow-x: auto;
                }
                .mermaid {
                    margin: 1em 0;
                }
            """)
            
            # Generate PDF
            HTML(string=html_content).write_pdf(
                str(output_path),
                stylesheets=[css]
            )
            
        except Exception as e:
            self.logger.error(f"Error generating PDF: {str(e)}")
            raise