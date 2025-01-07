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
    def __init__(self):
        self.db = DatabaseConnection.get_instance()

    def _execute_query(self, query: str, params: tuple = None) -> Optional[List[tuple]]:
        """Execute a query and return results"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:  # If the query returns data
                    return cur.fetchall()
                conn.commit()
                return None
        finally:
            conn.close()


class VisitRepository(BaseRepository):
    def create(self, date: datetime, location_id: uuid.UUID, metadata: Dict[str, Any] = None) -> Visit:
        query = """
        INSERT INTO visits (date, location_id, metadata)
        VALUES (%s, %s, %s)
        RETURNING id, date, location_id, metadata, created_at, updated_at
        """
        result = self._execute_query(query, (date, location_id, json.dumps(metadata or {})))
        row = result[0]
        return Visit(
            id=row[0],
            date=row[1],
            location_id=row[2],
            metadata=row[3],
            created_at=row[4],
            updated_at=row[5]
        )

    def get(self, visit_id: uuid.UUID) -> Optional[Visit]:
        query = "SELECT * FROM visits WHERE id = %s"
        result = self._execute_query(query, (str(visit_id),))
        if not result:
            return None
        row = result[0]
        return Visit(
            id=row[0],
            date=row[1],
            location_id=row[2],
            metadata=row[3],
            created_at=row[4],
            updated_at=row[5]
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
                id=row[0],
                date=row[1],
                location_id=row[2],
                metadata=row[3],
                created_at=row[4],
                updated_at=row[5]
            )
            for row in results
        ]

class ProblemRepository(BaseRepository):
    def create(self, visit_id: uuid.UUID, description: str, 
               severity: Severity, area: str) -> Problem:
        query = """
        INSERT INTO problems (visit_id, description, severity, area)
        VALUES (%s, %s, %s, %s)
        RETURNING id, visit_id, description, severity, area, status, created_at, updated_at
        """
        result = self._execute_query(query, (str(visit_id), description, severity.value, area))
        row = result[0]
        return Problem(
            id=row[0],
            visit_id=row[1],
            description=row[2],
            severity=Severity(row[3]),
            area=row[4],
            status=ProblemStatus(row[5]),
            created_at=row[6],
            updated_at=row[7]
        )

    def get_by_visit(self, visit_id: uuid.UUID) -> List[Problem]:
        query = "SELECT * FROM problems WHERE visit_id = %s"
        results = self._execute_query(query, (str(visit_id),))
        return [
            Problem(
                id=row[0],
                visit_id=row[1],
                description=row[2],
                severity=Severity(row[3]),
                area=row[4],
                status=ProblemStatus(row[5]),
                created_at=row[6],
                updated_at=row[7]
            )
            for row in results
        ]

    def get_history_by_location(self, location_id: uuid.UUID, 
                              area: Optional[str] = None) -> List[Dict[str, Any]]:
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
            {
                'problem': Problem(
                    id=row[0],
                    visit_id=row[1],
                    description=row[2],
                    severity=Severity(row[3]),
                    area=row[4],
                    status=ProblemStatus(row[5]),
                    created_at=row[6],
                    updated_at=row[7]
                )
            }
            for row in results
        ]

    def update_status(self, problem_id: uuid.UUID, status: ProblemStatus) -> Problem:
        query = """
        UPDATE problems SET status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING id, visit_id, description, severity, area, status, created_at, updated_at
        """
        result = self._execute_query(query, (status.value, str(problem_id)))
        row = result[0]
        return Problem(
            id=row[0],
            visit_id=row[1],
            description=row[2],
            severity=Severity(row[3]),
            area=row[4],
            status=ProblemStatus(row[5]),
            created_at=row[6],
            updated_at=row[7]
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
            id=row[0],
            problem_id=row[1],
            description=row[2],
            implemented_at=row[3],
            effectiveness_rating=row[4],
            created_at=row[5],
            updated_at=row[6]
        )

    def get_by_problem(self, problem_id: uuid.UUID) -> List[Solution]:
        query = "SELECT * FROM solutions WHERE problem_id = %s ORDER BY created_at DESC"
        results = self._execute_query(query, (str(problem_id),))
        return [
            Solution(
                id=row[0],
                problem_id=row[1],
                description=row[2],
                implemented_at=row[3],
                effectiveness_rating=row[4],
                created_at=row[5],
                updated_at=row[6]
            )
            for row in results
        ]

class ChronogramRepository(BaseRepository):
    def create(self, visit_id: uuid.UUID, task_name: str,
               planned_start: datetime, planned_end: datetime,
               dependencies: List[uuid.UUID] = None) -> ChronogramEntry:
        query = """
        INSERT INTO chronogram_entries 
        (visit_id, task_name, planned_start, planned_end, dependencies)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, visit_id, task_name, planned_start, planned_end,
                actual_start, actual_end, status, dependencies, created_at, updated_at
        """
        result = self._execute_query(query, (
            str(visit_id), task_name, planned_start, planned_end,
            [str(d) for d in (dependencies or [])]
        ))
        row = result[0]
        return ChronogramEntry(
            id=row[0],
            visit_id=row[1],
            task_name=row[2],
            planned_start=row[3],
            planned_end=row[4],
            actual_start=row[5],
            actual_end=row[6],
            status=ChronogramStatus(row[7]),
            dependencies=[uuid.UUID(str(d)) for d in (row[8] or [])],
            created_at=row[9],
            updated_at=row[10]
        )

    def get_by_visit(self, visit_id: uuid.UUID) -> List[ChronogramEntry]:
        query = "SELECT * FROM chronogram_entries WHERE visit_id = %s ORDER BY planned_start"
        results = self._execute_query(query, (str(visit_id),))
        return [
            ChronogramEntry(
                id=row[0],
                visit_id=row[1],
                task_name=row[2],
                planned_start=row[3],
                planned_end=row[4],
                actual_start=row[5],
                actual_end=row[6],
                status=ChronogramStatus(row[7]),
                dependencies=[uuid.UUID(str(d)) for d in (row[8] or [])],
                created_at=row[9],
                updated_at=row[10]
            )
            for row in results
        ]

    def update_progress(self, entry_id: uuid.UUID, actual_start: Optional[datetime] = None,
                       actual_end: Optional[datetime] = None,
                       status: Optional[ChronogramStatus] = None) -> ChronogramEntry:
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
            actual_start, actual_end,
            status.value if status else None,
            str(entry_id)
        ))
        row = result[0]
        return ChronogramEntry(
            id=row[0],
            visit_id=row[1],
            task_name=row[2],
            planned_start=row[3],
            planned_end=row[4],
            actual_start=row[5],
            actual_end=row[6],
            status=ChronogramStatus(row[7]),
            dependencies=[uuid.UUID(str(d)) for d in (row[8] or [])],
            created_at=row[9],
            updated_at=row[10]
        )

class ChecklistTemplateRepository(BaseRepository):
    def create(self, name: str, items: List[Dict[str, Any]], 
               description: Optional[str] = None) -> ChecklistTemplate:
        query = """
        INSERT INTO checklist_templates (name, description, items)
        VALUES (%s, %s, %s)
        RETURNING id, name, description, items, created_at, updated_at
        """
        result = self._execute_query(query, (name, description, json.dumps(items)))
        row = result[0]
        return ChecklistTemplate(
            id=row[0],
            name=row[1],
            description=row[2],
            items=row[3],
            created_at=row[4],
            updated_at=row[5]
        )

    def get(self, template_id: uuid.UUID) -> Optional[ChecklistTemplate]:
        query = "SELECT * FROM checklist_templates WHERE id = %s"
        result = self._execute_query(query, (str(template_id),))
        if not result:
            return None
        row = result[0]
        return ChecklistTemplate(
            id=row[0],
            name=row[1],
            description=row[2],
            items=row[3],
            created_at=row[4],
            updated_at=row[5]
        )

class VisitChecklistRepository(BaseRepository):
    def create(self, visit_id: uuid.UUID, template_id: uuid.UUID) -> VisitChecklist:
        query = """
        INSERT INTO visit_checklists (visit_id, template_id)
        VALUES (%s, %s)
        RETURNING id, visit_id, template_id, completed_items, completion_status,
                completed_at, created_at, updated_at
        """
        result = self._execute_query(query, (str(visit_id), str(template_id)))
        row = result[0]
        return VisitChecklist(
            id=row[0],
            visit_id=row[1],
            template_id=row[2],
            completed_items=row[3],
            completion_status=ChecklistStatus(row[4]),
            completed_at=row[5],
            created_at=row[6],
            updated_at=row[7]
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
            id=row[0],
            visit_id=row[1],
            template_id=row[2],
            completed_items=row[3],
            completion_status=ChecklistStatus(row[4]),
            completed_at=row[5],
            created_at=row[6],
            updated_at=row[7]
        )