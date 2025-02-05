# PaperPal Podcast Generator UI – Product Requirements Document (PRD)

## 1. Overview

The PaperPal Podcast Generator UI is a multi-page desktop/web application that allows users to generate, edit, and visualize podcasts derived from academic or other documents. The application leverages PDF parsing, text generation, and TTS (Text-to-Speech) to create podcast audio (and optionally video) content. In addition, it provides an interface for editing the generated script and regenerating videos from existing audio files using a neon matrix visualizer.

## 2. Objectives

- **Editing an Existing Podcast Script:**  
  - Allow users to load a JSON artifact representing a podcast script.
  - Enable users to add, delete, and rearrange (via drag and drop) individual dialogue items on a per-speaker basis.
  - Provide inline editing (text is edited directly in the list) and the ability to insert new speakers or lines between existing items.
  - *Note:* Preview will be text-only; no audio playback is required in the editor.

- **Generating a New Podcast:**  
  - Allow users to supply a mix of PDF URLs and local PDF files (and other supported file types, as the underlying parser supports DOCX, plain text, etc.).
  - Process inputs to extract text, generate dialogue through TTS and text generation, and produce a final podcast.
  - Output can be either audio-only or audio with video (visualizer).
  - Support multiple audio formats for output: `wav`, `mp3`, `ogg`, `flac`.

- **Regenerating a Visualizer Video from Audio:**  
  - Enable users to upload an existing audio file (supporting formats: `wav`, `mp3`, `ogg`, `flac`).
  - Regenerate a video using the neon wave visualizer with configurable settings.
  - Video output is always in MP4 format with a dropdown to select resolution (720p, 1080p, or 4K; default to 1080p).

---

## 3. User Workflows & Journeys

### 3.1 Editing an Existing Podcast Script

- **Entry Point:**  
  - User selects “Edit Existing Podcast Script” from the landing/dashboard page.
  
- **Process:**  
  - The user loads a JSON artifact representing the podcast script.
  - The script is rendered as a list of dialogue items, segregated by speaker.
  - The user can:
    - Edit text inline.
    - Add or delete dialogue lines.
    - Drag and drop items to rearrange them.
    - Reassign dialogue items between speakers.
    - Insert new speakers and dialogue items between existing lines.
  
- **Output:**  
  - The edited JSON artifact can be saved to disk or to a local SQLite database.

---

### 3.2 Generating a New Podcast

- **Entry Point:**  
  - User selects “New Podcast Generator” from the landing/dashboard page.

- **Process:**  
  - **File Input:**  
    - The user provides a list of PDF URLs and/or selects local PDF files via a file selector.
    - The file selector should support any file types that the parser supports (e.g., DOCX, plain text) without additional configuration.
  
  - **Configuration Settings:**  
    - Users can choose to generate audio only or audio with video.
    - **Output Options:**  
      - Audio output format: dropdown selection for `wav`, `mp3`, `ogg`, or `flac` (default settings read from configuration).
      - Video resolution: dropdown selection between 720p, 1080p (default), and 4K.
    - **TTS Settings:**  
      - Expose options to select TTS provider (kokoro, polly, or openai).
      - Allow configuration of voice and speed for each speaker.
      - Default values are loaded from a `configuration.json` file, with an “Advanced Settings” panel exposing all configurable options.
    - **Visualizer Settings (if video output is selected):**  
      - Basic settings: color pickers for matrix head/tail and wave colors, and resolution.
      - Advanced settings: FPS, matrix parameters (matrix count, character size, head step time, random jitter, fade time, etc.), and other detailed visualizer configurations.
  
  - **Backend Processing:**  
    - The system processes the PDFs, extracts the text, and uses text generation/TTS to create dialogue segments.
    - Each dialogue segment is converted to audio based on the TTS configuration.
    - All segments are merged to produce the final audio output.
    - If video is requested, the visualizer uses the generated audio and the user-defined parameters to create an MP4 video.
  
- **Output:**  
  - A final podcast file (audio in the chosen format and, optionally, video in MP4) is generated.
  - The transcript and script JSON artifact are also produced for further editing if needed.

---

### 3.3 Regenerating a Visualizer Video from Existing Audio

- **Entry Point:**  
  - User selects “Regenerate Visualizer Video” from the landing/dashboard page.

- **Process:**  
  - The user uploads an audio file (supporting `wav`, `mp3`, `ogg`, and `flac`).
  - The user can configure visualizer settings via a basic panel (colors, resolution) and access an “Advanced Settings” panel for more detailed options.
  - The system processes the audio and regenerates an MP4 video using the neon wave visualizer.
  
- **Output:**  
  - An MP4 video file is generated with the chosen resolution (default 1080p).

---

## 4. Functional Requirements

### 4.1 General UI/UX

- **Landing/Dashboard Page:**
  - Displays recent projects or an introduction.
  - Provides navigation to:
    - Podcast Script Editor
    - New Podcast Generator
    - Visualizer Regeneration Page
- **Theme and Appearance:**
  - Modern and clean design.
  - Light/Dark mode should follow system settings by default with an option for user override.
  - Mobile responsiveness is not a priority.

- **Status and Feedback:**
  - A status bar and progress indicators are provided during long-running operations (PDF processing, TTS conversion, video generation).
  - Full logging is available for error messages and operational details.

---

### 4.2 Podcast Script Editor

- **Core Features:**
  - Load and display a JSON artifact representing a podcast script.
  - Inline editing of dialogue items.
  - Add/delete dialogue items.
  - Drag and drop for rearrangement, including reassigning dialogue items between speakers.
  - Insert new speakers and new lines between existing items.
  
- **Output:**
  - Save the edited script to a JSON file and/or persist in a local SQLite database.
  
---

### 4.3 New Podcast Generator

- **File Input:**
  - Support for uploading local PDF files and entering PDF URLs.
  - Use a file selector that supports additional formats (e.g., DOCX, plain text) as supported by the parser.
  
- **Configuration Options:**
  - **Output Selection:**
    - Audio formats: `wav`, `mp3`, `ogg`, `flac`.
    - Video resolution: dropdown for 720p, 1080p (default), or 4K.
  - **TTS Settings:**
    - Provider selection (kokoro, polly, openai).
    - Voice and speed settings per speaker.
    - Defaults loaded from `configuration.json` with an “Advanced Settings” toggle to expose all parameters.
  - **Visualizer Settings (if applicable):**
    - Basic: color pickers for matrix head/tail and wave colors, resolution.
    - Advanced: additional settings such as FPS, matrix parameters, jitter, fade times, etc.
  
- **Processing:**
  - Parse PDFs to extract text.
  - Generate dialogue using text generation and TTS.
  - Merge audio segments.
  - Generate video if requested using the visualizer.
  
- **Output:**
  - Final audio file (in chosen format).
  - Final video file (MP4) if video was selected.
  - Transcript and JSON artifact of the podcast script.
  
---

### 4.4 Visualizer Regeneration

- **File Input:**
  - Upload an existing audio file (formats: `wav`, `mp3`, `ogg`, `flac`).
  
- **Configuration Options:**
  - Basic visualizer settings (colors via color pickers, resolution).
  - Advanced settings for detailed visualizer configuration.
  
- **Processing:**
  - Use the provided audio to regenerate an MP4 video using the neon visualizer.
  
- **Output:**
  - MP4 video file generated with selected resolution (default 1080p).

---

## 5. Technical & Deployment Considerations

### 5.1 Tech Stack

- **Frontend:**
  - Preferably a rich UI framework (e.g., React) to provide a modern, responsive experience.
  - Avoid prototype frameworks such as Streamlit or Gradio.
- **Backend:**
  - Python-based backend that exposes RESTful APIs to the frontend.
  - Leverage the existing Python codebase for PDF processing, TTS, text generation, and visualizer functionality.
  
### 5.2 Deployment

- **Model:**
  - The application should run locally.
  - Deployment options include:
    - A Dockerized web application.
    - An Electron-based desktop application.
  - Must support loading environment variables from a `.env` file (for API keys, provider URLs, etc.).
  
### 5.3 Persistence

- **Storage:**
  - Use a SQLite database for:
    - Storing user sessions and project data.
    - Saving generated files and JSON artifacts.
  - Allow users to save progress and automatically surface the most recent entry upon returning.

---

## 6. Future Considerations

- **User Accounts & Authentication:**  
  - Not required for now; the application is designed for a single local user.
  
- **Social Sharing / Integration:**  
  - Integration with platforms such as YouTube is already part of the backend.  
  - The UI may include toggles to enable or disable such integrations as needed.
  
- **Additional File Types / Enhancements:**  
  - As the parser already supports additional formats, the UI should remain flexible to support these without major changes.
  
- **Extended TTS and Visualizer Customization:**  
  - Further enhancements may include more granular presets and user-defined configurations in future releases.

---

## 7. Open Questions & Next Steps

- **UI Framework Decision:**  
  - Confirm if React (or another rich web framework) is acceptable, or if further research into alternatives is needed.
- **Deployment Model:**  
  - Decide between Docker and Electron based on ease-of-use and performance considerations.
- **API Exposure:**  
  - Finalize the RESTful API endpoints for interaction between the frontend and Python backend.