# src/historical_data/database/location_repository.py

from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime
import json
from .connection import DatabaseConnection
from ..models.models import Location  # Import Location from models
import logging

class LocationRepository:
    def __init__(self, connection=None):
        self.db = DatabaseConnection.get_instance()
        self._connection = connection
        self.logger = logging.getLogger(__name__)   

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
            with conn.cursor() as cur:
                if params:
                    params = tuple(
                        str(p) if isinstance(p, uuid.UUID) else p 
                        for p in params
                    )
                cur.execute(query, params)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
                return None
        finally:
            if close_conn:
                conn.close()

    def _to_uuid(self, value: Any) -> Optional[uuid.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError):
            return None
    

    def create(self, name: str, address: Optional[str] = None, 
               metadata: Dict[str, Any] = None) -> Location:
        """Create a new location"""
        try:
            self.logger.debug(f"Creating location with:")
            self.logger.debug(f"  name: {name!r}")
            self.logger.debug(f"  address: {address!r}")
            self.logger.debug(f"  metadata: {metadata!r}")
            
            # Ensure name is a string
            name = str(name)
            self.logger.debug(f"Normalized name: {name!r}")
            
            query = """
            INSERT INTO locations (name, address, metadata)
            VALUES (%s, %s, %s)
            RETURNING *
            """
            
            self.logger.debug("Executing INSERT query")
            result = self._execute_query(query, (
                name,
                address,
                json.dumps(metadata or {})
            ))
            
            if not result:
                raise ValueError("No result returned from INSERT query")
            
            row = result[0]
            self.logger.debug(f"Query result: {row!r}")
            
            location = Location(
                id=uuid.UUID(str(row['id'])),
                name=str(row['name']),
                address=row['address'],
                metadata=row['metadata'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
            self.logger.debug(f"Created location object: {location!r}")
            return location
            
        except Exception as e:
            self.logger.error(f"Error creating location: {str(e)}")
            self.logger.exception("Full traceback:")
            raise

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
        try:
            location_id = self._to_uuid(row['id'])
            if location_id is None:
                return None
                
            return Location(
                id=location_id,
                name=row['name'],
                address=row['address'],
                metadata=row['metadata'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        except (KeyError, ValueError) as e:
            print(f"Error creating Location object: {e}")
            return None


    def get_by_name(self, name: str) -> Optional[Location]:
        """Get a location by name"""
        query = "SELECT * FROM locations WHERE name = %s"
        result = self._execute_query(query, (name,))
        
        if not result:
            return None
            
        row = result[0]
        return Location(
            id=uuid.UUID(row['id']),  # Ensure UUID conversion
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