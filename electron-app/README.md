# Theseus Insight Desktop

This directory provides an Electron wrapper that bundles the Python backend and a local SQLite database using the `sqlite-vec` extension for vector search.

## Local Setup

1. Install **Node.js 20** or newer.
2. Run `npm install` to install Electron dependencies.
3. Run `npm start` to launch the desktop application.

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

The Electron package includes a bundled Python runtime and all required dependencies,
including the `sqlite-vec` extension. Ensure the `python_runtime` directory is
listed in the `extraResources` section of `package.json` so it is packaged with
the application.
