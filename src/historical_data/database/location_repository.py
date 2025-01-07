# src/historical_data/database/location_repository.py

from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime
import json
from .connection import DatabaseConnection
import psycopg2.extras
from ..models.models import Location  # Import Location from models

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

    def _to_uuid(self, value: Any) -> Optional[uuid.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
    

    def create(self, name: str, address: Optional[str] = None, 
               metadata: Dict[str, Any] = None) -> Location:
        """Create a new location"""
        query = """
        INSERT INTO locations (name, address, metadata)
        VALUES (%s, %s, %s)
        RETURNING *
        """
        result = self._execute_query(query, (
            name,
            address,
            json.dumps(metadata or {})
        ))
        row = result[0]
        return Location(
            id=self._to_uuid(row['id']),
            name=row['name'],
            address=row['address'],
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
            id=self._to_uuid(row['id']),
            name=row['name'],
            address=row['address'],
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
            id=self._to_uuid(row['id']),
            name=row['name'],
            address=row['address'],
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
                id=self._to_uuid(row['id']),
                name=row['name'],
                address=row['address'],
                metadata=row['metadata'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in results
        ]

    def update(self, location_id: uuid.UUID, 
               name: Optional[str] = None,
               address: Optional[str] = None,
               metadata: Optional[Dict[str, Any]] = None) -> Location:
        """Update a location"""
        update_parts = []
        params = []
        
        if name is not None:
            update_parts.append("name = %s")
            params.append(name)
        if address is not None:
            update_parts.append("address = %s")
            params.append(address)
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
        RETURNING *
        """
        
        params.append(str(location_id))
        result = self._execute_query(query, tuple(params))
        
        if not result:
            raise ValueError("Location not found")
            
        row = result[0]
        return Location(
            id=self._to_uuid(row['id']),
            name=row['name'],
            address=row['address'],
            metadata=row['metadata'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )