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
        Invokes the Ollama model to generate a response based on the provided messages and system prompt.

        This method orchestrates the interaction with the Ollama model, handling both streaming and non-streaming modes.
        It prepares the input messages, including the system prompt, and configures the model invocation options.
        Depending on the streaming flag, it either returns the full response string or an iterator yielding tokens.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, each containing a 'role' and 'content' for the message.
            system_prompt (str): The system prompt to be included in the input.
            streaming (bool, optional): If True, returns an iterator over the response tokens. Defaults to False.
            model_name (Optional[str], optional): The name of the model to use. Defaults to the model name set in the constructor.
            num_ctx (Optional[int], optional): The number of context tokens to use. Defaults to the num_ctx set in the constructor.
            schema (Optional[BaseModel], optional): The schema to use for formatting the response. Defaults to None.

        Returns:
            Union[str, Iterator[str]]: The response from the model, either as a full string or an iterator over tokens.
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
        Generates a response using the Anthropic model.

        This method orchestrates the interaction with the Anthropic API to generate a response based on the provided messages and system prompt. It can operate in either streaming or non-streaming mode, depending on the value of the `streaming` parameter. In streaming mode, it returns an iterator over the generated text chunks. In non-streaming mode, it returns the complete generated response as a string.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, each containing 'role' and 'content' keys, representing the conversation history.
            system_prompt (str): The system prompt to prepend to the conversation history.
            model_name (Optional[str]): The name of the model to use for generation. If not provided, the default model is used.

        Returns:
            Union[str, Iterator[str]]: The generated response text or an iterator over the generated text chunks if streaming is enabled.
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
               streaming: bool = False, model_name: Optional[str] = None,
               schema: Optional[BaseModel] = None, **kwargs) -> Union[str, Iterator[str]]:
        """
        Invokes the OpenAI model to generate a response based on the provided messages and system prompt.

        This method orchestrates the interaction with the OpenAI API to generate a response. It can operate in either streaming or non-streaming mode, depending on the value of the `streaming` parameter. In streaming mode, it returns an iterator over the generated text chunks. In non-streaming mode, it returns the complete generated response as a string.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, each containing 'role' and 'content' keys, representing the conversation history.
            system_prompt (str): The system prompt to prepend to the conversation history.
            streaming (bool, optional): If True, the method returns an iterator over the generated text chunks. Defaults to False.
            model_name (Optional[str], optional): The name of the model to use for generation. If not provided, the default model is used.
            schema (Optional[BaseModel]): A Pydantic schema for structured‑output via
                OpenAI function‑calling. If provided, the response is parsed against
                this schema and returned as a Pydantic object (or JSON string on
                fallback).
            **kwargs: Additional keyword arguments to pass to the model.

        Returns:
            Union[str, BaseModel | Iterator[str]]: Parsed object (or JSON string) when
            `schema` is supplied; otherwise the plain text response, or an iterator in
            streaming mode.
        """
        # If the caller requests streaming + structured output, fall back to
        # non‑streaming and warn—OpenAI’s function‑calling isn’t supported with
        # streaming responses yet.
        if streaming and schema is not None:
            import warnings
            warnings.warn(
                "OpenAI structured‑output (function calling) is not supported "
                "with `streaming=True`; falling back to non‑streaming."
            )
            streaming = False

        full_messages = [{"role": "system", "content": system_prompt}] + messages
        if streaming:
            stream = self.client.chat.completions.create(
                model=model_name or self.model_name,
                messages=full_messages,
                max_tokens=self.max_new_tokens,
                temperature=self.temperature,
                stream=True,
                **kwargs
            )

            def _gen() -> Iterator[str]:
                for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
            return _gen()
        else:
            # -------- Non‑streaming --------
            if schema is not None:
                # ---- Structured output via function‑calling ----
                import json, openai
                tool_spec = openai.pydantic_function_tool(schema)
                response = self.client.chat.completions.create(
                    model=model_name or self.model_name,
                    messages=full_messages,
                    tools=[tool_spec],
                    tool_choice="auto",
                    max_tokens=self.max_new_tokens,
                    temperature=self.temperature,
                    **kwargs
                )
                tool_calls = response.choices[0].message.tool_calls
                if tool_calls:
                    args_json = tool_calls[0].function.arguments
                    try:
                        parsed = schema.model_validate_json(args_json)
                        return parsed
                    except Exception:
                        # Validation failed – return raw JSON string
                        return args_json
                # If no tool call was produced, fall back to message content
                return response.choices[0].message.content
            else:
                # ---- Plain text completion ----
                response = self.client.chat.completions.create(
                    model=model_name or self.model_name,
                    messages=full_messages,
                    max_tokens=self.max_new_tokens,
                    temperature=self.temperature,
                    **kwargs
                )
                return response.choices[0].message.content


class GeminiInference(InferenceModel):
    """Gemini Inference for Google's Gemini API."""
    def __init__(self, model_name: str = "gemini-1.5-flash",
                 max_new_tokens: int = 4096,
                 temperature: float = 0.1):
        """
        Initializes the GeminiInference model with specified parameters.

        Args:
            model_name (str, optional): The name of the Gemini model to use for inference. Defaults to "gemini-1.5-flash".
            max_new_tokens (int, optional): The maximum number of new tokens to generate. Defaults to 4096.
            temperature (float, optional): The temperature parameter for the model. Defaults to 0.1.

        Raises:
            ValueError: If the model_name is not recognized or if max_new_tokens or temperature are invalid.
        """
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
        
        # Configure API key
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        
        return genai
    
    def invoke(self,
               messages: List[Dict[str, str]],
               system_prompt: str,
               *,
               streaming: bool = False,
               model_name: Optional[str] = None,
               schema: Optional[BaseModel] = None,
               **kwargs) -> Union[str, Iterator[str]]:
        """
        Initiates the Gemini Inference process for generating text or structured output based on input messages and a system prompt.

        This method orchestrates the Gemini Inference process, which involves preparing input messages, setting up the model configuration, and invoking the model to generate text or structured output. It supports both streaming and non-streaming modes of operation.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, where each dictionary contains a 'role' and a 'content'. The 'role' specifies the type of message (e.g., user or model), and the 'content' is the actual message.
            system_prompt (str): A string that serves as the initial prompt for the model to generate text.
            streaming (bool, optional): A boolean indicating whether to use streaming mode. Defaults to False.
            model_name (Optional[str], optional): The name of the model to use for inference. Defaults to None, which uses the default model name set during initialization.
            schema (Optional[BaseModel]): If provided, the response will be returned as structured JSON
                matching this Pydantic schema (Gemini structured‑output mode).
            **kwargs: Additional keyword arguments that can be passed to the model for configuration.

        Returns:
            Union[str, list | BaseModel | Iterator[str]]: Parsed objects (or JSON string) when
            `schema` is supplied; otherwise the generated text, or an iterator in streaming mode.
        """
        # If the caller asks for streaming *and* structured output in the same request,
        # Gemini cannot fulfil that combination yet.  Instead of raising, degrade
        # gracefully by issuing a warning and switching to non‑streaming mode so the
        # user still gets a structured JSON reply.
        if streaming and schema is not None:
            import warnings
            warnings.warn(
                "Gemini structured-output mode is not supported with `streaming=True`; "
                "falling back to non-streaming inference."
            )
            streaming = False

        # Build Gemini messages in the same style as before
        gemini_messages = [{"role": "user", "parts": [system_prompt]}]
        for message in messages:
            role = "model" if message["role"] == "assistant" else "user"
            gemini_messages.append({"role": role, "parts": [message["content"]]})

        # Common kwargs for the request
        request_kwargs = {
            "safety_settings": self.safety,
            "generation_config": self.client.types.GenerationConfig(
                max_output_tokens=self.max_new_tokens,
                temperature=self.temperature
            )
        }

        # If the caller requested structured output add the new fields
        if schema is not None:
            request_kwargs["response_mime_type"] = "application/json"
            request_kwargs["response_schema"] = schema   # e.g. list[MySchema]

        # --- STREAMING -----------------------------------------------------
        if streaming:
            model = self.client.GenerativeModel(model_name=model_name or self.model_name)
            stream = model.generate_content(
                gemini_messages,
                stream=True,
                request_options={'timeout': 300},
                **request_kwargs
            )

            def _gen() -> Iterator[str]:
                for chunk in stream:
                    text = getattr(chunk, "text", None)
                    if text:
                        yield text

            return _gen()

        # --- NON‑STREAMING -------------------------------------------------
        model = self.client.GenerativeModel(model_name=model_name or self.model_name)
        response = model.generate_content(gemini_messages, **request_kwargs)

        if schema is not None:
            # Prefer parsed objects if available, otherwise fall back to raw JSON
            return getattr(response, "parsed", None) or response.text

        return response.text


class SentenceTransformerInference(InferenceModel):
    def __init__(self,
                 model_name: str = "Alibaba-NLP/gte-large-en-v1.5",
                 remote_code: bool = True,
                 device: Optional[str] = None):
        """
        Initializes a SentenceTransformerInference model instance.

        This constructor sets up the SentenceTransformer model for inference tasks. It allows for customization of the model name, remote code execution, and device selection.

        Args:
            model_name (str, optional): The name of the SentenceTransformer model to use. Defaults to "Alibaba-NLP/gte-large-en-v1.5".
            remote_code (bool, optional): Whether to allow remote code execution. Defaults to True.
            device (Optional[str], optional): The device to use for model computations. Defaults to None, which automatically selects the best available device.

        Raises:
            ValueError: If an invalid device is specified.
        """
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
        Invokes the SentenceTransformer model to generate embeddings for the given text(s).

        This method processes the input text(s) and returns their corresponding embeddings. It supports
        various options for customization, such as streaming, converting to list, normalization, and more.

        Args:
            text (Union[str, List[str]]): The input text or list of texts to generate embeddings for.
            streaming (bool, optional): If True, processes the input text in a streaming fashion. Defaults to False.
            to_list (bool, optional): If True, converts the output embeddings to a list. Defaults to False.
            normalize (bool, optional): If True, normalizes the embeddings. Defaults to False.
            batch_size (Optional[int], optional): The batch size to use for encoding. Defaults to None.
            show_progress_bar (Optional[bool], optional): If True, shows a progress bar during encoding. Defaults to None.
            convert_to_numpy (bool, optional): If True, converts the embeddings to numpy arrays. Defaults to True.
            convert_to_tensor (bool, optional): If True, converts the embeddings to tensors. Defaults to False.
            **kwargs: Additional keyword arguments to pass to the encoding function.

        Returns:
            Union[List, object]: The generated embeddings. If `to_list` is True, returns a list of embeddings. Otherwise, returns the embeddings as is.
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
        Initializes the Ollama Embedding Inference model.

        Args:
            model_name (str, optional): The name of the model to use for embedding generation. Defaults to "nomic-embed-text".
            url (str, optional): The URL of the Ollama API. If None, uses the OLLAMA_URL environment variable. Defaults to None.
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
        Invokes the Ollama embedding model to generate embeddings for the given text(s).

        This method takes in a single string or a list of strings as input, and returns the corresponding embeddings. It supports various options such as streaming, converting to list, normalizing, and specifying a custom model name.

        Args:
            text (Union[str, List[str]]): The input text(s) for which embeddings are to be generated.
            streaming (bool, optional): If True, the method will process the input text(s) in a streaming fashion. Defaults to False.
            to_list (bool, optional): If True, the method will convert the embeddings to a list format. Defaults to False.
            normalize (bool, optional): If True, the method will normalize the embeddings. Defaults to False.
            model_name (Optional[str], optional): The name of the model to use for embedding generation. Defaults to the model name specified during initialization.

        Returns:
            Union[List, object]: The generated embeddings. If to_list is True, returns a list of embeddings; otherwise, returns a single embedding if the input was a single string, or a list of embeddings if the input was a list of strings.
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
        Initializes the LlamacppInference model with the specified parameters.

        Args:
            model_name (str): The name of the model to use for inference.
            max_new_tokens (int, optional): The maximum number of new tokens to generate. Defaults to 4096.
            temperature (float, optional): The temperature parameter for sampling. Defaults to 0.1.
            num_ctx (int, optional): The number of context tokens to use. Defaults to 131072.
            n_gpu_layers (int, optional): The number of GPU layers to use. Defaults to -1.
            verbose (bool, optional): Whether to enable verbose mode. Defaults to False.
            **kwargs: Additional keyword arguments to pass to the model.

        Raises:
            ValueError: If the model_name is not specified.
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
        Initiates the inference process for generating text based on input messages and a system prompt.

        This method orchestrates the text generation process by preparing the input messages, system prompt, and additional parameters for the model. It supports both streaming and non-streaming modes of operation. In streaming mode, it yields chunks of generated text as they become available. In non-streaming mode, it returns the complete generated text.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, where each dictionary contains a 'role' and 'content'. The 'role' specifies the type of message (e.g., 'system', 'user'), and 'content' is the text of the message.
            system_prompt (str): A string that provides context or instructions for the model to generate text.
            streaming (bool, optional): If True, the method operates in streaming mode, yielding chunks of generated text. Defaults to False.
            max_tokens (Optional[int], optional): The maximum number of tokens to generate. Defaults to the model's default max_new_tokens.
            temperature (Optional[float], optional): The temperature parameter for sampling. Defaults to the model's default temperature.
            schema (Optional[BaseModel], optional): A Pydantic model schema for structured output. Defaults to None.
            **kwargs: Additional keyword arguments to pass to the model for generation.

        Returns:
            Union[str, Iterator[str]]: In non-streaming mode, returns the complete generated text as a string. In streaming mode, returns an iterator that yields chunks of generated text as strings.
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


class CustomOAIInference(InferenceModel):
    """Custom OpenAI-compatible Inference."""
    def __init__(self,
                 model_name: str,
                 max_new_tokens: int = 4096,
                 temperature: float = 0.1,
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None):
        """
        Initializes a CustomOAIInference instance with the specified model name, maximum new tokens, temperature, base URL, and API key.

        Args:
            model_name (str): The name of the model to use for inference.
            max_new_tokens (int, optional): The maximum number of tokens to generate in a single response. Defaults to 4096.
            temperature (float, optional): The temperature parameter for sampling. Defaults to 0.1.
            base_url (Optional[str], optional): The base URL for the custom OAI-compatible server. Defaults to None.
            api_key (Optional[str], optional): The API key for the custom OAI-compatible server. Defaults to None.

        Raises:
            ValueError: If the base_url or CUSTOM_OAI_BASE_URL environment variable is not set.
        """
        self.base_url = base_url or os.environ.get("CUSTOM_OAI_BASE_URL")
        self.api_key = api_key or os.environ.get("CUSTOM_OAI_API_KEY")
        if not self.base_url:
            raise ValueError("CUSTOM_OAI_BASE_URL environment variable or base_url parameter must be set for CustomOAIInference.")
        # API key can be optional for some self-hosted OAI compatible servers
        super().__init__(model_name, max_new_tokens, temperature)

    def _get_provider(self) -> str:
        return "custom-oai"

    def _load_model(self):
        from openai import OpenAI
        return OpenAI(base_url=self.base_url, api_key=self.api_key)
    
    def invoke(self, 
               messages: List[Dict[str, str]], 
               system_prompt: str, *,
               streaming: bool = False, 
               model_name: Optional[str] = None,
               **kwargs) -> Union[str, Iterator[str]]:
        """
        Invokes the model to generate text based on the provided messages and system prompt.

        This method orchestrates the interaction with the model, preparing the input data and
        handling the response. It supports both streaming and non-streaming modes, allowing for
        flexible usage depending on the application's requirements.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, where each dictionary contains
                'role' and 'content' keys. 'role' specifies the role of the message (e.g., 'user' or
                'system'), and 'content' is the actual message content.
            system_prompt (str): The system prompt to be used as the initial message.
            streaming (bool, optional): If True, the method will return an iterator over the
                generated text, allowing for streaming of the output. Defaults to False.
            model_name (Optional[str], optional): The name of the model to use for generation. If
                not provided, the default model name set during initialization will be used.
            **kwargs: Additional keyword arguments to be passed to the model's generation method.

        Returns:
            Union[str, Iterator[str]]: The generated text or an iterator over the generated text,
                depending on the streaming mode.
        """
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        if streaming:
            stream = self.client.chat.completions.create(
                model=model_name or self.model_name,
                messages=full_messages,
                max_tokens=self.max_new_tokens,
                temperature=self.temperature,
                stream=True,
                **kwargs
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


class LLMModelFactory:
    """
    Factory class for creating inference model instances.
    """
    _models = {
        'ollama': OllamaInference,
        'anthropic': AnthropicInference,
        'openai': OpenAIInference,
        'gemini': GeminiInference,
        'custom-oai': CustomOAIInference,
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
        
        
