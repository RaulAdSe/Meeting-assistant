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
from src.timing.models import ScheduleGraph, Duration

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

    def _format_executive_summary(self, construction_analysis: Dict) -> str:
        """Format the executive summary section"""
        summary = construction_analysis.get('executive_summary', 'No summary available.')
        confidence = construction_analysis.get('confidence_scores', {}).get('overall', 0)
        vision_general = construction_analysis.get('vision_general', {})
        areas_visitadas = vision_general.get('areas_visitadas', [])

        areas_section = []
        if areas_visitadas:
            for area in areas_visitadas:
                # Add area heading
                areas_section.append(f"\n### {area['area']}\n")

                # Add key observations if present
                if area.get('observaciones_clave'):
                    areas_section.append("**Observaciones Clave:**")
                    for obs in area['observaciones_clave']:
                        areas_section.append(f"- {obs}")

                # Add identified problems if present
                if area.get('problemas_identificados'):
                    areas_section.append("\n**Problemas Identificados:**")
                    for prob in area['problemas_identificados']:
                        areas_section.append(f"- {prob}")

                areas_section.append("\n")
        else:
            areas_section = ["No se visitaron áreas"]

        areas_text = "\n".join(areas_section)

        formatted_summary = f"""## Resumen Ejecutivo

            {summary}

            ### Áreas Visitadas
            {areas_text}

            """

        if confidence:
            formatted_summary += f"\n**Nivel de confianza:** {confidence*100:.1f}%\n"

        formatted_summary += "\n        ---"

        return formatted_summary
    
    def _format_problems_section(self, analysis: Dict) -> str:
        """Format the problems and solutions section"""
        sections = ["## Problemas y Soluciones\n"]
        
        # Handle direct technical findings first
        if analysis.get('hallazgos_tecnicos'):
            for finding in analysis['hallazgos_tecnicos']:
                sections.append(f"### Problem in {finding['ubicacion']}")
                sections.append(f"**Severity:** {finding['severidad']}")
                sections.append(f"**Description:** {finding['hallazgo']}")
                if 'accion_recomendada' in finding:
                    sections.append(f"**Recommended Action:** {finding['accion_recomendada']}")
                sections.append("")
        
        # Handle safety concerns
        if analysis.get('preocupaciones_seguridad'):
            sections.append("### Safety Concerns")
            for concern in analysis['preocupaciones_seguridad']:
                sections.append(f"**Location:** {concern['ubicacion']}")
                sections.append(f"**Concern:** {concern['preocupacion']}")
                sections.append(f"**Priority:** {concern['prioridad']}")
                sections.append(f"**Mitigation:** {concern['mitigacion']}")
                sections.append("")
        
        # Then handle formal Problem objects if present
        if analysis.get('problems'):
            for problem in analysis['problems']:
                sections.append(f"### Problem in {problem.location_context.area}")
                sections.append(f"**Severity:** {problem.severity.value}")
                sections.append(f"**Description:** {problem.description}")
                
                # Add solutions for this problem
                if analysis.get('solutions') and problem.id in analysis['solutions']:
                    problem_solutions = analysis['solutions'][problem.id]
                    sections.append("\n**Proposed Solutions:**")
                    for solution in problem_solutions:
                        sections.append(f"- {solution.description}")
                        if solution.estimated_time:
                            sections.append(f"  - Estimated time: {solution.estimated_time} minutes")
                sections.append("")
        
        if len(sections) == 1:  # Only header present
            sections.append("No se han identificado problemas en esta visita.\n")
        
        return "\n".join(sections)

    def _get_task_properties(self, task) -> tuple:
        """Extract task properties safely whether task is a dict or Task object"""
        if isinstance(task, dict):
            return (
                task.get('name', 'Unknown Task'),
                task.get('duration', {}),
                task.get('can_be_parallel', False),
                task.get('dependencies', [])
            )
        else:
            # Handle Task object
            return (
                getattr(task, 'name', 'Unknown Task'),
                getattr(task, 'duration', None),
                getattr(task, 'can_be_parallel', False),
                getattr(task, 'dependencies', [])
            )

    def _format_timing_section(self, task_data: Dict) -> str:
        """Format the timing analysis section"""
        sections = ["## Timing Analysis\n"]
        
        # Add detailed timing information
        tasks = []
        if isinstance(task_data, ScheduleGraph):
            tasks = list(task_data.tasks.values())
        elif isinstance(task_data, dict) and task_data.get('tasks'):
            tasks = task_data['tasks']

        if not tasks:
            return ""

        sections.append("### Task Durations and Dependencies\n")
        for task in tasks:
            name, duration_data, can_parallel, dependencies = self._get_task_properties(task)

            # Format duration
            duration_str = None
            if isinstance(duration_data, dict):
                amount = duration_data.get('amount')
                unit = duration_data.get('unit')
                if amount is not None and unit is not None:
                    duration_str = f"{amount} {unit}"
            elif isinstance(duration_data, Duration):
                duration_str = f"{duration_data.amount} {duration_data.unit}"

            # Build section content
            if duration_str:
                sections.append(f"- **{name}:** {duration_str}")
                
            # Add dependencies
            if dependencies:
                sections.append(f"  - Depends on: {', '.join(str(d) for d in dependencies)}")
                
            # Add parallel execution info
            if can_parallel:
                sections.append("  - Can be executed in parallel")
                
        sections.append("")  # Add spacing at the end
        return "\n".join(sections)


    def _format_follow_up_section(self, data: Dict) -> str:
        """Format the follow-up items section"""
        sections = ["## Tareas Pendientes\n"]
        
        construction_analysis = data.get('construction_analysis', {})
        pending_tasks = construction_analysis.get('tareas_pendientes', [])
        
        # Add tasks from tareas_pendientes
        if pending_tasks:
            for task in pending_tasks:
                sections.extend([
                    f"### {task['tarea']}",
                    f"- **Ubicación:** {task['ubicacion']}",
                    f"- **Asignado a:** {task['asignado_a']}",
                    f"- **Prioridad:** {task['prioridad']}",
                    f"- **Plazo:** {task['plazo']}\n"
                ])
        
        # Add tasks from timing analysis
        timing_analysis = data.get('timing_analysis')
        if isinstance(timing_analysis, ScheduleGraph):
            for task in timing_analysis.tasks.values():
                sections.extend([
                    f"### {task.name}",
                    f"- **Ubicación:** {task.location or 'No especificada'}",
                    f"- **Responsable:** {task.responsible or 'No asignado'}",
                    f"- **Duración:** {task.duration.amount} {task.duration.unit}",
                    f"- **Estado:** {task.status.value}\n"
                ])
                if task.metadata.get('risks'):
                    sections.append("**Riesgos identificados:**")
                    for risk in task.metadata['risks']:
                        sections.append(f"- {risk}")
                    sections.append("")
        
        # Add general observations
        if construction_analysis.get('observaciones_generales'):
            sections.append("### Observaciones Generales")
            for obs in construction_analysis['observaciones_generales']:
                sections.append(f"- {obs}\n")
        
        if len(sections) == 1:  # Only header present
            sections.append("No hay tareas pendientes registradas.\n")
        
        return "\n".join(sections)

    def _format_location_analysis(self, location_data: Dict) -> str:
        """Format the location analysis section"""
        sections = ["## Location Analysis\n"]
        
        # Add location changes if present
        if location_data.get('location_changes'):
            sections.append("### Movement Timeline")
            
            # Sort changes by timestamp
            changes = sorted(location_data['location_changes'], key=lambda x: x.timestamp)
            
            for change in changes:
                time = change.timestamp.strftime('%H:%M:%S')
                area = change.area
                subloc = change.sublocation if change.sublocation else ''
                notes = f" - {change.notes}" if change.notes else ''
                
                location_str = f"- **{time}** - {area}"
                if subloc:
                    location_str += f" ({subloc})"
                if notes:
                    location_str += notes
                sections.append(location_str)
        
        # Always show current location
        main_site = location_data.get('main_site')
        if main_site:
            sections.append("### Current Location")
            if isinstance(main_site, dict):
                sections.append(f"**Company:** {main_site['company']}")
                sections.append(f"**Site:** {main_site['location'] if 'location' in main_site else main_site.get('site', 'Unknown')}")
            else:
                sections.append(f"**Company:** {getattr(main_site, 'company', 'Unknown')}")
                sections.append(f"**Site:** {getattr(main_site, 'site', 'Unknown')}")
        
        sections.append("")
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
        
        # Timing analysis (new section)
        if 'timing_analysis' in data:
            sections.append(ReportSection(
                title="Análisis de Tiempos",
                content=self._format_timing_section(data['timing_analysis']),
                order=4
            ))
        
        # Problems and solutions
        sections.append(ReportSection(
            title="Problemas y Soluciones",
            content=self._format_problems_section(data['construction_analysis']),
            order=5
        ))
        
        # Chronogram
        if 'chronogram' in data:
            sections.append(ReportSection(
                title="Cronograma del Proyecto",
                content=data['chronogram'],
                type="mermaid",
                order=6
            ))
        
        # Follow-up items
        sections.append(ReportSection(
            title="Tareas Pendientes",
            content=self._format_follow_up_section(data),
            order=7
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