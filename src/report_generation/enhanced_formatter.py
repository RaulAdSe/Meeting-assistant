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

    async def generate_comprehensive_report(
        self,
        transcript_text: str,
        visit_id: uuid.UUID,
        location_id: uuid.UUID,
        output_dir: Path,
        start_date: Optional[datetime] = None
    ) -> Dict[str, Path]:
        """
        Generate a comprehensive report integrating all analyses.
        
        Args:
            transcript_text: Raw transcript text
            visit_id: UUID of the current visit
            location_id: UUID of the construction site location
            output_dir: Directory to save the report
            start_date: Optional start date for chronogram
            
        Returns:
            Dictionary with paths to generated report files
        """
        try:
            # Process location data
            self.logger.info("Processing location data...")
            location_data = self.location_processor.process_transcript(transcript_text)
            
            # Get construction analysis
            self.logger.info("Analyzing construction aspects...")
            construction_analysis = self.construction_expert.analyze_visit(
                visit_id=visit_id,
                transcript_text=transcript_text,
                location_id=location_id
            )
            
            # Get timing analysis
            self.logger.info("Analyzing timing and tasks...")
            timing_analysis = self.task_analyzer.analyze_transcript(
                transcript_text=transcript_text,
                location_id=location_id
            )
            
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

    def _create_report_sections(self, **data) -> List[ReportSection]:
        """Create all report sections from analyzed data"""
        sections = []
        
        # Header section
        sections.append(ReportSection(
            title="Site Information",
            content=self._format_header(data['location_data']),
            order=1
        ))
        
        # Executive summary
        sections.append(ReportSection(
            title="Executive Summary",
            content=self._format_executive_summary(data['construction_analysis']),
            order=2
        ))
        
        # Location analysis
        sections.append(ReportSection(
            title="Location Analysis",
            content=self._format_location_analysis(data['location_data']),
            order=3
        ))
        
        # Problems and solutions
        sections.append(ReportSection(
            title="Problems and Solutions",
            content=self._format_problems_section(data['construction_analysis']),
            order=4
        ))
        
        # Chronogram
        sections.append(ReportSection(
            title="Project Timeline",
            content=data['chronogram'],
            type="mermaid",
            order=5
        ))
        
        # Follow-up items
        sections.append(ReportSection(
            title="Follow-up Items",
            content=self._format_follow_up_section(data),
            order=6
        ))
        
        return sorted(sections, key=lambda s: s.order)

    def _format_header(self, location_data: Dict) -> str:
        """Format the report header with site information"""
        main_site = location_data.get('main_site', {})
        company = main_site.get('company', 'Unknown Company')
        site = main_site.get('site', 'Unknown Location')
        
        return f"""# Construction Site Visit Report

## Site Information
- **Company:** {company}
- **Location:** {site}
- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
"""

    def _format_executive_summary(self, construction_analysis: Dict) -> str:
        """Format the executive summary section"""
        summary = construction_analysis.get('executive_summary', 'No summary available.')
        confidence = construction_analysis.get('confidence_scores', {}).get('overall', 0)
        
        return f"""## Executive Summary

{summary}

**Analysis Confidence:** {confidence:.1%}

---
"""

    def _format_location_analysis(self, location_data: Dict) -> str:
        """Format the location analysis section"""
        sections = ["## Location Analysis\n"]
        
        # Add movement tracking
        if location_data.get('location_changes'):
            sections.append("### Movement Timeline")
            for change in location_data['location_changes']:
                time = change.get('timestamp', '').strftime('%H:%M:%S')
                area = change.get('area', 'Unknown Area')
                subloc = change.get('sublocation', '')
                sections.append(f"- **{time}** - {area}" + 
                              (f" ({subloc})" if subloc else ""))
        
        return "\n".join(sections)

    def _format_problems_section(self, construction_analysis: Dict) -> str:
        """Format the problems and solutions section"""
        sections = ["## Problems and Solutions\n"]
        
        problems = construction_analysis.get('problems', [])
        solutions = construction_analysis.get('solutions', {})
        
        for problem in problems:
            problem_id = problem.get('id')
            severity = problem.get('severity', 'Unknown')
            description = problem.get('description', 'No description available')
            location = problem.get('location_context', {}).get('area', 'Unknown Area')
            
            sections.append(f"### Problem in {location}")
            sections.append(f"**Severity:** {severity}")
            sections.append(f"**Description:** {description}\n")
            
            # Add solutions if available for this problem
            if problem_id and problem_id in solutions:
                sections.append("#### Proposed Solutions:")
                for solution in solutions[problem_id]:
                    sections.append(f"- {solution.get('description', 'No description')}")
                    if solution.get('estimated_time'):
                        sections.append(f"  - Estimated time: {solution['estimated_time']} minutes")
                sections.append("")
            
        return "\n".join(sections)

    def _format_follow_up_section(self, data: Dict) -> str:
        """Format the follow-up items section"""
        sections = ["## Follow-up Items\n"]
        
        # Get follow-up items from construction analysis
        construction = data.get('construction_analysis', {})
        for item in construction.get('follow_up_required', []):
            priority = item.get('priority', 'Normal')
            description = item.get('item', 'No description')
            assigned = item.get('assigned_to', 'Unassigned')
            
            sections.append(f"### {description}")
            sections.append(f"- **Priority:** {priority}")
            sections.append(f"- **Assigned to:** {assigned}\n")
        
        return "\n".join(sections)

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