# src/location/models/location.py

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Location:
    """Represents a construction site location"""
    company: str
    site: str
    
@dataclass
class LocationChange:
    """Represents a change in location during site visit"""
    timestamp: datetime
    area: str
    sublocation: Optional[str] = None
    notes: Optional[str] = None