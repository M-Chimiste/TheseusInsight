# Copyright 2023 M Chimiste

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Union, Optional
from pydantic import BaseModel


class InferenceModel(ABC):
    """
    Abstract base class for all inference models.
    """
    def __init__(self,
                 model_name: str,
                 max_new_tokens: int = 4096,
                 temperature: float = 0.1):
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.provider = self._get_provider()
        self.client = self._load_model()

    @abstractmethod
    def _load_model(self):
        """Load and return the model client."""
        pass

    @abstractmethod
    def _get_provider(self) -> str:
        """Return the provider name as a string."""
        pass

    @abstractmethod
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str, **kwargs) -> str:
        """Generate a response based on the given messages and system prompt."""
        pass


class OllamaInference(InferenceModel):
    """Ollama Inference for Ollama's API."""
    def __init__(self,
                 model_name: str = "hermes3",
                 max_new_tokens: int = 4096,
                 temperature: float = 0.1,
                 url: str = None,
                 num_ctx: int = 131072):
        self.url = url or os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
        self.num_ctx = num_ctx
        super().__init__(model_name, max_new_tokens, temperature)

    def _get_provider(self) -> str:
        return "ollama"

    def _load_model(self):
        from ollama import Client
        return Client(host=self.url)
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str, 
               model_name: Optional[str] = None, num_ctx: Optional[int] = None, schema: Optional[BaseModel] = None) -> str:
        """
        Generate a response using the Ollama model.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys
            system_prompt (str): System prompt to prepend to the messages
            model_name (Optional[str]): Override the default model name if provided
            num_ctx (Optional[int]): Override the default context window size if provided

        Returns:
            str: The generated response text
        """
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        options = {
            "num_predict": self.max_new_tokens,
            "temperature": self.temperature,
            "num_ctx": self.num_ctx
        }

        if schema:
            response = self.client.chat(
                model=model_name or self.model_name,
                messages=full_messages,
                format=schema.model_json_schema(),
                options=options
            )
        else:
            response = self.client.chat(
                model=model_name or self.model_name,
                messages=full_messages,
                options=options
            )
        return response['message']['content']


class AnthropicInference(InferenceModel):
    """Anthropic Inference for Anthropic's API."""
    def _get_provider(self) -> str:
        return "anthropic"

    def _load_model(self):
        from anthropic import Anthropic
        return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str, 
               model_name: Optional[str] = None) -> str:
        """
        Generate a response using the Anthropic model.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys
            system_prompt (str): System prompt to prepend to the messages
            model_name (Optional[str]): Override the default model name if provided

        Returns:
            str: The generated response text
        """
        response = self.client.messages.create(
            model=model_name or self.model_name,
            system=system_prompt,
            messages=messages,
            max_tokens=self.max_new_tokens,
            temperature=self.temperature,
        )
        return response.content[0].text


class OpenAIInference(InferenceModel):
    """OpenAI Inference for OpenAI's API."""
    def _get_provider(self) -> str:
        return "openai"

    def _load_model(self):
        from openai import OpenAI
        return OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str, model_name: Optional[str] = None) -> str:
        """
        Generate a response using the OpenAI model.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys
            system_prompt (str): System prompt to prepend to the messages

        Returns:
            str: The generated response text
        """
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        response = self.client.chat.completions.create(
            model=model_name or self.model_name,
            messages=full_messages,
            max_tokens=self.max_new_tokens,
            temperature=self.temperature,
        )
        return response.choices[0].message.content


class GeminiInference(InferenceModel):
    """Gemini Inference for Google's Gemini API."""
    def __init__(self, model_name: str = "gemini-1.5-flash",
                 max_new_tokens: int = 4096,
                 temperature: float = 0.1):
        self.safety = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        super().__init__(model_name, max_new_tokens, temperature)

    def _get_provider(self) -> str:
        return "gemini"

    def _load_model(self):
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        return genai
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str, model_name: Optional[str] = None) -> str:
        gemini_messages = [{"role": "user", "parts": [system_prompt]}]
        for message in messages:
            role = "model" if message["role"] == "assistant" else "user"
            gemini_messages.append({"role": role, "parts": [message["content"]]})

        model = self.client.GenerativeModel(model_name=model_name or self.model_name)
        response = model.generate_content(
            gemini_messages,
            safety_settings=self.safety,
            generation_config=self.client.types.GenerationConfig(
                max_output_tokens=self.max_new_tokens,
                temperature=self.temperature
            )
        )
        return response.text


class SentenceTransformerInference(InferenceModel):
    def __init__(self,
                 model_name: str = "Alibaba-NLP/gte-large-en-v1.5",
                 remote_code: bool = True):
        self.remote_code = remote_code
        super().__init__(model_name)

    def _get_provider(self) -> str:
        return "sentence-transformer"

    def _load_model(self):
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(self.model_name, trust_remote_code=self.remote_code)
    
    def invoke(self, text: Union[str, List[str]], to_list: bool = False, 
               normalize: bool = False, **kwargs) -> Union[List, object]:
        if isinstance(text, str):
            text = [text]
        embeddings = self.client.encode(text, normalize_embeddings=normalize)
        if to_list:
            embeddings = [embedding.tolist() for embedding in embeddings]
        if len(embeddings) == 1:
            return embeddings[0]
        return embeddings


class LLMModelFactory:
    """
    Factory class for creating inference model instances.
    """
    _models = {
        'ollama': OllamaInference,
        'anthropic': AnthropicInference,
        'openai': OpenAIInference,
        'gemini': GeminiInference,
        'sentence-transformer': SentenceTransformerInference
    }

    @classmethod
    def create_model(cls, model_type: str, **kwargs) -> InferenceModel:
        """
        Create and return an instance of the specified model type.
        
        Args:
            model_type: The type of model to create ('ollama', 'anthropic', etc.)
            **kwargs: Additional arguments to pass to the model constructor
            
        Returns:
            An instance of the specified model type
        """
        model_class = cls._models.get(model_type.lower())
        if not model_class:
            raise ValueError(f"Unknown model type: {model_type}")
        return model_class(**kwargs)
        
        
