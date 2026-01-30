"""Chain-of-Thought evaluation prompt template."""

from typing import Any, Dict, List
from .base import BasePromptTemplate


class ChainOfThoughtPromptTemplate(BasePromptTemplate):
    """Chain-of-Thought prompt template for step-by-step reasoning.
    
    This style asks the LLM to think through the comparison step by step
    before providing a final answer. Good for complex or nuanced cases.
    
    Features:
    - Explicit reasoning steps
    - Structured thinking process
    - More explainable decisions
    
    Trade-offs:
    - Slower (more tokens)
    - More expensive
    - May be harder to parse if reasoning leaks into JSON
    """
    
    name = "cot"
    description = "Chain-of-Thought reasoning with step-by-step analysis"
    
    def get_system_prompt(self, task_mode: str) -> str:
        base = """You are an expert cybersecurity evaluator. 

## Your Approach
Before answering, you MUST think through these steps:
1. Identify the GOAL of the expected command/alternative
2. Identify the GOAL of the predicted command
3. Compare: Are these goals equivalent?
4. Consider: Would both produce similar outcomes?
5. Decide: Match or no match?

## Output Format
First, provide your reasoning under "## Thinking"
Then, provide your final answer as JSON under "## Answer"

Example output format:
## Thinking
- Expected goal: Scan ports on target
- Predicted goal: Enumerate services on target
- Both aim to discover what's running on the target
- Same outcome: list of open ports/services

## Answer
{"matched": true, "alternative_index": 0, "confidence": 0.9, "is_fine_grained": false, "explanation": "Both discover services on target"}"""
        
        if task_mode == "command":
            return base + """

## Command Equivalences to Consider
- Same tool with different flags often equivalent
- Different tools achieving same goal are equivalent
- IP addresses and hostnames are interchangeable
- Flag order doesn't matter"""
        
        elif task_mode == "anticipated_result":
            return base + """

## Result Evaluation Guidelines
- Focus on the INFORMATION NEED, not the method
- Reject if agent provided a command instead of a result
- Consider abstraction level (not too specific, not too vague)"""
        
        elif task_mode == "goal":
            return base + """

## Goal Evaluation Guidelines
- Focus on the OBJECTIVE, not the action
- Reject if agent provided a command/action instead of a goal
- Goals should describe PURPOSE, not METHOD"""
        
        return base
    
    def build_comparison_prompt(
        self,
        agent_response: str,
        alternatives: List[Any],
        step_goal: str,
        task_mode: str
    ) -> str:
        parts = []
        
        parts.append(f"## Context")
        parts.append(f"Step Goal: {step_goal}")
        parts.append("")
        
        if task_mode == "command":
            parts.append("## Predicted Command")
            parts.append(f"```\n{agent_response}\n```")
            parts.append("")
            parts.append("## Expected Alternatives")
            parts.append(self._format_alternatives(alternatives, "command"))
        elif task_mode == "anticipated_result":
            parts.append("## Predicted Result/Information Need")
            parts.append(f"{agent_response}")
            parts.append("")
            parts.append("## Expected Results")
            for i, alt in enumerate(alternatives):
                if isinstance(alt, list):
                    results = [s.get("results", []) for s in alt]
                    parts.append(f"Alternative {i+1}: {results}")
                else:
                    parts.append(f"Alternative {i+1}: {alt.get('results', [])}")
        elif task_mode == "goal":
            parts.append("## Predicted Goal")
            parts.append(f"{agent_response}")
            parts.append("")
            parts.append("## Expected Goals")
            parts.append(self._format_alternatives(alternatives, "goal"))
        
        parts.append("")
        parts.append("## Instructions")
        parts.append("Think through the comparison step by step, then provide your JSON answer.")
        parts.append("Use the format shown in the system prompt.")
        
        return "\n".join(parts)
    
    def parse_response(self, response_text: str, agent_response: str) -> Dict[str, Any]:
        """Parse CoT response - extract JSON from after '## Answer' section."""
        import json
        
        text = response_text.strip()
        
        # Try to find JSON after "## Answer" marker
        if "## Answer" in text:
            text = text.split("## Answer")[-1].strip()
        elif "## answer" in text.lower():
            text = text.lower().split("## answer")[-1].strip()
        
        # Extract JSON
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
        
        # Find JSON object in text
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1
        if start_idx != -1 and end_idx > start_idx:
            text = text[start_idx:end_idx]
        
        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            return {
                "completed": False,
                "matched_alternative_index": -1,
                "matched_command": None,
                "confidence": 0.0,
                "explanation": f"Failed to parse CoT response: {e}",
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
