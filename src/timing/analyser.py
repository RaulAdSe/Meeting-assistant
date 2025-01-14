import os
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime
import logging
import openai
import json
from pathlib import Path
import uuid
from .models import (
    Task, TaskRelationType, TaskRelationship,
    Duration, ScheduleGraph
)
from src.historical_data.services.visit_history import VisitHistoryService
from src.historical_data.models.models import Visit, ChronogramEntry, ChronogramStatus
from collections import defaultdict

class TaskAnalyzer:
    """Analyzes transcripts using GPT and historical data to extract and validate tasks"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.history_service = VisitHistoryService()
        
        # Load API key from environment
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = openai.Client(api_key=os.getenv('OPENAI_API_KEY'))

    def analyze_transcript(
        self, 
        transcript_text: str,
        location_id: uuid.UUID,
        visit_id: Optional[uuid.UUID] = None
    ) -> ScheduleGraph:
        """
        Analyze transcript using GPT and historical data to extract tasks.
        
        Args:
            transcript_text: Raw transcript text
            location_id: ID of the construction location
            visit_id: Optional current visit ID
            
        Returns:
            ScheduleGraph with tasks and relationships, enhanced with historical data
        """
        if not transcript_text.strip():
            raise ValueError("Empty transcript text")
            
        try:
            # Get historical data first
            historical_context = self._get_historical_context(location_id)
            
            # Use GPT with historical context for initial analysis
            initial_schedule = self._analyze_with_gpt(transcript_text, historical_context)
            
            # Enhance schedule with historical insights
            enhanced_schedule = self._enhance_with_historical_data(
                initial_schedule,
                historical_context
            )
            
            # Validate and adjust timings
            final_schedule = self._validate_and_adjust_schedule(enhanced_schedule)
            
            return final_schedule
            
        except Exception as e:
            self.logger.error(f"Error analyzing transcript: {str(e)}")
            raise

    def _get_historical_context(self, location_id: uuid.UUID) -> Dict:
        """Gather historical timing data for the location"""
        historical_context = {
            'tasks': defaultdict(list),
            'patterns': [],
            'deviations': {}
        }
        
        try:
            # Get past visits
            past_visits = self.history_service.get_visit_history(location_id)
            
            for visit in past_visits:
                # Get chronogram entries for this visit
                entries = self.history_service.chronogram_repo.get_by_visit(visit.id)
                
                for entry in entries:
                    task_data = {
                        'planned_duration': (entry.planned_end - entry.planned_start).days,
                        'actual_duration': None,
                        'status': entry.status,
                        'actual_start': entry.actual_start,
                        'actual_end': entry.actual_end,
                        'dependencies': []
                    }
                    
                    # Calculate actual duration if completed
                    if entry.status == ChronogramStatus.COMPLETED and entry.actual_start and entry.actual_end:
                        task_data['actual_duration'] = (entry.actual_end - entry.actual_start).days
                    
                    # Add dependency information
                    if entry.dependencies:
                        for dep_id in entry.dependencies:
                            dep_entry = next((e for e in entries if e.id == dep_id), None)
                            if dep_entry:
                                task_data['dependencies'].append({
                                    'task_name': dep_entry.task_name,
                                    'actual_end': dep_entry.actual_end
                                })
                    
                    historical_context['tasks'][entry.task_name].append(task_data)
            
            return historical_context
            
        except Exception as e:
            self.logger.error(f"Error getting historical context: {str(e)}")
            return historical_context
    
    def _analyze_with_gpt(
        self,
        transcript_text: str,
        historical_context: Dict
    ) -> ScheduleGraph:
        """Use GPT to analyze transcript with historical context"""
        try:
            # Prepare historical context summary for GPT
            context_summary = self._format_historical_context(historical_context)
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "system",
                    "content": f"""Eres un analizador de proyectos de construcción que extrae tareas y sus relaciones de transcripciones.
                    Considera estos datos históricos de proyectos similares:
                    {context_summary}
                    
                    Usa este contexto histórico para:
                    1. Validar las duraciones propuestas contra el rendimiento pasado
                    2. Identificar riesgos potenciales de tiempo basados en patrones anteriores
                    3. Sugerir ejecución en paralelo basada en experiencias exitosas pasadas
                    4. Ajustar estimaciones de tiempo basadas en desviaciones históricas
                    
                    Para cada tarea identifica:
                    - Nombre y descripción de la tarea
                    - Duración (con unidad: días, semanas, meses)
                    - Dependencias con otras tareas
                    - Si se puede hacer en paralelo (basado en historial)
                    - Cualquier retraso o período de espera requerido
                    - Nivel de confianza basado en datos históricos"""
                }, {
                    "role": "user",
                    "content": transcript_text
                }],
                functions=[{
                    "name": "extract_construction_tasks",
                    "description": "Extrae tareas y relaciones de la transcripción de construcción",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "description": {"type": "string"},
                                        "duration": {
                                            "type": "object",
                                            "properties": {
                                                "amount": {"type": "number"},
                                                "unit": {
                                                    "type": "string",
                                                    "enum": [
                                                        "dia", "dias", "día", "días",
                                                        "semana", "semanas",
                                                        "mes", "meses"
                                                    ]
                                                }
                                            }
                                        },
                                        "can_be_parallel": {"type": "boolean"},
                                        "confidence": {"type": "number"},
                                        "historical_deviation": {"type": "number", "nullable": True},
                                        "responsible": {"type": "string", "nullable": True},
                                        "location": {"type": "string", "nullable": True},
                                        "risks": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        }
                                    }
                                }
                            },
                            "relationships": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "from_task": {"type": "string"},
                                        "to_task": {"type": "string"},
                                        "type": {"type": "string", "enum": ["secuencial", "paralelo", "espera"]},
                                        "delay": {
                                            "type": "object",
                                            "properties": {
                                                "amount": {"type": "number"},
                                                "unit": {"type": "string", "enum": ["dias", "semanas", "meses"]}
                                            },
                                            "nullable": True
                                        }
                                    }
                                }
                            },
                            "parallel_groups": {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            }
                        }
                    }
                }],
                function_call={"name": "extract_construction_tasks"},
                temperature=0.3
            )

            # Parse GPT response
            try:
                gpt_data = json.loads(response.choices[0].message.function_call.arguments)
                return self._create_schedule_from_gpt_response(gpt_data)
                
            except (json.JSONDecodeError, AttributeError, IndexError) as e:
                self.logger.error(f"Failed to parse GPT response: {str(e)}")
                raise ValueError("Invalid GPT response format")
                
        except Exception as e:
            self.logger.error(f"GPT analysis failed: {str(e)}")
            raise

    def _enhance_with_historical_data(self, schedule: ScheduleGraph, historical_context: Dict) -> ScheduleGraph:
        """Enhance schedule with historical insights"""
        try:
            # Get historical data for task tracking
            task_history = defaultdict(list)
            
            # Process each task's historical data
            for task_name, task_data in historical_context.get('tasks', {}).items():
                for record in task_data:
                    if record.get('actual_duration') is not None:
                        task_history[task_name].append({
                            'planned_duration': record['planned_duration'],
                            'actual_duration': record['actual_duration'],
                            'status': record.get('status'),
                            'completion_date': record.get('completion_date')
                        })

            # Enhance each task with historical data
            for task_id, task in schedule.tasks.items():
                historical_data = task_history.get(task.name, [])
                if historical_data:
                    # Focus on completed tasks
                    completed_tasks = [t for t in historical_data 
                                    if t.get('status') == ChronogramStatus.COMPLETED]
                    
                    if completed_tasks:
                        # Calculate statistics
                        planned_durations = [t['planned_duration'] for t in completed_tasks]
                        actual_durations = [t['actual_duration'] for t in completed_tasks]
                        
                        task.metadata.update({
                            'historical_count': len(completed_tasks),
                            'avg_historical_duration': sum(actual_durations) / len(actual_durations),
                            'historical_min_duration': min(actual_durations),
                            'historical_max_duration': max(actual_durations),
                            'typical_deviation': (sum(actual_durations) / len(actual_durations)) - 
                                            (sum(planned_durations) / len(planned_durations))
                        })

            # Process relationships
            relationship_history = defaultdict(list)
            for rel in schedule.relationships:
                from_task = schedule.tasks[rel.from_task_id]
                to_task = schedule.tasks[rel.to_task_id]
                key = f"{from_task.name}->{to_task.name}"
                
                # Find historical gaps between these tasks
                for hist_data in historical_context.get('tasks', {}).get(to_task.name, []):
                    if hist_data.get('actual_start') and hist_data.get('dependencies'):
                        for dep in hist_data['dependencies']:
                            if dep.get('task_name') == from_task.name and dep.get('actual_end'):
                                gap = (hist_data['actual_start'] - dep['actual_end']).days
                                relationship_history[key].append(gap)

                if relationship_history[key]:
                    rel.metadata.update({
                        'historical_avg_gap': sum(relationship_history[key]) / len(relationship_history[key]),
                        'min_gap': min(relationship_history[key]),
                        'max_gap': max(relationship_history[key])
                    })

            return schedule
            
        except Exception as e:
            self.logger.error(f"Error enhancing schedule: {str(e)}")
            return schedule

    def _validate_and_adjust_schedule(self, schedule: ScheduleGraph) -> ScheduleGraph:
        """Validate and adjust schedule based on constraints and historical data"""
        # Check for unrealistic parallel tasks
        parallel_groups = schedule.parallel_groups.copy()
        for group in parallel_groups:
            tasks = [schedule.tasks[task_id] for task_id in group]
            if not self._validate_parallel_group(tasks):
                # Split group if historically risky
                schedule.parallel_groups.remove(group)
                # Create sequential relationships instead
                task_list = list(group)
                for i in range(len(task_list) - 1):
                    rel = TaskRelationship(
                        from_task_id=task_list[i],
                        to_task_id=task_list[i + 1],
                        relation_type=TaskRelationType.SEQUENTIAL
                    )
                    schedule.relationships.append(rel)
        
        return schedule

    def _format_historical_context(self, context: Dict) -> str:
        """Format historical context for GPT prompt"""
        summary = []
        
        if context['tasks']:
            summary.append("Historical Task Patterns:")
            for pattern in context['patterns']:
                summary.append(f"- {pattern}")
            
            summary.append("\nTypical Deviations:")
            for task_name, deviation in context['deviations'].items():
                summary.append(f"- {task_name}: {deviation:+.1f} days")
            
            summary.append("\nSuccess Rates:")
            for task_name, rate in context['success_rates'].items():
                summary.append(f"- {task_name}: {rate*100:.0f}%")
        
        return "\n".join(summary)

    def _find_similar_tasks(self, task_name: str, historical_tasks: List[Dict]) -> List[Dict]:
        """Find similar tasks in historical data using name similarity"""
        similar_tasks = []
        task_name_lower = task_name.lower()
        
        for hist_task in historical_tasks:
            hist_name_lower = hist_task['name'].lower()
            # Simple similarity check - could be enhanced with fuzzy matching
            if (task_name_lower in hist_name_lower or 
                hist_name_lower in task_name_lower or
                self._calculate_similarity(task_name_lower, hist_name_lower) > 0.8):
                similar_tasks.append(hist_task)
        
        return similar_tasks

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity ratio"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, str1, str2).ratio()

    def _validate_parallel_group(self, tasks: List[Task]) -> bool:
        """Validate if tasks can really be executed in parallel based on history"""
        # Check total duration - parallel tasks shouldn't be too long
        total_duration = sum(task.duration.to_days() for task in tasks)
        if total_duration > 30:  # Arbitrary threshold
            return False
        
        # Check historical success rates
        for task in tasks:
            if (task.metadata.get('historical_success_rate', 1.0) < 0.7 or
                task.metadata.get('historical_warning')):
                return False
        
        return True

    def _analyze_timing_patterns(self, historical_tasks: List[Dict]) -> List[str]:
        """Analyze patterns in historical timing data"""
        patterns = []
        
        # Group tasks by name
        from collections import defaultdict
        task_groups = defaultdict(list)
        for task in historical_tasks:
            task_groups[task['name']].append(task)
        
        # Analyze patterns for each task type
        for task_name, tasks in task_groups.items():
            # Calculate average deviation
            planned_vs_actual = [
                (t['actual_duration'] - t['planned_duration'])
                for t in tasks 
                if t['actual_duration'] is not None
            ]
            
            if planned_vs_actual:
                avg_deviation = sum(planned_vs_actual) / len(planned_vs_actual)
                if abs(avg_deviation) >= 1:
                    patterns.append(
                        f"{task_name} typically takes "
                        f"{'+' if avg_deviation > 0 else ''}{avg_deviation:.1f} "
                        f"days compared to plan"
                    )
        
        return patterns

    def _calculate_success_rates(self, historical_tasks: List[Dict]) -> Dict[str, float]:
        """Calculate success rates for each task type"""
        success_rates = {}
        task_groups = defaultdict(list)
        
        for task in historical_tasks:
            task_groups[task['name']].append(task['success'])
        
        for task_name, successes in task_groups.items():
            if successes:  # Check if list is not empty
                success_rates[task_name] = sum(successes) / len(successes)
            else:
                success_rates[task_name] = 0.0  # Default value for no historical data
        
        return success_rates

    def _calculate_deviations(self, historical_tasks: List[Dict]) -> Dict[str, float]:
        """Calculate average timing deviations for each task type"""
        deviations = {}
        task_groups = defaultdict(list)
        
        for task in historical_tasks:
            if task['actual_duration'] is not None:
                deviation = task['actual_duration'] - task['planned_duration']
                task_groups[task['name']].append(deviation)
        
        for task_name, task_deviations in task_groups.items():
            if task_deviations:
                deviations[task_name] = sum(task_deviations) / len(task_deviations)
        
        return deviations


    def _create_schedule_from_gpt_response(self, response: Dict) -> ScheduleGraph:
        """Create ScheduleGraph from GPT response with improved task name matching"""
        schedule = ScheduleGraph(tasks={}, relationships=[])
        task_ids = {}
        task_name_map = {}  # Map for fuzzy matching task names
        
        # First pass: Create all tasks
        for task_data in response.get('tasks', []):
            # Add default values and handle missing duration data safely
            duration_data = task_data.get('duration', {'amount': 1, 'unit': 'days'})
            
            # Ensure confidence is a float if present
            confidence = task_data.get('confidence')
            if confidence is not None:
                confidence = float(confidence)
            
            task = Task(
                name=task_data['name'],
                description=task_data.get('description', ''),
                duration=Duration(**duration_data),
                can_be_parallel=task_data.get('can_be_parallel', False),
                responsible=task_data.get('responsible'),
                location=task_data.get('location'),
                metadata={
                    'confidence': confidence,
                    'historical_deviation': task_data.get('historical_deviation'),
                    'risks': task_data.get('risks', [])
                }
            )
            schedule.add_task(task)
            
            # Store both exact and normalized task names for matching
            task_ids[task_data['name']] = task.id
            normalized_name = self._normalize_task_name(task_data['name'])
            task_name_map[normalized_name] = task.id
        
        # Second pass: Create relationships with robust name matching
        for rel_data in response.get('relationships', []):
            try:
                # Try to find task IDs using various matching methods
                from_id = self._find_task_id(rel_data['from_task'], task_ids, task_name_map)
                to_id = self._find_task_id(rel_data['to_task'], task_ids, task_name_map)
                
                if from_id and to_id:
                    rel_type = TaskRelationType[rel_data['type'].upper()]
                    relationship = TaskRelationship(
                        from_task_id=from_id,
                        to_task_id=to_id,
                        relation_type=rel_type,
                        delay=Duration(**rel_data['delay']) if rel_data.get('delay') else None
                    )
                    schedule.add_relationship(relationship)
                else:
                    self.logger.warning(
                        f"Skipping relationship due to unmatched tasks: {rel_data['from_task']} -> {rel_data['to_task']}"
                    )
            except Exception as e:
                self.logger.warning(f"Error creating relationship {rel_data}: {str(e)}")
                continue
        
        # Add parallel groups with robust name matching
        for group in response.get('parallel_groups', []):
            try:
                task_group = set()
                for task_name in group:
                    task_id = self._find_task_id(task_name, task_ids, task_name_map)
                    if task_id:
                        task_group.add(task_id)
                    else:
                        self.logger.warning(f"Task not found for parallel group: {task_name}")
                
                if task_group and self._validate_parallel_group_feasibility(task_group, schedule):
                    schedule.add_parallel_group(task_group)
            except Exception as e:
                self.logger.warning(f"Error creating parallel group {group}: {str(e)}")
                continue
        
        return schedule

    def _normalize_task_name(self, name: str) -> str:
        """Normalize task name for fuzzy matching"""
        import unicodedata
        import re
        
        # Convert to lowercase and remove accents
        name = name.lower()
        name = ''.join(c for c in unicodedata.normalize('NFD', name)
                    if unicodedata.category(c) != 'Mn')
        
        # Remove special characters and extra spaces
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name

    def _find_task_id(self, task_name: str, task_ids: Dict, task_name_map: Dict) -> Optional[uuid.UUID]:
        """Find task ID using various matching methods"""
        # Try exact match first
        if task_name in task_ids:
            return task_ids[task_name]
        
        # Try normalized match
        normalized_name = self._normalize_task_name(task_name)
        if normalized_name in task_name_map:
            return task_name_map[normalized_name]
        
        # Try fuzzy matching if exact and normalized matches fail
        try:
            from difflib import get_close_matches
            normalized_names = list(task_name_map.keys())
            matches = get_close_matches(normalized_name, normalized_names, n=1, cutoff=0.8)
            if matches:
                return task_name_map[matches[0]]
        except Exception as e:
            self.logger.debug(f"Fuzzy matching failed for {task_name}: {str(e)}")
        
        return None

    def _validate_parallel_group_feasibility(
        self, 
        task_group: Set[uuid.UUID], 
        schedule: ScheduleGraph
    ) -> bool:
        """Validate if a group of tasks can feasibly be executed in parallel"""
        tasks = [schedule.tasks[task_id] for task_id in task_group]
        
        # Check total duration - parallel tasks shouldn't be too long
        total_duration = sum(task.duration.to_days() for task in tasks)
        if total_duration > 90:  # More than 3 months parallel is risky
            return False
            
        # Check for tasks with low confidence - handle None values
        low_confidence_tasks = [
            task for task in tasks 
            if task.metadata.get('confidence') is not None and 
            float(task.metadata['confidence']) < 0.7
        ]
        if low_confidence_tasks:
            return False
            
        # Check for high-risk tasks - handle potential missing 'risks' key
        high_risk_tasks = [
            task for task in tasks
            if any('alto riesgo' in risk.lower() 
                for risk in task.metadata.get('risks', []))
        ]
        if high_risk_tasks:
            return False
            
        return True