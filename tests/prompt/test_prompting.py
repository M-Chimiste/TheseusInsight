import unittest
from unittest.mock import MagicMock

# Assuming PromptGenerator and other core classes/functions are in theseus_insight.prompt.prompting
# Adjust imports as per actual file structure and contents
try:
    from theseus_insight.prompt.prompting import PromptGenerator, PromptOutputParser # Example names
    from theseus_insight.inference.llm import LLMInterface, LLMResponse # For type hinting or mocking
    PROMPTING_CLASSES_EXIST = True
except ImportError:
    PROMPTING_CLASSES_EXIST = False
    class LLMInterface: pass # Dummy for type hint if needed
    class LLMResponse: pass # Dummy
    class PromptGenerator: # Dummy
        def __init__(self, llm_interface: LLMInterface, system_prompt: str = None):
            self.llm = llm_interface
            self.system_prompt = system_prompt
        def generate_response(self, user_prompt: str, schema=None, retries=3, initial_delay=1):
            # Simplified mockable behavior
            if hasattr(self.llm, 'invoke'):
                return self.llm.invoke(user_prompt, system_prompt=self.system_prompt, schema=schema)
            return LLMResponse(response_text="dummy_response")

    class PromptOutputParser: # Dummy
        def __init__(self, pydantic_model):
            self.pydantic_model = pydantic_model
        def parse(self, llm_output_text: str):
            # Simplified mockable behavior
            if self.pydantic_model:
                return {"parsed": True, "content": llm_output_text[:10]} # Simulate parsing
            return llm_output_text


@unittest.skipIf(not PROMPTING_CLASSES_EXIST, "Actual prompting classes not found.")
class TestPromptGenerator(unittest.TestCase):

    def setUp(self):
        self.mock_llm = MagicMock(spec=LLMInterface)
        self.system_prompt_text = "You are a helpful research assistant."
        self.user_prompt_text = "Summarize the following paper: ..."
        
    def test_init_with_system_prompt(self):
        generator = PromptGenerator(llm_interface=self.mock_llm, system_prompt=self.system_prompt_text)
        self.assertEqual(generator.llm, self.mock_llm)
        self.assertEqual(generator.system_prompt, self.system_prompt_text)

    def test_init_without_system_prompt(self):
        generator = PromptGenerator(llm_interface=self.mock_llm)
        self.assertIsNone(generator.system_prompt)

    def test_generate_response_simple(self):
        mock_llm_response_obj = MagicMock(spec=LLMResponse)
        mock_llm_response_obj.response_text = "This is a summary."
        self.mock_llm.invoke.return_value = mock_llm_response_obj

        generator = PromptGenerator(llm_interface=self.mock_llm, system_prompt=self.system_prompt_text)
        response = generator.generate_response(user_prompt=self.user_prompt_text)

        self.mock_llm.invoke.assert_called_once_with(
            self.user_prompt_text,
            system_prompt=self.system_prompt_text,
            schema=None # Default
        )
        self.assertEqual(response, mock_llm_response_obj) # Returns the LLMResponse object

    def test_generate_response_with_schema(self):
        mock_llm_response_obj = MagicMock(spec=LLMResponse)
        mock_llm_response_obj.response_text = '{"summary": "Structured summary."}'
        mock_llm_response_obj.response_json = {"summary": "Structured summary."}
        self.mock_llm.invoke.return_value = mock_llm_response_obj
        
        dummy_schema = {"type": "object", "properties": {"summary": {"type": "string"}}}

        generator = PromptGenerator(llm_interface=self.mock_llm)
        response = generator.generate_response(user_prompt="Extract info.", schema=dummy_schema)

        self.mock_llm.invoke.assert_called_once_with(
            "Extract info.",
            system_prompt=None,
            schema=dummy_schema
        )
        self.assertEqual(response.response_json, {"summary": "Structured summary."})

    @patch('time.sleep', return_value=None) # Mock time.sleep for retries
    def test_generate_response_with_retries_success_on_retry(self, mock_sleep):
        # Simulate failure then success
        mock_failure_response = Exception("API limit reached")
        mock_success_response_obj = MagicMock(spec=LLMResponse)
        mock_success_response_obj.response_text = "Success after retry"
        
        self.mock_llm.invoke.side_effect = [mock_failure_response, mock_success_response_obj]

        generator = PromptGenerator(llm_interface=self.mock_llm)
        response = generator.generate_response(user_prompt="Try this", retries=2, initial_delay=0.1)

        self.assertEqual(self.mock_llm.invoke.call_count, 2)
        mock_sleep.assert_called_once_with(0.1) # Check initial delay
        self.assertEqual(response.response_text, "Success after retry")

    @patch('time.sleep', return_value=None)
    @patch('logging.error') # Assuming logging is used for final failure
    def test_generate_response_all_retries_fail(self, mock_logging_error, mock_sleep):
        api_error = Exception("Persistent API error")
        self.mock_llm.invoke.side_effect = [api_error, api_error, api_error] # Fail 3 times

        generator = PromptGenerator(llm_interface=self.mock_llm)
        
        with self.assertRaises(Exception) as context:
            generator.generate_response(user_prompt="This will fail", retries=2, initial_delay=0.1) # retries=2 means 3 attempts

        self.assertIs(context.exception, api_error)
        self.assertEqual(self.mock_llm.invoke.call_count, 3) # Initial call + 2 retries
        self.assertEqual(mock_sleep.call_count, 2) # Delays before each retry
        # mock_logging_error.assert_called() # If an error is logged after all retries fail


@unittest.skipIf(not PROMPTING_CLASSES_EXIST or not hasattr(PromptOutputParser, 'parse'), "Actual PromptOutputParser not found or 'parse' method missing.")
class TestPromptOutputParser(unittest.TestCase):

    def test_parse_no_schema(self):
        parser = PromptOutputParser(pydantic_model=None)
        raw_text = "This is some raw output from the LLM."
        parsed_output = parser.parse(raw_text)
        self.assertEqual(parsed_output, raw_text)

    def test_parse_with_pydantic_schema_valid_json(self):
        # Define a simple Pydantic model for testing
        from pydantic import BaseModel
        class MySchema(BaseModel):
            name: str
            value: int

        parser = PromptOutputParser(pydantic_model=MySchema)
        valid_json_text = '{"name": "TestItem", "value": 123}'
        
        # Mock the Pydantic model parsing behavior if necessary,
        # or rely on actual Pydantic parsing if it's simple enough.
        # For this test, we'll assume the parser directly uses pydantic_model.parse_raw or similar.
        
        # If PromptOutputParser.parse itself calls MySchema.parse_raw or similar:
        with patch.object(MySchema, 'parse_raw', return_value=MySchema(name="TestItem", value=123)) as mock_parse_raw:
            parsed_output = parser.parse(valid_json_text)
        
        mock_parse_raw.assert_called_once_with(valid_json_text)
        self.assertIsInstance(parsed_output, MySchema)
        self.assertEqual(parsed_output.name, "TestItem")

    def test_parse_with_pydantic_schema_invalid_json(self):
        from pydantic import BaseModel, ValidationError
        class MySchema(BaseModel):
            name: str
            value: int

        parser = PromptOutputParser(pydantic_model=MySchema)
        invalid_json_text = '{"name": "TestItem", "value": "not_an_int"}' # Value should be int
        
        # The parser should catch Pydantic's ValidationError and re-raise or handle it.
        # Let's assume it re-raises for now.
        with self.assertRaises(ValidationError): # Or a custom error if wrapped by the parser
            parser.parse(invalid_json_text)

    def test_parse_with_pydantic_schema_non_json_string(self):
        from pydantic import BaseModel, ValidationError
        class MySchema(BaseModel):
            name: str
        
        parser = PromptOutputParser(pydantic_model=MySchema)
        non_json_text = "This is not JSON."
        
        # Depending on implementation, this might raise ValidationError (if parse_raw fails due to JSON)
        # or a specific JSONDecodeError if json.loads is used first.
        with self.assertRaises((ValidationError, ValueError)): # ValueError for json.JSONDecodeError
            parser.parse(non_json_text)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
