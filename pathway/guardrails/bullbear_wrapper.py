"""
Bull-Bear Guardrails Wrapper
Integrated into main guardrails system for Bull/Bear debate checks.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from nemoguardrails import RailsConfig, LLMRails
    NEMO_GUARDRAILS_AVAILABLE = True
except ImportError:
    NEMO_GUARDRAILS_AVAILABLE = False
    print("⚠️  NeMo Guardrails not installed. Running without NeMo guardrails.")


class BullBearGuardrailsWrapper:
    """
    Wrapper to apply NeMo Guardrails to Bull/Bear LLM calls.
    Unified wrapper for both Bull and Bear researchers.
    """
    
    def __init__(self, researcher_type: str = "bull", config_path: Optional[str] = None):
        """
        Initialize guardrails wrapper.
        
        Args:
            researcher_type: "bull" or "bear" - determines logging prefix
            config_path: Optional path to NeMo config directory
        """
        self.researcher_type = researcher_type.lower()
        self.enabled = NEMO_GUARDRAILS_AVAILABLE and os.getenv("BULLBEAR_GUARDRAILS_ENABLED", "true").lower() == "true"
        self.rails = None
        
        if not self.enabled:
            print(f"⚠️  [{self.researcher_type.upper()}] Guardrails disabled or NeMo not available")
            return
            
        try:
            if config_path is None:
                # Use nemo_config from guardrails folder
                config_path = str(Path(__file__).parent / "nemo_config")
            
            config = RailsConfig.from_path(config_path)
            self.rails = LLMRails(config)
            
            # Register custom actions
            from .nemo_config import actions
            self.rails.register_action(actions.check_disclaimer)
            self.rails.register_action(actions.check_toxicity)
            self.rails.register_action(actions.check_financial_safety)
            
            print(f"✅ [GUARDRAILS] NeMo Guardrails initialized for {self.researcher_type.capitalize()} Researcher")
            
        except Exception as e:
            print(f"⚠️  [GUARDRAILS] Failed to initialize {self.researcher_type} guardrails: {e}")
            self.enabled = False
    
    async def check_input(self, user_message: str) -> Dict[str, Any]:
        """
        Check user input through guardrails.
        
        Returns:
            Dict with 'allowed' (bool) and 'message' (str if blocked)
        """
        if not self.enabled or not self.rails:
            return {"allowed": True, "message": user_message}
        
        try:
            response = await self.rails.generate_async(
                messages=[{"role": "user", "content": user_message}]
            )
            
            if response and "content" in response:
                return {"allowed": True, "message": response["content"]}
            
            return {"allowed": True, "message": user_message}
            
        except Exception as e:
            print(f"⚠️  [{self.researcher_type.upper()} GUARDRAILS] Input check error: {e}")
            return {"allowed": True, "message": user_message}
    
    async def check_output(self, bot_message: str) -> Dict[str, Any]:
        """
        Check bot output through guardrails.
        
        Returns:
            Dict with 'allowed' (bool) and 'message' (str, possibly modified)
        """
        if not self.enabled or not self.rails:
            return {"allowed": True, "message": bot_message}
        
        try:
            response = await self.rails.generate_async(
                messages=[{"role": "assistant", "content": bot_message}]
            )
            
            if response and "content" in response:
                return {"allowed": True, "message": response["content"]}
            
            return {"allowed": True, "message": bot_message}
            
        except Exception as e:
            print(f"⚠️  [{self.researcher_type.upper()} GUARDRAILS] Output check error: {e}")
            return {"allowed": True, "message": bot_message}
    
    def check_input_sync(self, user_message: str) -> Dict[str, Any]:
        """Synchronous version of check_input."""
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, 
                        self.check_input(user_message)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.check_input(user_message))
        except RuntimeError:
            return asyncio.run(self.check_input(user_message))
    
    def check_output_sync(self, bot_message: str) -> Dict[str, Any]:
        """Synchronous version of check_output."""
        import asyncio
        
        # Default fallback - always return original message if anything fails
        default_result = {"allowed": True, "message": bot_message}
        
        try:
            result = asyncio.run(self.check_output(bot_message))
            
            # Ensure result has 'message' key, fallback to original
            if result and isinstance(result, dict):
                if "message" not in result or not result.get("message"):
                    result["message"] = bot_message
                return result
            return default_result
            
        except Exception as e:
            print(f"⚠️  [{self.researcher_type.upper()} GUARDRAILS] Sync check error: {e}")
            return default_result


# Singleton instances for Bull and Bear
_bull_guardrails: Optional[BullBearGuardrailsWrapper] = None
_bear_guardrails: Optional[BullBearGuardrailsWrapper] = None


def get_bull_guardrails() -> BullBearGuardrailsWrapper:
    """Get or create the Bull guardrails singleton."""
    global _bull_guardrails
    
    if _bull_guardrails is None:
        _bull_guardrails = BullBearGuardrailsWrapper(researcher_type="bull")
    
    return _bull_guardrails


def get_bear_guardrails() -> BullBearGuardrailsWrapper:
    """Get or create the Bear guardrails singleton."""
    global _bear_guardrails
    
    if _bear_guardrails is None:
        _bear_guardrails = BullBearGuardrailsWrapper(researcher_type="bear")
    
    return _bear_guardrails
