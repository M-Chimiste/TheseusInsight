# Theseus Insight Desktop

This directory provides an Electron wrapper that bundles the Python backend and a local PostgreSQL database using the `pgvector` extension.

## Local Setup

1. Install Node.js 20 or newer.
2. From this folder run `npm install` to install Electron dependencies.
3. Ensure the `postgres` binaries are available under `electron-app/postgres/<platform>/bin`. These are not included in the repository – copy prebuilt binaries for your OS.
4. Run `npm start` to launch the desktop application.

The application starts PostgreSQL on port **55432** to avoid conflicts with any existing database server.

## Building Distributables

`electron-builder` is used for packaging. Use the commands below for different platforms.

### macOS

```bash
npm run build -- -m
```
This produces a `.dmg` installer in the `dist/` directory.

### Linux

```bash
npm run build -- -l
```
Generates a `.AppImage` file.

### Windows

```bash
npm run build -- -w
```
Creates a Windows installer (`.exe`).

Ensure that Python and the PostgreSQL binaries are included in the `extraResources` section of `package.json` so they are packaged with the app.
