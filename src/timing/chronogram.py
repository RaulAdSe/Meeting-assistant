from typing import List, Dict, Optional
from datetime import datetime, timedelta
import uuid
from .models import Task, Duration, ScheduleGraph, TaskRelationship, TaskRelationType

class ChronogramVisualizer:
    """Creates visualizations of construction schedules"""
    
    def generate_mermaid_gantt(
        self, 
        schedule: ScheduleGraph,
        start_date: datetime
    ) -> str:
        """
        Generate a Mermaid.js Gantt diagram.
        
        Args:
            schedule: ScheduleGraph containing tasks and relationships
            start_date: Project start date
            
        Returns:
            Mermaid.js Gantt diagram markup
        """
        lines = [
            "gantt",
            "    dateFormat YYYY-MM-DD",
            "    title Cronograma de Construcción",
            "    %% Tasks are grouped by parallel execution",
            ""
        ]
        
        # Calculate task dates
        task_dates = self._calculate_task_dates(schedule, start_date)
        
        # Group tasks by parallel execution
        task_groups = self._group_tasks(schedule)
        
        # Add sections for each group
        for group_idx, group in enumerate(task_groups):
            if len(group) > 1:
                lines.append(f"    section Tareas Paralelas {group_idx + 1}")
            else:
                lines.append("    section Tareas Secuenciales")
                
            # Add tasks in group
            for task_id in group:
                task = schedule.tasks[task_id]
                task_dates_info = task_dates[task_id]
                
                # Format dependencies
                dependencies = [
                    str(rel.from_task_id) 
                    for rel in schedule.relationships 
                    if rel.to_task_id == task_id
                ]
                dependency_str = f" after {','.join(dependencies)}" if dependencies else ""
                
                # Add any risk indicators and responsible person
                risk_indicator = " 🚨" if task.metadata.get('risks') else ""
                responsible = f" [{task.responsible}]" if task.responsible else ""
                
                # Format task line
                lines.append(
                    f"    {task.name}{risk_indicator}{responsible}{dependency_str} : "
                    f"{task_dates_info['start'].strftime('%Y-%m-%d')}, "
                    f"{task_dates_info['end'].strftime('%Y-%m-%d')}"
                )
            
            lines.append("")
        
        return "\n".join(lines)

    def generate_html_visualization(
        self,
        schedule: ScheduleGraph,
        start_date: datetime
    ) -> str:
        """Generate an interactive HTML visualization using vis-timeline"""
        task_dates = self._calculate_task_dates(schedule, start_date)
        
        # Create timeline data
        timeline_data = []
        for task_id, task in schedule.tasks.items():
            dates = task_dates[task_id]
            
            # Find any delays required before this task
            delays = [
                rel.delay for rel in schedule.relationships
                if rel.to_task_id == task_id 
                and rel.relation_type == TaskRelationType.DELAY
                and rel.delay is not None
            ]
            
            delay_text = f" (Espera: {delays[0].amount} {delays[0].unit})" if delays else ""
            
            timeline_data.append({
                "id": str(task_id),
                "content": f"<div class='task-item'>"
                          f"<strong>{task.name}</strong>{delay_text}"
                          f"{f'<br>👤 {task.responsible}' if task.responsible else ''}"
                          f"</div>",
                "start": dates['start'].isoformat(),
                "end": dates['end'].isoformat(),
                "group": len(self._find_parallel_group(schedule, task_id)) > 1
            })
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Cronograma de Construcción</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.5.1/vis-timeline-graph2d.min.js"></script>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.5.1/vis-timeline-graph2d.min.css" rel="stylesheet" type="text/css" />
            <style>
                .task-item {{
                    padding: 5px;
                    border-radius: 3px;
                }}
                .vis-item {{
                    border-color: #2196F3;
                    background-color: #E3F2FD;
                }}
                .vis-item.vis-selected {{
                    border-color: #1565C0;
                    background-color: #BBDEFB;
                }}
            </style>
        </head>
        <body>
            <div id="timeline"></div>
            <script>
                var container = document.getElementById('timeline');
                var items = new vis.DataSet({str(timeline_data)});
                
                var groups = new vis.DataSet([
                    {{id: true, content: 'Tareas Paralelas'}},
                    {{id: false, content: 'Tareas Secuenciales'}}
                ]);
                
                var options = {{
                    groupOrder: 'content',
                    editable: false,
                    stack: true,
                    stackSubgroups: true,
                    zoomKey: 'ctrlKey'
                }};
                
                var timeline = new vis.Timeline(container, items, groups, options);
            </script>
        </body>
        </html>
        """

    def _calculate_task_dates(self, schedule: ScheduleGraph, start_date: datetime) -> Dict[uuid.UUID, Dict[str, datetime]]:
        """Calculate start and end dates for all tasks considering dependencies"""
        if not isinstance(schedule, ScheduleGraph):
            raise TypeError(f"Expected ScheduleGraph object, got {type(schedule).__name__}")
        
        task_dates = {}
        task_order = self._get_topological_order(schedule)
        
        # Define a small buffer between sequential tasks (e.g., 1 day)
        TASK_BUFFER = timedelta(days=1)
        
        for task_id in task_order:
            task = schedule.tasks[task_id]
            
            # Initialize with project start date
            task_start = start_date
            
            # Find all dependencies
            dependencies = [rel for rel in schedule.relationships if rel.to_task_id == task_id]
            
            # Update start based on dependencies
            if dependencies:
                dependency_ends = []
                for dep in dependencies:
                    if dep.from_task_id not in task_dates:
                        from_task = schedule.tasks[dep.from_task_id]
                        task_dates[dep.from_task_id] = {
                            'start': start_date,
                            'end': start_date + timedelta(days=from_task.duration.to_days())
                        }
                    
                    dep_end = task_dates[dep.from_task_id]['end']
                    
                    # Add delay if specified
                    if dep.relation_type == TaskRelationType.DELAY and dep.delay:
                        dep_end += timedelta(days=dep.delay.to_days())
                    elif dep.relation_type == TaskRelationType.SEQUENTIAL:
                        # Add buffer for sequential tasks
                        dep_end += TASK_BUFFER
                        
                    dependency_ends.append(dep_end)
                
                # Start after latest dependency
                if dependency_ends:
                    task_start = max(dependency_ends)
            
            # Calculate end date
            task_end = task_start + timedelta(days=task.duration.to_days())
            task_dates[task_id] = {
                'start': task_start,
                'end': task_end
            }
        
        return task_dates

    def _get_topological_order(self, schedule: ScheduleGraph) -> List[uuid.UUID]:
        """Get tasks in topological order (respecting dependencies)"""
        # Implementation of topological sort
        visited = set()
        temp_mark = set()
        order = []
        
        def visit(task_id: uuid.UUID):
            if task_id in temp_mark:
                raise ValueError("Circular dependency detected")
            if task_id not in visited:
                temp_mark.add(task_id)
                
                # Visit dependencies
                for rel in schedule.relationships:
                    if rel.to_task_id == task_id:
                        visit(rel.from_task_id)
                
                temp_mark.remove(task_id)
                visited.add(task_id)
                order.append(task_id)
        
        for task_id in schedule.tasks:
            if task_id not in visited:
                visit(task_id)
        
        return list(reversed(order))

    def _group_tasks(self, schedule: ScheduleGraph) -> List[List[uuid.UUID]]:
        """Group tasks by parallel execution"""
        groups = []
        seen_tasks = set()
        
        # First add parallel groups
        for parallel_group in schedule.parallel_groups:
            groups.append(list(parallel_group))
            seen_tasks.update(parallel_group)
        
        # Then add remaining tasks individually
        for task_id in schedule.tasks:
            if task_id not in seen_tasks:
                groups.append([task_id])
                
        return groups

    def _find_parallel_group(self, schedule: ScheduleGraph, task_id: uuid.UUID) -> set:
        """Find the parallel group containing a task"""
        for group in schedule.parallel_groups:
            if task_id in group:
                return group
        return {task_id}  # Return singleton set if task is not in any parallel group