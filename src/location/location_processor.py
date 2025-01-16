# src/location/location_processor.py

from typing import Dict, List, Optional
import openai
import json
from datetime import datetime
from .models.location import Location, LocationChange
from dotenv import load_dotenv
import os
from pathlib import Path


class LocationProcessor:
    """Processes transcripts to identify construction site locations and movements"""
    def __init__(self):
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(env_path)
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
            
        self.client = openai.OpenAI(api_key=api_key)

    def process_transcript(self, transcript_text: str) -> Dict:
        """
        Analiza el transcripto para identificar el sitio principal de construcción y los cambios de ubicación.
        Devuelve información estructurada sobre la ubicación.
        """
        prompt = self._create_location_prompt(transcript_text)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "Eres un analizador de ubicaciones de sitios de construcción. Extrae el sitio principal de construcción "
                               "y rastrea el movimiento entre diferentes áreas durante la visita."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                functions=[{
                    "name": "extract_locations",
                    "description": "Extrae ubicaciones de sitios de construcción del transcripto",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "main_site": {
                                "type": "object",
                                "properties": {
                                    "company": {"type": "string"},
                                    "location": {"type": "string"}
                                }
                            },
                            "location_changes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "timestamp": {"type": "string"},
                                        "location": {"type": "string"},
                                        "sublocation": {"type": "string", "description": "Área específica dentro de la ubicación"}
                                    }
                                }
                            }
                        },
                        "required": ["main_site"]
                    }
                }],
                function_call={"name": "extract_locations"}
            )
            
            result = json.loads(response.choices[0].message.function_call.arguments)
            
            # Convertir a modelos de dominio
            main_site = Location(
                company=result['main_site']['company'],
                site=result['main_site']['location']
            )
            
            location_changes = []

            # ach new location change should have an associated timestamp, which ideally comes from the transcript itself or from an inferred time based on the audio file.
            
            for change in result.get('location_changes', []):
                try:
                    raw_timestamp = change.get('timestamp')  # Use .get() to avoid KeyError

                    if not raw_timestamp:  # Covers None, empty strings, or missing keys
                        print("Warning: Missing or None timestamp, using current time.")
                        timestamp = datetime.now()
                    else:
                        # Attempt different timestamp formats
                        timestamp = None
                        for fmt in ['%H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                            try:
                                timestamp = datetime.strptime(raw_timestamp, fmt)
                                break
                            except ValueError:
                                continue
                        
                        if timestamp is None:
                            print(f"Warning: Could not parse timestamp '{raw_timestamp}', using current time.")
                            timestamp = datetime.now()

                    location_changes.append(LocationChange(
                        timestamp=timestamp,
                        area=change.get('location', 'Unknown Location'),
                        sublocation=change.get('sublocation', 'Unknown Sublocation')
                    ))

                except Exception as e:
                    print(f"Error processing timestamp {change.get('timestamp', 'UNKNOWN')}: {str(e)}")
                    continue

            
            return {
                'main_site': main_site,
                'location_changes': sorted(location_changes, key=lambda x: x.timestamp)
            }
        except Exception as e:
            print(f"Error processing locations: {str(e)}")
            return {
                'main_site': Location(company="Unknown", site="Unknown"),
                'location_changes': []
            }

    def _create_location_prompt(self, transcript: str) -> str:
        return f"""
        Analyze this transcript to:
        1. Identify the main construction site (company and location) mentioned at the start
        2. Track any mentions of moving to different areas within the site
        3. Note timestamps when locations change

        Focus on phrases like:
        - "Estoy en [construction site]"
        - "Ahora estamos en [area]"
        - "Me encuentro en [location]"
        - "Nos movemos a [area]"
        - "Pasamos a [location]"
        or similar ones. Also consider the catalan transations of these.

        Transcript:
        {transcript}
        """

    def format_location_string(self, location_data: dict) -> str:
        """Formats location data into a readable string"""
        main_site = location_data.get('main_site')
        if isinstance(main_site, Location):
            return f"{main_site.company} - {main_site.site}"
        return "Unknown Location"
    
    def _handle_location_change(self, change: Dict) -> Optional[LocationChange]:
        """Safely handle location change data"""
        try:
            # Default to current time if timestamp is missing
            timestamp = datetime.now()
            if change.get('timestamp'):
                try:
                    timestamp = datetime.strptime(change['timestamp'], '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    try:
                        timestamp = datetime.strptime(change['timestamp'], '%H:%M:%S')
                    except ValueError:
                        pass  # Keep default timestamp
            
            return LocationChange(
                timestamp=timestamp,
                area=change.get('location', 'Unknown Area'),
                sublocation=change.get('sublocation'),
                notes=change.get('notes')
            )
        except Exception as e:
            self.logger.warning(f"Error processing location change: {str(e)}")
            return None