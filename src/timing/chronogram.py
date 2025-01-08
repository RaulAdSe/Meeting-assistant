from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
from .models import ScheduleGraph, Task, TaskRelationType

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
                
                # Add risk indicators if any
                risks = task.metadata.get('risks', [])
                risk_indicator = " 🚨" if risks else ""
                
                # Format task line
                lines.append(
                    f"    {task.name}{risk_indicator}{dependency_str} : "
                    f"{task_dates_info['start'].strftime('%Y-%m-%d')}, "
                    f"{task_dates_info['end'].strftime('%Y-%m-%d')}"
                )
                
                # Add risk details if any
                for risk in risks:
                    lines.append(f"    %% Risk: {risk}")
            
            lines.append("")
        
        return "\n".join(lines)

    def generate_html_visualization(
        self,
        schedule: ScheduleGraph,
        start_date: datetime
    ) -> str:
        """Generate an interactive HTML visualization using a timeline library"""
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
                "name": task.name + delay_text,
                "start": dates['start'].isoformat(),
                "end": dates['end'].isoformat(),
                "dependencies": [
                    str(rel.from_task_id) 
                    for rel in schedule.relationships 
                    if rel.to_task_id == task_id
                ],
                "risks": task.metadata.get('risks', []),
                "confidence": task.metadata.get('confidence', 1.0),
                "responsible": task.responsible
            })
        
        # Generate HTML with timeline visualization
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Cronograma de Construcción</title>
            <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.5.1/vis-timeline-graph2d.min.js"></script>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.5.1/vis-timeline-graph2d.min.css" rel="stylesheet" type="text/css" />
            <style>
                .timeline-item {{
                    border-radius: 4px;
                    padding: 4px;
                }}
                .high-risk {{
                    background-color: #ffebee;
                    border-left: 4px solid #ef5350;
                }}
                .low-confidence {{
                    opacity: 0.7;
                    border-style: dashed;
                }}
            </style>
        </head>
        <body>
            <div id="timeline"></div>
            <script>
                var data = {json.dumps(timeline_data)};
                var container = document.getElementById('timeline');
                
                var items = new vis.DataSet(data.map(task => {{
                    var className = [];
                    if (task.risks && task.risks.length > 0) className.push('high-risk');
                    if (task.confidence < 0.7) className.push('low-confidence');
                    
                    return {{
                        id: task.id,
                        content: `<div>
                            <strong>${{task.name}}</strong>
                            ${{task.responsible ? `<br>Responsable: ${{task.responsible}}` : ''}}
                            ${{task.risks.length ? `<br>⚠️ ${{task.risks.join(', ')}}` : ''}}
                        </div>`,
                        start: task.start,
                        end: task.end,
                        className: className.join(' ')
                    }};
                }}));
                
                var options = {{
                    editable: false,
                    orientation: 'top',
                    stack: true,
                    zoomable: true
                }};
                
                var timeline = new vis.Timeline(container, items, options);
            </script>
        </body>
        </html>
        """

    def _calculate_task_dates(
        self,
        schedule: ScheduleGraph,
        start_date: datetime
    ) -> Dict[str, Dict[str, datetime]]:
        """Calculate start and end dates for all tasks considering dependencies"""
        task_dates = {}
        task_order = self._get_topological_order(schedule)
        
        for task_id in task_order:
            task = schedule.tasks[task_id]
            
            # Find all dependencies
            dependencies = [
                rel for rel in schedule.relationships
                if rel.to_task_id == task_id
            ]
            
            if not dependencies:
                # No dependencies, can start at project start
                task_start = start_date
            else:
                # Must start after all dependencies complete
                dependency_ends = []
                for dep in dependencies:
                    dep_end = task_dates[dep.from_task_id]['end']
                    if dep.relation_type == TaskRelationType.DELAY and dep.delay:
                        dep_end += timedelta(days=dep.delay.to_days())
                    dependency_ends.append(dep_end)
                
                task_start = max(dependency_ends)
            
            task_end = task_start + timedelta(days=task.duration.to_days())
            task_dates[task_id] = {
                'start': task_start,
                'end': task_end
            }
        
        return task_dates

    def _get_topological_order(self, schedule: ScheduleGraph) -> List[str]:
        """Get tasks in topological order (respecting dependencies)"""
        import networkx as nx
        
        # Create directed graph
        graph = nx.DiGraph()
        
        # Add all tasks
        for task_id in schedule.tasks:
            graph.add_node(task_id)
        
        # Add dependencies
        for rel in schedule.relationships:
            if rel.relation_type in [TaskRelationType.SEQUENTIAL, TaskRelationType.DELAY]:
                graph.add_edge(rel.from_task_id, rel.to_task_id)
        
        # Return topological sort
        try:
            return list(nx.topological_sort(graph))
        except nx.NetworkXUnfeasible:
            raise ValueError("Circular dependency detected in task relationships")

    def _group_tasks(self, schedule: ScheduleGraph) -> List[List[str]]:
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