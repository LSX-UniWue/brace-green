"""Evaluation prompt templates for the step evaluator.

This module provides different prompt styles for semantic command matching.
Each style can be selected at runtime via the --prompt-style CLI option.
"""

from .base import BasePromptTemplate
from .default import DefaultPromptTemplate
from .chain_of_thought import ChainOfThoughtPromptTemplate
from .rubric import RubricPromptTemplate
from .minimal import MinimalPromptTemplate

# Registry of available prompt styles
PROMPT_STYLES = {
    "default": DefaultPromptTemplate,
    "cot": ChainOfThoughtPromptTemplate,
    "rubric": RubricPromptTemplate,
    "minimal": MinimalPromptTemplate,
}

def get_prompt_template(style: str = "default") -> BasePromptTemplate:
    """Get a prompt template by style name.
    
    Args:
        style: Name of the prompt style ("default", "cot", "rubric", "minimal")
        
    Returns:
        Instance of the requested prompt template
        
    Raises:
        ValueError: If style is not recognized
    """
    if style not in PROMPT_STYLES:
        available = ", ".join(PROMPT_STYLES.keys())
        raise ValueError(f"Unknown prompt style '{style}'. Available: {available}")
    
    return PROMPT_STYLES[style]()


def list_prompt_styles() -> list[str]:
    """List available prompt style names."""
    return list(PROMPT_STYLES.keys())


__all__ = [
    "BasePromptTemplate",
    "DefaultPromptTemplate", 
    "ChainOfThoughtPromptTemplate",
    "RubricPromptTemplate",
    "MinimalPromptTemplate",
    "PROMPT_STYLES",
    "get_prompt_template",
    "list_prompt_styles",
]
