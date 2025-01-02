import openai
from typing import Dict, Any, List
from pathlib import Path
import json
from datetime import datetime
import logging
import os
from dotenv import load_dotenv
import httpx

# Load environment variables from project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

class LLMService:
    """Handles interaction with OpenAI API for report generation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
            
        # Initialize the OpenAI client with explicit configuration
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url="https://api.openai.com/v1",
            http_client=httpx.Client()
        )
        
        # Define function schema for structured outputs
        self.function_schema = {
            "name": "analyze_transcript",
            "description": "Analyzes meeting transcript and provides structured output",
            "parameters": {
                "type": "object",
                "properties": {
                    "executive_summary": {
                        "type": "string",
                        "description": "Brief overview of the meeting"
                    },
                    "key_points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic": {"type": "string"},
                                "details": {"type": "string"},
                                "decisions": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "action_items": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            }
                        }
                    },
                    "participant_analysis": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "speaker_id": {"type": "string"},
                                "contribution_summary": {"type": "string"},
                                "key_points": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    },
                    "follow_up_required": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item": {"type": "string"},
                                "priority": {"type": "string"},
                                "assigned_to": {"type": "string"}
                            }
                        }
                    },
                    "language_analysis": {
                        "type": "object",
                        "properties": {
                            "languages_used": {"type": "array", "items": {"type": "string"}},
                            "language_distribution": {"type": "string"}
                        }
                    }
                },
                "required": ["executive_summary", "key_points"]
            }
        }
    
    def analyze_transcript(self, transcript_text: str, session_info: Dict) -> Dict[str, Any]:
        """Generate analysis from transcript using GPT-4"""
        try:
            # Create analysis prompt
            prompt = self._create_analysis_prompt(transcript_text, session_info)
            
            # Prepare messages array with system context
            messages = [
                {
                    "role": "system",
                    "content": "You are a multilingual meeting analyst that provides detailed analysis. Analyze meetings in Spanish, English, and Catalan. Always provide your response in valid JSON format."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # Get analysis from OpenAI with function calling
            response = self.client.chat.completions.create(
                model="gpt-4",  # or your preferred model
                messages=messages,
                functions=[self.function_schema],
                function_call={"name": "analyze_transcript"},
                temperature=0.3
            )
            
            # Extract and parse the response
            try:
                if response.choices and response.choices[0].message.function_call:
                    # If function calling worked, parse the arguments
                    analysis = json.loads(response.choices[0].message.function_call.arguments)
                else:
                    # Fallback to parsing the content directly
                    content = response.choices[0].message.content
                    # Try to extract JSON from the content if it's wrapped in text
                    try:
                        start_idx = content.find('{')
                        end_idx = content.rfind('}') + 1
                        if start_idx >= 0 and end_idx > start_idx:
                            json_str = content[start_idx:end_idx]
                            analysis = json.loads(json_str)
                        else:
                            analysis = json.loads(content)
                    except json.JSONDecodeError:
                        # If JSON parsing fails, return a structured error response
                        analysis = {
                            "error": "Failed to parse response as JSON",
                            "raw_content": content
                        }
                
                # Ensure all expected fields exist, even if empty
                analysis.setdefault('executive_summary', '')
                analysis.setdefault('key_points', [])
                analysis.setdefault('participant_analysis', [])
                analysis.setdefault('follow_up_required', [])
                analysis.setdefault('language_analysis', {
                    'languages_used': [],
                    'language_distribution': ''
                })
                
                return analysis
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Error parsing JSON response: {str(e)}")
                return {
                    "error": "Failed to parse response",
                    "details": str(e),
                    "raw_response": str(response)
                }
            
        except Exception as e:
            self.logger.error(f"Error in transcript analysis: {str(e)}")
            raise
    
    def _create_analysis_prompt(self, transcript: str, session_info: Dict) -> str:
        """Create structured prompt for GPT analysis"""
        return f"""Analyze this meeting transcript and provide a structured report.

Context:
- Session ID: {session_info.get('session_id')}
- Location: {session_info.get('location')}
- Date: {session_info.get('start_time')}
- Duration: {session_info.get('total_duration')}
- Notes: {session_info.get('notes', 'None provided')}

Analyze the transcript, focusing on:
1. Overall summary
2. Key discussion points and decisions
3. Action items and follow-ups
4. Language usage (Spanish/English/Catalan)
5. Speaker contributions

Provide output in the specified JSON format, including:
- executive_summary
- key_points (with topic, details, decisions, action_items)
- participant_analysis
- follow_up_required
- language_analysis

Transcript:
{transcript}"""