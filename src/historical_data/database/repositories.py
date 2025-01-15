from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import json

from ..models.models import (  # Fixed import path
    Visit, Problem, Solution, ChronogramEntry,
    ChecklistTemplate, VisitChecklist,
    Severity, ProblemStatus, ChronogramStatus, ChecklistStatus
)
from src.speakers.database.connection import DatabaseConnection  # Full import path


class BaseRepository:
    def __init__(self, connection=None):
        self.db = DatabaseConnection.get_instance()
        self._connection = connection

    def _get_connection(self):
        """Get the connection to use for queries"""
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
                    params = tuple(str(p) if isinstance(p, uuid.UUID) else p for p in params)
                cur.execute(query, params)
                if cur.description:  # If the query returns data
                    columns = [desc[0] for desc in cur.description]
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
                return None
        finally:
            if close_conn:
                conn.close()

    def _to_uuid(self, value: Any) -> Optional[uuid.UUID]:
        """Convert string to UUID if possible"""
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

class VisitRepository(BaseRepository):
    def create(self, date: datetime, location_id: uuid.UUID, metadata: Dict[str, Any] = None) -> Visit:
        query = """
        INSERT INTO visits (date, location_id, metadata)
        VALUES (%s, %s, %s)
        RETURNING id, date, location_id, metadata, created_at, updated_at
        """
        result = self._execute_query(query, (date, str(location_id), json.dumps(metadata or {})))
        if not result:
            raise ValueError("Failed to create visit")
            
        row = result[0]
        return Visit(
            id=self._to_uuid(row['id']),
            date=row['date'],
            location_id=self._to_uuid(row['location_id']),
            metadata=row['metadata'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def get(self, visit_id: uuid.UUID) -> Optional[Visit]:
        query = "SELECT * FROM visits WHERE id = %s"
        result = self._execute_query(query, (str(visit_id),))
        if not result:
            return None
            
        row = result[0]
        return Visit(
            id=self._to_uuid(row['id']),
            date=row['date'],
            location_id=self._to_uuid(row['location_id']),
            metadata=row['metadata'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def get_by_location(self, location_id: uuid.UUID, start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None) -> List[Visit]:
        query = "SELECT * FROM visits WHERE location_id = %s"
        params = [str(location_id)]
        
        if start_date:
            query += " AND date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND date <= %s"
            params.append(end_date)
            
        query += " ORDER BY date DESC"
        
        results = self._execute_query(query, tuple(params))
        return [
            Visit(
                id=self._to_uuid(row['id']),
                date=row['date'],
                location_id=self._to_uuid(row['location_id']),
                metadata=row['metadata'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in (results or [])
        ]

class ProblemRepository(BaseRepository):
    def create(self, visit_id: uuid.UUID, description: str, 
               severity: Severity, area: str) -> Problem:
        query = """
        INSERT INTO problems (visit_id, description, severity, area)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """
        result = self._execute_query(query, (str(visit_id), description, severity.value, area))
        row = result[0]
        return Problem(
            id=self._to_uuid(row['id']),
            visit_id=self._to_uuid(row['visit_id']),
            description=row['description'],
            severity=Severity(row['severity']),
            area=row['area'],
            status=ProblemStatus(row['status']),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def get_by_visit(self, visit_id: uuid.UUID) -> List[Problem]:
        query = "SELECT * FROM problems WHERE visit_id = %s"
        results = self._execute_query(query, (str(visit_id),))
        return [
            Problem(
                id=self._to_uuid(row['id']),
                visit_id=self._to_uuid(row['visit_id']),
                description=row['description'],
                severity=Severity(row['severity']),
                area=row['area'],
                status=ProblemStatus(row['status']),
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in results
        ]

    def get_history_by_location(self, location_id: uuid.UUID, 
                              area: Optional[str] = None) -> List[Problem]:
        """Get problems history for a location, optionally filtered by area"""
        query = """
        SELECT p.* FROM problems p
        JOIN visits v ON p.visit_id = v.id
        WHERE v.location_id = %s
        """
        params = [str(location_id)]
        
        if area:
            query += " AND p.area = %s"
            params.append(area)
            
        query += " ORDER BY v.date DESC, p.created_at DESC"
            
        results = self._execute_query(query, tuple(params))
        return [
            Problem(
                id=self._to_uuid(row['id']),
                visit_id=self._to_uuid(row['visit_id']),
                description=row['description'],
                severity=Severity(row['severity']),
                area=row['area'],
                status=ProblemStatus(row['status']),
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in (results or [])
        ]

    def get_problem_trends(self, location_id: uuid.UUID, 
                          area: Optional[str] = None) -> Dict[str, Any]:
        """Get problem trends and statistics"""
        problems = self.get_history_by_location(location_id, area)
        
        # Calculate trends
        total_problems = len(problems)
        severity_distribution = {}
        status_distribution = {}

        for problem in problems:
            severity_distribution[problem.severity] = severity_distribution.get(problem.severity, 0) + 1
            status_distribution[problem.status] = status_distribution.get(problem.status, 0) + 1

        return {
            'total_problems': total_problems,
            'severity_distribution': severity_distribution,
            'status_distribution': status_distribution
        }

    def update_status(self, problem_id: uuid.UUID, status: ProblemStatus) -> Problem:
        query = """
        UPDATE problems SET status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
        """
        result = self._execute_query(query, (status.value, str(problem_id)))
        row = result[0]
        return Problem(
            id=self._to_uuid(row['id']),
            visit_id=self._to_uuid(row['visit_id']),
            description=row['description'],
            severity=Severity(row['severity']),
            area=row['area'],
            status=ProblemStatus(row['status']),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

class SolutionRepository(BaseRepository):
    def create(self, problem_id: uuid.UUID, description: str,
               implemented_at: Optional[datetime] = None,
               effectiveness_rating: Optional[int] = None) -> Solution:
        query = """
        INSERT INTO solutions (problem_id, description, implemented_at, effectiveness_rating)
        VALUES (%s, %s, %s, %s)
        RETURNING id, problem_id, description, implemented_at, effectiveness_rating, 
                created_at, updated_at
        """
        result = self._execute_query(query, (
            str(problem_id), description, implemented_at, effectiveness_rating
        ))
        row = result[0]
        return Solution(
            id=self._to_uuid(row['id']),
            problem_id=self._to_uuid(row['problem_id']),
            description=row['description'],
            implemented_at=row['implemented_at'],
            effectiveness_rating=row['effectiveness_rating'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def get_by_problem(self, problem_id: uuid.UUID) -> List[Solution]:
        query = "SELECT * FROM solutions WHERE problem_id = %s ORDER BY created_at DESC"
        results = self._execute_query(query, (str(problem_id),))
        return [
            Solution(
                id=self._to_uuid(row['id']),
                problem_id=self._to_uuid(row['problem_id']),
                description=row['description'],
                implemented_at=row['implemented_at'],
                effectiveness_rating=row['effectiveness_rating'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in (results or [])
        ]

class ChronogramRepository(BaseRepository):
    def create(self, visit_id: uuid.UUID, task_name: str,
               planned_start: datetime, planned_end: datetime,
               dependencies: List[uuid.UUID] = None) -> ChronogramEntry:
        """Create a new chronogram entry."""
        query = """
        INSERT INTO chronogram_entries 
        (visit_id, task_name, planned_start, planned_end, dependencies)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """
        # Convert dependencies to list of strings if provided
        deps_array = [str(d) for d in dependencies] if dependencies else []
        
        result = self._execute_query(query, (
            str(visit_id),
            task_name,
            planned_start,
            planned_end,
            deps_array
        ))
        
        if not result:
            raise ValueError("Failed to create chronogram entry")
            
        row = result[0]
        
        # Handle dependencies safely
        dep_list = []
        if row['dependencies']:
            for dep in row['dependencies']:
                try:
                    if dep and str(dep).strip():  # Check if dep is not empty
                        dep_list.append(self._to_uuid(dep))
                except (ValueError, AttributeError):
                    continue  # Skip invalid UUIDs
        
        # Create ChronogramEntry with safe values
        return ChronogramEntry(
            id=self._to_uuid(row['id']),
            visit_id=self._to_uuid(row['visit_id']),
            task_name=row['task_name'],
            planned_start=row['planned_start'],
            planned_end=row['planned_end'],
            actual_start=row.get('actual_start'),
            actual_end=row.get('actual_end'),
            status=ChronogramStatus(row.get('status', 'planned')),
            dependencies=dep_list,
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def update_progress(self, entry_id: uuid.UUID,
                       actual_start: Optional[datetime] = None,
                       actual_end: Optional[datetime] = None,
                       status: Optional[ChronogramStatus] = None) -> ChronogramEntry:
        """Update progress of chronogram entry."""
        query = """
        UPDATE chronogram_entries 
        SET actual_start = COALESCE(%s, actual_start),
            actual_end = COALESCE(%s, actual_end),
            status = COALESCE(%s, status),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
        """
        result = self._execute_query(query, (
            actual_start,
            actual_end,
            status.value if status else None,
            str(entry_id)
        ))
        
        if not result:
            raise ValueError("Chronogram entry not found")
            
        row = result[0]
        
        # Handle dependencies safely
        dep_list = []
        if row['dependencies']:
            for dep in row['dependencies']:
                try:
                    if dep and str(dep).strip():
                        dep_list.append(self._to_uuid(dep))
                except (ValueError, AttributeError):
                    continue
        
        return ChronogramEntry(
            id=self._to_uuid(row['id']),
            visit_id=self._to_uuid(row['visit_id']),
            task_name=row['task_name'],
            planned_start=row['planned_start'],
            planned_end=row['planned_end'],
            actual_start=row['actual_start'],
            actual_end=row['actual_end'],
            status=ChronogramStatus(row['status']),
            dependencies=dep_list,
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def get_by_visit(self, visit_id: uuid.UUID) -> List[ChronogramEntry]:
        """Get all chronogram entries for a visit."""
        query = "SELECT * FROM chronogram_entries WHERE visit_id = %s ORDER BY planned_start"
        results = self._execute_query(query, (str(visit_id),))
        
        entries = []
        for row in results or []:
            # Handle dependencies safely
            dep_list = []
            if row['dependencies']:
                for dep in row['dependencies']:
                    try:
                        if dep and str(dep).strip():
                            dep_list.append(self._to_uuid(dep))
                    except (ValueError, AttributeError):
                        continue
            
            entries.append(ChronogramEntry(
                id=self._to_uuid(row['id']),
                visit_id=self._to_uuid(row['visit_id']),
                task_name=row['task_name'],
                planned_start=row['planned_start'],
                planned_end=row['planned_end'],
                actual_start=row['actual_start'],
                actual_end=row['actual_end'],
                status=ChronogramStatus(row['status']),
                dependencies=dep_list,
                created_at=row['created_at'],
                updated_at=row['updated_at']
            ))
            
        return entries

class ChecklistTemplateRepository(BaseRepository):
    def create(self, name: str, items: List[Dict[str, Any]], description: Optional[str] = None) -> ChecklistTemplate:
        query = """
        INSERT INTO checklist_templates (name, description, items)
        VALUES (%s, %s, %s)
        RETURNING *
        """
        result = self._execute_query(query, (name, description, json.dumps(items)))
        row = result[0]
        return ChecklistTemplate(
            id=self._to_uuid(row['id']),
            name=row['name'],
            description=row['description'],
            items=row['items'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def get(self, template_id: uuid.UUID) -> Optional[ChecklistTemplate]:
        query = "SELECT * FROM checklist_templates WHERE id = %s"
        result = self._execute_query(query, (str(template_id),))
        if not result:
            return None
        row = result[0]
        return ChecklistTemplate(
            id=self._to_uuid(row['id']),
            name=row['name'],
            description=row['description'],
            items=row['items'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

class VisitChecklistRepository(BaseRepository):
    def create(self, visit_id: uuid.UUID, template_id: uuid.UUID) -> VisitChecklist:
        query = """
        INSERT INTO visit_checklists (visit_id, template_id)
        VALUES (%s, %s)
        RETURNING *
        """
        result = self._execute_query(query, (str(visit_id), str(template_id)))
        row = result[0]
        return VisitChecklist(
            id=self._to_uuid(row['id']),
            visit_id=self._to_uuid(row['visit_id']),
            template_id=self._to_uuid(row['template_id']),
            completed_items=row['completed_items'],
            completion_status=ChecklistStatus(row['completion_status']),
            completed_at=row['completed_at'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def update_progress(self, checklist_id: uuid.UUID, 
                       completed_items: List[Dict[str, Any]],
                       completion_status: ChecklistStatus) -> VisitChecklist:
        query = """
        UPDATE visit_checklists
        SET completed_items = %s,
            completion_status = %s,
            completed_at = CASE WHEN %s = 'completed' THEN CURRENT_TIMESTAMP ELSE completed_at END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
        """
        result = self._execute_query(query, (
            json.dumps(completed_items),
            completion_status.value,
            completion_status.value,
            str(checklist_id)
        ))
        row = result[0]
        return VisitChecklist(
            id=self._to_uuid(row['id']),
            visit_id=self._to_uuid(row['visit_id']),
            template_id=self._to_uuid(row['template_id']),
            completed_items=row['completed_items'],
            completion_status=ChecklistStatus(row['completion_status']),
            completed_at=row['completed_at'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

class LocationRepository(BaseRepository):
    def create(self, name: str, address: str = None, coordinates: tuple = None, 
               metadata: Dict[str, Any] = None) -> Any:
        query = """
        INSERT INTO locations (name, address, coordinates, metadata)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """
        result = self._execute_query(query, (
            name,
            address,
            coordinates,
            json.dumps(metadata or {})
        ))
        row = result[0]
        return {
            'id': self._to_uuid(row['id']),
            'name': row['name'],
            'address': row['address'],
            'coordinates': row['coordinates'],
            'metadata': row['metadata'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }