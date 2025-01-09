from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
from .models import (
    ConstructionProblem, AnalysisContext, ProblemCategory,
    AnalysisConfidence, LocationContext
)
from src.historical_data.models.models import Severity, ProblemStatus
from src.report_generation.llm_service import LLMService

class ProblemAnalyzer:
    """Analyzes and identifies construction problems from visit data."""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()
        
        # Initialize keyword mappings for categorization
        self.category_keywords = {
            ProblemCategory.STRUCTURAL: [
                'grieta', 'fisura', 'deformación', 'asentamiento', 'structural',
                'cimentación', 'columna', 'viga', 'muro portante'
            ],
            ProblemCategory.SAFETY: [
                'riesgo', 'peligro', 'seguridad', 'protección', 'safety',
                'accidente', 'epp', 'caída', 'prevención'
            ],
            ProblemCategory.QUALITY: [
                'calidad', 'acabado', 'especificación', 'estándar', 'quality',
                'material', 'técnica', 'procedimiento', 'control'
            ],
            ProblemCategory.SCHEDULE: [
                'retraso', 'cronograma', 'plazo', 'tiempo', 'schedule',
                'demora', 'avance', 'progreso', 'fecha'
            ],
            ProblemCategory.RESOURCE: [
                'material', 'equipo', 'herramienta', 'personal', 'resource',
                'suministro', 'inventario', 'disponibilidad'
            ],
            ProblemCategory.ENVIRONMENTAL: [
                'ambiental', 'contaminación', 'residuo', 'environmental',
                'ruido', 'polvo', 'emisión', 'impacto'
            ]
        }
        
        # Severity assessment criteria
        self.severity_criteria = {
            Severity.CRITICAL: [
                'inmediato', 'grave', 'crítico', 'urgente', 'peligro',
                'structural failure', 'colapso'
            ],
            Severity.HIGH: [
                'importante', 'significativo', 'alto', 'serio', 'alta',  
                'substantial', 'major', 'severe'
            ],
            Severity.MEDIUM: [
                'moderado', 'medio', 'regular', 'notable',
                'moderate', 'significant'
            ],
            Severity.LOW: [
                'menor', 'leve', 'bajo', 'mínimo',
                'minor', 'slight', 'small'
            ]
        }

    def analyze_transcript(
        self,
        transcript_text: str,
        context: AnalysisContext
    ) -> List[ConstructionProblem]:
        """
        Analyze transcript to identify construction problems.
        
        Args:
            transcript_text: Raw transcript text from the visit
            context: Analysis context including historical data
            
        Returns:
            List of identified ConstructionProblem instances
        """
        # Get initial analysis from LLM
        llm_analysis = self.llm_service.analyze_transcript(
            transcript_text=transcript_text,
            session_info={"session_id": str(context.visit_id)},
            location_data=None  # Location already processed in context
        )
        
        # Extract problems from LLM analysis
        problems = self._extract_problems_from_llm(llm_analysis, context)
        
        # Enhance with historical context
        self._enhance_with_historical_context(problems, context)
        
        # Validate and refine problem details
        self._validate_and_refine_problems(problems)
        
        return problems

    def _extract_problems_from_llm(
        self,
        llm_analysis: Dict[str, Any],
        context: AnalysisContext
    ) -> List[ConstructionProblem]:
        """Extract problems from LLM analysis results."""
        problems = []
        
        # Process technical findings
        for finding in llm_analysis.get('technical_findings', []):
            location_context = self._create_location_context(finding, context)
            
            category = self._determine_category(finding.get('hallazgo', ''))
            severity = self._assess_severity(finding)
            
            problem = ConstructionProblem(
                category=category,
                description=finding.get('hallazgo', ''),
                severity=severity,
                location_context=location_context,
                confidence=self._assess_confidence(finding)
            )
            problems.append(problem)
        
        # Process safety concerns as problems
        for concern in llm_analysis.get('preocupaciones_seguridad', []):
            location_context = self._create_location_context(concern, context)
            
            problem = ConstructionProblem(
                category=ProblemCategory.SAFETY,
                description=concern.get('preocupacion', ''),
                severity=Severity.HIGH,  # Safety concerns default to high severity
                location_context=location_context,
                confidence=AnalysisConfidence.HIGH
            )
            problems.append(problem)
        
        return problems

    def _determine_category(self, description: str) -> ProblemCategory:
        """Determine problem category based on description and keywords."""
        description = description.lower()
        
        # Calculate keyword matches for each category
        matches = {
            category: sum(1 for keyword in keywords if keyword in description)
            for category, keywords in self.category_keywords.items()
        }
        
        # Return category with most matches, or OTHER if no matches
        max_matches = max(matches.values()) if matches else 0
        if max_matches > 0:
            return max(matches.items(), key=lambda x: x[1])[0]
        return ProblemCategory.OTHER

    def _assess_severity(self, finding: Dict[str, Any]) -> Severity:
        """Assess problem severity based on finding details."""
        description = f"{finding.get('hallazgo', '')} {finding.get('severidad', '')}".lower()
        
        # Check against severity criteria
        for severity, keywords in self.severity_criteria.items():
            if any(keyword in description for keyword in keywords):
                return severity
        
        # Default to MEDIUM if no clear indicators
        return Severity.MEDIUM

    def _assess_confidence(self, finding: Dict[str, Any]) -> AnalysisConfidence:
        """Assess confidence in problem identification."""
        # This could be enhanced with more sophisticated confidence assessment
        if finding.get('severidad') and finding.get('accion_recomendada'):
            return AnalysisConfidence.HIGH
        elif finding.get('severidad') or finding.get('accion_recomendada'):
            return AnalysisConfidence.MEDIUM
        return AnalysisConfidence.LOW

    def _create_location_context(
        self,
        finding: Dict[str, Any],
        context: AnalysisContext
    ) -> LocationContext:
        """Create location context for a problem."""
        return LocationContext(
            area=finding.get('ubicacion', 'Unknown Area'),
            sub_location=finding.get('sub_ubicacion'),
            change_history=[
                change for change in context.location_changes
                if change.area == finding.get('ubicacion')
            ],
            additional_info={
                'finding_metadata': finding,
                'timestamp': datetime.now().isoformat()
            }
        )

    def _enhance_with_historical_context(
        self,
        problems: List[ConstructionProblem],
        context: AnalysisContext
    ) -> None:
        """Enhance problems with historical context and patterns."""
        for problem in problems:
            historical_matches = []
            
            # Check each previous visit for similar problems
            for visit in context.previous_visit_findings:
                for hist_problem in visit['problems']:
                    if self._are_problems_similar(problem, hist_problem):
                        historical_matches.append({
                            'problem_id': hist_problem.id,
                            'visit_date': visit['date'],
                            'severity': hist_problem.severity,
                            'status': hist_problem.status
                        })
            
            if historical_matches:
                problem.historical_pattern = True
                problem.related_problems.extend(
                    match['problem_id'] for match in historical_matches
                )
                problem.metadata['historical_matches'] = historical_matches
                
                # Adjust severity if historical problems were more severe
                if any(match['severity'] == Severity.CRITICAL for match in historical_matches):
                    problem.severity = Severity.CRITICAL
                    problem.confidence = AnalysisConfidence.HIGH

    def _validate_and_refine_problems(
        self,
        problems: List[ConstructionProblem]
    ) -> None:
        """Validate and refine problem details."""
        for problem in problems:
            # Ensure description is meaningful
            if len(problem.description.strip()) < 10:
                problem.confidence = AnalysisConfidence.LOW
            
            # Validate location context
            if not problem.location_context.area or problem.location_context.area == 'Unknown Area':
                problem.confidence = AnalysisConfidence.LOW
            
            # Set appropriate status based on confidence
            if problem.confidence == AnalysisConfidence.LOW:
                problem.status = ProblemStatus.MONITORING
            
            # Add metadata about validation
            problem.metadata['validation'] = {
                'timestamp': datetime.now().isoformat(),
                'confidence_reason': self._get_confidence_reason(problem)
            }

    def _are_problems_similar(
        self,
        current_problem: ConstructionProblem,
        historical_problem: Any
    ) -> bool:
        """
        Compare current problem with a historical one for similarity.
        
        Args:
            current_problem: Current ConstructionProblem instance
            historical_problem: Historical problem from database
            
        Returns:
            bool indicating if problems are similar
        """
        # Check category matches (if available)
        if hasattr(historical_problem, 'category'):
            if current_problem.category == historical_problem.category:
                return True
        
        # Check description similarity
        current_desc = current_problem.description.lower()
        historical_desc = historical_problem.description.lower()
        
        # Split descriptions into words and check overlap
        current_words = set(current_desc.split())
        historical_words = set(historical_desc.split())
        
        # Calculate Jaccard similarity
        intersection = len(current_words.intersection(historical_words))
        union = len(current_words.union(historical_words))
        
        similarity = intersection / union if union > 0 else 0
        
        # Check location similarity
        same_location = (
            current_problem.location_context.area.lower() in historical_problem.description.lower() or
            historical_problem.description.lower() in current_problem.location_context.area.lower()
        )
        
        # Return True if either similarity is high or locations match with some word overlap
        return similarity > 0.3 or (same_location and similarity > 0.1)

    def _get_confidence_reason(self, problem: ConstructionProblem) -> str:
        """Get reason for confidence level assignment."""
        reasons = []

        # Check description quality
        if len(problem.description.strip()) >= 50:
            reasons.append("Detailed description")
        elif len(problem.description.strip()) >= 20:
            reasons.append("Basic description")
        else:
            reasons.append("Insufficient description")

        # Check location information
        if problem.location_context.sub_location:
            reasons.append("Precise location")
        elif problem.location_context.area != "Unknown Area":
            reasons.append("General location")
        else:
            reasons.append("Unclear location")

        # Check historical context
        if problem.historical_pattern:
            reasons.append("Historical pattern identified")
            if len(problem.related_problems) > 2:
                reasons.append("Multiple historical occurrences")

        # Calculate confidence level
        confidence_score = 0
        confidence_score += 2 if len(problem.description.strip()) >= 50 else (1 if len(problem.description.strip()) >= 20 else 0)
        confidence_score += 2 if problem.location_context.sub_location else (1 if problem.location_context.area != "Unknown Area" else 0)
        confidence_score += 2 if problem.historical_pattern and len(problem.related_problems) > 2 else (1 if problem.historical_pattern else 0)

        # Update problem confidence based on score
        if confidence_score >= 5:
            problem.confidence = AnalysisConfidence.HIGH
        elif confidence_score >= 3:
            problem.confidence = AnalysisConfidence.MEDIUM
        else:
            problem.confidence = AnalysisConfidence.LOW

        return "; ".join(reasons)