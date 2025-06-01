#!/usr/bin/env node

/**
 * Simple Working Build for Theseus Insight
 * 
 * This script creates a basic working Electron app with minimal complexity.
 * Use this to test core functionality before adding signing and packaging.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function log(message, level = 'info') {
  const icons = { info: '✅', warn: '⚠️', error: '❌' };
  console.log(`${icons[level]} ${message}`);
}

function execCommand(command, options = {}) {
  try {
    const result = execSync(command, { 
      stdio: options.silent ? 'pipe' : 'inherit',
      cwd: options.cwd || process.cwd(),
      ...options 
    });
    return result ? result.toString().trim() : '';
  } catch (error) {
    if (!options.allowFailure) {
      log(`Command failed: ${command}`, 'error');
      throw error;
    }
    return null;
  }
}

// Clean previous builds
log('Cleaning previous builds...');
if (fs.existsSync('dist')) {
  fs.rmSync('dist', { recursive: true, force: true });
}

// Install dependencies if needed
if (!fs.existsSync('node_modules')) {
  log('Installing dependencies...');
  execCommand('npm install');
}

// Build frontend
log('Building React frontend...');
const frontendDir = '../theseus-ui';
if (!fs.existsSync(path.join(frontendDir, 'node_modules'))) {
  log('Installing frontend dependencies...');
  execCommand('npm install', { cwd: frontendDir });
}
execCommand('npm run build', { cwd: frontendDir });

// Create basic package.json for build
const basicConfig = {
  name: "theseus-desktop",
  version: "0.9.4",
  main: "main.js",
  description: "Electron wrapper for Theseus Insight",
  author: "Theseus Insight Team",
  scripts: {
    "build:mac": "electron-builder --mac --dir"
  },
  build: {
    appId: "com.theseusinsight.desktop",
    productName: "Theseus Insight",
    directories: { output: "dist" },
    asar: false, // Keep disabled for easier debugging
    files: [
      "**/*",
      "!node_modules/*/{CHANGELOG.md,README.md,readme.md,example,examples,**/test/**}",
      "!unused"
    ],
    extraResources: [
      {
        from: "../",
        to: "app",
        filter: [
          "theseus_insight/**",
          "theseus-ui/dist/**",
          "config/**",
          "data/**",
          "run_theseus_insight.py",
          "requirements.txt"
        ]
      },
      { from: "env.template", to: ".env" }
    ],
    mac: {
      icon: "icons/mac/icon.icns",
      category: "public.app-category.productivity",
      target: [{ target: "dir" }]  // Build directory only, no DMG
    }
  },
  engines: { node: ">=20" },
  devDependencies: {
    "electron": "^31.0.0",
    "electron-builder": "^24.11.0"
  }
};

// Backup original package.json
const originalConfig = fs.readFileSync('package.json', 'utf8');

try {
  // Use basic config
  fs.writeFileSync('package.json', JSON.stringify(basicConfig, null, 2));
  
  // Build unsigned app directory
  log('Building unsigned Electron app...');
  execCommand('npm run build:mac');
  
  log('✅ Basic app built successfully!');
  
  // Find the built app
  const appPath = 'dist/mac/Theseus Insight.app';
  if (fs.existsSync(appPath)) {
    log(`App created at: ${appPath}`);
    
    // Install to Applications for testing
    const applicationsPath = '/Applications/Theseus Insight.app';
    if (fs.existsSync(applicationsPath)) {
      fs.rmSync(applicationsPath, { recursive: true, force: true });
    }
    
    execCommand(`cp -R "${appPath}" "/Applications/"`);
    log('App installed to Applications folder');
    
    // Try to launch it
    log('Testing app launch...');
    execCommand('open "/Applications/Theseus Insight.app"');
    log('App launched! Check if it works properly.');
    
  } else {
    log('App not found at expected location', 'error');
  }
  
} finally {
  // Restore original package.json
  fs.writeFileSync('package.json', originalConfig);
}

log('Simple build complete!'); 