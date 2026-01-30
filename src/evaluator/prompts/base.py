"""Base class for evaluation prompt templates."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BasePromptTemplate(ABC):
    """Abstract base class for evaluation prompt templates.
    
    Each prompt template defines how to format prompts for semantic
    command comparison and how to parse the LLM's response.
    """
    
    # Human-readable name for this style
    name: str = "base"
    description: str = "Base prompt template"
    
    @abstractmethod
    def get_system_prompt(self, task_mode: str) -> str:
        """Get the system prompt for the evaluator.
        
        Args:
            task_mode: "command", "anticipated_result", or "goal"
            
        Returns:
            System prompt string
        """
        pass
    
    @abstractmethod
    def build_comparison_prompt(
        self,
        agent_response: str,
        alternatives: List[Any],
        step_goal: str,
        task_mode: str
    ) -> str:
        """Build the user prompt for comparing agent response to alternatives.
        
        Args:
            agent_response: The prediction from the agent
            alternatives: List of expected alternatives
            step_goal: The goal of the current step
            task_mode: "command", "anticipated_result", or "goal"
            
        Returns:
            Formatted user prompt string
        """
        pass
    
    def parse_response(self, response_text: str, agent_response: str) -> Dict[str, Any]:
        """Parse the LLM's evaluation response.
        
        Default implementation handles JSON extraction. Override for custom parsing.
        
        Args:
            response_text: Raw response from LLM
            agent_response: The original agent response being evaluated
            
        Returns:
            Parsed evaluation result dictionary
        """
        import json
        
        # Extract JSON from response (handle code blocks if present)
        text = response_text.strip()
        
        if text.startswith("```json"):
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif text.startswith("```"):
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        
        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            return {
                "completed": False,
                "matched_alternative_index": -1,
                "matched_command": None,
                "confidence": 0.0,
                "explanation": f"Failed to parse evaluation response: {e}",
                "is_fine_grained": False
            }
        
        return {
            "completed": result.get("matched", False),
            "matched_alternative_index": result.get("alternative_index", -1),
            "matched_command": agent_response if result.get("matched", False) else None,
            "confidence": result.get("confidence", 0.0),
            "explanation": result.get("explanation", ""),
            "is_fine_grained": result.get("is_fine_grained", False)
        }
    
    def _format_alternatives(self, alternatives: List[Any], field: str = "command") -> str:
        """Helper to format alternatives list for prompts.
        
        Args:
            alternatives: List of alternative steps
            field: Field to extract ("command", "goal", "results")
            
        Returns:
            Formatted string of alternatives
        """
        parts = []
        for i, alt in enumerate(alternatives):
            if isinstance(alt, list):
                parts.append(f"\nAlternative {i + 1} (multi-step sequence):")
                for j, sub_step in enumerate(alt):
                    value = sub_step.get(field, "")
                    goal = sub_step.get("goal", "")
                    parts.append(f"  Step {j + 1}: {value}")
                    if goal and field != "goal":
                        parts.append(f"    Goal: {goal}")
            else:
                value = alt.get(field, "")
                parts.append(f"\nAlternative {i + 1}: {value}")
                if field == "command":
                    results = alt.get("results", [])
                    if results:
                        parts.append(f"  Expected results: {', '.join(results)}")
        
        return "\n".join(parts)
