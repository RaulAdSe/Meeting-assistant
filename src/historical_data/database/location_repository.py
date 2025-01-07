# src/historical_data/database/location_repository.py

from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime
import json
from dataclasses import dataclass, field
from .connection import DatabaseConnection
import psycopg2.extras

@dataclass
class Location:
    """Represents a construction site location"""
    id: uuid.UUID
    name: str
    address: Optional[str] = None
    coordinates: Optional[tuple] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

class LocationRepository:
    def __init__(self, connection=None):
        self.db = DatabaseConnection.get_instance()
        self._connection = connection

    def _get_connection(self):
        if self._connection:
            return self._connection
        return self.db.get_connection()

    def _execute_query(self, query: str, params: tuple = None) -> Optional[List[Dict]]:
        """Execute a query and return results"""
        conn = self._get_connection()
        close_conn = False
        if not self._connection:
            close_conn = True
            conn.autocommit = True
        
        try:
            # Use RealDictCursor to get dictionary results
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if params:
                    params = tuple(
                        str(p) if isinstance(p, uuid.UUID) else p 
                        for p in params
                    )
                cur.execute(query, params)
                if cur.description:
                    return cur.fetchall()
                return None
        finally:
            if close_conn:
                conn.close()

    def create(self, name: str, address: Optional[str] = None, 
               coordinates: Optional[tuple] = None, metadata: Dict[str, Any] = None) -> Location:
        """Create a new location"""
        query = """
        INSERT INTO locations (name, address, coordinates, metadata)
        VALUES (%s, %s, %s, %s)
        RETURNING id, name, address, coordinates, metadata, created_at, updated_at
        """
        
        point = f"({coordinates[0]},{coordinates[1]})" if coordinates else None
        result = self._execute_query(
            query, 
            (name, address, point, json.dumps(metadata or {}))
        )
        
        if not result:
            raise ValueError("Failed to create location")
            
        row = result[0]
        return Location(
            id=uuid.UUID(str(row['id'])),
            name=row['name'],
            address=row['address'],
            coordinates=tuple(float(x) for x in row['coordinates'][1:-1].split(',')) if row['coordinates'] else None,
            metadata=row['metadata'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def get(self, location_id: uuid.UUID) -> Optional[Location]:
        """Get a location by ID"""
        query = "SELECT * FROM locations WHERE id = %s"
        result = self._execute_query(query, (str(location_id),))
        
        if not result:
            return None
            
        row = result[0]
        return Location(
            id=uuid.UUID(str(row['id'])),
            name=row['name'],
            address=row['address'],
            coordinates=tuple(float(x) for x in row['coordinates'][1:-1].split(',')) if row['coordinates'] else None,
            metadata=row['metadata'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def get_by_name(self, name: str) -> Optional[Location]:
        """Get a location by name"""
        query = "SELECT * FROM locations WHERE name = %s"
        result = self._execute_query(query, (name,))
        
        if not result:
            return None
            
        row = result[0]
        return Location(
            id=uuid.UUID(str(row['id'])),
            name=row['name'],
            address=row['address'],
            coordinates=tuple(float(x) for x in row['coordinates'][1:-1].split(',')) if row['coordinates'] else None,
            metadata=row['metadata'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def get_all(self) -> List[Location]:
        """Get all locations"""
        query = "SELECT * FROM locations ORDER BY name"
        results = self._execute_query(query)
        
        return [
            Location(
                id=uuid.UUID(str(row['id'])),
                name=row['name'],
                address=row['address'],
                coordinates=tuple(float(x) for x in row['coordinates'][1:-1].split(',')) if row['coordinates'] else None,
                metadata=row['metadata'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in results
        ]

    def update(self, location_id: uuid.UUID, 
               name: Optional[str] = None,
               address: Optional[str] = None,
               coordinates: Optional[tuple] = None,
               metadata: Optional[Dict[str, Any]] = None) -> Location:
        """Update a location"""
        # Build update query dynamically based on provided fields
        update_parts = []
        params = []
        
        if name is not None:
            update_parts.append("name = %s")
            params.append(name)
        if address is not None:
            update_parts.append("address = %s")
            params.append(address)
        if coordinates is not None:
            update_parts.append("coordinates = %s")
            params.append(f"({coordinates[0]},{coordinates[1]})")
        if metadata is not None:
            update_parts.append("metadata = %s")
            params.append(json.dumps(metadata))
            
        if not update_parts:
            raise ValueError("No fields to update")
            
        update_parts.append("updated_at = CURRENT_TIMESTAMP")
        
        query = f"""
        UPDATE locations 
        SET {', '.join(update_parts)}
        WHERE id = %s
        RETURNING id, name, address, coordinates, metadata, created_at, updated_at
        """
        
        params.append(str(location_id))
        result = self._execute_query(query, tuple(params))
        
        if not result:
            raise ValueError("Location not found")
            
        row = result[0]
        return Location(
            id=uuid.UUID(str(row['id'])),
            name=row['name'],
            address=row['address'],
            coordinates=tuple(float(x) for x in row['coordinates'][1:-1].split(',')) if row['coordinates'] else None,
            metadata=row['metadata'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )