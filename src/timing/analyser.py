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
            'tasks': [],
            'patterns': [],
            'deviations': [],
            'success_rates': {}
        }
        
        try:
            # Get past visits
            past_visits = self.history_service.get_visit_history(location_id)
            
            for visit in past_visits:
                # Get chronogram entries for this visit
                entries = self.history_service.chronogram_repo.get_by_visit(visit.id)
                
                for entry in entries:
                    task_history = {
                        'name': entry.task_name,
                        'planned_duration': (entry.planned_end - entry.planned_start).days,
                        'actual_duration': None,
                        'success': False
                    }
                    
                    # Calculate actual duration if task was completed
                    if entry.status == ChronogramStatus.COMPLETED and entry.actual_start and entry.actual_end:
                        task_history['actual_duration'] = (entry.actual_end - entry.actual_start).days
                        task_history['success'] = True
                    
                    historical_context['tasks'].append(task_history)
            
            # Analyze patterns and calculate metrics
            if historical_context['tasks']:
                historical_context['patterns'] = self._analyze_timing_patterns(
                    historical_context['tasks']
                )
                historical_context['success_rates'] = self._calculate_success_rates(
                    historical_context['tasks']
                )
                historical_context['deviations'] = self._calculate_deviations(
                    historical_context['tasks']
                )
            
            return historical_context
            
        except Exception as e:
            self.logger.warning(f"Error getting historical data: {str(e)}")
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
                model="gpt-4",
                messages=[{
                    "role": "system",
                    "content": f"""You are a construction project analyzer that extracts tasks and their relationships from transcripts.
                    Consider this historical data from similar projects:
                    {context_summary}
                    
                    Use this historical context to:
                    1. Validate proposed durations against past performance
                    2. Identify potential timing risks based on past patterns
                    3. Suggest parallel execution based on successful past experiences
                    4. Adjust time estimates based on historical deviations
                    
                    For each task identify:
                    - Task name and description
                    - Duration (with unit: days, weeks, months)
                    - Dependencies on other tasks
                    - If it can be done in parallel (based on history)
                    - Any delays or waiting periods required
                    - Confidence level based on historical data"""
                }, {
                    "role": "user",
                    "content": transcript_text
                }],
                functions=[{
                    "name": "extract_construction_tasks",
                    "description": "Extract tasks and relationships from construction transcript",
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
                                                "unit": {"type": "string"}
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
                                        "type": {"type": "string"},
                                        "delay": {
                                            "type": "object",
                                            "properties": {
                                                "amount": {"type": "number"},
                                                "unit": {"type": "string"}
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
                function_call={"name": "extract_construction_tasks"}
            )

            # Safely parse GPT response
            try:
                gpt_data = json.loads(response.choices[0].message.function_call.arguments)
            except (json.JSONDecodeError, AttributeError, IndexError) as e:
                self.logger.error(f"Failed to parse GPT response: {str(e)}")
                raise ValueError("Invalid GPT response format")

            return self._create_schedule_from_gpt_response(gpt_data)
            
        except Exception as e:
            self.logger.error(f"GPT analysis failed: {str(e)}")
            raise

    def _enhance_with_historical_data(
        self,
        schedule: ScheduleGraph,
        historical_context: Dict
    ) -> ScheduleGraph:
        """Enhance schedule with historical insights"""
        for task_id, task in schedule.tasks.items():
            # Find similar historical tasks
            historical_matches = self._find_similar_tasks(
                task.name,
                historical_context['tasks']
            )
            
            if historical_matches:
                # Calculate average actual duration
                actual_durations = [
                    match['actual_duration'] 
                    for match in historical_matches 
                    if match['actual_duration'] is not None
                ]
                
                if actual_durations:
                    avg_duration = sum(actual_durations) / len(actual_durations)
                    # Adjust task duration if significant deviation
                    if abs(task.duration.to_days() - avg_duration) > 2:
                        task.metadata['historical_warning'] = (
                            f"Historical duration differs: {avg_duration:.1f} days"
                        )
                        task.metadata['historical_duration'] = avg_duration
                
                # Add success rate to metadata
                success_rate = sum(1 for m in historical_matches if m['success']) / len(historical_matches)
                task.metadata['historical_success_rate'] = success_rate
        
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
        """Create ScheduleGraph from GPT response"""
        schedule = ScheduleGraph(tasks={}, relationships=[])
        task_ids = {}
        
        # Create tasks
        for task_data in response['tasks']:
            # Add default values and handle missing duration data safely
            duration_data = task_data.get('duration', {'amount': 1, 'unit': 'days'})
            task = Task(
                name=task_data['name'],
                description=task_data['description'],
                duration=Duration(**duration_data),
                can_be_parallel=task_data.get('can_be_parallel', False),  # Add default
                responsible=task_data.get('responsible'),
                location=task_data.get('location'),
                metadata={
                    'confidence': task_data.get('confidence', 0.0),
                    'historical_deviation': task_data.get('historical_deviation'),
                    'risks': task_data.get('risks', [])
                }
            )
            schedule.add_task(task)
            task_ids[task_data['name']] = task.id

        # Create relationships
        for rel_data in response['relationships']:
            try:
                from_id = task_ids[rel_data['from_task']]
                to_id = task_ids[rel_data['to_task']]
                rel_type = TaskRelationType[rel_data['type'].upper()]
                
                relationship = TaskRelationship(
                    from_task_id=from_id,
                    to_task_id=to_id,
                    relation_type=rel_type,
                    delay=Duration(**rel_data['delay']) if rel_data.get('delay') else None
                )
                schedule.add_relationship(relationship)
            except KeyError:
                self.logger.warning(f"Invalid task reference in relationship: {rel_data}")
                continue

        # Add parallel groups
        for group in response.get('parallel_groups', []):
            try:
                task_group = {task_ids[task_name] for task_name in group}
                if self._validate_parallel_group_feasibility(task_group, schedule):
                    schedule.add_parallel_group(task_group)
            except KeyError:
                self.logger.warning(f"Invalid task reference in parallel group: {group}")
                continue

        return schedule

    def _validate_parallel_group_feasibility(
        self, 
        task_group: Set[uuid.UUID], 
        schedule: ScheduleGraph
    ) -> bool:
        """Validate if a group of tasks can feasibly be executed in parallel"""
        tasks = [schedule.tasks[task_id] for task_id in task_group]
        
        # Check total resource requirements
        total_duration = sum(task.duration.to_days() for task in tasks)
        if total_duration > 90:  # More than 3 months parallel is risky
            return False
            
        # Check for tasks with low confidence
        low_confidence_tasks = [
            task for task in tasks 
            if task.metadata.get('confidence', 0) < 0.7
        ]
        if low_confidence_tasks:
            return False
            
        # Check for high-risk tasks
        high_risk_tasks = [
            task for task in tasks
            if any('alto riesgo' in risk.lower() 
                  for risk in task.metadata.get('risks', []))
        ]
        if high_risk_tasks:
            return False
            
        return True