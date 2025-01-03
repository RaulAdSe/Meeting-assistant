# src/report_generation/report_formatter.py

from pathlib import Path
from typing import Dict, Any
import json
from datetime import datetime
from ..location.models.location import Location, LocationChange

class ReportFormatter:
    """Formatea informes de visitas de obra combinando ubicación y análisis de contenido"""
    
    def format_site_report(
        self,
        analysis: Dict[str, Any],
        location_data: Dict[str, Any],
        output_dir: Path,
        session_id: str
    ) -> Path:
        """
        Crea un informe formateado combinando seguimiento de ubicación y análisis de contenido.
        Devuelve la ruta al informe generado.
        """
        # Create report directory
        report_dir = output_dir / session_id
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = report_dir / "informe_visita_obra.md"
        
        with open(report_path, "w", encoding="utf-8") as f:
            # Write report header
            f.write(self._format_header(analysis, location_data))
            
            # Write executive summary
            f.write("\n## Resumen Ejecutivo\n\n")
            f.write(analysis.get('resumen_ejecutivo', 'No hay resumen disponible.'))
            
            # Write site overview
            f.write("\n## Visión General de la Obra\n\n")
            vision_general = analysis.get('vision_general', {})
            
            # Format areas visited
            f.write("\n### Áreas Visitadas\n\n")
            for area in vision_general.get('areas_visitadas', []):
                f.write(f"\n#### {area['area']}\n\n")
                f.write("**Observaciones Clave:**\n")
                for obs in area.get('observaciones_clave', []):
                    f.write(f"- {obs}\n")
                
                if area.get('problemas_identificados'):
                    f.write("\n**Problemas Identificados:**\n")
                    for issue in area['problemas_identificados']:
                        f.write(f"- {issue}\n")
            
            # Write technical findings
            if analysis.get('hallazgos_tecnicos'):
                f.write("\n## Hallazgos Técnicos\n\n")
                for finding in analysis['hallazgos_tecnicos']:
                    f.write(f"### {finding['ubicacion']}\n\n")
                    f.write(f"**Hallazgo:** {finding['hallazgo']}\n")
                    f.write(f"**Severidad:** {finding['severidad']}\n")
                    f.write(f"**Acción Recomendada:** {finding['accion_recomendada']}\n\n")
            
            # Write safety concerns
            if analysis.get('preocupaciones_seguridad'):
                f.write("\n## Preocupaciones de Seguridad\n\n")
                for concern in analysis['preocupaciones_seguridad']:
                    f.write(f"### {concern['ubicacion']}\n\n")
                    f.write(f"**Preocupación:** {concern['preocupacion']}\n")
                    f.write(f"**Prioridad:** {concern['prioridad']}\n")
                    f.write(f"**Mitigación:** {concern['mitigacion']}\n\n")
            
            # Write action items
            f.write("\n## Tareas Pendientes\n\n")
            for item in analysis.get('tareas_pendientes', []):
                f.write(f"### {item['tarea']}\n\n")
                f.write(f"- **Ubicación:** {item['ubicacion']}\n")
                f.write(f"- **Asignado a:** {item['asignado_a']}\n")
                f.write(f"- **Prioridad:** {item['prioridad']}\n")
                f.write(f"- **Plazo:** {item['plazo']}\n\n")
            
            # Write general observations
            if analysis.get('observaciones_generales'):
                f.write("\n## Observaciones Generales\n\n")
                for observation in analysis['observaciones_generales']:
                    f.write(f"- {observation}\n")
        
        # Also save raw data for future reference
        data_path = report_dir / "datos_informe.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump({
                'analisis': analysis,
                'datos_ubicacion': {
                    'obra_principal': {
                        'empresa': location_data['main_site'].company,
                        'ubicacion': location_data['main_site'].site
                    } if isinstance(location_data.get('main_site'), Location) else {},
                    'cambios_ubicacion': [
                        {
                            'hora': change.timestamp.isoformat(),
                            'area': change.area,
                            'sububicacion': change.sublocation
                        }
                        for change in location_data.get('location_changes', [])
                        if isinstance(change, LocationChange)
                    ]
                }
            }, f, indent=2, default=str)
        
        return report_path
    
    def _format_header(self, analysis: Dict[str, Any], location_data: Dict[str, Any]) -> str:
        """Formats the report header with site and session information"""
        main_site = location_data.get('main_site')
        metadata = analysis.get('metadata', {})
        
        header = f"""# Informe de Visita de Obra

**Obra:** {main_site.company} - {main_site.site if isinstance(main_site, Location) else 'Desconocida'}
**Fecha:** {metadata.get('fecha', 'Desconocida')}
**Duración:** {metadata.get('duracion', 'Desconocida')}
**Áreas Visitadas:** {metadata.get('areas_visitadas', 0)}

---
"""
        return header