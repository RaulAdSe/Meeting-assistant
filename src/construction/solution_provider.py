from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timedelta
from .models import (
    ConstructionProblem, ProposedSolution, AnalysisContext,
    ProblemCategory, AnalysisConfidence
)
from src.historical_data.models.models import Severity
from src.historical_data.services.visit_history import VisitHistoryService
from src.report_generation.llm_service import LLMService

class SolutionProvider:
    """Generates and manages solutions for construction problems."""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()
        self.visit_history = VisitHistoryService()
        
        # Initialize solution templates
        self.solution_templates = {
            ProblemCategory.STRUCTURAL: [
                "Realizar evaluación estructural detallada",
                "Implementar refuerzo estructural",
                "Reparar elementos dañados",
                "Monitorear deformaciones"
            ],
            ProblemCategory.SAFETY: [
                "Implementar medidas de seguridad inmediatas",
                "Revisar y actualizar protocolos de seguridad",
                "Proporcionar EPP adicional",
                "Realizar capacitación de seguridad"
            ],
            ProblemCategory.QUALITY: [
                "Realizar control de calidad exhaustivo",
                "Revisar especificaciones técnicas",
                "Implementar nuevos procedimientos",
                "Mejorar supervisión de acabados"
            ],
            ProblemCategory.SCHEDULE: [
                "Actualizar cronograma de trabajo",
                "Optimizar secuencia de actividades",
                "Asignar recursos adicionales",
                "Implementar seguimiento diario"
            ],
            ProblemCategory.RESOURCE: [
                "Gestionar nuevos proveedores",
                "Optimizar inventario",
                "Reorganizar equipos de trabajo",
                "Implementar sistema de control de recursos"
            ],
            ProblemCategory.ENVIRONMENTAL: [
                "Implementar medidas de mitigación ambiental",
                "Mejorar gestión de residuos",
                "Reducir impacto en entorno",
                "Monitorear emisiones y ruido"
            ]
        }

    def generate_solutions(
        self,
        problem: ConstructionProblem,
        context: AnalysisContext
    ) -> List[ProposedSolution]:
        """
        Generate solutions for a construction problem.
        
        Args:
            problem: The construction problem to solve
            context: Analysis context including historical data
            
        Returns:
            List of proposed solutions
        """
        solutions = []
        
        # Try to find historical solutions first
        historical_solutions = self._find_historical_solutions(problem, context)
        solutions.extend(historical_solutions)
        
        # Generate new solutions if needed
        if len(solutions) < 2:
            llm_solutions = self._generate_llm_solutions(problem, context)
            solutions.extend(llm_solutions)
        
        # Add template-based solutions if still needed
        if len(solutions) < 2:
            template_solutions = self._generate_template_solutions(problem)
            solutions.extend(template_solutions)
        
        # Ensure unique solutions
        solutions = self._deduplicate_solutions(solutions)
        
        # Prioritize solutions
        self._prioritize_solutions(solutions, problem)
        
        return solutions

    def _find_historical_solutions(
        self,
        problem: ConstructionProblem,
        context: AnalysisContext
    ) -> List[ProposedSolution]:
        """Find relevant historical solutions."""
        historical_solutions = []
        
        if problem.related_problems:
            for related_id in problem.related_problems:
                # Get historical solutions from database
                solutions = self.visit_history.solution_repo.get_by_problem(related_id)
                
                for hist_sol in solutions:
                    if hist_sol.effectiveness_rating and hist_sol.effectiveness_rating >= 3:
                        solution = ProposedSolution(
                            problem_id=problem.id,
                            description=hist_sol.description,
                            estimated_time=hist_sol.implemented_at,
                            effectiveness_rating=hist_sol.effectiveness_rating,
                            historical_success_rate=hist_sol.effectiveness_rating,
                            metadata={
                                'source': 'historical',
                                'original_solution_id': hist_sol.id
                            }
                        )
                        historical_solutions.append(solution)
        
        return historical_solutions

    def _generate_llm_solutions(
        self,
        problem: ConstructionProblem,
        context: AnalysisContext
    ) -> List[ProposedSolution]:
        """Generate solutions using LLM."""
        try:
            # Prepare prompt for LLM
            prompt = self._create_solution_prompt(problem, context)
            
            # Get LLM analysis
            response = self.llm_service.analyze_transcript(
                transcript_text=prompt,
                session_info={"type": "solution_generation"},
                location_data=None
            )
            
            solutions = []
            for suggestion in response.get('optimization_suggestions', []):
                solution = ProposedSolution(
                    problem_id=problem.id,
                    description=suggestion,
                    estimated_time=self._estimate_solution_time(suggestion),
                    metadata={'source': 'llm_generated'}
                )
                solutions.append(solution)
            
            return solutions
            
        except Exception as e:
            print(f"Error generating LLM solutions: {str(e)}")
            return []

    def _generate_template_solutions(
        self,
        problem: ConstructionProblem
    ) -> List[ProposedSolution]:
        """Generate solutions based on templates."""
        templates = self.solution_templates.get(problem.category, [])
        
        solutions = []
        for template in templates:
            solution = ProposedSolution(
                problem_id=problem.id,
                description=template,
                estimated_time=self._estimate_solution_time(template),
                metadata={'source': 'template'}
            )
            solutions.append(solution)
        
        return solutions

    def _create_solution_prompt(
        self,
        problem: ConstructionProblem,
        context: AnalysisContext
    ) -> str:
        """Create prompt for LLM solution generation."""
        return f"""Analizar y proponer soluciones para el siguiente problema de construcción:

Categoría: {problem.category.value}
Descripción: {problem.description}
Severidad: {problem.severity.value}
Ubicación: {problem.location_context.area}

Contexto adicional:
- Problemas similares anteriores: {len(problem.related_problems)}
- Nivel de confianza: {problem.confidence.value}

Por favor proponer soluciones específicas, incluyendo:
1. Acciones inmediatas requeridas
2. Recursos necesarios
3. Tiempo estimado de implementación
4. Medidas de seguimiento"""

    def _estimate_solution_time(self, description: str) -> int:
        """Estimate time needed for solution implementation."""
        # Simple estimation based on keywords
        if any(word in description.lower() for word in ['inmediato', 'urgente', 'emergency']):
            return 60  # 1 hour
        elif any(word in description.lower() for word in ['implementar', 'instalar', 'construct']):
            return 480  # 8 hours
        elif any(word in description.lower() for word in ['monitorear', 'seguimiento', 'evaluar']):
            return 240  # 4 hours
        return 120  # 2 hours default

    def _deduplicate_solutions(
        self,
        solutions: List[ProposedSolution]
    ) -> List[ProposedSolution]:
        """Remove duplicate solutions."""
        unique_solutions = []
        descriptions = set()
        
        for solution in solutions:
            desc_lower = solution.description.lower()
            if desc_lower not in descriptions:
                descriptions.add(desc_lower)
                unique_solutions.append(solution)
        
        return unique_solutions

    def _prioritize_solutions(
        self,
        solutions: List[ProposedSolution],
        problem: ConstructionProblem
    ) -> None:
        """Prioritize solutions based on problem severity and solution characteristics."""
        for solution in solutions:
            priority_score = 0  # Lower score means higher priority
            
            # Base priority based on problem severity
            if problem.severity == Severity.CRITICAL:
                priority_score -= 5
            elif problem.severity == Severity.HIGH:
                priority_score -= 3
            elif problem.severity == Severity.MEDIUM:
                priority_score -= 1
                
            # Adjust based on solution source and effectiveness
            if solution.metadata.get('source') == 'historical':
                if solution.historical_success_rate:
                    # Higher success rate reduces priority score
                    priority_score -= min(3, int(solution.historical_success_rate))
                if solution.effectiveness_rating and solution.effectiveness_rating >= 4:
                    priority_score -= 2
                    
            # Adjust based on implementation characteristics
            if solution.estimated_time:
                if solution.estimated_time <= 60:  # Quick solutions (1 hour or less)
                    priority_score -= 2
                elif solution.estimated_time <= 240:  # Medium duration (4 hours or less)
                    priority_score -= 1
                    
            # Adjust based on required resources
            if solution.required_resources:
                if len(solution.required_resources) <= 2:  # Minimal resources needed
                    priority_score -= 1
                else:  # More complex resource requirements
                    priority_score += 1
                    
            # Adjust based on prerequisites
            if solution.prerequisites:
                priority_score += len(solution.prerequisites)
                
            # Convert score to priority level (1-5)
            # Lower scores become higher priority (1)
            normalized_score = max(1, min(5, int((priority_score + 8) / 3)))
            solution.priority = normalized_score
            
            # Update solution metadata with prioritization details
            solution.metadata.update({
                'prioritization': {
                    'base_score': priority_score,
                    'severity_impact': problem.severity.value,
                    'implementation_speed': 'fast' if solution.estimated_time and solution.estimated_time <= 60 else 'normal',
                    'resource_complexity': 'low' if not solution.required_resources or len(solution.required_resources) <= 2 else 'high',
                    'historical_performance': solution.historical_success_rate if solution.historical_success_rate else None,
                    'timestamp': datetime.now().isoformat()
                }
            })