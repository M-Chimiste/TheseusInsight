# Electron App Development Guide

## The Problem

Previously, changes to the UI in `theseus-ui` weren't being reflected in the Electron app because:

1. Electron was loading `localhost:8000` (FastAPI backend)
2. FastAPI serves the **built/static** version from `theseus-ui/dist`
3. UI development happens in the **Vite dev server** (usually `localhost:5173`)

## The Solution

We've configured the Electron app to load different URLs based on the environment:

- **Development**: Loads `localhost:5173` (Vite dev server) for live UI updates
- **Production**: Loads `localhost:8000` (FastAPI with built UI) for full integration

## Development Workflow

### Option 1: Automated Setup (Recommended)

```bash
cd electron-app
npm run dev-full
```

This script:
- Starts the Vite dev server in the background
- Launches Electron in development mode
- Automatically points to the live development server
- Cleans up processes when you stop it

### Option 2: Manual Setup

1. **Start FastAPI backend** (in project root):
   ```bash
   uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Start Vite dev server** (in separate terminal):
   ```bash
   cd theseus-ui
   npm run dev
   ```

3. **Start Electron in development mode**:
   ```bash
   cd electron-app
   npm run dev
   ```

### Option 3: Individual Components

- **Electron only** (assumes dev server is running): `npm run dev`
- **Electron production mode**: `npm start`

## Building the Electron App

### Prerequisites

1. **Build the UI first**:
   ```bash
   cd theseus-ui
   npm run build
   ```

2. **Ensure config files exist**:
   - `config/orchestration.json`
   - `config/research_interests.txt`
   - `config/arxiv_taxonomy.json`

### Build Commands

```bash
cd electron-app

# Build for current platform
npm run build

# Build for specific platforms
npm run build:mac
npm run build:win
npm run build:linux
```

### What Gets Bundled

The build process includes:

1. **Python Backend**: All `theseus_insight/**` files
2. **Built UI**: `theseus-ui/dist/**` files
3. **Configuration**: `config/**` files
4. **Environment Template**: `env.template` → `.env` in the built app
5. **PostgreSQL Binaries**: Platform-specific PostgreSQL installation
6. **Python Dependencies**: As specified in `requirements.txt`

### Environment Configuration in Built App

The built Electron app includes:

1. **Default .env file**: Created from `env.template` with sensible defaults
2. **Path Resolution**: Automatic detection of packaged vs development environment
3. **Config Loading**: Uses environment variables to locate config files

### Troubleshooting Build Issues

1. **Settings page shows blank/grey box**:
   - Ensure `theseus-ui/dist` exists and contains built files
   - Check that config files are present in the `config/` directory
   - Verify the FastAPI backend can find config files using the path resolver

2. **Config files not found**:
   - Check that `THESEUS_CONFIG_DIR` environment variable is set correctly
   - Verify config files are included in the build (check `extraResources` in package.json)

3. **Python backend fails to start**:
   - Ensure Python dependencies are installed in the target environment
   - Check that the `start_backend.py` script has correct permissions
   - Verify `ELECTRON_IS_PACKAGED` environment variable is set

### Build Output

The built application will be in the `dist/` directory with:
- **macOS**: `.dmg` installer
- **Windows**: `.exe` installer via NSIS
- **Linux**: `.AppImage` and `.deb` packages

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Electron App  │───▶│  Vite Dev Server │───▶│  React UI Code  │
│  (localhost:-)  │    │ (localhost:5173) │    │  (theseus-ui)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼ /api/* requests
                       ┌──────────────────┐
                       │ FastAPI Backend  │
                       │ (localhost:8000) │
                       └──────────────────┘
```

## Configuration Details

- **Vite Proxy**: API calls (`/api/*`) are proxied to FastAPI backend
- **Environment Detection**: Uses `NODE_ENV=development` to determine URL
- **Hot Reload**: UI changes trigger automatic updates in Electron
- **Path Resolution**: Automatic detection of development vs packaged paths

## Troubleshooting

1. **Electron shows blank/error page**: 
   - Ensure Vite dev server is running on port 5173
   - Check if `NODE_ENV=development` is set

2. **API calls fail**:
   - Ensure FastAPI backend is running on port 8000
   - Check Vite proxy configuration

3. **Changes not reflecting**:
   - Verify you're using `npm run dev` (not `npm start`)
   - Check browser dev tools for errors
   - Restart Vite dev server if needed

4. **Built app settings page blank**:
   - Ensure UI was built before Electron build
   - Check that config files are bundled correctly
   - Verify environment variables are loaded properly

## Production Building

For production builds, the UI is built into `theseus-ui/dist` and served by FastAPI:

```bash
cd theseus-ui
npm run build
cd ../electron-app
npm start  # Uses production mode (port 8000)
``` 