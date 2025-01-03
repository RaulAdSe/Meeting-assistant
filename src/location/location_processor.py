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
        Analyzes transcript to identify main construction site and location changes.
        Returns structured location information.
        """
        prompt = self._create_location_prompt(transcript_text)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "You are a construction site location analyzer. Extract the main construction "
                              "site and track movement between different areas during the visit."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                functions=[{
                    "name": "extract_locations",
                    "description": "Extracts construction site locations from transcript",
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
                                        "sublocation": {"type": "string", "description": "Specific area within location"}
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
            
            # Convert to domain models
            main_site = Location(
                company=result['main_site']['company'],
                site=result['main_site']['location']
            )
            
            location_changes = []
            for change in result.get('location_changes', []):
                try:
                    # Try different timestamp formats
                    timestamp = None
                    for fmt in ['%H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                        try:
                            timestamp = datetime.strptime(change['timestamp'], fmt)
                            break
                        except ValueError:
                            continue
                    
                    if timestamp is None:
                        # If no format matches, use current time
                        timestamp = datetime.now()
                    
                    location_changes.append(LocationChange(
                        timestamp=timestamp,
                        area=change['location'],
                        sublocation=change.get('sublocation')
                    ))
                except Exception as e:
                    print(f"Error processing timestamp {change['timestamp']}: {str(e)}")
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