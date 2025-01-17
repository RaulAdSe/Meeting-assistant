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
    def _normalize_location_entry(self, loc: Dict) -> Dict:
        """
        Normalize a location entry to ensure it has both location and sublocation.
        If only sublocation is present, use it as the location.
        """
        normalized = {
            "location": loc.get("location", loc.get("sublocation", "Unknown")),
            "sublocation": loc.get("sublocation", "Unknown Sublocation")
        }
        # If we used sublocation as location, make sublocation unknown
        if "location" not in loc and "sublocation" in loc:
            normalized["sublocation"] = "Unknown Sublocation"
        return normalized

    def assign_timestamps_to_locations(self, transcript_data, extracted_locations):
        """
        Assigns timestamps to locations based on when they appear in the transcript.
        
        Args:
            transcript_data: List of dicts with 'text' and 'timestamp' keys
            extracted_locations: List of dicts with location information
        
        Returns:
            List of LocationChange objects with assigned timestamps
        """
        if not transcript_data:
            return []

        location_changes = []
        default_timestamp = transcript_data[0]["timestamp"] if transcript_data else datetime.now()

        for loc in extracted_locations:
            # Normalize the location entry
            normalized_loc = self._normalize_location_entry(loc)
            matched_timestamp = None
            location_text = normalized_loc["location"].lower()

            # Search for the first occurrence of the location in the transcript data
            for entry in transcript_data:
                entry_text = entry["text"].lower()
                if location_text in entry_text:
                    matched_timestamp = entry["timestamp"]
                    break

            # Create LocationChange with matched or default timestamp
            location_changes.append(LocationChange(
                timestamp=matched_timestamp or default_timestamp,
                area=normalized_loc["location"],
                sublocation=normalized_loc["sublocation"]
            ))

        return location_changes


    def process_transcript(self, transcript_text: str, transcript_data: Optional[List[Dict]] = None) -> Dict:
        """
        Processes the transcript, identifying the main site and tracking location changes.
        Uses actual timestamps from transcript_data instead of AI-generated timestamps.
        """
        prompt = self._create_location_prompt(transcript_text)
        transcript_data = transcript_data or []

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "Eres un analizador de ubicaciones de sitios de construcción. Extrae el sitio principal de construcción "
                            "y rastrea los nombres de áreas mencionadas, pero no asignas marcas de tiempo."
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
                            "locations": {
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

          # Extract locations directly from the result
            extracted_locations = result.get('locations', [])
            
            # Print debug info
            if extracted_locations:
                print("Extracted locations:")
                for loc in extracted_locations:
                    print(f"- {loc.get('location', 'Unknown')}: {loc.get('sublocation', 'No sublocation')}")

            # Assign timestamps
            location_changes = self.assign_timestamps_to_locations(transcript_data, extracted_locations)

            if location_changes:
                print("\nCreated location changes:")
                for change in location_changes:
                    print(f"- {change.area} at {change.timestamp}")

            return {
                'main_site': main_site,
                'location_changes': sorted(location_changes, key=lambda x: x.timestamp)
            }

        except Exception as e:
            print(f"Error processing locations: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
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
        


