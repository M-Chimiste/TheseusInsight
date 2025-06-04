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
from typing import List, Dict, Union, Optional, Iterator
from pydantic import BaseModel
import numpy as np

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
    def invoke(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        *,
        streaming: bool = False,
        **kwargs
    ) -> Union[str, Iterator[str]]:
        """Generate a response.

        If *streaming* is True and the underlying provider offers token
        streaming, return an iterator that yields those tokens.  Providers
        that do not support streaming MUST silently ignore the flag and
        return the full response string as before."""
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
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str, *,
               streaming: bool = False,
               model_name: Optional[str] = None, num_ctx: Optional[int] = None,
               schema: Optional[BaseModel] = None) -> Union[str, Iterator[str]]:
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

        if streaming:
            if schema:
                stream = self.client.chat(
                    model=model_name or self.model_name,
                    messages=full_messages,
                    format=schema.model_json_schema(),
                    options=options,
                    stream=True
                )
            else:
                stream = self.client.chat(
                    model=model_name or self.model_name,
                    messages=full_messages,
                    options=options,
                    stream=True
                )

            def _gen() -> Iterator[str]:
                for chunk in stream:
                    content = chunk["message"]["content"]
                    if content:
                        yield content
            return _gen()
        else:
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
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str, *,
               streaming: bool = False, model_name: Optional[str] = None) -> Union[str, Iterator[str]]:
        """
        Generate a response using the Anthropic model.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys
            system_prompt (str): System prompt to prepend to the messages
            model_name (Optional[str]): Override the default model name if provided

        Returns:
            str: The generated response text
        """
        if streaming:
            stream = self.client.messages.create(
                model=model_name or self.model_name,
                system=system_prompt,
                messages=messages,
                max_tokens=self.max_new_tokens,
                temperature=self.temperature,
                stream=True,
            )

            def _gen() -> Iterator[str]:
                for event in stream:
                    if getattr(event, "type", None) == "content_block_delta":
                        delta = event.delta.get("text", "")
                        if delta:
                            yield delta
            return _gen()
        else:
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
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str, *,
               streaming: bool = False, model_name: Optional[str] = None) -> Union[str, Iterator[str]]:
        """
        Generate a response using the OpenAI model.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys
            system_prompt (str): System prompt to prepend to the messages

        Returns:
            str: The generated response text
        """
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        if streaming:
            stream = self.client.chat.completions.create(
                model=model_name or self.model_name,
                messages=full_messages,
                max_tokens=self.max_new_tokens,
                temperature=self.temperature,
                stream=True,
            )

            def _gen() -> Iterator[str]:
                for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
            return _gen()
        else:
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
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str, *,
               streaming: bool = False, model_name: Optional[str] = None) -> Union[str, Iterator[str]]:
        gemini_messages = [{"role": "user", "parts": [system_prompt]}]
        for message in messages:
            role = "model" if message["role"] == "assistant" else "user"
            gemini_messages.append({"role": role, "parts": [message["content"]]})

        if streaming:
            model = self.client.GenerativeModel(model_name=model_name or self.model_name)
            stream = model.generate_content(
                gemini_messages,
                safety_settings=self.safety,
                generation_config=self.client.types.GenerationConfig(
                    max_output_tokens=self.max_new_tokens,
                    temperature=self.temperature
                ),
                stream=True
            )

            def _gen() -> Iterator[str]:
                for chunk in stream:
                    text = getattr(chunk, "text", None)
                    if text:
                        yield text
            return _gen()
        else:
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
                 remote_code: bool = True,
                 device: Optional[str] = None):
        import torch
        self.remote_code = remote_code
        if not device:
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self.device = device
        super().__init__(model_name)

    def _get_provider(self) -> str:
        return "sentence-transformer"

    def _load_model(self):
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(self.model_name, trust_remote_code=self.remote_code, device=self.device)
    
    def invoke(self,
               text: Union[str, List[str]],
               *,
               streaming: bool = False,
               to_list: bool = False,
               normalize: bool = False,
               batch_size: Optional[int] = None,
               show_progress_bar: Optional[bool] = None,
               convert_to_numpy: bool = True,
               convert_to_tensor: bool = False,
               **kwargs) -> Union[List, object]:
        """
        Generate embeddings for text(s) using SentenceTransformer.
        
        Args:
            text: String or list of strings to embed
            to_list: Whether to convert embeddings to Python lists
            normalize: Whether to normalize the embeddings  
            batch_size: Batch size for processing. If None, uses model default
            show_progress_bar: Whether to show progress bar for large batches
            convert_to_numpy: Whether to convert to numpy arrays (default: True)
            convert_to_tensor: Whether to convert to PyTorch tensors
            **kwargs: Additional arguments passed to SentenceTransformer.encode()
            
        Returns:
            Embeddings as numpy array(s), tensor(s), or list(s) depending on parameters
        """
        _ = streaming
        is_string_input = isinstance(text, str)
        if is_string_input:
            text = [text]
        
        # Build encode parameters
        encode_params = {
            'sentences': text,
            'normalize_embeddings': normalize,
            'convert_to_numpy': convert_to_numpy,
            'convert_to_tensor': convert_to_tensor,
            **kwargs
        }
        
        # Add optional parameters if provided
        if batch_size is not None:
            encode_params['batch_size'] = batch_size
        if show_progress_bar is not None:
            encode_params['show_progress_bar'] = show_progress_bar
            
        embeddings = self.client.encode(**encode_params)
        
        if to_list and convert_to_numpy:
            embeddings = [embedding.tolist() for embedding in embeddings]
        
        # Only return single embedding if input was a single string, not a list
        if is_string_input and len(embeddings) == 1:
            return embeddings[0]
        return embeddings


class OllamaEmbedInference(InferenceModel):
    """Ollama Embedding Inference for Ollama's embedding API."""
    def __init__(self,
                 model_name: str = "nomic-embed-text",
                 url: str = None):
        """
        Initialize Ollama embedding inference.
        
        Args:
            model_name (str): Name of the embedding model (e.g., 'nomic-embed-text')
            url (str): Ollama server URL, defaults to environment variable or localhost
        """
        self.url = url or os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
        super().__init__(model_name)

    def _get_provider(self) -> str:
        return "ollama-embed"

    def _load_model(self):
        from ollama import Client
        return Client(host=self.url)
    
    def invoke(self, text: Union[str, List[str]], *,
               streaming: bool = False,
               to_list: bool = False,
               normalize: bool = False, model_name: Optional[str] = None, **kwargs) -> Union[List, object]:
        """
        Generate embeddings using the Ollama embedding model.

        Args:
            text (Union[str, List[str]]): Text or list of texts to embed
            to_list (bool): Whether to convert embeddings to Python lists
            normalize (bool): Whether to normalize the embeddings (Note: normalization handled by model)
            model_name (Optional[str]): Override the default model name if provided
            **kwargs: Additional arguments

        Returns:
            Union[List, object]: The generated embeddings
        """
        _ = streaming
        if isinstance(text, str):
            text = [text]
        
        # Generate embeddings for each text
        embeddings = []
        for single_text in text:
            response = self.client.embeddings(
                model=model_name or self.model_name,
                prompt=single_text
            )
            embeddings.append(response['embedding'])
        
        # Convert to numpy arrays for consistency with SentenceTransformer
        embeddings = [np.array(embedding) for embedding in embeddings]
        
        # Handle normalization if requested
        if normalize:
            embeddings = [embedding / np.linalg.norm(embedding) for embedding in embeddings]
        
        # Convert to list format if requested
        if to_list:
            embeddings = [embedding.tolist() for embedding in embeddings]
        
        # Return single embedding if only one text was provided
        if len(embeddings) == 1:
            return embeddings[0]
        return embeddings


class LlamacppInference(InferenceModel):
    """Llamacpp Inference for local GGUF models using llama-cpp-python."""
    def __init__(self,
                 model_name: str,
                 max_new_tokens: int = 4096,
                 temperature: float = 0.1,
                 num_ctx: int = 131072,
                 n_gpu_layers: int = -1,
                 verbose: bool = False,
                 **kwargs):
        """
        Initialize Llamacpp inference.
        
        Args:
            model_name (str): Path to the GGUF model file
            max_new_tokens (int): Maximum number of new tokens to generate
            temperature (float): Sampling temperature
            num_ctx (int): Context window size
            n_gpu_layers (int): Number of layers to offload to GPU (-1 for all)
            verbose (bool): Whether to enable verbose logging
            **kwargs: Additional arguments to pass to Llama constructor
        """
        self.num_ctx = num_ctx
        self.n_gpu_layers = n_gpu_layers
        self.verbose = verbose
        self.model_kwargs = kwargs
        super().__init__(model_name, max_new_tokens, temperature)

    def _get_provider(self) -> str:
        return "llamacpp"

    def _load_model(self):
        from llama_cpp import Llama
        return Llama(
            model_path=self.model_name,
            n_ctx=self.num_ctx,
            n_gpu_layers=self.n_gpu_layers,
            verbose=self.verbose,
            **self.model_kwargs
        )
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str, *,
               streaming: bool = False,
               max_tokens: Optional[int] = None,
               temperature: Optional[float] = None,
               schema: Optional[BaseModel] = None,
               **kwargs) -> Union[str, Iterator[str]]:
        """
        Generate a response using the Llamacpp model.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys
            system_prompt (str): System prompt to prepend to the messages
            max_tokens (Optional[int]): Override the default max_new_tokens if provided
            temperature (Optional[float]): Override the default temperature if provided
            schema (Optional[BaseModel]): Pydantic model for structured output

        Returns:
            str: The generated response text
        """
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        # Prepare generation parameters
        generation_params = {
            "messages": full_messages,
            "max_tokens": max_tokens or self.max_new_tokens,
            "temperature": temperature or self.temperature,
            **kwargs
        }
        
        # Add schema support for structured output
        if schema:
            generation_params["response_format"] = {
                "type": "json_object",
                "schema": schema.model_json_schema()
            }
        
        if streaming:
            stream = self.client.create_chat_completion(**generation_params, stream=True)

            def _gen() -> Iterator[str]:
                for chunk in stream:
                    delta = chunk["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
            return _gen()
        else:
            response = self.client.create_chat_completion(**generation_params)
            return response['choices'][0]['message']['content']


class LLMModelFactory:
    """
    Factory class for creating inference model instances.
    """
    _models = {
        'ollama': OllamaInference,
        'anthropic': AnthropicInference,
        'openai': OpenAIInference,
        'gemini': GeminiInference,
        'sentence-transformer': SentenceTransformerInference,
        'ollama-embed': OllamaEmbedInference,
        'llamacpp': LlamacppInference
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
        
        
