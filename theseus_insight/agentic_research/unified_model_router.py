import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pydantic import BaseModel

from ..data_model.data_handling import PaperDatabase
from ..inference.llm import LLMModelFactory
from ..api.models import ModelConfig


@dataclass
class ModelInvocation:
    """Record of a model invocation for trace logging."""
    timestamp: str
    node_name: str
    model_name: str
    model_type: str
    task_description: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    duration_ms: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None


class UnifiedModelRouter:
    """
    Unified model router that handles both configuration management and runtime execution.
    Replaces both AgentModelRouter and GraphModelRouter with a simpler, more focused design.
    """
    
    def __init__(self, db: PaperDatabase):
        self.db = db
        self.model_cache = {}
        self.trace_log: List[ModelInvocation] = []
        
        # Default model mappings for LangGraph nodes
        self.default_models = {
            "generate_query": "hermes3",
            "reflection": "hermes3", 
            "finalize_answer": "hermes3",
            "judge_papers": "hermes3",
            "outline": "hermes3"
        }
    
    def get_model(self, node_name: str) -> 'UnifiedLLMWrapper':
        """Get a model instance for a specific graph node."""
        if node_name not in self.model_cache:
            model_name = self._get_model_name_for_node(node_name)
            self.model_cache[node_name] = UnifiedLLMWrapper(model_name, self)
        return self.model_cache[node_name]
    
    def _get_model_name_for_node(self, node_name: str) -> str:
        """Get the configured model name for a specific node."""
        # Try to get from LangGraph configuration first
        config_json = self.db.get_setting("research_agent_langgraph_config")
        if config_json:
            try:
                config_data = json.loads(config_json)
                
                # Map node names to config fields
                node_model_mapping = {
                    "generate_query": "query_generator_model",
                    "reflection": "reflection_model",
                    "finalize_answer": "answer_model",
                    "judge_papers": "judge_model",
                    "outline": "reasoning_model"  # Use reasoning model for outline by default
                }
                
                config_key = node_model_mapping.get(node_name)
                if config_key and config_data.get(config_key) and config_data[config_key] is not None:
                    # Check if the specific model config has a model_name
                    specific_model = config_data[config_key]
                    if isinstance(specific_model, dict) and specific_model.get("model_name"):
                        return specific_model["model_name"]
                
                # Fall back to reasoning model if specific model not configured
                if config_data.get("reasoning_model") and isinstance(config_data["reasoning_model"], dict):
                    reasoning_model_name = config_data["reasoning_model"].get("model_name")
                    if reasoning_model_name:
                        return reasoning_model_name
                    
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Try legacy node-specific settings
        setting_key = f"research_agent_{node_name}_model"
        setting_value = self.db.get_setting(setting_key)
        if setting_value:
            return setting_value
            
        # Fall back to defaults
        return self.default_models.get(node_name, "hermes3")
    
    def update_model_for_node(self, node_name: str, model_name: str):
        """Update the model configuration for a specific node."""
        setting_key = f"research_agent_{node_name}_model"
        self.db.set_setting(setting_key, model_name)
        
        # Clear cache so it gets reloaded
        if node_name in self.model_cache:
            del self.model_cache[node_name]
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current research agent configuration."""
        # Try to get LangGraph configuration first
        config_json = self.db.get_setting("research_agent_langgraph_config")
        if config_json:
            try:
                return json.loads(config_json)
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Return default configuration
        return {
            "reasoning_model": {
                "model_name": "gemini-2.0-flash",
                "model_type": "gemini",
                "max_new_tokens": 4096,
                "temperature": 0.1,
                "num_ctx": 131072
            },
            "query_generator_model": None,  # Falls back to reasoning_model if not specified
            "reflection_model": None,       # Falls back to reasoning_model if not specified  
            "answer_model": None,           # Falls back to reasoning_model if not specified
            "judge_model": None,            # Falls back to reasoning_model if not specified
            "max_research_loops": 10,
            "initial_search_query_count": 3,
            "local_search_limit": 10,
            "external_search_limit": 5,
            "max_context_tokens": 30000,
            "search_config": {
                "semantic_weight": 0.6,
                "keyword_weight": 0.4,
                "similarity_threshold": 0.3,
                "enable_pdf_download": True
            }
        }
    
    def save_configuration(self, config: Dict[str, Any]):
        """Save research agent configuration to database."""
        config_json = json.dumps(config, indent=2)
        self.db.set_setting("research_agent_langgraph_config", config_json)
        
        # Clear cache to force reload
        self.model_cache.clear()
    
    def _log_invocation(
        self,
        node_name: str,
        model_name: str,
        model_type: str,
        task_description: str = "",
        duration_ms: float = 0,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """Log a model invocation for trace recording."""
        invocation = ModelInvocation(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            node_name=node_name,
            model_name=model_name,
            model_type=model_type,
            task_description=task_description,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message
        )
        self.trace_log.append(invocation)
    
    def get_trace_log(self) -> List[Dict[str, Any]]:
        """Get the trace log as a list of dictionaries."""
        return [asdict(invocation) for invocation in self.trace_log]
    
    def clear_trace_log(self):
        """Clear the trace log."""
        self.trace_log.clear()


class UnifiedLLMWrapper:
    """
    Wrapper that adapts the existing LLM infrastructure for unified usage.
    Provides a simple interface for structured and unstructured generation.
    """
    
    def __init__(self, model_name: str, router: UnifiedModelRouter):
        self.model_name = model_name
        self.router = router
        self.model = self._create_model(model_name)
    
    def _create_model(self, model_name: str):
        """Create a model instance using the existing factory."""
        # Map to provider-specific model creation
        if model_name.startswith("gpt-") or model_name.startswith("o1-"):
            return LLMModelFactory.create_model("openai", model_name=model_name)
        elif model_name.startswith("claude-"):
            return LLMModelFactory.create_model("anthropic", model_name=model_name)
        elif model_name.startswith("gemini-"):
            return LLMModelFactory.create_model("gemini", model_name=model_name)
        else:
            # Default to Ollama for local models
            return LLMModelFactory.create_model("ollama", model_name=model_name)
    
    def invoke(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: str, 
        schema: Optional[BaseModel] = None,
        node_name: str = "unknown"
    ) -> Any:
        """
        Invoke the model with optional structured output.
        
        Args:
            messages: List of conversation messages
            system_prompt: System prompt for the model
            schema: Optional Pydantic schema for structured output
            node_name: Name of the LangGraph node for logging
            
        Returns:
            Model response (structured if schema provided, otherwise string)
        """
        start_time = time.time()
        
        try:
            if schema:
                # For structured output, we'll use the schema if supported
                if hasattr(self.model, 'invoke') and 'schema' in self.model.invoke.__code__.co_varnames:
                    response = self.model.invoke(
                        messages=messages,
                        system_prompt=system_prompt,
                        schema=schema
                    )
                    # Try to parse the response as JSON if it's a string
                    if isinstance(response, str):
                        try:
                            json_data = json.loads(response)
                            result = schema(**json_data)
                        except (json.JSONDecodeError, ValueError):
                            # If parsing fails, try to extract JSON from the response
                            import re
                            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                            if json_match:
                                json_data = json.loads(json_match.group(1))
                                result = schema(**json_data)
                            else:
                                # Fallback: try to parse the entire response
                                json_data = json.loads(response)
                                result = schema(**json_data)
                    else:
                        result = response
                else:
                    # Model doesn't support schema, so we'll request JSON format in the prompt
                    enhanced_prompt = (
                        f"{system_prompt}\n\n"
                        f"IMPORTANT: Return your response as valid JSON matching this schema:\n"
                        f"{schema.model_json_schema()}\n\n"
                        f"Your response must be parseable JSON."
                    )
                    response = self.model.invoke(
                        messages=messages,
                        system_prompt=enhanced_prompt
                    )
                    
                    # Parse the JSON response
                    if isinstance(response, str):
                        try:
                            # Try direct parsing first
                            json_data = json.loads(response)
                            result = schema(**json_data)
                        except (json.JSONDecodeError, ValueError):
                            # Try to extract JSON from markdown code blocks
                            import re
                            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                            if json_match:
                                json_data = json.loads(json_match.group(1))
                                result = schema(**json_data)
                            else:
                                raise ValueError(f"Could not parse JSON from model response: {response}")
            else:
                # Regular string response
                response = self.model.invoke(
                    messages=messages,
                    system_prompt=system_prompt
                )
                result = _ModelResponse(content=response)
            
            # Log successful invocation
            duration_ms = (time.time() - start_time) * 1000
            self.router._log_invocation(
                node_name=node_name,
                model_name=self.model_name,
                model_type=getattr(self.model, '_get_provider', lambda: 'unknown')(),
                task_description=f"Node: {node_name}, Schema: {schema.__name__ if schema else 'None'}",
                duration_ms=duration_ms,
                success=True
            )
            
            return result
                
        except Exception as e:
            # Log failed invocation
            duration_ms = (time.time() - start_time) * 1000
            self.router._log_invocation(
                node_name=node_name,
                model_name=self.model_name,
                model_type=getattr(self.model, '_get_provider', lambda: 'unknown')(),
                task_description=f"Node: {node_name}, Schema: {schema.__name__ if schema else 'None'}",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise RuntimeError(f"Model invocation failed for {self.model_name}: {str(e)}")


class _ModelResponse:
    """Simple response wrapper to mimic LangChain's AIMessage interface."""
    def __init__(self, content: str):
        self.content = content


def load_unified_router(db: PaperDatabase) -> UnifiedModelRouter:
    """Load and return a unified model router."""
    return UnifiedModelRouter(db) 