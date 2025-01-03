# src/report_generation/llm_service.py

import openai
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from datetime import datetime
import logging
import os
from dotenv import load_dotenv
from ..location.models.location import Location, LocationChange

class LLMService:
    """Enhanced LLM service with Spanish output"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Get the project root directory (same level as src)
        project_root = Path(__file__).parent.parent
        
        # Load environment variables from .env file at the same level as src
        env_path = project_root.parent / '.env'
        if not env_path.exists():
            raise FileNotFoundError(
                f"'.env' file not found at {env_path}. "
                "Please create a .env file in your project root with your OPENAI_API_KEY"
            )
            
        load_dotenv(env_path)

        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.client = openai.Client(api_key=self.api_key)
        
    def analyze_transcript(
        self,
        transcript_text: str,
        location_data: Dict[str, Any],
        session_info: Dict
    ) -> Dict[str, Any]:
        """Generate analysis in Spanish incorporating location context"""
        try:
            # Create analysis prompt with location context
            prompt = self._create_analysis_prompt(
                transcript_text,
                location_data,
                session_info
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": """Eres un analista especializado en visitas de obra que:
                        1. Comprende terminología de construcción
                        2. Rastrea movimiento entre diferentes áreas
                        3. Identifica problemas técnicos y de seguridad
                        4. Reconoce tareas pendientes específicas por ubicación
                        
                        IMPORTANTE: Genera SIEMPRE el análisis en español."""
                }, {
                    "role": "user",
                    "content": prompt
                }],
                functions=[{
                    "name": "analizar_visita_obra",
                    "description": "Analiza visita de obra con consciencia de ubicación",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "resumen_ejecutivo": {"type": "string"},
                            "vision_general": {
                                "type": "object",
                                "properties": {
                                    "obra_principal": {"type": "string"},
                                    "areas_visitadas": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "area": {"type": "string"},
                                                "observaciones_clave": {"type": "array", "items": {"type": "string"}},
                                                "problemas_identificados": {"type": "array", "items": {"type": "string"}}
                                            }
                                        }
                                    }
                                }
                            },
                            "hallazgos_tecnicos": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "ubicacion": {"type": "string"},
                                        "hallazgo": {"type": "string"},
                                        "severidad": {"type": "string", "enum": ["Baja", "Media", "Alta"]},
                                        "accion_recomendada": {"type": "string"}
                                    }
                                }
                            },
                            "preocupaciones_seguridad": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "ubicacion": {"type": "string"},
                                        "preocupacion": {"type": "string"},
                                        "prioridad": {"type": "string", "enum": ["Baja", "Media", "Alta"]},
                                        "mitigacion": {"type": "string"}
                                    }
                                }
                            },
                            "tareas_pendientes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "ubicacion": {"type": "string"},
                                        "tarea": {"type": "string"},
                                        "asignado_a": {"type": "string"},
                                        "prioridad": {"type": "string"},
                                        "plazo": {"type": "string"}
                                    }
                                }
                            },
                            "observaciones_generales": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["resumen_ejecutivo", "vision_general", "tareas_pendientes"]
                    }
                }],
                function_call={"name": "analizar_visita_obra"},
                temperature=0.3
            )
            
            # Parse and structure the response
            if response.choices[0].message.function_call:
                try:
                    # Parse the response and log it
                    raw_response = response.choices[0].message.function_call.arguments
                    self.logger.info(f"Raw API response: {raw_response}")
                    
                    analysis = json.loads(raw_response)
                    self.logger.info(f"Parsed analysis: {analysis}")
                    
                    # Create a new dictionary with proper types
                    processed_analysis = {
                        'executive_summary': str(analysis.get('resumen_ejecutivo', 'No executive summary available.')),
                        'key_points': [],
                        'follow_up_required': []
                    }
                    
                    # Map Spanish fields to English
                    if 'vision_general' in analysis:
                        key_points = []
                        for area in analysis['vision_general'].get('areas_visitadas', []):
                            if area.get('observaciones_clave'):
                                key_points.append({
                                    'topic': area['area'],
                                    'details': ' '.join(area['observaciones_clave'])
                                })
                        processed_analysis['key_points'] = key_points
                    
                    if 'tareas_pendientes' in analysis:
                        processed_analysis['follow_up_required'] = [
                            {
                                'item': task['tarea'],
                                'priority': task['prioridad'],
                                'assigned_to': task['asignado_a']
                            }
                            for task in analysis['tareas_pendientes']
                        ]
                    
                    # Add additional fields
                    processed_analysis['technical_findings'] = analysis.get('hallazgos_tecnicos', [])
                    processed_analysis['security_concerns'] = analysis.get('preocupaciones_seguridad', [])
                    processed_analysis['general_observations'] = analysis.get('observaciones_generales', [])
                    
                    # Add metadata
                    processed_analysis = self._enhance_analysis_with_metadata(
                        processed_analysis, 
                        location_data, 
                        session_info
                    )
                    
                    self.logger.info(f"Final processed analysis: {processed_analysis}")
                    return processed_analysis
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse API response: {e}")
                    raise
            
            return {
                "error": "Error al generar análisis",
                "detalles": "No se pudo generar la respuesta",
                "executive_summary": "Failed to generate analysis"
            }
            
        except Exception as e:
            self.logger.error(f"Error en análisis de transcripción: {str(e)}")
            raise

    def _create_analysis_prompt(
        self,
        transcript: str,
        session_info: Dict,
        location_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create detailed prompt with location context in Spanish"""
        location_context = ""
        if location_data:
            main_site = location_data.get('main_site')
            location_changes = location_data.get('location_changes', [])
            
            # Format location changes for context
            location_sequence = []
            for change in location_changes:
                if isinstance(change, LocationChange):
                    location_str = f"- {change.timestamp.strftime('%H:%M:%S')}: {change.area}"
                    if change.sublocation:
                        location_str += f" ({change.sublocation})"
                    location_sequence.append(location_str)
            
            if isinstance(main_site, Location):
                location_context = f"\n- Empresa: {main_site.company}\n- Ubicación: {main_site.site}"
            
            if location_sequence:
                location_context += "\n\nRecorrido por la Obra:\n" + "\n".join(location_sequence)
        
        return f"""Analiza esta transcripción de visita de obra con el siguiente contexto:

Información del Sitio:
- ID Sesión: {session_info.get('session_id')}
- Fecha: {session_info.get('start_time')}
- Duración: {session_info.get('total_duration')}{location_context}

Áreas de Enfoque:
1. Observaciones específicas para cada área visitada
2. Problemas técnicos identificados en ubicaciones específicas
3. Preocupaciones de seguridad y sus ubicaciones exactas
4. Tareas pendientes vinculadas a áreas específicas
5. Observaciones generales de progreso y calidad

Transcripción:
{transcript}"""

    def _enhance_analysis_with_metadata(
        self,
        analysis: Dict[str, Any],
        location_data: Optional[Dict[str, Any]],
        session_info: Dict
    ) -> Dict[str, Any]:
        """Enhance analysis with metadata and statistics"""
        # Add metadata in Spanish
        metadata = {
            'id_sesion': session_info.get('session_id'),
            'fecha': session_info.get('start_time'),
            'duracion': session_info.get('total_duration'),
            'fecha_analisis': datetime.now().isoformat()
        }
        
        # Add location data if available
        if location_data:
            main_site = location_data.get('main_site')
            if isinstance(main_site, Location):
                metadata['obra_principal'] = {
                    'empresa': main_site.company,
                    'ubicacion': main_site.site
                }
            metadata['areas_visitadas'] = len(location_data.get('location_changes', []))
        
        analysis['metadata'] = metadata
        return analysis

