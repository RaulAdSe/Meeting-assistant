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

# Assuming `transcript_data` contains word-level timestamps from the transcription service
    def assign_timestamps_to_locations(transcript_data, extracted_locations):
        """
        Assigns timestamps to locations based on when they appear in the transcript.
        """
        location_changes = []

        for loc in extracted_locations:
            matched_timestamp = None

            # Search for the first occurrence of the location in the transcript data
            for entry in transcript_data:
                if loc["location"].lower() in entry["text"].lower():
                    matched_timestamp = entry["timestamp"]
                    break  # Stop at the first match

            # If no timestamp is found, use first available timestamp
            if not matched_timestamp and transcript_data:
                matched_timestamp = transcript_data[0]["timestamp"]

            location_changes.append(LocationChange(
                timestamp=matched_timestamp,
                area=loc["location"],
                sublocation=loc.get("sublocation", "Unknown Sublocation")
            ))

        return location_changes

    def process_transcript(self, transcript_text: str, transcript_data: List[Dict]) -> Dict:
        """
        Processes the transcript, identifying the main site and tracking location changes.
        Uses actual timestamps from transcript_data instead of AI-generated timestamps.
        """
        prompt = self._create_location_prompt(transcript_text)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "Eres un analizador de ubicaciones de sitios de construcción. Extrae el sitio principal de construcción "
                            "y rastrea los nombres de áreas mencionadas, pero no asigna marcas de tiempo."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                functions=[{
                    "name": "extract_locations",
                    "description": "Extrae ubicaciones mencionadas en el transcripto.",
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
                            "locations": {  # No timestamps here!
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
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

            print("DEBUG: Raw AI response data (before processing):")
            print(result)

            # Convert to domain models
            main_site = Location(
                company=result['main_site']['company'],
                site=result['main_site']['location']
            )

            # Extract locations without timestamps
            extracted_locations = result.get('locations', [])

            # Assign timestamps using transcript data
            location_changes = self.assign_timestamps_to_locations(transcript_data, extracted_locations)

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
        


