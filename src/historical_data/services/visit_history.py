from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging
from ..models.models import (
    Visit, Problem, Solution, ChronogramEntry,
    ChecklistTemplate, VisitChecklist, Location,
    Severity, ProblemStatus, ChronogramStatus, ChecklistStatus
)
from ..database.repositories import (
    VisitRepository, ProblemRepository, SolutionRepository,
    ChronogramRepository, ChecklistTemplateRepository,
    VisitChecklistRepository
)
from ..database.location_repository import LocationRepository

class VisitHistoryService:
    """Service to manage visit history and related data."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.visit_repo = VisitRepository()
        self.problem_repo = ProblemRepository()
        self.solution_repo = SolutionRepository()
        self.chronogram_repo = ChronogramRepository()
        self.checklist_template_repo = ChecklistTemplateRepository()
        self.visit_checklist_repo = VisitChecklistRepository()
        self.location_repo = LocationRepository()
        

    def create_visit(self, location_id: uuid.UUID, date: datetime,
                    metadata: Optional[Dict[str, Any]] = None) -> Visit:
        """Create a new visit record."""
        try:
            # Verify location exists
            location = self.location_repo.get(location_id)
            if not location:
                raise ValueError(f"Location {location_id} not found")

            visit = self.visit_repo.create(
                date=date,
                location_id=location_id,
                metadata=metadata
            )
            self.logger.info(f"Created visit: {visit.id}")
            return visit
        except Exception as e:
            self.logger.error(f"Error creating visit: {str(e)}")
            raise

    def record_problem(self, visit_id: uuid.UUID, description: str,
                      severity: Severity, area: str) -> Problem:
        """Record a problem identified during a visit."""
        try:
            problem = self.problem_repo.create(
                visit_id=visit_id,
                description=description,
                severity=severity,
                area=area
            )
            self.logger.info(f"Recorded problem for visit {visit_id}: {problem.id}")
            return problem
        except Exception as e:
            self.logger.error(f"Error recording problem: {str(e)}")
            raise

    def add_solution(self, problem_id: uuid.UUID, description: str,
                    implemented_at: Optional[datetime] = None,
                    effectiveness_rating: Optional[int] = None) -> Solution:
        """Add a solution for a recorded problem."""
        try:
            solution = self.solution_repo.create(
                problem_id=problem_id,
                description=description,
                implemented_at=implemented_at,
                effectiveness_rating=effectiveness_rating
            )
            self.logger.info(f"Added solution for problem {problem_id}: {solution.id}")
            return solution
        except Exception as e:
            self.logger.error(f"Error adding solution: {str(e)}")
            raise

    def create_chronogram_entry(self, visit_id: uuid.UUID, task_name: str,
                              planned_start: datetime, planned_end: datetime,
                              dependencies: List[uuid.UUID] = None) -> ChronogramEntry:
        """Create a new chronogram entry for a visit."""
        try:
            entry = self.chronogram_repo.create(
                visit_id=visit_id,
                task_name=task_name,
                planned_start=planned_start,
                planned_end=planned_end,
                dependencies=dependencies
            )
            self.logger.info(f"Created chronogram entry: {entry.id}")
            return entry
        except Exception as e:
            self.logger.error(f"Error creating chronogram entry: {str(e)}")
            raise

    def update_chronogram_progress(self, entry_id: uuid.UUID,
                                 actual_start: Optional[datetime] = None,
                                 actual_end: Optional[datetime] = None,
                                 status: Optional[ChronogramStatus] = None) -> ChronogramEntry:
        """Update progress of a chronogram entry."""
        try:
            return self.chronogram_repo.update_progress(
                entry_id=entry_id,
                actual_start=actual_start,
                actual_end=actual_end,
                status=status
            )
        except Exception as e:
            self.logger.error(f"Error updating chronogram progress: {str(e)}")
            raise

    def create_checklist_template(self, name: str, items: List[Dict[str, Any]],
                                description: Optional[str] = None) -> ChecklistTemplate:
        """Create a new checklist template."""
        try:
            template = self.checklist_template_repo.create(
                name=name,
                items=items,
                description=description
            )
            self.logger.info(f"Created checklist template: {template.id}")
            return template
        except Exception as e:
            self.logger.error(f"Error creating checklist template: {str(e)}")
            raise

    def create_visit_checklist(self, visit_id: uuid.UUID,
                             template_id: uuid.UUID) -> VisitChecklist:
        """Create a new checklist for a visit based on a template."""
        try:
            checklist = self.visit_checklist_repo.create(
                visit_id=visit_id,
                template_id=template_id
            )
            self.logger.info(f"Created visit checklist: {checklist.id}")
            return checklist
        except Exception as e:
            self.logger.error(f"Error creating visit checklist: {str(e)}")
            raise

    def update_checklist_progress(self, checklist_id: uuid.UUID,
                                completed_items: List[Dict[str, Any]],
                                completion_status: ChecklistStatus) -> VisitChecklist:
        """Update progress of a visit checklist."""
        try:
            return self.visit_checklist_repo.update_progress(
                checklist_id=checklist_id,
                completed_items=completed_items,
                completion_status=completion_status
            )
        except Exception as e:
            self.logger.error(f"Error updating checklist progress: {str(e)}")
            raise

    def get_visit_history(self, location_id: uuid.UUID,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> List[Visit]:
        """Get visit history for a location."""
        try:
            # Verify location exists
            location = self.location_repo.get(location_id)
            if not location:
                raise ValueError(f"Location {location_id} not found")

            visits = self.visit_repo.get_by_location(
                location_id=location_id,
                start_date=start_date,
                end_date=end_date
            )
            return visits
        except Exception as e:
            self.logger.error(f"Error getting visit history: {str(e)}")
            raise

    def get_problem_trends(self, location_id: uuid.UUID,
                          area: Optional[str] = None) -> Dict[str, Any]:
        """Get problem history trends for a location."""
        try:
            # Verify location exists
            location = self.location_repo.get(location_id)
            if not location:
                raise ValueError(f"Location {location_id} not found")

            return self.problem_repo.get_problem_trends(
                location_id=location_id,
                area=area
            )
        except Exception as e:
            self.logger.error(f"Error getting problem trends: {str(e)}")
            raise