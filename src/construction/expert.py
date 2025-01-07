from typing import List, Dict, Any, Optional
import uuid
import time
from datetime import datetime

from .models import (
    ConstructionProblem, ProposedSolution, AnalysisContext,
    AnalysisResult, ProblemCategory, AnalysisConfidence, LocationContext
)
from src.historical_data.models.models import Severity, ProblemStatus
from src.historical_data.services.visit_history import VisitHistoryService
from src.location.location_processor import LocationProcessor
from src.report_generation.llm_service import LLMService

class ConstructionExpert:
    """Main class for construction site analysis and problem identification."""
    
    def __init__(self):
        self.visit_history = VisitHistoryService()
        self.location_processor = LocationProcessor()
        self.llm_service = LLMService()

    def analyze_visit(
        self,
        visit_id: uuid.UUID,
        transcript_text: str,
        location_id: uuid.UUID,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Analyze a construction site visit using transcript and historical data.
        
        Args:
            visit_id: UUID of the current visit
            transcript_text: Raw transcript text from the visit
            location_id: UUID of the construction site location
            metadata: Additional metadata about the visit
            
        Returns:
            AnalysisResult containing identified problems and proposed solutions
        """
        start_time = time.time()
        
        try:
            # Process location data
            location_data = self.location_processor.process_transcript(transcript_text)
            
            # Create analysis context
            context = self._build_analysis_context(
                visit_id=visit_id,
                location_id=location_id,
                location_data=location_data,
                metadata=metadata
            )
            
            # Get LLM analysis of transcript
            llm_analysis = self.llm_service.analyze_transcript(
                transcript_text=transcript_text,
                session_info={"session_id": str(visit_id)},
                location_data=location_data
            )
            
            # Extract problems from LLM analysis
            problems = self._identify_problems(llm_analysis, context)
            
            # Generate solutions for each problem
            solutions = self._generate_solutions(problems, context)
            
            # Calculate confidence scores
            confidence_scores = self._calculate_confidence_scores(
                problems=problems,
                solutions=solutions,
                context=context
            )
            
            execution_time = time.time() - start_time
            
            return AnalysisResult(
                context=context,
                problems=problems,
                solutions=solutions,
                confidence_scores=confidence_scores,
                execution_time=execution_time,
                metadata={
                    "llm_analysis_id": llm_analysis.get("metadata", {}).get("analysis_id"),
                    "location_data": location_data
                }
            )
            
        except Exception as e:
            # Log error and return minimal result
            print(f"Error in construction analysis: {str(e)}")
            raise

    def _build_analysis_context(
        self,
        visit_id: uuid.UUID,
        location_id: uuid.UUID,
        location_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> AnalysisContext:
        """Build analysis context from visit data and historical information."""
        # Get previous visits
        previous_visits = self.visit_history.get_visit_history(
            location_id=location_id
        )
        
        # Extract previous findings
        previous_findings = []
        for visit in previous_visits:
            problems = self.visit_history.problem_repo.get_by_visit(visit.id)
            if problems:
                previous_findings.append({
                    "visit_id": visit.id,
                    "date": visit.date,
                    "problems": problems
                })
        
        return AnalysisContext(
            visit_id=visit_id,
            location_id=location_id,
            datetime=datetime.now(),
            previous_visit_findings=previous_findings,
            location_changes=location_data.get("location_changes", []),
            metadata=metadata or {}
        )

    def _identify_problems(
        self,
        llm_analysis: Dict[str, Any],
        context: AnalysisContext
    ) -> List[ConstructionProblem]:
        """Extract and categorize problems from LLM analysis."""
        problems = []
        
        # Process technical findings
        for finding in llm_analysis.get('technical_findings', []):
            location_context = LocationContext(
                area=finding.get('ubicacion', 'Unknown'),
                sub_location=finding.get('sub_ubicacion'),
                additional_info={'raw_finding': finding}
            )
            
            # Map severity
            severity_map = {
                'Baja': Severity.LOW,
                'Media': Severity.MEDIUM,
                'Alta': Severity.HIGH,
                'Crítica': Severity.CRITICAL
            }
            severity = severity_map.get(finding.get('severidad', 'Media'), Severity.MEDIUM)
            
            # Determine category based on finding content
            category = self._categorize_problem(finding.get('hallazgo', ''))
            
            problem = ConstructionProblem(
                category=category,
                description=finding.get('hallazgo', ''),
                severity=severity,
                location_context=location_context,
                status=ProblemStatus.IDENTIFIED,
                confidence=AnalysisConfidence.MEDIUM
            )
            problems.append(problem)
            
        # Look for historical patterns
        self._analyze_historical_patterns(problems, context)
        
        return problems

    def _categorize_problem(self, description: str) -> ProblemCategory:
        """Categorize problem based on description."""
        # This is a simple categorization that should be enhanced
        keywords = {
            ProblemCategory.STRUCTURAL: ['structural', 'estructura', 'cimientos', 'grietas'],
            ProblemCategory.SAFETY: ['safety', 'seguridad', 'riesgo', 'peligro'],
            ProblemCategory.QUALITY: ['quality', 'calidad', 'acabados', 'materiales'],
            ProblemCategory.SCHEDULE: ['schedule', 'cronograma', 'retraso', 'plazo'],
            ProblemCategory.RESOURCE: ['resource', 'recursos', 'materiales', 'equipo'],
            ProblemCategory.ENVIRONMENTAL: ['environmental', 'ambiental', 'contaminación']
        }
        
        description = description.lower()
        for category, words in keywords.items():
            if any(word in description for word in words):
                return category
        
        return ProblemCategory.OTHER

    def _generate_solutions(
        self,
        problems: List[ConstructionProblem],
        context: AnalysisContext
    ) -> Dict[uuid.UUID, List[ProposedSolution]]:
        """Generate solutions for identified problems."""
        solutions = {}
        
        for problem in problems:
            problem_solutions = []
            
            # Check historical solutions first
            historical_solutions = self._find_historical_solutions(problem, context)
            if historical_solutions:
                problem_solutions.extend(historical_solutions)
            
            # Generate new solutions if needed
            if len(problem_solutions) < 2:  # Ensure at least 2 solutions per problem
                new_solutions = self._generate_new_solutions(problem, context)
                problem_solutions.extend(new_solutions)
            
            solutions[problem.id] = problem_solutions
        
        return solutions

    def _analyze_historical_patterns(
        self,
        problems: List[ConstructionProblem],
        context: AnalysisContext
    ) -> None:
        """Analyze problems for historical patterns."""
        for problem in problems:
            for historical_visit in context.previous_visit_findings:
                for hist_problem in historical_visit['problems']:
                    if self._are_problems_similar(problem, hist_problem):
                        problem.historical_pattern = True
                        problem.related_problems.append(hist_problem.id)

    def _find_historical_solutions(
        self,
        problem: ConstructionProblem,
        context: AnalysisContext
    ) -> List[ProposedSolution]:
        """Find relevant historical solutions for a problem."""
        solutions = []
        
        # Get historical solutions through visit history service
        if problem.related_problems:
            for related_id in problem.related_problems:
                historical_solutions = self.visit_history.solution_repo.get_by_problem(related_id)
                for hist_sol in historical_solutions:
                    # Create new solution based on historical one
                    solution = ProposedSolution(
                        problem_id=problem.id,
                        description=hist_sol.description,
                        estimated_time=hist_sol.implemented_at,
                        effectiveness_rating=hist_sol.effectiveness_rating,
                        historical_success_rate=hist_sol.effectiveness_rating
                    )
                    solutions.append(solution)
        
        return solutions

    def _generate_new_solutions(
        self,
        problem: ConstructionProblem,
        context: AnalysisContext
    ) -> List[ProposedSolution]:
        """Generate new solutions for a problem."""
        # This is a placeholder - in practice, this would use the LLM service
        # to generate creative solutions based on the problem description
        solution = ProposedSolution(
            problem_id=problem.id,
            description=f"Standard mitigation for {problem.category.value} issue",
            priority=2
        )
        return [solution]

    def _are_problems_similar(self, problem1: ConstructionProblem, problem2: Any) -> bool:
        """Compare two problems for similarity."""
        # Simple comparison - should be enhanced with better similarity metrics
        return (
            problem1.category.value in problem2.description.lower() or
            problem1.description.lower() in problem2.description.lower()
        )

    def _calculate_confidence_scores(
        self,
        problems: List[ConstructionProblem],
        solutions: Dict[uuid.UUID, List[ProposedSolution]],
        context: AnalysisContext
    ) -> Dict[str, float]:
        """Calculate confidence scores for analysis results."""
        scores = {
            'overall': 0.0,
            'problem_identification': 0.0,
            'solution_generation': 0.0,
            'historical_analysis': 0.0
        }
        
        # Problem identification confidence
        if problems:
            problem_scores = [
                1.0 if p.confidence == AnalysisConfidence.HIGH else
                0.7 if p.confidence == AnalysisConfidence.MEDIUM else
                0.4
                for p in problems
            ]
            scores['problem_identification'] = sum(problem_scores) / len(problem_scores)
        
        # Solution generation confidence
        if solutions:
            solution_scores = []
            for problem_solutions in solutions.values():
                if problem_solutions:
                    avg_effectiveness = sum(
                        s.effectiveness_rating or 0.5 
                        for s in problem_solutions
                    ) / len(problem_solutions)
                    solution_scores.append(avg_effectiveness)
            if solution_scores:
                scores['solution_generation'] = sum(solution_scores) / len(solution_scores)
        
        # Historical analysis confidence
        if context.previous_visit_findings:
            scores['historical_analysis'] = 0.8  # High if we have historical data
        
        # Overall confidence
        scores['overall'] = sum(
            score for score in scores.values() if score > 0
        ) / len([score for score in scores.values() if score > 0])
        
        return scores