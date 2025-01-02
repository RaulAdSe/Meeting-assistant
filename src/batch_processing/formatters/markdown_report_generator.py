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
    
    def generate_report(self,
                       session_info: Dict[str, Any],
                       analysis: Dict[str, Any],
                       output_dir: Path) -> Tuple[Path, Path]:
        """
        Generate both markdown and PDF reports from analysis data.
        
        Args:
            session_info: Dictionary containing session metadata
            analysis: Dictionary containing the LLM analysis results
            output_dir: Directory to save the reports
        
        Returns:
            Tuple of (markdown_path, pdf_path)
        """
        try:
            # Generate markdown content
            markdown_content = self._generate_markdown(session_info, analysis)
            
            # Create output directory if it doesn't exist
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save markdown file
            markdown_path = output_dir / f"{session_info['session_id']}_report.md"
            markdown_path.write_text(markdown_content, encoding='utf-8')
            self.logger.info(f"Markdown report generated: {markdown_path}")
            
            # Convert to PDF
            pdf_path = output_dir / f"{session_info['session_id']}_report.pdf"
            self._convert_to_pdf(markdown_content, pdf_path)
            self.logger.info(f"PDF report generated: {pdf_path}")
            
            return markdown_path, pdf_path
            
        except Exception as e:
            self.logger.error(f"Error generating report: {str(e)}")
            raise
    
    def _generate_markdown(self, session_info: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        """Generate markdown formatted content."""
        
        # Start with metadata header
        content = [
            f"# Meeting Analysis Report",
            f"## Session Details",
            f"- **Session ID**: {session_info.get('session_id')}",
            f"- **Location**: {session_info.get('location')}",
            f"- **Date**: {session_info.get('start_time').strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **Duration**: {format_duration(session_info.get('total_duration', 0))}",
        ]
        
        if session_info.get('notes'):
            content.append(f"- **Notes**: {session_info['notes']}\n")
        
        # Executive Summary
        content.extend([
            "## Executive Summary",
            analysis.get('executive_summary', 'No summary provided.'),
            ""
        ])
        
        # Key Points
        content.append("## Key Discussion Points")
        for point in analysis.get('key_points', []):
            content.extend([
                f"### {point['topic']}",
                point['details'],
                "",
                "**Decisions:**"
            ])
            
            for decision in point.get('decisions', []):
                content.append(f"- {decision}")
            
            content.append("\n**Action Items:**")
            for item in point.get('action_items', []):
                content.append(f"- {item}")
            content.append("")
        
        # Participant Analysis
        content.append("## Participant Contributions")
        for participant in analysis.get('participant_analysis', []):
            content.extend([
                f"### {participant['speaker_id']}",
                participant['contribution_summary'],
                "\n**Key Points:**"
            ])
            for point in participant.get('key_points', []):
                content.append(f"- {point}")
            content.append("")
        
        # Follow-up Items
        content.append("## Required Follow-ups")
        content.append("| Item | Priority | Assigned To |")
        content.append("|------|----------|-------------|")
        for item in analysis.get('follow_up_required', []):
            content.append(
                f"| {item['item']} | {item['priority']} | {item['assigned_to']} |"
            )
        content.append("")
        
        # Language Analysis
        if 'language_analysis' in analysis:
            content.extend([
                "## Language Analysis",
                f"**Languages Used**: {', '.join(analysis['language_analysis'].get('languages_used', []))}",
                f"**Distribution**: {analysis['language_analysis'].get('language_distribution', 'Not specified')}",
                ""
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
            
            # Generate PDF
            HTML(string=full_html).write_pdf(
                str(output_path),
                stylesheets=[css]
            )
            
        except Exception as e:
            self.logger.error(f"Error converting to PDF: {str(e)}")
            raise