from pathlib import Path
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import markdown
from weasyprint import HTML, CSS
import logging
from dataclasses import dataclass

from rapidfuzz import fuzz, process  # Use fuzzy matching for area names

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

            return f"""# Informe de Visita de Obra

    ## Información de la Obra
    - **Empresa:** {company}
    - **Localización:** {site}
    - **Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

    ---
    """
        except Exception as e:
            print(f"Error formatting header: {str(e)}")
            self.logger.error(f"Error formatting header: {str(e)}")
            # Return a default header rather than failing
            return f"""# Informe de Visita de Obra

    ## Site Information
    - **Company:** Error retrieving company
    - **Location:** Error retrieving location
    - **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

    ---
    """
    
    def _format_executive_summary(self, construction_analysis: dict, location_data: dict) -> str:
        summary = construction_analysis.get('executive_summary', 'No summary available.')
        areas = []
        if location_data.get('extracted_locations'):
            areas.extend(loc.get('location') for loc in location_data['extracted_locations'] if loc.get('location'))
        if construction_analysis.get('vision_general', {}).get('areas_visitadas'):
            areas.extend(area.get('area') for area in construction_analysis['vision_general']['areas_visitadas'] if area.get('area'))
        visited_areas = ", ".join(set(areas)) or "No se visitaron áreas"

        return f"""## Resumen Ejecutivo

{summary}

### Áreas Visitadas
{visited_areas}

---
"""

    def _format_problems_section(self, construction_analysis: Dict) -> str:
        """Format problems section handling both objects and dicts"""
        sections = ["## Problemas Identificados y Plan de Acción\n"]
        problems_by_area = {}

        # Extract and normalize problems
        problems_list = construction_analysis.get('problems', [])
        if not problems_list:
            sections.append("No se han identificado problemas en esta visita.\n")
            return "\n".join(sections)

        # Group problems by area
        for problem in problems_list:
            problem_data = self._get_problem_data(problem)
            area = problem_data['location_context']['area']
            
            if area not in problems_by_area:
                problems_by_area[area] = {
                    'problems': [],
                    'solutions': []
                }
            
            problems_by_area[area]['problems'].append(problem_data)

        # Get solutions
        solutions_data = construction_analysis.get('solutions', {})
        for area_data in problems_by_area.values():
            for problem in area_data['problems']:
                solutions = self._get_solutions(problem['id'], solutions_data)
                area_data['solutions'].extend(solutions)

        # Generate markdown
        for area, data in problems_by_area.items():
            sections.append(f"### {area}\n")
            sections.append("#### Problemas Técnicos")
            
            for problem in data['problems']:
                sections.append(f"- **Problema:** {problem['description']}")
                sections.append(f"  - Severidad: {problem['severity']}")

                if problem['recommended_action']:
                    sections.append(f"  - Acción recomendada: {problem['recommended_action']}")
                                
                if problem['location_context']['observations']:
                    sections.append("  - Observaciones en la zona:")
                    for obs in problem['location_context']['observations']:
                        sections.append(f"    * {obs}")
                
                # Add tasks
                if problem['tasks']:
                    sections.append("  - Tareas relacionadas:")
                    for task in problem['tasks']:
                        sections.append(f"    * {task['tarea']}")
                        sections.append(f"      - Ubicación: {task.get('ubicacion', 'No especificado')}")
                        if problem['assigned_to'] not in ('None', 'No asignado', ''):
                            sections.append(f"  - Asignado a: {problem['assigned_to']}")
                        else:
                            sections.append(f"  - Asignado a: No especificado")
                        sections.append(f"      - Prioridad: {task.get('prioridad', 'No especificado')}")
                        sections.append(f"      - Plazo: {task.get('plazo', 'No especificado')}")
                
                # THESE DO NOT WORK YET
                # Add solutions
                """""
                solutions = [s for s in data['solutions'] if s['problem_id'] == problem['id']]
                if solutions:
                    sections.append("  - **Soluciones Propuestas:**")
                    for solution in solutions:
                        sections.append(f"    * {solution['description']}")
                        if solution.get('estimated_time'):
                            sections.append(f"      Tiempo estimado: {solution['estimated_time']}")
                """
                sections.append("")
            
            sections.append("---\n")

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
        """Format the follow-up tasks, merging information from construction and timing analysis"""
        sections = ["## Tareas Pendientes por Prioridad\n"]
        
        # Dictionary to store unique tasks, keyed by normalized name
        unique_tasks = {}

        # Process tasks from construction problems first
        construction_analysis = data.get('construction_analysis', {})
        problems = construction_analysis.get('problems', [])
        
        # Extract and normalize tasks from problems
        for problem in problems:
            for task in problem.get('tasks', []):
                try:
                    task_name = task['tarea'].lower().strip()
                    task_data = {
                        'name': task['tarea'],  # Keep original name for display
                        'normalized_name': task_name,
                        'areas': {task.get('ubicacion', 'No especificada')},
                        'responsibles': {task.get('asignado_a', 'No especificado')},
                        'priorities': {task.get('prioridad', 'No especificada')},
                        'deadlines': {task.get('plazo', 'No especificado')},
                        'duration': 'No especificada',
                        'status': 'Pendiente',
                        'related_problems': [{
                            'description': problem.get('description', ''),
                            'severity': problem.get('severity', 'No especificada'),
                            'recommended_action': problem.get('recommended_action', '')
                        }],
                        'dependencies': set()
                    }
                    
                    # Use fuzzy matching to find existing similar tasks
                    match_result = None
                    if unique_tasks:
                        match_result = process.extractOne(
                            task_name,
                            [t['normalized_name'] for t in unique_tasks.values()],
                            scorer=fuzz.token_sort_ratio,
                            score_cutoff=85  # Stricter matching threshold
                        )
                    
                    if match_result:
                        # Update existing task with new information
                        existing_task = next(t for t in unique_tasks.values() 
                                        if t['normalized_name'] == match_result[0])
                        existing_task['areas'].update(task_data['areas'])
                        existing_task['responsibles'].update(task_data['responsibles'])
                        existing_task['priorities'].update(task_data['priorities'])
                        existing_task['deadlines'].update(task_data['deadlines'])
                        existing_task['related_problems'].extend(task_data['related_problems'])
                    else:
                        unique_tasks[task_name] = task_data
                        
                except Exception as e:
                    print(f"Error processing construction task: {str(e)}")
                    continue

        # Add timing analysis information
        timing_analysis = data.get('timing_analysis')
        if isinstance(timing_analysis, ScheduleGraph):
            # First pass: collect dependencies
            task_dependencies = {}
            for rel in timing_analysis.relationships:
                from_task = timing_analysis.tasks[rel.from_task_id].name.lower()
                to_task = timing_analysis.tasks[rel.to_task_id].name.lower()
                if to_task not in task_dependencies:
                    task_dependencies[to_task] = set()
                task_dependencies[to_task].add(from_task)

            # Second pass: process tasks
            for task_id, timing_task in timing_analysis.tasks.items():
                try:
                    task_name = timing_task.name.lower().strip()
                    duration_str = (f"{timing_task.duration.amount} {timing_task.duration.unit}" 
                                if timing_task.duration else "No especificada")
                    
                    task_data = {
                        'name': timing_task.name,
                        'normalized_name': task_name,
                        'areas': {timing_task.location} if timing_task.location else {'No especificada'},
                        'responsibles': {timing_task.responsible} if timing_task.responsible else {'No especificado'},
                        'priorities': {'Media'} if not timing_task.priority else {timing_task.priority},
                        'deadlines': {'No especificado'},
                        'duration': duration_str,
                        'status': timing_task.status.value if timing_task.status else 'Pendiente',
                        'dependencies': task_dependencies.get(task_name, set()),
                        'can_be_parallel': timing_task.can_be_parallel,
                        'related_problems': []
                    }

                    # Update or add task
                    match_result = None
                    if unique_tasks:
                        match_result = process.extractOne(
                            task_name,
                            [t['normalized_name'] for t in unique_tasks.values()],
                            scorer=fuzz.token_sort_ratio,
                            score_cutoff=85
                        )

                    if match_result:
                        existing_task = next(t for t in unique_tasks.values() 
                                        if t['normalized_name'] == match_result[0])
                        existing_task['duration'] = duration_str
                        existing_task['dependencies'].update(task_data['dependencies'])
                        existing_task['can_be_parallel'] = task_data['can_be_parallel']
                        if timing_task.responsible:
                            existing_task['responsibles'].add(timing_task.responsible)
                        if timing_task.location:
                            existing_task['areas'].add(timing_task.location)
                    else:
                        unique_tasks[task_name] = task_data

                except Exception as e:
                    print(f"Error processing timing task: {str(e)}")
                    continue

        # Sort tasks by priority
        def get_priority_value(task):
            priority_map = {'alta': 3, 'media': 2, 'baja': 1}
            priorities = task['priorities']
            max_priority = max((priority_map.get(p.lower(), 0) for p in priorities), default=0)
            return (max_priority, len(task['related_problems']))

        # Generate formatted sections, sorted by priority
        sorted_tasks = sorted(unique_tasks.values(), key=get_priority_value, reverse=True)
        
        for task in sorted_tasks:
            # Clean and sort all fields
            areas = sorted(area for area in task['areas'] if area and area != 'None')
            responsibles = sorted(resp for resp in task['responsibles'] if resp and resp != 'None')
            priorities = sorted(prio for prio in task['priorities'] if prio and prio != 'None')
            deadlines = sorted(deadline for deadline in task['deadlines'] if deadline and deadline != 'None')
            dependencies = sorted(dep for dep in task['dependencies'] if dep)
            
            sections.extend([
                f"### {task['name']}",
                f"- **Ubicación:** {', '.join(areas) or 'No especificada'}",
                f"- **Responsable:** {', '.join(responsibles) or 'No especificado'}",
                f"- **Prioridad:** {', '.join(priorities) or 'Media'}",
                f"- **Duración:** {task['duration']}"
            ])

            if deadlines:
                sections.append(f"- **Plazo:** {', '.join(deadlines)}")
                
            if dependencies:
                sections.append(f"- **Depende de:** {', '.join(dependencies)}")
                
            if task.get('can_be_parallel'):
                sections.append("- **Nota:** Puede ejecutarse en paralelo")
                
            if task['related_problems']:
                sections.append("- **Problemas relacionados:**")
                for problem in task['related_problems']:
                    if problem['description']:
                        sections.append(f"  * {problem['description']}")
                        if problem['recommended_action']:
                            sections.append(f"    - Acción recomendada: {problem['recommended_action']}")

            sections.append(f"- **Estado:** {task['status']}\n")

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
        
        """""
        # Location analysis
        sections.append(ReportSection(
            title="Análisis de Ubicación",
            content=self._format_location_analysis(data['location_data']),
            order=3
        ))
        """
        
        # Timing analysis (new section)
        if 'timing_analysis' in data:
            sections.append(ReportSection(
                title="Análisis de Tiempos",
                content=self._format_timing_section(data['timing_analysis']),
                order=3
            ))
        
        # Problems and solutions
        sections.append(ReportSection(
            title="Problemas y Soluciones",
            content=self._format_problems_section(data['construction_analysis']),
            order=4
        ))
        
        # Chronogram
        if 'chronogram' in data:
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
        session_id: str,  # from session_results["session_id"]
        location_id: str, # from session_results["metadata"]["location_id"]
        output_dir: Path,
        location_data: Optional[Dict[str, Any]] = None,
        construction_analysis: Optional[Dict[str, Any]] = None,
        timing_analysis: Optional[Dict[str, Any]] = None,
        chronogram: Optional[str] = None,
        transcripts: Optional[List[str]] = None,  # if you want transcripts
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

            print("DEBUG: Generated report sections")
            print(sections)
            
            # Generate report files
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate markdown
            markdown_path = output_dir / "report.md"
            markdown_content = self._generate_markdown(sections)
            markdown_path.write_text(markdown_content, encoding='utf-8')
            
            print("DEBUG: Generated markdown content")

            # Generate PDF
            pdf_path = output_dir / "report.pdf"
            await self._generate_pdf(markdown_content, pdf_path)
            print("DEBUG: Generated PDF")

            docx_path = output_dir / "report.docx"
            await self._generate_docx(markdown_content,docx_path)
            print("DEBUG: Generated DOCXs")

            # Save metadata
            metadata_path = output_dir / "report_metadata.json"
            metadata = {
                "session_id": str(session_id),
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
                parts.append(section.content)
            
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


    def _get_problem_data(self, problem) -> Dict:
        """Extract problem data handling both dict and object formats"""

            # Add severity mapping
        SEVERITY_MAP = {
            'HIGH': 'Alta',
            'MEDIUM': 'Media',
            'LOW': 'Baja',
            'CRITICAL': 'Crítica',
            'Severity.HIGH': 'Alta',
            'Severity.MEDIUM': 'Media',
            'Severity.LOW': 'Baja',
            'Severity.CRITICAL': 'Crítica',
            'medium': 'Media'
        }

        if isinstance(problem, dict):
            loc_context = problem.get('location_context', {})
            raw_severity = str(problem.get('severity', 'UNKNOWN'))
            return {
                'id': str(problem.get('id')),
                'description': problem.get('description'),
                'severity': SEVERITY_MAP.get(raw_severity, raw_severity),
                'location_context': {
                    'area': loc_context.get('area', 'Área General'),
                    'observations': loc_context.get('observations', []),
                    'additional_info': loc_context.get('additional_info', {})
                },
                'recommended_action': problem.get('recommended_action'),
                'assigned_to': problem.get('assigned_to', 'No asignado'),
                'tasks': problem.get('tasks', [])
            }
        
        # Handle object
        loc_context = problem.location_context if problem.location_context else {}
        raw_severity = str(getattr(problem.severity, 'value', 'UNKNOWN'))
        return {
            'id': str(problem.id),
            'description': problem.description,
            'severity': SEVERITY_MAP.get(raw_severity, raw_severity),
            'location_context': {
                'area': getattr(loc_context, 'area', 'Área General'),
                'observations': getattr(loc_context, 'observations', []),
                'additional_info': getattr(loc_context, 'additional_info', {})
            },
            'recommended_action': getattr(problem, 'recommended_action', None),
            'assigned_to': getattr(problem, 'assigned_to', 'No asignado'),
            'tasks': getattr(problem, 'tasks', [])
        }
    
    def _get_solutions(self, problem_id: str, solutions_data: Dict) -> List[Dict]:
        """Extract solutions for a specific problem"""
        solutions = []
        for sol_id, sol_list in solutions_data.items():
            if str(sol_id) == problem_id:
                for sol in sol_list:
                    if isinstance(sol, dict):
                        solution = {
                            'problem_id': problem_id,
                            'description': sol.get('description', ''),
                            'estimated_time': sol.get('estimated_time'),
                            'priority': sol.get('priority')
                        }
                    else:
                        solution = {
                            'problem_id': problem_id,
                            'description': getattr(sol, 'description', ''),
                            'estimated_time': getattr(sol, 'estimated_time', None),
                            'priority': getattr(sol, 'priority', None)
                        }
                    solutions.append(solution)
        return solutions 
    
    async def _generate_docx(self, markdown_content: str, output_path: Path) -> None:
        """Generate DOCX from markdown content using python-docx"""
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        import re

        document = Document()

        # Set default font
        style = document.styles['Normal']
        style.font.name = 'Arial'
        style.font.size = Pt(11)

        def apply_inline_formatting(paragraph, text: str) -> None:
            """Apply bold and italic formatting to text within a paragraph"""
            # Handle bold text
            if '**' in text:
                parts = text.split('**')
                for i, part in enumerate(parts):
                    if i % 2 == 1:  # Bold sections
                        run = paragraph.add_run(part)
                        run.bold = True
                    else:
                        paragraph.add_run(part)
                return

            # Handle italic text
            if '*' in text or '_' in text:
                pattern = r'\*(.*?)\*|_(.*?)_'
                matches = list(re.finditer(pattern, text))
                if matches:
                    last_end = 0
                    for match in matches:
                        # Add text before the italic
                        if match.start() > last_end:
                            paragraph.add_run(text[last_end:match.start()])
                        # Add italic text
                        italic_text = match.group(1) or match.group(2)
                        run = paragraph.add_run(italic_text)
                        run.italic = True
                        last_end = match.end()
                    # Add remaining text
                    if last_end < len(text):
                        paragraph.add_run(text[last_end:])
                    return

            # Plain text
            paragraph.add_run(text)

        # Process content line by line
        lines = markdown_content.split('\n')
        current_list = []
        in_list = False

        for line in lines:
            line = line.rstrip()
            
            # Skip empty lines but handle list endings
            if not line:
                if in_list and current_list:
                    # End the current list
                    for item in current_list:
                        list_para = document.add_paragraph(style='List Bullet')
                        apply_inline_formatting(list_para, item)
                    current_list = []
                    in_list = False
                continue

            # Headers
            if line.startswith('#'):
                level = len(re.match(r'^#+', line).group())
                text = line.strip('#').strip()
                document.add_heading(text, level)
                continue

            # Lists
            if line.strip().startswith(('- ', '* ', '+ ')):
                in_list = True
                item_text = line.strip()[2:].strip()
                current_list.append(item_text)
                continue

            # Handle any pending list items before processing other content
            if in_list and current_list:
                for item in current_list:
                    list_para = document.add_paragraph(style='List Bullet')
                    apply_inline_formatting(list_para, item)
                current_list = []
                in_list = False

            # Regular paragraphs
            para = document.add_paragraph()
            apply_inline_formatting(para, line)

        # Handle any remaining list items
        if current_list:
            for item in current_list:
                list_para = document.add_paragraph(style='List Bullet')
                apply_inline_formatting(list_para, item)

        # Save the document
        document.save(str(output_path))