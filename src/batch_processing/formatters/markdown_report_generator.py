from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import markdown
from weasyprint import HTML, CSS
import logging
from ..utils.time_utils import format_duration

class MarkdownReportGenerator:
    """Generates markdown and PDF reports from meeting analysis."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_report(self, session_info: Dict, analysis: Dict, output_dir: Path) -> Tuple[Path, Path]:
        """Generate a markdown report and convert it to PDF"""
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create report paths
            report_path = output_dir / "session_report.md"
            pdf_path = output_dir / "session_report.pdf"
            
            # Extract location from analysis metadata
            metadata = analysis.get('metadata', {})
            obra_principal = metadata.get('obra_principal', {})
            location = f"{obra_principal.get('empresa', 'Unknown')} - {obra_principal.get('ubicacion', 'Unknown')}"
            
            self.logger.info(f"Generating markdown report at {report_path}")
            
            with open(report_path, "w", encoding="utf-8") as f:
                # Write header
                f.write("# Session Analysis Report\n\n")
                
                # Write metadata
                f.write("## Session Information\n\n")
                f.write(f"- **Session ID**: {session_info.get('session_id', 'Unknown')}\n")
                f.write(f"- **Location**: {location}\n")
                
                # Format the date
                start_time = session_info.get('start_time')
                if isinstance(start_time, datetime):
                    formatted_date = start_time.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    formatted_date = str(start_time)
                f.write(f"- **Date**: {formatted_date}\n")
                
                # Format duration
                duration = session_info.get('total_duration', 0)
                if duration:
                    minutes = duration // 60
                    hours = minutes // 60
                    remaining_minutes = minutes % 60
                    f.write(f"- **Duration**: {hours:02d}:{remaining_minutes:02d}\n")
                
                if session_info.get('notes'):
                    f.write(f"- **Notes**: {session_info['notes']}\n")
                f.write("\n")
                
                # Write executive summary
                if 'executive_summary' in analysis:
                    f.write("## Executive Summary\n\n")
                    f.write(f"{analysis['executive_summary']}\n\n")
                
                # Write key points
                if analysis.get('key_points'):
                    f.write("## Key Points\n\n")
                    for point in analysis['key_points']:
                        if isinstance(point, dict):
                            f.write(f"### {point.get('topic', 'Unnamed Topic')}\n\n")
                            f.write(f"{point.get('details', '')}\n\n")
                            
                            if point.get('decisions'):
                                f.write("**Decisions:**\n")
                                for decision in point['decisions']:
                                    f.write(f"- {decision}\n")
                                f.write("\n")
                                
                            if point.get('action_items'):
                                f.write("**Action Items:**\n")
                                for item in point['action_items']:
                                    f.write(f"- {item}\n")
                                f.write("\n")
                
                # Write follow-up items
                if analysis.get('follow_up_required'):
                    f.write("## Follow-up Required\n\n")
                    for item in analysis['follow_up_required']:
                        if isinstance(item, dict):
                            f.write(f"### {item.get('item', 'Unnamed Task')}\n")
                            f.write(f"- **Priority**: {item.get('priority', 'Not specified')}\n")
                            f.write(f"- **Assigned to**: {item.get('assigned_to', 'Not assigned')}\n\n")

            self.logger.info(f"Markdown report generated successfully at {report_path}")
            
            # Generate PDF
            try:
                markdown_content = report_path.read_text(encoding='utf-8')
                self._convert_to_pdf(markdown_content, pdf_path)
            except Exception as pdf_error:
                self.logger.error(f"Failed to generate PDF: {str(pdf_error)}")
                # Even if PDF generation fails, return the paths
            
            return report_path, pdf_path
            
        except Exception as e:
            self.logger.error(f"Error generating report: {str(e)}")
            raise
    
    def _generate_markdown(self, session_info: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        """Generate markdown formatted content."""
        
        # Start with metadata header
        content = [
            f"# Site Visit Analysis Report",
            f"## Session Details",
            f"- **Session ID**: {session_info.get('session_id')}",
            f"- **Location**: {session_info.get('location', 'Unknown Location')}",
            f"- **Date**: {session_info.get('start_time').strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **Duration**: {format_duration(session_info.get('total_duration', 0))}",
        ]
        
        if session_info.get('notes'):
            content.append(f"- **Notes**: {session_info['notes']}\n")
        
        # Executive Summary
        content.extend([
            "## Executive Summary",
            str(analysis.get('executive_summary', 'No summary provided.')),
            ""
        ])
        
        # Key Points
        if analysis.get('key_points'):
            content.append("## Key Points")
            for point in analysis['key_points']:
                content.extend([
                    f"### {point.get('topic', 'Unknown Area')}",
                    point.get('details', 'No details available.'),
                    ""
                ])
        
        # Technical Findings
        if analysis.get('technical_findings'):
            content.append("## Technical Findings")
            for finding in analysis['technical_findings']:
                content.extend([
                    f"- **Location**: {finding.get('ubicacion')}",
                    f"  - Finding: {finding.get('hallazgo')}",
                    f"  - Severity: {finding.get('severidad')}",
                    f"  - Recommended Action: {finding.get('accion_recomendada')}",
                    ""
                ])
        
        # Follow-up Items
        if analysis.get('follow_up_required'):
            content.append("## Required Follow-ups")
            content.append("| Item | Priority | Assigned To |")
            content.append("|------|----------|-------------|")
            for item in analysis['follow_up_required']:
                content.append(
                    f"| {item.get('item', 'Unknown')} | {item.get('priority', 'Not specified')} | {item.get('assigned_to', 'Unassigned')} |"
                )
            content.append("")
        
        # General Observations
        if analysis.get('general_observations'):
            content.append("## General Observations")
            for observation in analysis['general_observations']:
                content.append(f"- {observation}")
            content.append("")
        
        # Add metadata if available
        if analysis.get('metadata'):
            content.extend([
                "## Metadata",
                "```json",
                json.dumps(analysis['metadata'], indent=2, ensure_ascii=False),
                "```"
            ])
        
        # Join all content with double newlines for better formatting
        return '\n'.join(content)
    
    def _convert_to_pdf(self, markdown_content: str, output_path: Path) -> None:
            """Convert markdown content to PDF using WeasyPrint."""
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
                    h1 {
                        color: #2c3e50;
                        border-bottom: 2px solid #2c3e50;
                        padding-bottom: 10px;
                    }
                    h2 {
                        color: #34495e;
                        border-bottom: 1px solid #eee;
                        padding-bottom: 5px;
                        margin-top: 30px;
                    }
                    h3 {
                        color: #7f8c8d;
                    }
                    table {
                        width: 100%;
                        border-collapse: collapse;
                        margin: 20px 0;
                    }
                    th, td {
                        border: 1px solid #ddd;
                        padding: 8px;
                        text-align: left;
                    }
                    th {
                        background-color: #f5f5f5;
                    }
                    tr:nth-child(even) {
                        background-color: #f9f9f9;
                    }
                """)
                
                # Create HTML with proper DOCTYPE and charset
                full_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Meeting Analysis Report</title>
                </head>
                <body>
                    {html_content}
                </body>
                </html>
                """
                
                # Convert output_path to string
                output_path_str = str(output_path)
                
                # Generate PDF using the string path
                HTML(string=full_html).write_pdf(
                    output_path_str,
                    stylesheets=[css]
                )
                
            except Exception as e:
                self.logger.error(f"Error converting to PDF: {str(e)}")
                raise