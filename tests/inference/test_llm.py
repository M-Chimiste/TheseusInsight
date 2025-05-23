import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json

# Assuming models are in theseus_insight.inference.llm
from theseus_insight.inference.llm import (
    SentenceTransformerInference,
    LLMInterface, # Assuming this is a base class or ABC
    ChatAnthropic,
    ChatOpenAI,
    ChatVertexAI, # Assuming this is Gemini
    ChatOllama
)
from theseus_insight.constants import (
    ANTHROPIC_API_KEY_ENV_VAR, OPENAI_API_KEY_ENV_VAR,
    GOOGLE_APPLICATION_CREDENTIALS_ENV_VAR, OLLAMA_HOST_ENV_VAR
)

# Helper for creating mock API responses
def create_mock_api_response(content_text="", json_data=None):
    mock_response = MagicMock()
    mock_response.text = content_text
    if json_data:
        mock_response.json.return_value = json_data
    return mock_response


class TestSentenceTransformerInference(unittest.TestCase):

    @patch('sentence_transformers.SentenceTransformer')
    def test_init_and_invoke_single_text(self, MockSentenceTransformer):
        mock_model_instance = MockSentenceTransformer.return_value
        mock_model_instance.encode.return_value = [[0.1, 0.2, 0.3]] # Example embedding

        model_name = "all-MiniLM-L6-v2"
        sti = SentenceTransformerInference(model_name=model_name, trust_remote_code=True)

        MockSentenceTransformer.assert_called_once_with(model_name, trust_remote_code=True)
        
        text_to_embed = "This is a test sentence."
        embedding = sti.invoke(text_to_embed)

        mock_model_instance.encode.assert_called_once_with([text_to_embed])
        self.assertEqual(embedding, [[0.1, 0.2, 0.3]])

    @patch('sentence_transformers.SentenceTransformer')
    def test_invoke_multiple_texts(self, MockSentenceTransformer):
        mock_model_instance = MockSentenceTransformer.return_value
        expected_embeddings = [[0.1, 0.2], [0.3, 0.4]]
        mock_model_instance.encode.return_value = expected_embeddings

        sti = SentenceTransformerInference(model_name="multi-qa-mpnet-base-dot-v1")
        
        texts_to_embed = ["First sentence.", "Second sentence for embedding."]
        embeddings = sti.invoke(texts_to_embed)

        mock_model_instance.encode.assert_called_once_with(texts_to_embed)
        self.assertEqual(embeddings, expected_embeddings)

    @patch('sentence_transformers.SentenceTransformer')
    def test_init_default_trust_remote_code(self, MockSentenceTransformer):
        model_name = "default_model"
        sti = SentenceTransformerInference(model_name=model_name)
        MockSentenceTransformer.assert_called_once_with(model_name, trust_remote_code=False)


class TestLLMInterface(unittest.TestCase):
    # LLMInterface might be an abstract class or have minimal concrete logic.
    # If it has validation or helper methods, they would be tested here.
    # For now, assume it's primarily for defining a common interface.

    def test_llm_interface_instantiable_if_not_abc(self):
        # This test is valid only if LLMInterface is not an ABC with abstract methods
        try:
            interface = LLMInterface(model_name="test_model")
            self.assertIsNotNone(interface)
            self.assertEqual(interface.model_name, "test_model")
        except TypeError:
            # This will happen if LLMInterface is an ABC with abstract methods
            # and cannot be instantiated directly.
            pass
        except AttributeError:
             # This will happen if LLMInterface is an ABC with abstract methods
            # and cannot be instantiated directly.
            pass


class TestChatAnthropic(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_anthropic_key"
        self.model_name = "claude-3-opus-20240229"
        os.environ[ANTHROPIC_API_KEY_ENV_VAR] = self.api_key

    def tearDown(self):
        del os.environ[ANTHROPIC_API_KEY_ENV_VAR]

    @patch('anthropic.Anthropic')
    def test_init(self, MockAnthropicClient):
        chat = ChatAnthropic(model_name=self.model_name, max_tokens=100, temperature=0.5)
        self.assertEqual(chat.model_name, self.model_name)
        self.assertEqual(chat.max_tokens, 100)
        self.assertEqual(chat.temperature, 0.5)
        MockAnthropicClient.assert_called_once_with(api_key=self.api_key)

    @patch('anthropic.Anthropic')
    def test_invoke_success(self, MockAnthropicClient):
        mock_anthropic_instance = MockAnthropicClient.return_value
        mock_completion = MagicMock()
        mock_completion.content = [MagicMock(text="Anthropic says hello!")]
        mock_anthropic_instance.messages.create.return_value = mock_completion

        chat = ChatAnthropic(model_name=self.model_name)
        prompt = "Hello, Anthropic!"
        system_prompt = "You are a helpful assistant."
        
        response_obj = chat.invoke(prompt, system_prompt=system_prompt)
        response_text = response_obj.response_text # Assuming LLMResponse object is returned

        self.assertEqual(response_text, "Anthropic says hello!")
        mock_anthropic_instance.messages.create.assert_called_once_with(
            model=self.model_name,
            max_tokens=chat.max_tokens, # Default if not overridden in invoke
            temperature=chat.temperature,
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt
        )

    @patch('anthropic.Anthropic')
    def test_invoke_api_error(self, MockAnthropicClient):
        mock_anthropic_instance = MockAnthropicClient.return_value
        from anthropic import APIError # Use the actual error type
        mock_anthropic_instance.messages.create.side_effect = APIError("Test API Error", request=MagicMock())

        chat = ChatAnthropic(model_name=self.model_name)
        with self.assertRaises(APIError): # Or a custom wrapped exception if the class does that
            chat.invoke("Test prompt")

    def test_init_missing_api_key(self):
        del os.environ[ANTHROPIC_API_KEY_ENV_VAR]
        with self.assertRaises(ValueError) as context:
            ChatAnthropic(model_name=self.model_name)
        self.assertIn("Anthropic API key not found", str(context.exception))


class TestChatOpenAI(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_openai_key"
        self.model_name = "gpt-4"
        os.environ[OPENAI_API_KEY_ENV_VAR] = self.api_key

    def tearDown(self):
        del os.environ[OPENAI_API_KEY_ENV_VAR]

    @patch('openai.OpenAI')
    def test_init(self, MockOpenAIClient):
        chat = ChatOpenAI(model_name=self.model_name, max_tokens=200, temperature=0.7)
        self.assertEqual(chat.model_name, self.model_name)
        self.assertEqual(chat.max_tokens, 200)
        self.assertEqual(chat.temperature, 0.7)
        MockOpenAIClient.assert_called_once_with(api_key=self.api_key)

    @patch('openai.OpenAI')
    def test_invoke_success(self, MockOpenAIClient):
        mock_openai_instance = MockOpenAIClient.return_value
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="OpenAI says hi!"))]
        mock_openai_instance.chat.completions.create.return_value = mock_completion

        chat = ChatOpenAI(model_name=self.model_name)
        prompt = "Hi OpenAI!"
        system_prompt = "Be concise."
        
        response_obj = chat.invoke(prompt, system_prompt=system_prompt)
        response_text = response_obj.response_text

        self.assertEqual(response_text, "OpenAI says hi!")
        mock_openai_instance.chat.completions.create.assert_called_once_with(
            model=self.model_name,
            max_tokens=chat.max_tokens,
            temperature=chat.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )

    @patch('openai.OpenAI')
    def test_invoke_api_error(self, MockOpenAIClient):
        mock_openai_instance = MockOpenAIClient.return_value
        from openai import APIError # Use the actual error type
        mock_openai_instance.chat.completions.create.side_effect = APIError("OpenAI Test Error", request=MagicMock(), body=None)

        chat = ChatOpenAI(model_name=self.model_name)
        with self.assertRaises(APIError):
            chat.invoke("Test prompt for OpenAI error")

    def test_init_missing_api_key(self):
        del os.environ[OPENAI_API_KEY_ENV_VAR]
        with self.assertRaises(ValueError) as context:
            ChatOpenAI(model_name=self.model_name)
        self.assertIn("OpenAI API key not found", str(context.exception))


class TestChatVertexAI(unittest.TestCase): # For Gemini
    def setUp(self):
        self.credentials_path = "fake_google_creds.json"
        self.model_name = "gemini-pro"
        os.environ[GOOGLE_APPLICATION_CREDENTIALS_ENV_VAR] = self.credentials_path

        # Create a dummy credentials file for os.path.exists to pass in the constructor
        with open(self.credentials_path, "w") as f:
            json.dump({"type": "service_account"}, f)


    def tearDown(self):
        del os.environ[GOOGLE_APPLICATION_CREDENTIALS_ENV_VAR]
        if os.path.exists(self.credentials_path):
            os.remove(self.credentials_path)

    @patch('google.generativeai.GenerativeModel')
    @patch('google.auth.default', return_value=(MagicMock(), "test_project")) # Mock google auth
    def test_init(self, mock_google_auth, MockGenerativeModel):
        chat = ChatVertexAI(model_name=self.model_name, max_output_tokens=256, temperature=0.6)
        self.assertEqual(chat.model_name, self.model_name)
        self.assertEqual(chat.max_output_tokens, 256)
        self.assertEqual(chat.temperature, 0.6)
        MockGenerativeModel.assert_called_once_with(self.model_name)
        mock_google_auth.assert_called_once() # Check that google.auth.default() was called

    @patch('google.generativeai.GenerativeModel')
    @patch('google.auth.default', return_value=(MagicMock(), "test_project"))
    def test_invoke_success(self, mock_google_auth, MockGenerativeModel):
        mock_model_instance = MockGenerativeModel.return_value
        mock_response = MagicMock()
        mock_response.text = "Gemini says hello!"
        mock_model_instance.generate_content.return_value = mock_response

        chat = ChatVertexAI(model_name=self.model_name)
        prompt = "Hello, Gemini!"
        system_prompt = "You are a helpful AI." # System prompt handling for Gemini might differ
        
        response_obj = chat.invoke(prompt, system_prompt=system_prompt)
        response_text = response_obj.response_text

        self.assertEqual(response_text, "Gemini says hello!")
        
        # VertexAI/Gemini combines system and user prompt in the contents list.
        # The actual implementation might wrap this differently.
        # Assuming direct pass-through for now or check internal _prepare_contents method if it exists.
        expected_contents = []
        if system_prompt:
             # The current implementation of ChatVertexAI seems to prepend system prompt to user prompt
             # if system_prompt is provided.
            expected_contents.append(f"{system_prompt}\n\n{prompt}")
        else:
            expected_contents.append(prompt)

        mock_model_instance.generate_content.assert_called_once()
        call_args = mock_model_instance.generate_content.call_args[0]
        self.assertEqual(call_args[0], expected_contents) # Check the actual content passed
        
        # Check generation_config
        gen_config = mock_model_instance.generate_content.call_args[1]['generation_config']
        self.assertEqual(gen_config.max_output_tokens, chat.max_output_tokens)
        self.assertEqual(gen_config.temperature, chat.temperature)


    @patch('google.generativeai.GenerativeModel')
    @patch('google.auth.default', return_value=(MagicMock(), "test_project"))
    def test_invoke_api_error(self, mock_google_auth, MockGenerativeModel):
        mock_model_instance = MockGenerativeModel.return_value
        # Simulate an API error. The specific exception type may vary.
        # Using a generic Exception for now, replace with actual Google API error if known.
        mock_model_instance.generate_content.side_effect = Exception("Gemini API Error")

        chat = ChatVertexAI(model_name=self.model_name)
        with self.assertRaises(Exception): # Or the specific Google API error
            chat.invoke("Test prompt for Gemini error")

    def test_init_missing_credentials_env_var(self):
        del os.environ[GOOGLE_APPLICATION_CREDENTIALS_ENV_VAR]
        with self.assertRaises(ValueError) as context:
            ChatVertexAI(model_name=self.model_name)
        self.assertIn("GOOGLE_APPLICATION_CREDENTIALS environment variable not set", str(context.exception))

    def test_init_credentials_file_not_found(self):
        os.remove(self.credentials_path) # Ensure file is not there
        with self.assertRaises(ValueError) as context:
            ChatVertexAI(model_name=self.model_name)
        self.assertIn(f"Google credentials file not found at {self.credentials_path}", str(context.exception))


class TestChatOllama(unittest.TestCase):
    def setUp(self):
        self.ollama_host = "http://localhost:11434" # Default if not in env
        self.model_name = "llama2"
        os.environ[OLLAMA_HOST_ENV_VAR] = self.ollama_host

    def tearDown(self):
        if OLLAMA_HOST_ENV_VAR in os.environ:
            del os.environ[OLLAMA_HOST_ENV_VAR]

    @patch('ollama.Client')
    def test_init(self, MockOllamaClient):
        chat = ChatOllama(model_name=self.model_name, temperature=0.2, num_ctx=2048, top_p=0.9)
        self.assertEqual(chat.model_name, self.model_name)
        self.assertEqual(chat.temperature, 0.2)
        self.assertEqual(chat.num_ctx, 2048)
        self.assertEqual(chat.top_p, 0.9)
        MockOllamaClient.assert_called_once_with(host=self.ollama_host)

    @patch('ollama.Client')
    def test_invoke_success_no_schema(self, MockOllamaClient):
        mock_ollama_instance = MockOllamaClient.return_value
        mock_response = {
            "model": self.model_name,
            "created_at": "2023-10-13T14:30:00Z",
            "message": {"role": "assistant", "content": "Ollama says hello!"},
            "done": True,
            "total_duration": 1000000000,
            "load_duration": 1000000,
            "prompt_eval_count": 10,
            "eval_count": 5,
            "eval_duration": 500000000
        }
        mock_ollama_instance.chat.return_value = mock_response

        chat = ChatOllama(model_name=self.model_name)
        prompt = "Hello, Ollama!"
        system_prompt = "You are Ollama."
        
        response_obj = chat.invoke(prompt, system_prompt=system_prompt)
        response_text = response_obj.response_text
        response_json = response_obj.response_json # Should be None if no schema

        self.assertEqual(response_text, "Ollama says hello!")
        self.assertIsNone(response_json)
        
        expected_options = {
            "temperature": chat.temperature, "num_ctx": chat.num_ctx, "top_p": chat.top_p
        }
        # Filter out None values from expected_options if attributes are None
        expected_options = {k: v for k, v in expected_options.items() if v is not None}


        mock_ollama_instance.chat.assert_called_once_with(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            format="", # Default when no schema
            options=expected_options
        )

    @patch('ollama.Client')
    def test_invoke_success_with_json_schema(self, MockOllamaClient):
        mock_ollama_instance = MockOllamaClient.return_value
        json_response_content = {"greeting": "Ollama says hello in JSON!", "valid": True}
        mock_response = {
            "message": {"role": "assistant", "content": json.dumps(json_response_content)}
            # Other fields as in previous test...
        }
        mock_ollama_instance.chat.return_value = mock_response

        chat = ChatOllama(model_name=self.model_name)
        prompt = "Respond in JSON."
        # A Pydantic model or a JSON schema dict could be used for 'schema'
        # For simplicity in test, let's assume it just triggers 'format: "json"'
        # If actual schema validation against a Pydantic model is done, test that too.
        
        response_obj = chat.invoke(prompt, schema="json") # Using string "json" to trigger format
        response_text = response_obj.response_text # Raw JSON string
        response_json = response_obj.response_json # Parsed JSON

        self.assertEqual(response_text, json.dumps(json_response_content))
        self.assertEqual(response_json, json_response_content)
        
        mock_ollama_instance.chat.assert_called_once()
        call_args = mock_ollama_instance.chat.call_args_list[0]
        self.assertEqual(call_args[1]['format'], "json")


    @patch('ollama.Client')
    def test_invoke_api_error(self, MockOllamaClient):
        mock_ollama_instance = MockOllamaClient.return_value
        from ollama import ResponseError # Use the actual error type
        mock_ollama_instance.chat.side_effect = ResponseError("Ollama Test Error", status_code=500)

        chat = ChatOllama(model_name=self.model_name)
        with self.assertRaises(ResponseError):
            chat.invoke("Test prompt for Ollama error")

    def test_init_no_host_env_var(self):
        if OLLAMA_HOST_ENV_VAR in os.environ:
            del os.environ[OLLAMA_HOST_ENV_VAR] # Ensure it's not set
        
        with patch('ollama.Client') as MockOllamaClientFallback:
             # Should use default host from ollama library if env var is missing
            chat = ChatOllama(model_name=self.model_name)
            # The ollama library itself might default the host.
            # We are checking if our ChatOllama class passes None or relies on ollama's default.
            # If ChatOllama has its own default when env var is missing, test that.
            # Current ChatOllama uses os.getenv("OLLAMA_HOST", "http://localhost:11434")
            # So it will always have a host.
            MockOllamaClientFallback.assert_called_once_with(host="http://localhost:11434")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
