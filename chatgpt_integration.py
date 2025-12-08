#!/usr/bin/env python3
"""
GPT Integration Service for Video Script Generation

This module provides a dedicated GPT class for generating and formatting video scripts
based on categories and subcategories.

Usage:
    from chatgpt_integration import GPT
    
    gpt = GPT()
    script = await gpt.generateScript("Technology", "AI")
    formatted = gpt.formatForVideo(script)
    
    # Or use the routing function:
    from chatgpt_integration import createVideoFromCategory
    result = await createVideoFromCategory("Technology", "AI")
"""

import os
import sys
import json
import re
from typing import Optional, Dict, List, Tuple, Any

import requests

from log_utils import attach_log_streams, get_logger, log_call

# ------------------------------------------------------------
# OpenAI API Configuration
# ------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_API_URL = os.environ.get(
    "OPENAI_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
OPENAI_MAX_TOKENS = int(os.environ.get("OPENAI_MAX_TOKENS", "1000"))

attach_log_streams("chatgpt_integration")
logger = get_logger("gallardo.chatgpt_integration")


class GPT:
    """
    Dedicated GPT class for video script generation.
    
    Provides methods to generate scripts from categories/subcategories
    and format them for the video generator.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize GPT service.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model name (defaults to OPENAI_MODEL env var)
        """
        self.api_key = api_key or OPENAI_API_KEY
        self.model = model or OPENAI_MODEL
        self.api_url = OPENAI_API_URL
        self.max_tokens = OPENAI_MAX_TOKENS
        
        if not self.api_key:
            logger.warning(
                "[GPT] OPENAI_API_KEY not configured. GPT service may not work."
            )
    
    def _build_prompt_template(
        self, category: str, subcategory: str, additional_context: Optional[str] = None
    ) -> str:
        """
        Build comprehensive prompt template with category, subcategory, style rules,
        and output structure requirements.
        
        Args:
            category: The category value
            subcategory: The subcategory value
            additional_context: Optional additional context (e.g., Post Text)
            
        Returns:
            Complete prompt string
        """
        prompt = f"""You are a professional video script generator. Generate a 3 text overlay captions for our video based on the following information:

CATEGORY: {category or 'N/A'}
SUBCATEGORY: {subcategory or 'N/A'}
"""
        
        if additional_context:
            prompt += f"\nADDITIONAL CONTEXT: {additional_context}\n"
        
        prompt += """
STYLE RULES:
- Keep the script engaging and concise
- Use clear, conversational language
- Each text segment should be short enough to display on screen (max 50 words per segment)
- Create 3 text overlays that complement the video content
- Make the text attention-grabbing and relevant to the category/subcategory

OUTPUT STRUCTURE (JSON format):
You MUST return a valid JSON object with the following structure:
{
  "texts": [
    {
      "content": "Text content for overlay 1",
      "location": "top|top-left|top-right|center|center-left|center-right|bottom|bottom-left|bottom-right"
    },
    {
      "content": "Text content for overlay 2",
      "location": "bottom"
    }
  ],
  "metadata": {
    "category": "category name",
    "subcategory": "subcategory name",
    "generated_at": "timestamp if available"
  }
}

REQUIRED MARKERS:
- The response MUST be valid JSON
- The "texts" array MUST contain at least 1 text object
- Each text object MUST have "content" and "location" fields
- Location MUST be one of: top, top-left, top-right, center, center-left, center-right, bottom, bottom-left, bottom-right
- Content MUST be a non-empty string

IMPORTANT: Return ONLY the JSON object, no additional text or explanation before or after.
"""
        return prompt
    
    @log_call(logger)
    def generateScript(
        self, category: str, subcategory: str, *, additional_context: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a video script from category and subcategory.
        
        Args:
            category: The category value from the sheet
            subcategory: The subcategory value from the sheet
            additional_context: Optional additional context to include
            
        Returns:
            Raw script response dict if successful, None otherwise
        """
        if not category and not subcategory:
            logger.info("[GPT] Skipping: both category and subcategory are empty")
            return None
        
        if not self.api_key:
            logger.warning(
                "[GPT] OPENAI_API_KEY not configured. Skipping GPT script generation."
            )
            return None
        
        try:
            logger.info(
                "[GPT] Generating script for category='%s', subcategory='%s'",
                category,
                subcategory,
            )
            
            prompt = self._build_prompt_template(category, subcategory, additional_context)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            api_payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "max_tokens": self.max_tokens,
                "temperature": 0.7,  # Balance creativity and consistency
            }
            
            logger.debug(
                "[GPT] POST %s payload=%s",
                self.api_url,
                {**api_payload, "messages": [{"role": "user", "content": prompt[:200] + "..."}]},
            )
            
            response = requests.post(
                self.api_url,
                json=api_payload,
                headers=headers,
                timeout=30,
            )
            
            logger.info(
                "[GPT] Response status=%s",
                response.status_code,
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract the content from the response
            if "choices" in result and result["choices"]:
                choice = result["choices"][0]
                message = choice.get("message", {})
                content = message.get("content", "")
                
                if content:
                    logger.debug("[GPT] Received content: %s", content[:200])
                    return {
                        "raw_content": content,
                        "full_response": result,
                    }
            
            logger.warning("[GPT] No content in response")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error("[GPT] API request failed: %s", e)
            return None
        except Exception as e:
            logger.error("[GPT] Failed to generate script: %s", e, exc_info=True)
            return None
    
    def formatForVideo(self, script_response: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Format the GPT script response for the video generator.
        
        Extracts and validates the JSON structure, ensuring it matches
        what the video generator expects.
        
        Args:
            script_response: The response dict from generateScript()
            
        Returns:
            Formatted dict with 'texts' and 'text_locations' arrays, or None if invalid
        """
        if not script_response:
            logger.warning("[GPT] Cannot format: script_response is None")
            return None
        
        raw_content = script_response.get("raw_content", "")
        if not raw_content:
            logger.warning("[GPT] Cannot format: no raw_content in script_response")
            return None
        
        try:
            # Try to extract JSON from the response
            # Handle cases where response might have markdown code blocks
            content = raw_content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```"):
                # Extract content between ```json and ```
                json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                else:
                    # Try without json tag
                    content = re.sub(r"^```\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)
            
            # Parse JSON
            script_data = json.loads(content)
            
            # Validate structure
            if not isinstance(script_data, dict):
                logger.error("[GPT] Formatted script is not a dict")
                return None
            
            if "texts" not in script_data:
                logger.error("[GPT] Formatted script missing 'texts' field")
                return None
            
            texts_array = script_data["texts"]
            if not isinstance(texts_array, list) or len(texts_array) == 0:
                logger.error("[GPT] Formatted script 'texts' must be a non-empty array")
                return None
            
            # Extract texts and locations
            formatted_texts = []
            formatted_locations = []
            
            valid_locations = {
                "top", "top-left", "top-right",
                "center", "center-left", "center-right",
                "bottom", "bottom-left", "bottom-right"
            }
            
            for i, text_obj in enumerate(texts_array):
                if not isinstance(text_obj, dict):
                    logger.warning("[GPT] Text object %d is not a dict, skipping", i)
                    continue
                
                content = text_obj.get("content", "").strip()
                location = text_obj.get("location", "bottom").strip().lower()
                
                if not content:
                    logger.warning("[GPT] Text object %d has empty content, skipping", i)
                    continue
                
                # Validate location
                if location not in valid_locations:
                    logger.warning(
                        "[GPT] Text object %d has invalid location '%s', defaulting to 'bottom'",
                        i,
                        location,
                    )
                    location = "bottom"
                
                formatted_texts.append(content)
                formatted_locations.append(location)
            
            if len(formatted_texts) == 0:
                logger.error("[GPT] No valid text objects found after formatting")
                return None
            
            # Return format expected by video generator
            result = {
                "texts": formatted_texts,
                "text_locations": formatted_locations,
                "metadata": script_data.get("metadata", {}),
            }
            
            logger.info(
                "[GPT] Formatted script: %d text overlay(s)",
                len(formatted_texts),
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error("[GPT] Failed to parse JSON from script: %s", e)
            logger.debug("[GPT] Raw content was: %s", raw_content[:500])
            return None
        except Exception as e:
            logger.error("[GPT] Failed to format script: %s", e, exc_info=True)
            return None
    
    def validateScript(self, formatted_script: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """
        Quality-check layer: Validate the formatted script.
        
        Checks:
        - Output length (texts array not empty)
        - Required markers exist (texts, text_locations)
        - Content is usable (non-empty strings)
        
        Args:
            formatted_script: The formatted script from formatForVideo()
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not formatted_script:
            return False, "Script is None or empty"
        
        # Check required fields
        if "texts" not in formatted_script:
            return False, "Missing 'texts' field"
        
        if "text_locations" not in formatted_script:
            return False, "Missing 'text_locations' field"
        
        texts = formatted_script["texts"]
        locations = formatted_script["text_locations"]
        
        # Validate output length
        if not isinstance(texts, list) or len(texts) == 0:
            return False, "Texts array is empty"
        
        if not isinstance(locations, list) or len(locations) == 0:
            return False, "Text locations array is empty"
        
        if len(texts) != len(locations):
            return False, f"Texts ({len(texts)}) and locations ({len(locations)}) arrays have different lengths"
        
        # Ensure required markers exist and content is usable
        for i, (text, location) in enumerate(zip(texts, locations)):
            if not isinstance(text, str) or not text.strip():
                return False, f"Text at index {i} is empty or not a string"
            
            if not isinstance(location, str) or not location.strip():
                return False, f"Location at index {i} is empty or not a string"
            
            # Check text length (reasonable bounds)
            if len(text) > 500:
                return False, f"Text at index {i} is too long ({len(text)} chars, max 500)"
        
        return True, None


# Global GPT instance
_gpt_instance: Optional[GPT] = None


def get_gpt_instance() -> GPT:
    """Get or create the global GPT instance."""
    global _gpt_instance
    if _gpt_instance is None:
        _gpt_instance = GPT()
    return _gpt_instance


def createVideoFromCategory(
    category: str, subcategory: str, *, additional_context: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Route inputs: Generate script from category/subcategory and format for video.
    
    This is the main entry point that:
    1. Generates a script using GPT
    2. Formats it for the video generator
    3. Validates the output
    
    Args:
        category: The category value
        subcategory: The subcategory value
        additional_context: Optional additional context
        
    Returns:
        Validated and formatted script dict, or None if generation/validation fails
    """
    gpt = get_gpt_instance()
    
    # Step 1: Generate script
    script = gpt.generateScript(category, subcategory, additional_context=additional_context)
    if not script:
        logger.error("[createVideoFromCategory] Failed to generate script")
        return None
    
    # Step 2: Format for video
    formatted = gpt.formatForVideo(script)
    if not formatted:
        logger.error("[createVideoFromCategory] Failed to format script")
        return None
    
    # Step 3: Quality check
    is_valid, error_msg = gpt.validateScript(formatted)
    if not is_valid:
        logger.error(
            "[createVideoFromCategory] Script validation failed: %s",
            error_msg,
        )
        return None
    
    logger.info(
        "[createVideoFromCategory] Successfully generated and validated script with %d text overlay(s)",
        len(formatted["texts"]),
    )
    
    return formatted


# Backward compatibility: Keep the old function name
@log_call(logger)
def send_categories_to_chatgpt(
    category: str, subcategory: str, *, additional_context: Optional[str] = None
) -> Optional[dict]:
    """
    Legacy function for backward compatibility.
    
    This function now uses the new GPT class internally.
    """
    gpt = get_gpt_instance()
    return gpt.generateScript(category, subcategory, additional_context=additional_context)


if __name__ == "__main__":
    # Test function
    import argparse
    
    parser = argparse.ArgumentParser(description="Test GPT integration")
    parser.add_argument("--category", default="Technology", help="Category value")
    parser.add_argument("--subcategory", default="AI", help="Subcategory value")
    parser.add_argument("--context", default="", help="Additional context")
    
    args = parser.parse_args()
    
    print("Testing GPT Integration...")
    print(f"Category: {args.category}")
    print(f"Subcategory: {args.subcategory}")
    if args.context:
        print(f"Context: {args.context}")
    print()
    
    result = createVideoFromCategory(
        category=args.category,
        subcategory=args.subcategory,
        additional_context=args.context if args.context else None,
    )
    
    if result:
        print("✓ SUCCESS!")
        print(f"Generated {len(result['texts'])} text overlay(s):")
        for i, (text, location) in enumerate(
            zip(result["texts"], result["text_locations"]), 1
        ):
            print(f"  {i}. [{location}] {text[:50]}...")
    else:
        print("✗ FAILED")
        print("Check logs for details")
