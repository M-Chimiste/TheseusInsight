# Theseus Insight - Streamlit UI

A modern, interactive web interface for Theseus Insight, built with Streamlit and connected to the FastAPI backend.

## Features

- **Newsletter Builder**: Generate research newsletters from selected papers
- **Podcast Creator**: Convert research papers into audio podcasts
- **Paper Browser**: Browse and search research papers with filtering
- **Run History**: View and manage past runs
- **Settings**: Configure application settings and preferences

## Prerequisites

- Python 3.8+
- Theseus Insight FastAPI backend running (default: http://localhost:8000)
- Required Python packages (install via `pip install -r requirements.txt`)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd TheseusInsight/streamlit_app
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the `streamlit_app` directory with your configuration:
   ```env
   # API configuration
   API_BASE_URL=http://localhost:8000
   WS_BASE_URL=ws://localhost:8000
   
   # Optional: Authentication
   # AUTH_TOKEN=your-auth-token
   ```

## Running the Application

1. Start the FastAPI backend if it's not already running.

2. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

3. Open your browser to the URL shown in the terminal (usually http://localhost:8501).

## Development

To enable hot-reloading during development, use:

```bash
streamlit run app.py --server.runOnSave true
```

## Project Structure

```
streamlit_app/
├── app.py                 # Main application entry point
├── pages/                 # Page modules
│   ├── settings.py        # Settings page
│   ├── newsletter.py      # Newsletter builder
│   ├── podcast.py         # Podcast creator
│   ├── papers.py          # Paper browser
│   └── runs.py            # Run history
├── .env                   # Environment variables
└── requirements.txt       # Python dependencies
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | Base URL for the FastAPI backend | `http://localhost:8000` |
| `WS_BASE_URL` | WebSocket URL for real-time updates | `ws://localhost:8000` |
| `AUTH_TOKEN` | Optional authentication token | `None` |

## License

This project is licensed under the same license as the main Theseus Insight project.
