"""LLM utilities for Phase 2"""

from openai import OpenAI
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def create_openai_client(api_key: str) -> OpenAI:
    """
    Create OpenAI client
    
    Args:
        api_key: OpenAI API key
    
    Returns:
        Configured OpenAI client
    """
    
    client = OpenAI(api_key=api_key)
    logger.info("OpenAI client created")
    
    return client


def chat_completion(
    client: OpenAI,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    response_format: Optional[Dict[str, str]] = None
) -> str:
    """
    Generate chat completion
    
    Args:
        client: OpenAI client
        model: Model name (e.g., 'gpt-4-turbo-preview')
        messages: List of message dicts with 'role' and 'content'
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response
        response_format: Optional response format (e.g., {"type": "json_object"})
    
    Returns:
        Assistant response content
    """
    
    try:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        response = client.chat.completions.create(**kwargs)
        
        content = response.choices[0].message.content
        
        logger.debug(f"Generated completion: {len(content)} chars")
        
        return content
        
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise


def generate_with_system_prompt(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000
) -> str:
    """
    Generate completion with system and user prompts
    
    Args:
        client: OpenAI client
        model: Model name
        system_prompt: System instruction
        user_prompt: User query
        temperature: Sampling temperature
        max_tokens: Maximum tokens
    
    Returns:
        Assistant response
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    return chat_completion(
        client=client,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )


def extract_json_from_response(response: str) -> str:
    """
    Extract JSON from LLM response that may contain markdown
    
    Args:
        response: Raw LLM response
    
    Returns:
        Extracted JSON string
    """
    
    # Try to extract from markdown code blocks
    if "```json" in response:
        json_str = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        json_str = response.split("```")[1].split("```")[0].strip()
    else:
        json_str = response.strip()
    
    return json_str
