import pytest
import pytest_asyncio # For async fixtures
from httpx import AsyncClient
import os
import json
from unittest.mock import patch, mock_open, MagicMock

import uuid
from datetime import datetime, timedelta, date

# Models from the application
from theseus_insight.api.models import (
    OrchestrationConfig, ModelConfig, TTSModelConfig,
    ArxivCategoriesConfig, ResearchInterests, EmailRecipients,
    VisualizerSettings, ModelProvider,
    NewsletterConfig, PodcastGenerationParams, VisualizerSettings as VisualizerParamsForPipeline, # Alias for clarity
    NewsletterRunParams, LogEntry, Run, PaginatedResponse,
    PodcastListItemResponse, PodcastDetailResponse, PodcastScriptItem, TaskStatus as ApiTaskStatus # Renamed to avoid conflict
)
# The FastAPI app instance
from theseus_insight.main import app, DB_PATH as MAIN_DB_PATH, task_manager as main_task_manager
from theseus_insight.api.tasks import TaskStatus # This is the Enum used by task_manager

# Store the original DB_PATH and restore it after tests if necessary,
# though for isolated test runs, patching is usually sufficient.
ORIGINAL_DB_PATH = MAIN_DB_PATH
TEST_DB_PATH = "sqlite+aiosqlite:///:memory:" # In-memory SQLite for tests


@pytest_asyncio.fixture(scope="function")
async def async_client(mock_task_manager): # Add mock_task_manager fixture here
    """
    Fixture to create an AsyncClient with an in-memory SQLite DB and mocked task_manager.
    Ensures each test function gets a fresh database, app instance, and task manager.
    """
    with patch('theseus_insight.main.DB_PATH', TEST_DB_PATH), \
         patch('theseus_insight.main.task_manager', mock_task_manager), \
         patch('theseus_insight.api.tasks.task_manager', mock_task_manager): # If tasks module uses its own import
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client


@pytest.fixture(scope="function")
def mock_task_manager():
    """
    Fixture to create a MagicMock for the task_manager.
    This allows us to assert calls to task_manager methods.
    """
    manager = MagicMock()
    manager.get_task_status = MagicMock()
    manager.create_task = MagicMock(return_value=None) # Async method, but called via BackgroundTasks
    manager.update_task_status = MagicMock(return_value=None) # Async method
    manager.run_newsletter_task = MagicMock() # The actual function that BackgroundTasks calls
    manager.run_podcast_task = MagicMock()
    manager.run_visualizer_task = MagicMock()
    # For WebSocket related parts, if needed by endpoint logic directly, mock them here too
    manager.subscribe_to_updates = MagicMock()
    manager.unsubscribe_from_updates = MagicMock()
    return manager


# --- Helper for mocking file reads / UploadFile ---
def mock_file_content(mock_data):
    m = mock_open(read_data=json.dumps(mock_data) if isinstance(mock_data, dict) else mock_data)
    # Make it behave like a context manager
    m.return_value.__enter__ = lambda s: s
    m.return_value.__exit__ = MagicMock()
    return m

def create_mock_upload_file(filename="test.pdf", content_type="application/pdf", content=b"dummy pdf content"):
    mock_file = MagicMock()
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.read = MagicMock(return_value=content) # For async read, use AsyncMock if needed by FastAPI version
    mock_file.seek = MagicMock()
    return mock_file

# --- Test Cases ---

# Settings endpoints (existing tests from previous step, ensure they still pass)

# /api/settings/orchestration 
# ... (keep existing tests for /api/settings/*) ...
# For brevity, I will assume the previous settings tests are here and still valid.
# I will add new tests below this section.

# --- NEW TESTS FOR PIPELINE, TASK, AND UTILITY ENDPOINTS ---

# /api/newsletter/run
@pytest.mark.asyncio
async def test_run_newsletter_success(async_client: AsyncClient, mock_task_manager):
    newsletter_config_data = {
        "start_date": "2023-01-01", "end_date": "2023-01-07",
        "research_summary_model": {"model_name": "test_sum_model", "model_type": "ollama"},
        "title_generation_model": {"model_name": "test_title_model", "model_type": "ollama"},
        "intro_generation_model": {"model_name": "test_intro_model", "model_type": "ollama"},
        "layout_optimization_model": {"model_name": "test_layout_model", "model_type": "ollama"},
        "max_papers_to_select": 5, "min_score_threshold": 0.6, "send_email": False
    }
    config_json = json.dumps(newsletter_config_data)

    with patch('fastapi.BackgroundTasks.add_task') as mock_add_task:
        response = await async_client.post(
            "/api/newsletter/run",
            data={"config": config_json},
            files={"intro_music_file": ("music.mp3", b"somemusic", "audio/mpeg")} # Optional file
        )

    assert response.status_code == 200
    response_data = response.json()
    assert "taskId" in response_data
    task_id = response_data["taskId"]

    mock_task_manager.create_task.assert_called_once()
    args, kwargs = mock_task_manager.create_task.call_args
    assert kwargs["task_id"] == task_id
    assert kwargs["task_type"] == "newsletter"
    assert kwargs["config"]["start_date"] == "2023-01-01" # Check some config propagation

    mock_add_task.assert_called_once_with(mock_task_manager.run_newsletter_task, task_id)


@pytest.mark.asyncio
async def test_run_newsletter_missing_config(async_client: AsyncClient):
    response = await async_client.post("/api/newsletter/run", data={}) # No "config"
    assert response.status_code == 400 # As per endpoint logic for missing form field
    assert "Newsletter configuration is required" in response.json()["detail"]

@pytest.mark.asyncio
async def test_run_newsletter_invalid_config_json(async_client: AsyncClient):
    response = await async_client.post("/api/newsletter/run", data={"config": "this is not json"})
    assert response.status_code == 400 # Pydantic/JSON validation error
    assert "Invalid JSON format" in response.json()["detail"].lower() or "value is not a valid dict" in response.json()["detail"].lower()


# /api/podcast/generate
@pytest.mark.asyncio
async def test_generate_podcast_success_with_pdfs(async_client: AsyncClient, mock_task_manager):
    podcast_params = {
        "input_type": "pdfs",
        "podcast_model_config": {"model_name": "podcast_llm", "model_type": "ollama"},
        "tts_model_config": {"tts_provider": "openai", "tts_model_name": "tts-1", "speaker_1_voice": "echo", "speaker_1_speed":1.0, "speaker_2_voice": "onyx", "speaker_2_speed":1.0},
        "create_visualization": False
    }
    params_json = json.dumps(podcast_params)
    mock_pdf = create_mock_upload_file(filename="paper1.pdf")

    with patch('fastapi.BackgroundTasks.add_task') as mock_add_task, \
         patch('os.makedirs'), patch('builtins.open', mock_open()): # Mock FS operations
        response = await async_client.post(
            "/api/podcast/generate",
            data={"params_json": params_json},
            files={"pdf_files": mock_pdf}
        )

    assert response.status_code == 200
    response_data = response.json()
    assert "task_id" in response_data
    task_id = response_data["task_id"]

    mock_task_manager.create_task.assert_called_once()
    args, kwargs = mock_task_manager.create_task.call_args
    assert kwargs["task_id"] == task_id
    assert kwargs["task_type"] == "podcast"
    assert kwargs["config"]["input_type"] == "pdfs"
    assert "input_pdf_paths" in kwargs["config"]

    mock_add_task.assert_called_once_with(mock_task_manager.run_podcast_task, task_id)

@pytest.mark.asyncio
async def test_generate_podcast_input_type_pdfs_no_files(async_client: AsyncClient):
    podcast_params = {"input_type": "pdfs", "podcast_model_config": {"model_name":"m", "model_type":"t"}, "tts_model_config": {"tts_provider":"p", "tts_model_name":"tn", "speaker_1_voice":"v1", "speaker_1_speed":1.0, "speaker_2_voice":"v2", "speaker_2_speed":1.0}, "create_visualization": False}
    params_json = json.dumps(podcast_params)
    response = await async_client.post("/api/podcast/generate", data={"params_json": params_json}) # No files
    assert response.status_code == 400
    assert "PDF files are required when input_type is 'pdfs'" in response.json()["detail"]


# /api/actions/run-visualizer-pipeline
@pytest.mark.asyncio
async def test_run_visualizer_pipeline_success(async_client: AsyncClient, mock_task_manager):
    visualizer_params = VisualizerParamsForPipeline().dict() # Use default visualizer settings
    params_json = json.dumps(visualizer_params)
    mock_audio = create_mock_upload_file(filename="audio.mp3", content_type="audio/mpeg")

    with patch('fastapi.BackgroundTasks.add_task') as mock_add_task, \
         patch('os.makedirs'), patch('builtins.open', mock_open()):
        response = await async_client.post(
            "/api/actions/run-visualizer-pipeline",
            data={"visualizer_params_json": params_json},
            files={"audio_file": mock_audio}
        )

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    mock_task_manager.create_task.assert_called_once()
    args, kwargs = mock_task_manager.create_task.call_args
    assert kwargs["task_id"] == task_id
    assert kwargs["task_type"] == "visualizer"
    assert "audio_file_path" in kwargs["config"]
    mock_add_task.assert_called_once_with(mock_task_manager.run_visualizer_task, task_id)


# /api/actions/run-newsletter-pipeline (TheseusInsight direct call)
@pytest.mark.asyncio
async def test_run_theseus_insight_newsletter_pipeline(async_client: AsyncClient, mock_task_manager):
    run_params = {
        "start_date": "2023-05-01", "end_date": "2023-05-07",
        "email_recipients": ["test@example.com"],
        "research_interests": "AI safety",
        "generate_podcast_run": False
    }

    # Mock the TheseusInsight class itself to prevent actual run
    with patch('theseus_insight.main.TheseusInsight') as MockTheseusInsight, \
         patch('fastapi.BackgroundTasks.add_task') as mock_add_task:
        
        mock_ti_instance = MagicMock()
        MockTheseusInsight.return_value = mock_ti_instance # __init__ returns our mock

        response = await async_client.post("/api/actions/run-newsletter-pipeline", json=run_params)

    assert response.status_code == 200
    task_id = response.json()["task_id"]

    mock_task_manager.create_task.assert_called_once() # For initial task registration
    args, kwargs = mock_task_manager.create_task.call_args
    assert kwargs["task_id"] == task_id
    
    # Check that BackgroundTasks.add_task was called, implying the pipeline function was scheduled
    mock_add_task.assert_called_once()
    # Further inspection could check that mock_ti_instance.run would have been called by the background task
    # This requires more intricate mocking of the background function itself if needed.


# /api/tasks/{task_id}/status
@pytest.mark.asyncio
async def test_get_task_status_found(async_client: AsyncClient, mock_task_manager):
    task_id = "test_task_123"
    mock_status_data = {"task_id": task_id, "status": TaskStatus.PROCESSING.value, "progress": 50, "message": "Working..."}
    mock_task_manager.get_task_status.return_value = mock_status_data
    
    response = await async_client.get(f"/api/tasks/{task_id}/status")
    assert response.status_code == 200
    assert response.json()["status"] == TaskStatus.PROCESSING.value
    mock_task_manager.get_task_status.assert_called_once_with(task_id)

@pytest.mark.asyncio
async def test_get_task_status_not_found(async_client: AsyncClient, mock_task_manager):
    task_id = "non_existent_task"
    mock_task_manager.get_task_status.return_value = None
    response = await async_client.get(f"/api/tasks/{task_id}/status")
    assert response.status_code == 404


# /api/tasks/{task_id}/result
@pytest.mark.asyncio
async def test_get_task_result_completed(async_client: AsyncClient, mock_task_manager):
    task_id = "completed_task"
    mock_result = {"data": "some_result_data"}
    mock_task_manager.get_task_status.return_value = {
        "task_id": task_id, "status": TaskStatus.COMPLETED.value, "result": mock_result
    }
    response = await async_client.get(f"/api/tasks/{task_id}/result")
    assert response.status_code == 200
    assert response.json() == mock_result

@pytest.mark.asyncio
async def test_get_task_result_not_completed(async_client: AsyncClient, mock_task_manager):
    task_id = "processing_task"
    mock_task_manager.get_task_status.return_value = {"task_id": task_id, "status": TaskStatus.PROCESSING.value}
    response = await async_client.get(f"/api/tasks/{task_id}/result")
    assert response.status_code == 400
    assert "Task is not completed" in response.json()["detail"]


# /api/tasks/{task_id}/download/{file_type}
@pytest.mark.asyncio
@pytest.mark.parametrize("task_type, file_type, mock_result_key, expected_filename, expected_media_type", [
    ("newsletter", "markdown", "newsletter_content", "newsletter.md", "text/markdown"),
    ("podcast", "audio", "output_file", "podcast.mp3", "audio/mpeg"),
    ("podcast", "video", "visualizer_file", "podcast.mp4", "video/mp4"),
    ("visualizer", "video", "visualizer_file", "visualization.mp4", "video/mp4"),
])
async def test_download_task_artifact_success(
    async_client: AsyncClient, mock_task_manager, task_type, file_type, mock_result_key, expected_filename, expected_media_type
):
    task_id = "download_task"
    mock_file_path = f"/tmp/fake_{expected_filename}"
    mock_task_manager.get_task_status.return_value = {
        "task_id": task_id, "status": TaskStatus.COMPLETED.value, "type": task_type,
        "result": {mock_result_key: mock_file_path if task_type != "newsletter" else "dummy markdown content"}
    }

    # For newsletter, content is directly in result, not a path
    if task_type == "newsletter":
        mock_os_path_exists_target = 'os.path.exists'
        mock_open_target = 'builtins.open'
    else: # For others, it's a file path
        mock_os_path_exists_target = 'os.path.exists'
        mock_open_target = 'builtins.open' # FileResponse will use open indirectly

    with patch(mock_os_path_exists_target, return_value=True) as mock_exists, \
         patch(mock_open_target, mock_open(read_data=b"file_content")) as mock_file_open, \
         patch('os.makedirs'): # Mock makedirs for newsletter temp file creation
        
        response = await async_client.get(f"/api/tasks/{task_id}/download/{file_type}")

    assert response.status_code == 200
    assert response.headers["content-type"] == expected_media_type
    # For FileResponse, content-disposition might indicate filename
    # For newsletter (direct content), this check might be different or less relevant
    if "content-disposition" in response.headers:
         assert f'filename="{expected_filename}"' in response.headers["content-disposition"]
    
    if task_type != "newsletter":
        mock_exists.assert_called_with(mock_file_path)
    else: # Newsletter writes to a temp file
        # Check if os.makedirs was called for the temp dir
        # Check if builtins.open was called to write the newsletter content
        pass # More specific checks can be added if needed for newsletter file creation path


# /api/logs
@pytest.mark.asyncio
async def test_get_logs(async_client: AsyncClient):
    mock_log_data = [
        {"task_id": "t1", "status": "completed", "datetime_run": datetime.now().isoformat()},
        {"task_id": "t2", "status": "failed", "datetime_run": (datetime.now() - timedelta(days=1)).isoformat()}
    ]
    # Need to patch 'db.get_recent_logs' which is accessed via 'theseus_insight.main.db'
    with patch('theseus_insight.main.db.get_recent_logs', return_value=mock_log_data) as mock_get_db_logs:
        response = await async_client.get("/api/logs?limit=50")
    
    assert response.status_code == 200
    logs = response.json()
    assert len(logs) == 2
    assert logs[0]["task_id"] == "t1"
    mock_get_db_logs.assert_called_once_with(limit=50, from_date=None, to_date=None)


# /api/runs & /api/runs/{run_id}/artifact
@pytest.mark.asyncio
async def test_get_runs_and_delete_artifact(async_client: AsyncClient):
    mock_newsletters = [{"id": 1, "date_sent": "2023-01-01"}]
    mock_podcasts = [{"id": 2, "date": "2023-01-02", "title": "P", "description": "D"}] # Added title/desc for PodcastListItemResponse

    with patch('theseus_insight.main.db.fetch_all_newsletters', return_value=mock_newsletters), \
         patch('theseus_insight.main.db.fetch_all_podcasts', return_value=mock_podcasts):
        response_get = await async_client.get("/api/runs")

    assert response_get.status_code == 200
    runs_data = response_get.json()
    assert len(runs_data["items"]) == 2 # One newsletter, one podcast
    assert runs_data["items"][0]["pipeline_type"] == "podcast" # Sorted by date desc

    # Test delete artifact (e.g., podcast run_id = 2)
    with patch('os.path.exists', return_value=True) as mock_exists, \
         patch('os.remove') as mock_remove, \
         patch('os.rmdir') as mock_rmdir, \
         patch('theseus_insight.main.db.fetch_all_newsletters', return_value=mock_newsletters), \
         patch('theseus_insight.main.db.fetch_all_podcasts', return_value=mock_podcasts): # Ensure DB still returns it for lookup
        
        response_delete = await async_client.delete("/api/runs/2/artifact")

    assert response_delete.status_code == 200
    mock_exists.assert_called_with("data/podcasts/2/audio.mp3")
    mock_remove.assert_called_once_with("data/podcasts/2/audio.mp3")


# /api/podcasts/history & /api/podcasts/history/{podcast_id}
@pytest.mark.asyncio
async def test_get_podcast_history_and_detail(async_client: AsyncClient):
    mock_podcast_list = [
        {"id": 1, "title": "Podcast One", "date": "2023-02-01", "description": "Desc 1"},
        {"id": 2, "title": "Podcast Two", "date": "2023-02-15", "description": "Desc 2 snippet " * 20},
    ]
    mock_podcast_detail = {
        "id": 1, "title": "Podcast One", "date": "2023-02-01", "description": "Desc 1",
        "script": [{"text": "Hello", "speaker": "narrator"}]
    }

    with patch('theseus_insight.main.db.fetch_all_podcasts', return_value=mock_podcast_list) as mock_fetch_all, \
         patch('theseus_insight.main.db.fetch_podcast_by_id', return_value=mock_podcast_detail) as mock_fetch_by_id:
        
        # Test list
        response_list = await async_client.get("/api/podcasts/history")
        assert response_list.status_code == 200
        history_data = response_list.json()
        assert len(history_data) == 2
        assert history_data[0]["title"] == "Podcast Two" # Sorted by date desc
        assert history_data[1]["description_snippet"].endswith("...") # Check snippet
        mock_fetch_all.assert_called_once()

        # Test detail
        response_detail = await async_client.get("/api/podcasts/history/1")
        assert response_detail.status_code == 200
        detail_data = response_detail.json()
        assert detail_data["title"] == "Podcast One"
        assert len(detail_data["script"]) == 1
        mock_fetch_by_id.assert_called_once_with(1)


# /api/settings/send-test-email
@pytest.mark.asyncio
async def test_send_test_email_success(async_client: AsyncClient):
    mock_sender = "test_sender@example.com"
    mock_password = "test_password"
    
    with patch.dict(os.environ, {"GMAIL_SENDER_ADDRESS": mock_sender, "GMAIL_APP_PASSWORD": mock_password}), \
         patch('theseus_insight.main.GmailCommunication') as MockGmailComm:
        
        mock_gmail_instance = MagicMock()
        MockGmailComm.return_value = mock_gmail_instance

        response = await async_client.post("/api/settings/send-test-email")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    MockGmailComm.assert_called_once_with(
        sender_address=mock_sender,
        app_password=mock_password,
        receiver_address=mock_sender # Sends to self
    )
    mock_gmail_instance.compose_message.assert_called_once()
    mock_gmail_instance.send_email.assert_called_once()

@pytest.mark.asyncio
async def test_send_test_email_missing_creds(async_client: AsyncClient):
    # Ensure env vars are not set or are empty for this test
    with patch.dict(os.environ, {"GMAIL_SENDER_ADDRESS": "", "GMAIL_APP_PASSWORD": ""}):
        response = await async_client.post("/api/settings/send-test-email")
    assert response.status_code == 500 # Or specific error code if endpoint changes
    assert "Email credentials not configured" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_orchestration_settings_default_from_mocked_json(async_client: AsyncClient):
    default_orchestration_data = {
        "embedding_model": {"model_name": "embed_default", "model_type": "sentence-transformers"},
        "judge_model": {"model_name": "judge_default", "model_type": "ollama"},
        "content_extraction_model": {"model_name": "extract_default", "model_type": "ollama"},
        "newsletter_sections_model": {"model_name": "sections_default", "model_type": "ollama"},
        "newsletter_intro_model": {"model_name": "intro_default", "model_type": "gemini"},
        "podcast_model": {"model_name": "podcast_default", "model_type": "gemini"},
        "tts_model": {"tts_provider": "openai", "tts_model_name": "tts-1", "speaker_1_voice": "echo", "speaker_1_speed": 1.0, "speaker_2_voice": "onyx", "speaker_2_speed": 1.0}
    }
    # Mock that the orchestration.json exists and has specific content
    # This will be used during the app's lifespan startup if DB is empty for this setting
    with patch('os.path.exists') as mock_exists, \
         patch('builtins.open', mock_file_content(default_orchestration_data)) as mock_file:
        
        mock_exists.side_effect = lambda path: 'orchestration.json' in path # Only orchestration.json "exists"

        response = await async_client.get("/api/settings/orchestration")
    
    assert response.status_code == 200
    response_data = response.json()
    # Validate against Pydantic model (implicitly checks structure)
    parsed_config = OrchestrationConfig(**response_data)
    
    assert parsed_config.embedding_model.model_name == "embed_default"
    assert parsed_config.judge_model.model_name == "judge_default"
    assert parsed_config.podcast_model.model_name == "podcast_default"
    assert parsed_config.tts_model.tts_model_name == "tts-1"
    mock_file.assert_any_call(os.path.join(os.path.dirname(__file__), '../config/orchestration.json'), 'r')


@pytest.mark.asyncio
async def test_update_and_get_orchestration_settings(async_client: AsyncClient):
    new_config_data = {
        "embedding_model": {"model_name": "new_embed", "model_type": "openai"},
        "judge_model": {"model_name": "new_judge", "model_type": "anthropic"},
        "content_extraction_model": {"model_name": "new_extract", "model_type": "ollama"},
        "newsletter_sections_model": {"model_name": "new_sections", "model_type": "ollama"},
        "newsletter_intro_model": {"model_name": "new_intro", "model_type": "gemini"},
        "podcast_model": {"model_name": "new_podcast", "model_type": "gemini"},
        "tts_model": {"tts_provider": "elevenlabs", "tts_model_name": "v2", "speaker_1_voice": "adam", "speaker_1_speed": 1.1, "speaker_2_voice": "eve", "speaker_2_speed": 0.9}
    }
    # Mock open for the PUT operation to avoid actual file writes if the endpoint tries it
    with patch('builtins.open', mock_open()) as mock_put_file:
        put_response = await async_client.put("/api/settings/orchestration", json=new_config_data)
    assert put_response.status_code == 200
    assert put_response.json()["status"] == "success"

    get_response = await async_client.get("/api/settings/orchestration")
    assert get_response.status_code == 200
    retrieved_config = OrchestrationConfig(**get_response.json())
    
    assert retrieved_config.embedding_model.model_name == "new_embed"
    assert retrieved_config.judge_model.model_type == "anthropic"
    assert retrieved_config.tts_model.speaker_1_voice == "adam"


# /api/settings/arxiv-categories
@pytest.mark.asyncio
async def test_get_arxiv_categories_default(async_client: AsyncClient):
    response = await async_client.get("/api/settings/arxiv-categories")
    assert response.status_code == 200
    # Default values from ArxivCategoriesConfig model in main.py
    expected_defaults = ArxivCategoriesConfig(
        main_category="cs",
        filter_categories=["cs.ai", "cs.cl", "cs.lg", "cs.ir", "cs.ma", "cs.cv"]
    )
    assert ArxivCategoriesConfig(**response.json()) == expected_defaults

@pytest.mark.asyncio
async def test_update_and_get_arxiv_categories(async_client: AsyncClient):
    new_categories_data = {"main_category": "math", "filter_categories": ["math.AG", "math.CO"]}
    put_response = await async_client.put("/api/settings/arxiv-categories", json=new_categories_data)
    assert put_response.status_code == 200
    assert put_response.json()["status"] == "success"

    get_response = await async_client.get("/api/settings/arxiv-categories")
    assert get_response.status_code == 200
    assert ArxivCategoriesConfig(**get_response.json()) == ArxivCategoriesConfig(**new_categories_data)

@pytest.mark.asyncio
async def test_update_arxiv_categories_invalid_data(async_client: AsyncClient):
    invalid_data = {"main_category": "hep-th", "filter_categories": "not-a-list"} # filter_categories should be a list
    response = await async_client.put("/api/settings/arxiv-categories", json=invalid_data)
    assert response.status_code == 422 # Pydantic validation error


# /api/settings/research-interests
@pytest.mark.asyncio
async def test_get_research_interests_default_from_mocked_txt(async_client: AsyncClient):
    default_interests_text = "Default research interests from mocked file."
    # Mock that research_interests.txt exists and has specific content
    with patch('os.path.exists') as mock_exists, \
         patch('builtins.open', mock_file_content(default_interests_text)) as mock_file:
        
        mock_exists.side_effect = lambda path: 'research_interests.txt' in path

        response = await async_client.get("/api/settings/research-interests")

    assert response.status_code == 200
    assert response.json()["interests"] == default_interests_text
    mock_file.assert_any_call(os.path.join(os.path.dirname(__file__), '../config/research_interests.txt'), 'r')


@pytest.mark.asyncio
async def test_update_and_get_research_interests(async_client: AsyncClient):
    new_interests_data = {"interests": "Quantum computing and cryptography"}
    # Mock open for the PUT to avoid actual file writes
    with patch('builtins.open', mock_open()) as mock_put_file:
        put_response = await async_client.put("/api/settings/research-interests", json=new_interests_data)
    
    assert put_response.status_code == 200
    assert ResearchInterests(**put_response.json()) == ResearchInterests(**new_interests_data)

    get_response = await async_client.get("/api/settings/research-interests")
    assert get_response.status_code == 200
    assert ResearchInterests(**get_response.json()) == ResearchInterests(**new_interests_data)

@pytest.mark.asyncio
async def test_update_research_interests_invalid_data(async_client: AsyncClient):
    invalid_data = {"interests": ["this", "is", "a", "list"]} # interests should be a string
    response = await async_client.put("/api/settings/research-interests", json=invalid_data)
    assert response.status_code == 422


# /api/settings/email-recipients
@pytest.mark.asyncio
async def test_get_email_recipients_default(async_client: AsyncClient):
    response = await async_client.get("/api/settings/email-recipients")
    assert response.status_code == 200
    assert response.json() == {"recipients": []} # Default is an empty list

@pytest.mark.asyncio
async def test_update_and_get_email_recipients(async_client: AsyncClient):
    new_recipients_data = {"recipients": ["data@example.com", "science@example.org"]}
    put_response = await async_client.put("/api/settings/email-recipients", json=new_recipients_data)
    assert put_response.status_code == 200
    assert put_response.json()["status"] == "success"

    get_response = await async_client.get("/api/settings/email-recipients")
    assert get_response.status_code == 200
    assert EmailRecipients(**get_response.json()) == EmailRecipients(**new_recipients_data)

@pytest.mark.asyncio
async def test_update_email_recipients_invalid_email(async_client: AsyncClient):
    invalid_data = {"recipients": ["valid@example.com", "not-an-email"]}
    response = await async_client.put("/api/settings/email-recipients", json=invalid_data)
    assert response.status_code == 400 # As per endpoint's custom validation
    assert "Invalid email address: not-an-email" in response.json()["detail"]

@pytest.mark.asyncio
async def test_update_email_recipients_invalid_payload_type(async_client: AsyncClient):
    invalid_data = {"recipients": "iamastring@example.com"} # Should be a list
    response = await async_client.put("/api/settings/email-recipients", json=invalid_data)
    assert response.status_code == 422


# /api/settings/visualizer-settings
@pytest.mark.asyncio
async def test_get_visualizer_settings_default(async_client: AsyncClient):
    response = await async_client.get("/api/settings/visualizer-settings")
    assert response.status_code == 200
    # Check against default Pydantic model
    assert response.json() == VisualizerSettings().dict()


# /api/model-providers
@pytest.mark.asyncio
async def test_get_model_providers_empty_initially(async_client: AsyncClient):
    # The DB schema for model_providers might be empty or have defaults.
    # Assuming it's empty for a fresh in-memory DB unless lifespan adds some.
    # The lifespan in main.py does NOT add model providers.
    # PaperDatabase.get_model_providers() will return what's in the table.
    # For a fresh in-memory db, this table IS created but might be empty.
    # Let's check the DB schema for default providers.
    # `theseus_insight.data_model.data_handling.PaperDatabase.__init__` has:
    # CREATE TABLE IF NOT EXISTS model_providers (id INTEGER PRIMARY KEY, name TEXT UNIQUE)
    # INSERT OR IGNORE INTO model_providers (name) VALUES ('ollama'), ('openai'), ('anthropic'), ('gemini'), ('sentence-transformers'), ('huggingface');
    # So, there WILL be default providers.

    response = await async_client.get("/api/model-providers")
    assert response.status_code == 200
    providers = response.json()
    assert isinstance(providers, list)
    
    expected_providers = ["ollama", "openai", "anthropic", "gemini", "sentence-transformers", "huggingface"]
    assert len(providers) == len(expected_providers)
    
    provider_names_from_response = sorted([p["name"] for p in providers])
    assert provider_names_from_response == sorted(expected_providers)
    
    # Check structure of one item
    if providers:
        assert "id" in providers[0]
        assert "name" in providers[0]
        assert isinstance(providers[0]["id"], int)
        assert isinstance(providers[0]["name"], str)

        # Validate with Pydantic model
        for p_data in providers:
            ModelProvider(**p_data)
