from pathlib import Path
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import markdown
from weasyprint import HTML, CSS
import logging
from dataclasses import dataclass

from rapidfuzz import fuzz  # Use fuzzy matching for area names

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
        self.logger = logging.getLogger(__name__)
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
                print("Location Data OK:", location_data["main_site"])
                # Handle both object and dictionary formats
                if hasattr(main_site, 'company'):
                    company = main_site.company
                    site = main_site.site
                else:
                    company = main_site.get('company', 'Unknown Company')
                    site = main_site.get('site', 'Unknown Site')

            # Format the header
            print("DEBUG: Extracted locations before report generation:", location_data)

            return f"""# Construction Site Visit Report

    ## Site Information
    - **Company:** {company}
    - **Location:** {site}
    - **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

    ---
    """
        except Exception as e:
            print(f"Error formatting header: {str(e)}")
            self.logger.error(f"Error formatting header: {str(e)}")
            # Return a default header rather than failing
            return f"""# Construction Site Visit Report

    ## Site Information
    - **Company:** Error retrieving company
    - **Location:** Error retrieving location
    - **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

    ---
    """
    
    def _format_executive_summary(self, construction_analysis: dict, location_data: dict) -> str:
        summary = construction_analysis.get('executive_summary', 'No summary available.')
        extracted_locations = location_data.get('extracted_locations', [])
        if extracted_locations:
            area_names = [loc.get('location') for loc in extracted_locations]
            visited_areas = ", ".join(area for area in area_names if area)
        else:
            visited_areas = "No se visitaron áreas"

        return f"""## Resumen Ejecutivo

{summary}

### Áreas Visitadas
{visited_areas}

---
"""

    def _format_problems_section(self, construction_analysis: Dict) -> str:
        SEVERITY_MAPPING = {
            'LOW': 'Baja', 
            'MEDIUM': 'Media', 
            'HIGH': 'Alta', 
            'CRITICAL': 'Crítica',
        }

        sections = ["## Problemas Identificados y Plan de Acción\n"]
        problems_by_area = {}

        if construction_analysis.get('problems'):
            for problem in construction_analysis['problems']:
                # -- Existing logic to read problem data --
                if not isinstance(problem, dict):
                    area = problem.location_context.area if problem.location_context else 'Área General'
                    severity_raw = problem.severity.value if hasattr(problem.severity, 'value') else str(problem.severity)
                    description = problem.description
                    problem_id = problem.id
                    recommended_action = (
                        problem.location_context.additional_info.get('raw_finding', {})
                        .get('accion_recomendada') if problem.location_context else None
                    )
                else:
                    area = problem.get('location_context', {}).get('area', 'Área General')
                    severity_raw = problem.get('severity', 'Unknown')
                    description = problem.get('description', '')
                    problem_id = problem.get('id')
                    recommended_action = None

                # -- NEW: Normalize severity to match your dictionary keys --
                if severity_raw.startswith("Severity."):
                    severity_raw = severity_raw.replace("Severity.", "")
                severity_str = severity_raw.upper()  # e.g. "MEDIUM" or "HIGH"

                # Now map it to Spanish
                severity_in_spanish = SEVERITY_MAPPING.get(severity_str, severity_str)

                # store in problems_by_area
                if area not in problems_by_area:
                    problems_by_area[area] = {'problems': [], 'safety': [], 'solutions': []}

                problems_by_area[area]['problems'].append({
                    'description': description,
                    'severity': severity_in_spanish,
                    'id': problem_id,
                    'recommended_action': recommended_action,
                })

                # -- Existing logic to fetch solutions --
                if problem_id and construction_analysis.get('solutions'):
                    solutions = construction_analysis['solutions'].get(str(problem_id), [])
                    for solution in solutions:
                        if isinstance(solution, dict):
                            solution_desc = solution.get('description', '')
                            est_time = solution.get('estimated_time')
                            priority = solution.get('priority')
                        else:
                            solution_desc = solution.description
                            est_time = solution.estimated_time
                            priority = solution.priority

                        problems_by_area[area]['solutions'].append({
                            'description': solution_desc,
                            'estimated_time': est_time,
                            'problem_id': problem_id,
                            'priority': priority
                        })

            # Format output by area
            for area, data in problems_by_area.items():
                sections.append(f"### {area}")
                
                if data['problems']:
                    sections.append("\n#### Problemas Técnicos")
                    for problem in data['problems']:
                        sections.append(f"- **Problema:** {problem['description']}")
                        sections.append(f"  - Severidad: {problem['severity']}")
                        
                        # Add recommended action if available
                        if problem['recommended_action']:
                            sections.append(f"  - Acción recomendada: {problem['accion_recomendada']}")
                        
                        # Add associated solutions
                        related_solutions = [s for s in data['solutions'] if s['problem_id'] == problem['id']]
                        if related_solutions:
                            sections.append("  - Plan de acción:")
                            for solution in related_solutions:
                                priority_str = f" (Prioridad: {solution['priority']})" if solution['priority'] else ""
                                sections.append(f"    * {solution['description']}{priority_str}")
                                if solution['estimated_time']:
                                    sections.append(f"      Tiempo estimado: {solution['estimated_time']} minutos")
                    sections.append("")

                if data['safety']:
                    sections.append("#### Preocupaciones de Seguridad")
                    for concern in data['safety']:
                        sections.append(f"- **Riesgo:** {concern['description']}")
                        sections.append(f"  - Prioridad: {concern['priority']}")
                    sections.append("")
                
                sections.append("---\n")

            if len(sections) == 1:
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
        """Formatear la sección de análisis de tiempos"""
        sections = ["## Análisis Temporal\n"]
        
        # Agregar información detallada sobre los tiempos
        tasks = []
        if isinstance(task_data, ScheduleGraph):
            tasks = list(task_data.tasks.values())
        elif isinstance(task_data, dict) and task_data.get('tasks'):
            tasks = task_data['tasks']

        if not tasks:
            return ""

        sections.append("### Duraciones de Tareas y Dependencias\n")
        for task in tasks:
            name, duration_data, can_parallel, dependencies = self._get_task_properties(task)

            # Formatear la duración
            duration_str = None
            if isinstance(duration_data, dict):
                amount = duration_data.get('amount')
                unit = duration_data.get('unit')
                if amount is not None and unit is not None:
                    duration_str = f"{amount} {unit}"
            elif isinstance(duration_data, Duration):
                duration_str = f"{duration_data.amount} {duration_data.unit}"

            # Construir el contenido de la sección
            if duration_str:
                sections.append(f"- **{name}:** {duration_str}")
                
            # Agregar dependencias
            if dependencies:
                sections.append(f"  - Depende de: {', '.join(str(d) for d in dependencies)}")
                
            # Indicar si se puede ejecutar en paralelo
            if can_parallel:
                sections.append("  - Puede ejecutarse en paralelo")
                
        sections.append("")  # Agregar espacio al final
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
                    f"- **Plazo:** {task['plazo']}",
                    f"- **Observaciones Generales:** {task['observaciones_generales']}\n",
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
            content=self._format_executive_summary(data['construction_analysis'], data['location_data']),
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
        location_data: Optional[Dict[str, Any]] = None,
        construction_analysis: Optional[Dict[str, Any]] = None,
        timing_analysis: Optional[Dict[str, Any]] = None,
        chronogram: Optional[str] = None,
        start_date: Optional[datetime] = None
    ) -> Dict[str, Path]:
        """Generate a comprehensive report using pre-analyzed data."""
        try:
            logger = logging.getLogger(__name__)
            
            # Create report sections directly from provided data
            sections = self._create_report_sections(
                location_data=location_data,
                construction_analysis=construction_analysis,
                timing_analysis=timing_analysis,
                chronogram=chronogram
            )
            
            # Generate report files
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate markdown
            markdown_path = output_dir / "report.md"
            markdown_content = self._generate_markdown(sections)
            markdown_path.write_text(markdown_content, encoding='utf-8')
            
            # Generate PDF
            pdf_path = output_dir / "report.pdf"
            await self._generate_pdf(markdown_content, pdf_path)
            
            # Save metadata
            metadata_path = output_dir / "report_metadata.json"
            metadata = {
                "visit_id": str(visit_id),
                "location_id": str(location_id),
                "generated_at": datetime.now().isoformat(),
                "sections": [
                    {
                        "title": section.title,
                        "type": section.type,
                        "order": section.order
                    }
                    for section in sections
                ]
            }
            metadata_path.write_text(json.dumps(metadata, indent=2))
            
            return {
                "markdown": markdown_path,
                "pdf": pdf_path,
                "metadata": metadata_path
            }
            
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