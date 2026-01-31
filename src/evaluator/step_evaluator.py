"""Step evaluator for semantic comparison of agent predictions."""

import os
import json
from typing import Dict, Any, List, Optional
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_community.chat_models import ChatLiteLLM
from langchain_core.messages import HumanMessage, SystemMessage

# Import caching utilities
from .cache import init_cache, is_cache_enabled

# Import prompt templates
from .prompts import get_prompt_template, list_prompt_styles, BasePromptTemplate


class StepEvaluator(Runnable):
    """Evaluates agent predictions against expected step alternatives.
    
    Uses LLM-based semantic comparison with LangChain for proper trace context propagation.
    Supports multiple prompt styles via the prompts/ module.
    """
    
    def __init__(
        self,
        model: str = "gpt-5.1",
        max_tokens: int = 2000,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        evaluation_protocol: str = "match_alternatives",
        task_mode: str = "command",
        prompt_style: str = "default"
    ):
        """Initialize the step evaluator.
        
        Args:
            model: Model name for litellm
            max_tokens: Maximum tokens in response
            api_key: API key (falls back to environment variable)
            base_url: Base URL for API (falls back to environment variable)
            evaluation_protocol: "match_alternatives" or "single_path"
            task_mode: "command", "anticipated_result", or "goal"
            prompt_style: Prompt template style ("default", "cot", "rubric", "minimal")
        """
        self.model = model
        self.max_tokens = max_tokens
        self.evaluation_protocol = evaluation_protocol
        self.task_mode = task_mode
        self.prompt_style = prompt_style
        
        # Load prompt template
        self.prompt_template: BasePromptTemplate = get_prompt_template(prompt_style)
        
        # Set up API credentials
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        
        if self.api_key:
            os.environ["OPENAI_API_KEY"] = self.api_key
        if self.base_url:
            os.environ["OPENAI_BASE_URL"] = self.base_url
        
        # Initialize LLM caching (no-op if already initialized)
        init_cache(verbose=not is_cache_enabled())
        
        # Get system prompt from template
        self.system_prompt = self.prompt_template.get_system_prompt(self.task_mode)
        
        # Create LangChain ChatLiteLLM instance for proper context propagation
        self.llm = ChatLiteLLM(
            model=self.model,
            temperature=0.0,  # Deterministic for evaluation
            max_tokens=self.max_tokens,
            api_key=self.api_key,
            api_base=self.base_url,
        )
    
    def invoke(self, input: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        """LangChain Runnable interface - delegates to evaluate_prediction.
        
        Args:
            input: Dictionary with agent_response, step_alternatives, and step_goal
            config: Optional LangChain config for context propagation
            
        Returns:
            Evaluation result dictionary
        """
        return self.evaluate_prediction(
            input["agent_response"],
            input["step_alternatives"],
            input["step_goal"]
        )
    
    def evaluate_prediction(
        self,
        agent_response: str,
        step_alternatives: List[Any],
        step_goal: str
    ) -> Dict[str, Any]:
        """Evaluate an agent's prediction against step alternatives.
        
        Args:
            agent_response: The command predicted by the agent
            step_alternatives: List of alternative commands/steps from "or" clause
            step_goal: The goal this step is trying to achieve
            
        Returns:
            Dictionary with:
                - completed: Whether a match was found
                - matched_alternative_index: Index of matched alternative (-1 if none)
                - matched_command: The predicted command that matched
                - confidence: Confidence score (0.0-1.0)
                - explanation: Reason for the evaluation
                - agent_unknown: True if agent explicitly said "I don't know"
        """
        if not agent_response or not agent_response.strip():
            return {
                "completed": False,
                "matched_alternative_index": -1,
                "matched_command": None,
                "confidence": 0.0,
                "explanation": "Empty agent response",
                "is_fine_grained": False
            }
        
        # Check for exact "I don't know" response - no need to evaluate or reiterate
        if agent_response.strip() == "I don't know":
            return {
                "completed": False,
                "matched_alternative_index": -1,
                "matched_command": None,
                "confidence": 0.0,
                "explanation": "Agent explicitly indicated lack of knowledge",
                "is_fine_grained": False,
                "agent_unknown": True
            }
        
        # Protocol determines which alternatives to check
        # Task mode determines what field to compare
        if self.evaluation_protocol == "single_path":
            # Find gold standard alternative
            alternatives_to_check = self._get_gold_alternative(step_alternatives)
        else:  # match_alternatives
            alternatives_to_check = step_alternatives
        
        # Now compare based on task mode
        if self.task_mode == "command":
            return self._compare_commands(agent_response, alternatives_to_check, step_goal)
        elif self.task_mode == "anticipated_result":
            return self._compare_results(agent_response, alternatives_to_check, step_goal)
        elif self.task_mode == "goal":
            return self._compare_goals(agent_response, alternatives_to_check, step_goal)
        else:
            # Fallback
            return self._compare_commands(agent_response, alternatives_to_check, step_goal)
    
    def _get_gold_alternative(self, step_alternatives: List[Any]) -> List[Any]:
        """Extract gold standard alternative from alternatives list.
        
        In the step data structure, each step with alternatives has exactly one marked
        as gold: true and zero or more marked as gold: false. This method finds and
        returns only the gold standard alternative.
        
        Args:
            step_alternatives: List of alternatives from a step's "or" array
            
        Returns:
            List containing only the gold alternative. Falls back to all alternatives
            if no gold marker is found (indicates malformed data).
            
        Examples:
            - Atomic alternatives: [{"goal": "...", "gold": true}, {"goal": "...", "gold": false}]
              Returns: [{"goal": "...", "gold": true}]
            
            - Multi-step alternative: [[{"goal": "...", "gold": true}, {...}], [{"goal": "...", "gold": false}]]
              Returns: [[{"goal": "...", "gold": true}, {...}]]
        """
        for alt in step_alternatives:
            if isinstance(alt, list):
                # Multi-step alternative - check if first step is marked as gold
                if alt and alt[0].get("gold", False):
                    return [alt]
            else:
                # Atomic alternative - check if marked as gold
                if alt.get("gold", False):
                    return [alt]
        
        # If no gold found, log warning and return all (fallback for malformed data)
        # In well-formed step data, there should always be exactly one gold: true
        print(f"⚠ Warning: No gold alternative found in step alternatives. Using all alternatives as fallback.")
        return step_alternatives
    
    def _compare_commands(
        self,
        agent_response: str,
        alternatives: List[Any],
        step_goal: str
    ) -> Dict[str, Any]:
        """Compare agent's predicted command against alternative commands.
        
        Args:
            agent_response: The command predicted by the agent
            alternatives: List of alternatives to check (filtered by protocol)
            step_goal: The goal this step is trying to achieve
            
        Returns:
            Evaluation result dictionary
        """
        prompt = self.prompt_template.build_comparison_prompt(
            agent_response, alternatives, step_goal, "command"
        )
        return self._evaluate_with_llm(prompt, agent_response)
    
    def _compare_results(
        self,
        agent_response: str,
        alternatives: List[Any],
        step_goal: str
    ) -> Dict[str, Any]:
        """Compare agent's anticipated result against alternative results.
        
        Args:
            agent_response: The anticipated result predicted by the agent
            alternatives: List of alternatives to check (filtered by protocol)
            step_goal: The goal this step is trying to achieve
            
        Returns:
            Evaluation result dictionary
        """
        prompt = self.prompt_template.build_comparison_prompt(
            agent_response, alternatives, step_goal, "anticipated_result"
        )
        return self._evaluate_with_llm(prompt, agent_response)
    
    def _compare_goals(
        self,
        agent_response: str,
        alternatives: List[Any],
        step_goal: str
    ) -> Dict[str, Any]:
        """Compare agent's predicted goal against alternative goals.
        
        Args:
            agent_response: The goal predicted by the agent
            alternatives: List of alternatives to check (filtered by protocol)
            step_goal: The goal this step is trying to achieve
            
        Returns:
            Evaluation result dictionary
        """
        prompt = self.prompt_template.build_comparison_prompt(
            agent_response, alternatives, step_goal, "goal"
        )
        return self._evaluate_with_llm(prompt, agent_response)
    
    def _evaluate_with_llm(self, prompt: str, agent_response: str) -> Dict[str, Any]:
        """Common LLM evaluation logic.
        
        Args:
            prompt: The evaluation prompt
            agent_response: The agent's response being evaluated
            
        Returns:
            Evaluation result dictionary
        """
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            response_text = response.content
            
            if not response_text:
                raise RuntimeError("Empty response from LLM API")
                
        except Exception as e:
            raise RuntimeError(f"Failed to call LLM API for evaluation: {e}")
        
        # Parse the evaluation result using prompt template's parser
        return self.prompt_template.parse_response(response_text, agent_response)
    
    def check_goal_reached(
        self,
        evaluation_result: Dict[str, Any],
        step_data: Any,
        iteration_count: int,
        max_iterations: int,
        accumulated_commands: Optional[str] = None,
        include_goal: str = "always"
    ) -> Dict[str, Any]:
        """Determine if the step's goal has been reached or ruled out.
        
        Args:
            evaluation_result: Result from evaluate_prediction
            step_data: The step data from steps_enriched.json
            iteration_count: Current iteration count
            max_iterations: Maximum allowed iterations
            accumulated_commands: Concatenated commands if evaluating a sequence
            include_goal: When goals are included ("always", "first", or "never")
            
        Returns:
            Dictionary with:
                - goal_reached: Whether goal is confirmed or ruled out
                - needs_more_predictions: Whether to continue prompting
                - reason: Explanation of the decision
                - is_fine_grained: Whether the command/result is too fine-grained
        """
        # If agent explicitly said "I don't know", stop without reiterating
        if evaluation_result.get("agent_unknown", False):
            return {
                "goal_reached": True,  # Consider it "ruled out"
                "needs_more_predictions": False,
                "reason": "Agent indicated lack of knowledge - goal ruled out",
                "is_fine_grained": False
            }
        
        # If we found a match, goal is reached
        if evaluation_result["completed"]:
            # Adapt message based on protocol and task mode
            matched_idx = evaluation_result.get('matched_alternative_index', -1)
            
            # Base message on task mode
            if self.task_mode == "command":
                base_msg = "Command"
            elif self.task_mode == "anticipated_result":
                base_msg = "Anticipated result"
            elif self.task_mode == "goal":
                base_msg = "Predicted goal"
            else:
                base_msg = "Prediction"
            
            # Adapt based on protocol
            if self.evaluation_protocol == "single_path":
                reason = f"{base_msg} is valid - goal achieved"
            else:  # match_alternatives
                reason = f"{base_msg} matched alternative {matched_idx} - goal achieved"
            
            return {
                "goal_reached": True,
                "needs_more_predictions": False,
                "reason": reason,
                "is_fine_grained": False
            }
        
        # If we've hit max iterations, stop
        if iteration_count >= max_iterations:
            return {
                "goal_reached": True,  # Consider it "ruled out"
                "needs_more_predictions": False,
                "reason": f"Max iterations ({max_iterations}) reached - goal ruled out",
                "is_fine_grained": False
            }
        
        # Check if prediction is too fine-grained
        # Use explicit flag from LLM evaluation (all task modes now return this)
        if "is_fine_grained" in evaluation_result and evaluation_result.get("is_fine_grained"):
            is_fine_grained = True
            
            # Adapt message based on task mode
            if self.task_mode == "command":
                reason = f"Command is too fine-grained (confidence: {evaluation_result['confidence']:.2f}). Continue proposing commands to complete the goal."
            elif self.task_mode == "anticipated_result":
                reason = f"Result is too fine-grained (confidence: {evaluation_result['confidence']:.2f}). Continue building toward step-level result."
            elif self.task_mode == "goal":
                reason = f"Goal is too vague/specific (confidence: {evaluation_result['confidence']:.2f}). Refine goal statement."
            else:
                reason = f"Prediction is too fine-grained (confidence: {evaluation_result['confidence']:.2f}). Continue to complete the step."
        elif not evaluation_result["completed"] and iteration_count < max_iterations - 1:
            # Fallback heuristic (if LLM didn't provide fine-grained flag)
            is_fine_grained = True
            if self.task_mode == "command":
                reason = f"Command is too fine-grained (confidence: {evaluation_result['confidence']:.2f}). Continue proposing commands to complete the goal."
            else:
                reason = f"Prediction incomplete (confidence: {evaluation_result['confidence']:.2f}). Continue refining."
        else:
            is_fine_grained = False
            reason = None
        
        if is_fine_grained:
            return {
                "goal_reached": False,
                "needs_more_predictions": True,
                "reason": reason,
                "is_fine_grained": True
            }
        
        # No match yet, continue trying
        if iteration_count < max_iterations:
            return {
                "goal_reached": False,
                "needs_more_predictions": True,
                "reason": f"No match yet, iteration {iteration_count}/{max_iterations}",
                "is_fine_grained": False
            }
        
        # Shouldn't reach here, but handle gracefully
        return {
            "goal_reached": True,
            "needs_more_predictions": False,
            "reason": "Iteration limit reached",
            "is_fine_grained": False
        }
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'StepEvaluator':
        """Create a StepEvaluator from a configuration dictionary.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Configured StepEvaluator instance
        """
        return cls(
            model=config.get("model", "gpt-5.1"),
            max_tokens=config.get("max_tokens", 2000),
            api_key=config.get("api_key"),
            base_url=config.get("base_url")
        )
