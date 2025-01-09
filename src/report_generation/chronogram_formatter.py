from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pathlib import Path

class ChronogramFormatter:
    """Formats chronogram data into Markdown for reports"""
    
    def format_chronogram_section(
        self,
        timing_analysis: Dict[str, Any],
        mermaid_diagram: Optional[str] = None
    ) -> str:
        """
        Format chronogram section in Markdown, including Mermaid diagram
        and task details.
        
        Args:
            timing_analysis: Dictionary containing timing analysis data
            mermaid_diagram: Optional pre-generated Mermaid diagram
            
        Returns:
            Formatted Markdown string
        """
        sections = []
        
        # Add section header
        sections.append("## Project Timeline\n")
        
        # Add Mermaid diagram if provided
        if mermaid_diagram:
            sections.extend([
                "### Visual Timeline",
                "```mermaid",
                mermaid_diagram,
                "```\n"
            ])
        
        # Add task details
        sections.append("### Task Details\n")
        
        if timing_analysis and "tasks" in timing_analysis:
            tasks = self._process_tasks(timing_analysis["tasks"])
            sections.extend(self._format_task_details(tasks))
            
            # Add task dependencies if any exist
            if any(task.get("dependencies") for task in tasks):
                sections.extend(self._format_dependencies(tasks))
            
            # Add parallel tasks section if any exist
            parallel_groups = timing_analysis.get("parallel_groups", [])
            if parallel_groups:
                sections.extend(self._format_parallel_tasks(parallel_groups, tasks))
        
        return "\n".join(sections)

    def _process_tasks(self, tasks: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process raw task data into a format suitable for the report"""
        processed = []
        for task_id, task in tasks.items():
            processed.append({
                "id": str(task_id),
                "name": task.get("name", "Unnamed Task"),
                "description": task.get("description", ""),
                "duration": self._format_duration(task.get("duration", {})),
                "status": task.get("status", "planned"),
                "responsible": task.get("responsible", "Unassigned"),
                "dependencies": task.get("dependencies", []),
                "start_date": task.get("planned_start"),
                "end_date": task.get("planned_end"),
                "confidence": task.get("metadata", {}).get("confidence", "N/A")
            })
        return processed

    def _format_duration(self, duration: Dict[str, Any]) -> str:
        """Format duration information"""
        if not duration:
            return "Duration not specified"
            
        amount = duration.get("amount", 0)
        unit = duration.get("unit", "days")
        return f"{amount} {unit}"

    def _format_task_details(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """Format detailed task information"""
        sections = []
        for task in tasks:
            sections.extend([
                f"#### {task['name']}",
                f"- **Duration:** {task['duration']}",
                f"- **Responsible:** {task['responsible']}",
                f"- **Status:** {task['status'].title()}"
            ])
            
            if task.get("description"):
                sections.append(f"- **Description:** {task['description']}")
                
            if task.get("confidence") != "N/A":
                sections.append(f"- **Confidence:** {task['confidence']:.0%}")
                
            sections.append("")  # Add blank line between tasks
            
        return sections

    def _format_dependencies(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """Format task dependencies section"""
        sections = ["### Task Dependencies\n"]
        
        # Create task lookup by id
        task_lookup = {task["id"]: task["name"] for task in tasks}
        
        for task in tasks:
            if task.get("dependencies"):
                dep_names = [
                    task_lookup.get(dep_id, f"Task {dep_id}") 
                    for dep_id in task["dependencies"]
                ]
                sections.append(
                    f"- **{task['name']}** depends on: {', '.join(dep_names)}"
                )
        
        sections.append("")  # Add final blank line
        return sections

    def _format_parallel_tasks(
        self,
        parallel_groups: List[List[str]],
        tasks: List[Dict[str, Any]]
    ) -> List[str]:
        """Format parallel tasks section"""
        sections = ["### Parallel Task Groups\n"]
        
        # Create task lookup
        task_lookup = {task["id"]: task["name"] for task in tasks}
        
        for i, group in enumerate(parallel_groups, 1):
            task_names = [
                task_lookup.get(task_id, f"Task {task_id}") 
                for task_id in group
            ]
            sections.append(f"**Group {i}:**")
            sections.extend([f"- {name}" for name in task_names])
            sections.append("")  # Add blank line between groups
            
        return sections

    def save_chronogram_data(
        self,
        timing_analysis: Dict[str, Any],
        output_dir: Path,
        format: str = "json"
    ) -> Path:
        """
        Save chronogram data to file for potential future use.
        
        Args:
            timing_analysis: Dictionary containing timing analysis data
            output_dir: Directory to save the file
            format: Output format ('json' or 'yaml')
            
        Returns:
            Path to saved file
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            output_path = output_dir / "chronogram_data.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(timing_analysis, f, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")
            
        return output_path