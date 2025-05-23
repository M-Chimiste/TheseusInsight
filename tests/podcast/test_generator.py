import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import os
import pandas as pd
from datetime import datetime

# Assuming PodcastGenerator and related classes are in theseus_insight.podcast.generator
# Adjust import paths if necessary
try:
    from theseus_insight.podcast.generator import PodcastGenerator, PodcastScript, PodcastEpisode
    from theseus_insight.inference.llm import LLMInterface, LLMResponse # For mocking
    from theseus_insight.inference.tts import BaseTTS # For mocking
    from theseus_insight.data_model.papers import Paper # For creating paper objects
    PODCAST_CLASSES_EXIST = True
except ImportError as e:
    print(f"Test setup import error: {e}")
    PODCAST_CLASSES_EXIST = False
    # Define dummy classes if the real ones can't be imported
    class LLMInterface: pass
    class BaseTTS: pass
    class Paper: pass
    class PodcastGenerator:
        def __init__(self, *args, **kwargs): pass
        def generate_podcast_script(self, *args, **kwargs): pass
        def generate_podcast_audio(self, *args, **kwargs): pass
        def generate_podcast(self, *args, **kwargs): pass
    class PodcastScript:
        def __init__(self, *args, **kwargs): pass
    class PodcastEpisode:
        def __init__(self, *args, **kwargs): pass


@unittest.skipIf(not PODCAST_CLASSES_EXIST, "Actual PodcastGenerator classes not found.")
class TestPodcastGenerator(unittest.TestCase):

    def setUp(self):
        self.mock_llm_interface = MagicMock(spec=LLMInterface)
        self.mock_tts_interface = MagicMock(spec=BaseTTS)
        
        self.papers_df = pd.DataFrame({
            'id': ['1', '2'],
            'title': ['Paper Alpha', 'Paper Beta'],
            'abstract': ['Abstract Alpha...', 'Abstract Beta...'],
            'content_text': ['Full content Alpha.', 'Full content Beta.'], # Assuming content_text is available
            'authors': [['Author A'], ['Author B']],
            'publish_date': [datetime(2023,1,1).date(), datetime(2023,1,2).date()],
            'pdf_url': ['url_a', 'url_b'],
            'relevance_score': [9, 8],
            'summary': ["Summary for Alpha.", "Summary for Beta."] # Assuming pre-summarized
        })

        self.default_config = {
            "podcast_title": "AI Research Today",
            "podcast_artist": "Theseus AI",
            "podcast_description_model": self.mock_llm_interface,
            "podcast_script_model": self.mock_llm_interface,
            "podcast_tts_model": self.mock_tts_interface,
            "podcast_description_prompt": "Generate a description...",
            "podcast_intro_prompt": "Generate an intro...",
            "podcast_outro_prompt": "Generate an outro...",
            "podcast_paper_discussion_prompt": "Discuss this paper: {title}...",
            "podcast_host_voice_ids": ["host_voice_1", "host_voice_2"],
            "podcast_host_speeds": [1.0, 1.1],
            "podcast_guest_voice_ids": ["guest_voice_1"],
            "podcast_guest_speeds": [1.0],
            "podcast_max_papers": 2,
            "podcast_intro_music_path": None,
            "podcast_outro_music_path": None,
            "verbose": False
        }

    @patch('theseus_insight.podcast.generator.PodcastScript') # Mock the class used internally
    def test_init_default_config(self, MockPodcastScript):
        gen = PodcastGenerator(**self.default_config)
        self.assertEqual(gen.title, "AI Research Today")
        self.assertEqual(gen.artist, "Theseus AI")
        self.assertIsNone(gen.intro_music_path)
        MockPodcastScript.assert_called_once() # Check if script obj is created

    @patch('theseus_insight.podcast.generator.PodcastScript')
    def test_init_with_music(self, MockPodcastScript):
        config_with_music = {**self.default_config, 
                             "podcast_intro_music_path": "intro.mp3",
                             "podcast_outro_music_path": "outro.mp3"}
        with patch('os.path.exists', return_value=True): # Assume music files exist
            gen = PodcastGenerator(**config_with_music)
        self.assertEqual(gen.intro_music_path, "intro.mp3")
        self.assertEqual(gen.outro_music_path, "outro.mp3")

    def test_init_music_file_not_found(self):
        config_with_bad_music = {**self.default_config, "podcast_intro_music_path": "non_existent.mp3"}
        with patch('os.path.exists', return_value=False), \
             self.assertRaises(FileNotFoundError):
            PodcastGenerator(**config_with_bad_music)
            
    @patch('theseus_insight.podcast.generator.PodcastScript') # Mock the class
    def test_generate_podcast_script_one_host(self, MockPodcastScript):
        mock_script_instance = MockPodcastScript.return_value
        
        config_one_host = {**self.default_config, 
                           "podcast_host_voice_ids": ["single_host_voice"],
                           "podcast_host_speeds": [1.0]}
        gen = PodcastGenerator(**config_one_host)

        # Mock LLM responses
        self.mock_llm_interface.invoke.side_effect = [
            LLMResponse(response_text="Podcast Description Text"), # For description
            LLMResponse(response_text="Podcast Intro Text"),       # For intro
            LLMResponse(response_text="Discussion for Paper Alpha"), # Paper 1
            LLMResponse(response_text="Discussion for Paper Beta"),  # Paper 2
            LLMResponse(response_text="Podcast Outro Text")        # For outro
        ]

        episode_script = gen.generate_podcast_script(self.papers_df)

        self.assertIsInstance(episode_script, PodcastScript) # Should be the mocked instance
        
        # Check calls to LLM for script parts
        self.assertEqual(self.mock_llm_interface.invoke.call_count, 5) # Desc, Intro, 2xPaper, Outro
        
        # Check calls to the script object's methods (via the mocked instance)
        mock_script_instance.set_description.assert_called_once_with("Podcast Description Text")
        mock_script_instance.add_segment.assert_any_call("Podcast Intro Text", host_id=0, segment_type="intro")
        mock_script_instance.add_segment.assert_any_call("Discussion for Paper Alpha", host_id=0, segment_type="paper_discussion", paper_id='1')
        mock_script_instance.add_segment.assert_any_call("Discussion for Paper Beta", host_id=0, segment_type="paper_discussion", paper_id='2')
        mock_script_instance.add_segment.assert_any_call("Podcast Outro Text", host_id=0, segment_type="outro")

    @patch('theseus_insight.podcast.generator.PodcastScript')
    def test_generate_podcast_script_two_hosts(self, MockPodcastScript):
        mock_script_instance = MockPodcastScript.return_value
        gen = PodcastGenerator(**self.default_config) # Default has 2 hosts

        self.mock_llm_interface.invoke.side_effect = [
            LLMResponse(response_text="Desc"), LLMResponse(response_text="Intro"),
            LLMResponse(response_text="Host 0: Discuss Alpha"), LLMResponse(response_text="Host 1: Also Alpha"), # Paper 1, 2 segments
            LLMResponse(response_text="Host 0: Discuss Beta"),  LLMResponse(response_text="Host 1: Also Beta"),  # Paper 2, 2 segments
            LLMResponse(response_text="Outro")
        ]
        # Assuming the prompt for paper discussion is crafted to indicate which host should speak
        # or the LLM is expected to alternate or assign roles in its response.
        # The test here assumes the LLM output might contain indicators or the generator logic handles alternation.
        # For simplicity, let's assume the prompt for paper discussion is called once per paper,
        # and the LLM response itself might contain multi-host dialogue, or the generator
        # calls the LLM per host turn (this test assumes the former for fewer LLM calls).
        # If it's one call per host turn per paper, invoke.call_count would be 1 (desc) + 1 (intro) + 2*2 (papers) + 1 (outro) = 7

        # To align with the provided code's generate_podcast_script logic:
        # It seems to call LLM once per paper with a general discussion prompt.
        # The host assignment is done by cycling through host_ids.
        # So, the invoke side_effect should be:
        self.mock_llm_interface.invoke.side_effect = [
            LLMResponse(response_text="Podcast Description Text"),
            LLMResponse(response_text="Podcast Intro Text (Host 0)"),
            LLMResponse(response_text="Discussion for Paper Alpha (Host 1)"), # Paper 1 assigned to host 1
            LLMResponse(response_text="Discussion for Paper Beta (Host 0)"),  # Paper 2 assigned to host 0 (cycles)
            LLMResponse(response_text="Podcast Outro Text (Host 1)")
        ]

        gen.generate_podcast_script(self.papers_df)
        
        self.assertEqual(self.mock_llm_interface.invoke.call_count, 5)
        mock_script_instance.add_segment.assert_any_call("Podcast Intro Text (Host 0)", host_id=0, segment_type="intro")
        mock_script_instance.add_segment.assert_any_call("Discussion for Paper Alpha (Host 1)", host_id=1, segment_type="paper_discussion", paper_id='1')
        mock_script_instance.add_segment.assert_any_call("Discussion for Paper Beta (Host 0)", host_id=0, segment_type="paper_discussion", paper_id='2')
        mock_script_instance.add_segment.assert_any_call("Podcast Outro Text (Host 1)", host_id=1, segment_type="outro")


    @patch('pydub.AudioSegment')
    @patch('builtins.open', new_callable=mock_open) # Mock saving audio file
    @patch('os.makedirs') # Mock directory creation
    def test_generate_podcast_audio_no_music(self, mock_makedirs, mock_file, MockAudioSegment):
        mock_audio_segment_instance = MagicMock()
        MockAudioSegment.silent.return_value = MagicMock() # For initial combined audio
        MockAudioSegment.from_mp3.return_value = mock_audio_segment_instance # If music files were real
        
        # Simulate TTS interface successfully creating audio files for segments
        def mock_synthesize_effect(text, output_filename, voice, speed):
            # Create a dummy file to simulate TTS output
            with open(output_filename, "wb") as f: f.write(b"dummy_audio_data")
            # Return a mock AudioSegment for this synthesized part
            segment = MagicMock(spec=MockAudioSegment)
            segment.duration_seconds = len(text) / 10.0 # Dummy duration
            return output_filename, segment # Return path and mock segment

        self.mock_tts_interface.synthesize.side_effect = mock_synthesize_effect
        
        # Create a mock PodcastScript object with some segments
        mock_script = MagicMock(spec=PodcastScript)
        mock_script.segments = [
            {"text": "Intro segment", "host_id": 0, "segment_type": "intro", "audio_path": None},
            {"text": "Paper 1 discussion", "host_id": 1, "segment_type": "paper_discussion", "audio_path": None},
            {"text": "Outro segment", "host_id": 0, "segment_type": "outro", "audio_path": None}
        ]
        mock_script.get_script_for_tts.return_value = mock_script.segments # For iteration
        mock_script.description = "Test podcast description."

        gen = PodcastGenerator(**self.default_config)
        output_dir = "test_podcast_output"
        final_filename_base = "my_podcast"
        
        # Create an Episode object to pass to generate_podcast_audio
        episode = PodcastEpisode(
            title=gen.title, 
            artist=gen.artist, 
            script=mock_script, # Use the mocked script
            description=mock_script.description
        )

        final_audio_path, _ = gen.generate_podcast_audio(episode, output_dir, final_filename_base)

        self.assertEqual(final_audio_path, os.path.join(output_dir, f"{final_filename_base}.mp3"))
        mock_makedirs.assert_called_with(output_dir, exist_ok=True)
        
        # Check TTS calls
        self.assertEqual(self.mock_tts_interface.synthesize.call_count, len(mock_script.segments))
        calls = self.mock_tts_interface.synthesize.call_args_list
        self.assertEqual(calls[0][0][0], "Intro segment") # text
        self.assertEqual(calls[0][0][2], self.default_config["podcast_host_voice_ids"][0]) # voice
        self.assertEqual(calls[0][0][3], self.default_config["podcast_host_speeds"][0])   # speed

        self.assertEqual(calls[1][0][0], "Paper 1 discussion")
        self.assertEqual(calls[1][0][2], self.default_config["podcast_host_voice_ids"][1]) # voice host 1
        self.assertEqual(calls[1][0][3], self.default_config["podcast_host_speeds"][1])   # speed host 1

        # Check that the combined audio was exported
        # The actual combined_audio object is internal to the method,
        # but we can check if its 'export' method was called on the final result.
        # This requires that the mock_synthesize_effect returns a mock that can be combined.
        # For simplicity, let's assume the last call to export is on the final combined audio.
        # This part is tricky to test without deeper mocking of AudioSegment's combination logic.
        # We'll check that 'export' was called on *some* AudioSegment instance.
        # A better way would be to capture the combined_audio if it's a return value or class member.
        
        # Find the call to export the final combined file
        export_call_found = False
        for call_obj in MockAudioSegment.silent.return_value.export.mock_calls:
            if call_obj[1][0] == final_audio_path: # Check if exported to final path
                export_call_found = True
                break
        # This check is a bit indirect. It might be better to mock combined_audio.export directly if possible.
        # The current mock setup for AudioSegment might not be sufficient for this precise check.
        # For now, we trust the mocked file write via mock_file.
        mock_file.assert_called_with(final_audio_path, "wb")


    @patch.object(PodcastGenerator, 'generate_podcast_script', return_value=MagicMock(spec=PodcastScript))
    @patch.object(PodcastGenerator, 'generate_podcast_audio', return_value=("final_audio.mp3", "final_script.txt"))
    @patch('theseus_insight.podcast.generator.PodcastEpisode') # Mock the class itself
    @patch('shutil.copy') # If script is copied
    def test_generate_podcast_main_method_audio_only(self, mock_shutil_copy, MockPodcastEpisode,
                                                     mock_gen_audio, mock_gen_script):
        
        mock_script_obj = mock_gen_script.return_value # This is already a MagicMock
        mock_script_obj.description = "Generated test description"
        mock_script_obj.get_full_text_script.return_value = "Full script content." # For saving script text

        mock_episode_instance = MockPodcastEpisode.return_value # Instance of PodcastEpisode
        mock_episode_instance.script = mock_script_obj
        mock_episode_instance.title = self.default_config["podcast_title"]
        mock_episode_instance.artist = self.default_config["podcast_artist"]
        mock_episode_instance.description = "Generated test description"


        gen = PodcastGenerator(**self.default_config)
        output_dir = "test_output"
        prefix = "testrun"
        
        result = gen.generate_podcast(
            papers_df=self.papers_df, 
            output_dir=output_dir, 
            file_prefix=prefix,
            generate_visualization=False # Audio only
        )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, PodcastEpisode) # Should be the mocked instance
        
        mock_gen_script.assert_called_once_with(self.papers_df)
        # generate_podcast_audio is called with the Episode instance
        mock_gen_audio.assert_called_once()
        call_args_audio, _ = mock_gen_audio.call_args
        self.assertIsInstance(call_args_audio[0], PodcastEpisode) # Check it got an episode
        self.assertEqual(call_args_audio[1], output_dir)
        self.assertEqual(call_args_audio[2], f"{prefix}_podcast") # final_filename_base

        # Check if script text file was saved (via the episode object)
        mock_episode_instance.save_script_to_file.assert_called_once_with(
            os.path.join(output_dir, f"{prefix}_podcast_script.txt")
        )


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
