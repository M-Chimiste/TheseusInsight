import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from ..data_model.data_handling import PaperDatabase
from ..inference.llm import LLMModelFactory


class GraphModelRouter:
    """
    Model router for the LangGraph research agent that integrates with existing infrastructure.
    Maps LangGraph node roles to specific models and handles model invocation.
    """
    
    def __init__(self, db: PaperDatabase):
        self.db = db
        self.model_cache = {}
        self.default_models = {
            "generate_query": "hermes3",
            "reflection": "hermes3", 
            "finalize_answer": "hermes3"
        }
        
    def get_model(self, node_name: str) -> 'GraphLLMWrapper':
        """Get a model instance for a specific graph node."""
        if node_name not in self.model_cache:
            model_name = self._get_model_name_for_node(node_name)
            self.model_cache[node_name] = GraphLLMWrapper(model_name)
        return self.model_cache[node_name]
    
    def _get_model_name_for_node(self, node_name: str) -> str:
        """Get the configured model name for a specific node."""
        # Try to get from database settings first
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


class GraphLLMWrapper:
    """
    Wrapper that adapts the existing LLM infrastructure for LangGraph usage.
    Provides a simple interface for structured and unstructured generation.
    """
    
    def __init__(self, model_name: str):
        self.model_name = model_name
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
        schema: Optional[BaseModel] = None
    ) -> Any:
        """
        Invoke the model with optional structured output.
        
        Args:
            messages: List of conversation messages
            system_prompt: System prompt for the model
            schema: Optional Pydantic schema for structured output
            
        Returns:
            Model response (structured if schema provided, otherwise string)
        """
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
                            return schema(**json_data)
                        except (json.JSONDecodeError, ValueError):
                            # If parsing fails, try to extract JSON from the response
                            import re
                            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                            if json_match:
                                json_data = json.loads(json_match.group(1))
                                return schema(**json_data)
                            else:
                                # Fallback: try to parse the entire response
                                json_data = json.loads(response)
                                return schema(**json_data)
                    return response
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
                            return schema(**json_data)
                        except (json.JSONDecodeError, ValueError):
                            # Try to extract JSON from markdown code blocks
                            import re
                            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                            if json_match:
                                json_data = json.loads(json_match.group(1))
                                return schema(**json_data)
                            else:
                                raise ValueError(f"Could not parse JSON from model response: {response}")
            else:
                # Regular string response
                response = self.model.invoke(
                    messages=messages,
                    system_prompt=system_prompt
                )
                return _ModelResponse(content=response)
                
        except Exception as e:
            raise RuntimeError(f"Model invocation failed for {self.model_name}: {str(e)}")


class _ModelResponse:
    """Simple response wrapper to mimic LangChain's AIMessage interface."""
    def __init__(self, content: str):
        self.content = content


def load_model_router(db: PaperDatabase) -> GraphModelRouter:
    """Load and return a configured model router."""
    return GraphModelRouter(db) 