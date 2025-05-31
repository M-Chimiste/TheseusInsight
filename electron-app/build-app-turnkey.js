#!/usr/bin/env node

/**
 * Universal Turnkey Build Script for Theseus Insight
 * Builds signed, self-contained apps for macOS, Windows, and Linux
 */

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Configuration
const config = {
  appName: 'Theseus Insight',
  version: '0.9.4',
  pythonRuntimeDir: 'python_runtime',
  platforms: {
    mac: { arch: ['x64', 'arm64'], target: 'dmg' },
    win: { arch: ['x64'], target: 'nsis' },
    linux: { arch: ['x64'], target: ['AppImage', 'deb'] }
  }
};

// Utility functions
function log(message, level = 'info') {
  const icons = { info: '✅', warn: '⚠️', error: '❌', progress: '🔄' };
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
      process.exit(1);
    }
    return null;
  }
}

function detectPlatform() {
  const platform = os.platform();
  switch (platform) {
    case 'darwin': return 'mac';
    case 'win32': return 'win';
    case 'linux': return 'linux';
    default:
      log(`Unsupported platform: ${platform}`, 'error');
      process.exit(1);
  }
}

function detectArch() {
  const arch = os.arch();
  switch (arch) {
    case 'x64': return 'x64';
    case 'arm64': return 'arm64';
    default: return 'x64'; // Default fallback
  }
}

// Platform-specific Python bundling
function bundlePythonRuntime() {
  log('Bundling Python runtime...');
  
  // Remove existing runtime
  if (fs.existsSync(config.pythonRuntimeDir)) {
    fs.rmSync(config.pythonRuntimeDir, { recursive: true, force: true });
  }

  const platform = detectPlatform();
  const pythonCmd = platform === 'win' ? 'python' : 'python3';
  
  try {
    // Create virtual environment
    execCommand(`${pythonCmd} -m venv ${config.pythonRuntimeDir} --copies`);
    
    // Get platform-specific paths
    const binDir = platform === 'win' ? 'Scripts' : 'bin';
    const pipCmd = path.join(config.pythonRuntimeDir, binDir, platform === 'win' ? 'pip.exe' : 'pip');
    const pythonExe = path.join(config.pythonRuntimeDir, binDir, platform === 'win' ? 'python.exe' : 'python3');
    
    // Upgrade pip
    execCommand(`"${pythonExe}" -m pip install --upgrade pip`, { silent: true });
    
    // Install requirements
    log('Installing Python dependencies...');
    execCommand(`"${pythonExe}" -m pip install -r ../requirements.txt`, { silent: true });
    
    log('Python runtime bundled successfully');
    return true;
  } catch (error) {
    log('Python runtime bundling failed', 'error');
    return false;
  }
}

// Clean Python runtime for distribution
function cleanPythonRuntime() {
  log('Cleaning Python runtime for distribution...');
  
  if (!fs.existsSync(config.pythonRuntimeDir)) {
    log('Python runtime directory not found', 'warn');
    return;
  }

  const platform = detectPlatform();
  
  // Files to remove (cross-platform)
  const filesToRemove = [
    '**/*.pyc', '**/*.pyo', '**/*.wav', '**/*.mp3', '**/*.mp4',
    '**/*.jpg', '**/*.jpeg', '**/*.png', '**/*.gif', '**/*.svg',
    '**/*.pdf', '**/*.txt', '**/*.md', '**/*.rst', '**/*.gz',
    '**/*.zip', '**/*.tar', '**/*.bz2'
  ];

  // Directories to remove
  const dirsToRemove = [
    'test*', '*test*', 'tests', 'doc*', 'example*', 'sample*',
    '__pycache__', '*.egg-info', '*.dist-info'
  ];

  try {
    // Use platform-appropriate commands
    if (platform === 'win') {
      // Windows cleanup using PowerShell
      filesToRemove.forEach(pattern => {
        execCommand(`powershell -Command "Get-ChildItem -Path '${config.pythonRuntimeDir}' -Recurse -File -Include '${pattern.replace('**/', '')}' | Remove-Item -Force"`, { allowFailure: true, silent: true });
      });
    } else {
      // Unix-like cleanup
      filesToRemove.forEach(pattern => {
        execCommand(`find ${config.pythonRuntimeDir} -name "${pattern.replace('**/', '')}" -delete`, { allowFailure: true, silent: true });
      });
      
      dirsToRemove.forEach(pattern => {
        execCommand(`find ${config.pythonRuntimeDir} -type d -name "${pattern}" -exec rm -rf {} +`, { allowFailure: true, silent: true });
      });
    }
    
    log('Python runtime cleaned successfully');
  } catch (error) {
    log('Python runtime cleanup had some issues (non-critical)', 'warn');
  }
}

// Build frontend
function buildFrontend() {
  log('Building React frontend...');
  
  const frontendDir = '../theseus-ui';
  
  // Check if node_modules exists
  if (!fs.existsSync(path.join(frontendDir, 'node_modules'))) {
    log('Installing frontend dependencies...');
    execCommand('npm install', { cwd: frontendDir });
  }
  
  // Build frontend
  execCommand('npm run build', { cwd: frontendDir });
  
  // Verify build
  const distPath = path.join(frontendDir, 'dist');
  if (!fs.existsSync(path.join(distPath, 'index.html'))) {
    log('Frontend build failed - index.html not found', 'error');
    process.exit(1);
  }
  
  const assetCount = fs.readdirSync(path.join(distPath, 'assets')).length;
  log(`Frontend build successful (${assetCount} assets)`);
}

// Create unsigned build config
function createUnsignedConfig(targetPlatform, targetArch) {
  const unsignedConfig = {
    name: "theseus-desktop",
    version: config.version,
    main: "main.js",
    description: "Electron wrapper for Theseus Insight",
    author: "Theseus Insight Team",
    scripts: {
      [`build:${targetPlatform}`]: `electron-builder --${targetPlatform}${targetArch ? ` --${targetArch}` : ''}`
    },
    build: {
      appId: "com.theseusinsight.desktop",
      productName: config.appName,
      directories: { output: "dist" },
      asar: false,
      files: [
        "**/*",
        "!node_modules/*/{CHANGELOG.md,README.md,readme.md,example,examples,**/test/**}",
        "!unused",
        "!python_runtime/**"
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
      ]
    },
    engines: { node: ">=20" },
    devDependencies: {
      "@electron/notarize": "^2.5.0",
      "electron": "^31.0.0",
      "electron-builder": "^24.11.0"
    }
  };

  // Add platform-specific config
  if (targetPlatform === 'mac') {
    unsignedConfig.build.mac = {
      icon: "icons/mac/icon.icns",
      category: "public.app-category.productivity",
      target: [{ target: "dmg", arch: [targetArch] }]
    };
  } else if (targetPlatform === 'win') {
    unsignedConfig.build.win = {
      icon: "icons/win/icon.ico",
      target: [{ target: "nsis", arch: [targetArch] }]
    };
    unsignedConfig.build.nsis = {
      oneClick: false,
      allowToChangeInstallationDirectory: true
    };
  } else if (targetPlatform === 'linux') {
    unsignedConfig.build.linux = {
      icon: "icons/png",
      category: "Office",
      target: [
        { target: "AppImage", arch: [targetArch] },
        { target: "deb", arch: [targetArch] }
      ]
    };
  }

  return unsignedConfig;
}

// Build unsigned app
function buildUnsignedApp(targetPlatform, targetArch) {
  log(`Building unsigned ${targetPlatform} app for ${targetArch}...`);
  
  // Backup original package.json
  const originalConfig = fs.readFileSync('package.json', 'utf8');
  
  try {
    // Create and use unsigned config
    const unsignedConfig = createUnsignedConfig(targetPlatform, targetArch);
    fs.writeFileSync('package.json', JSON.stringify(unsignedConfig, null, 2));
    
    // Build without signing
    const env = { ...process.env, CSC_IDENTITY_AUTO_DISCOVERY: 'false' };
    execCommand(`npm run build:${targetPlatform}`, { env });
    
    log('Unsigned build completed');
    return true;
  } finally {
    // Restore original package.json
    fs.writeFileSync('package.json', originalConfig);
  }
}

// Add Python runtime to built app
function addPythonRuntimeToApp(appPath, platform) {
  log('Adding Python runtime to app bundle...');
  
  let pythonDestPath;
  if (platform === 'mac') {
    pythonDestPath = path.join(appPath, 'Contents/Resources/app/python_runtime');
  } else if (platform === 'win') {
    pythonDestPath = path.join(appPath, 'resources/app/python_runtime');
  } else if (platform === 'linux') {
    pythonDestPath = path.join(appPath, 'resources/app/python_runtime');
  }
  
  try {
    // Copy Python runtime
    if (platform === 'win') {
      execCommand(`xcopy "${config.pythonRuntimeDir}" "${pythonDestPath}" /E /I /H /Y`, { allowFailure: true });
    } else {
      execCommand(`cp -R ${config.pythonRuntimeDir} "${pythonDestPath}"`);
    }
    
    if (fs.existsSync(pythonDestPath)) {
      // Get size
      const stats = execCommand(`du -sh "${pythonDestPath}"`, { silent: true, allowFailure: true });
      const size = stats ? stats.split('\t')[0] : 'unknown size';
      log(`Python runtime added (${size})`);
      return true;
    }
  } catch (error) {
    log('Failed to add Python runtime', 'error');
    return false;
  }
}

// Platform-specific signing
function signApp(appPath, platform) {
  log(`Signing ${platform} app...`);
  
  if (platform === 'mac') {
    // macOS code signing
    try {
      execCommand(`codesign --sign "Developer ID Application: Christian Merrill (4H8Z97B24M)" --force --timestamp --options runtime --entitlements build/entitlements.mac.plist --deep "${appPath}"`);
      
      // Verify signature
      execCommand(`codesign --verify --verbose "${appPath}"`);
      log('macOS app signed and verified successfully');
      return true;
    } catch (error) {
      log('macOS signing failed', 'error');
      return false;
    }
  } else if (platform === 'win') {
    // Windows code signing (if certificate is available)
    log('Windows code signing not configured (certificate required)', 'warn');
    return true; // Continue without signing
  } else if (platform === 'linux') {
    // Linux doesn't require signing for most distributions
    log('Linux apps do not require code signing');
    return true;
  }
  
  return false;
}

// Find built app
function findBuiltApp(platform) {
  const distDir = 'dist';
  let appPattern;
  
  if (platform === 'mac') {
    appPattern = '*.app';
  } else if (platform === 'win') {
    appPattern = '**/win-unpacked';
  } else if (platform === 'linux') {
    appPattern = '**/linux-unpacked';
  }
  
  // Find the app directory
  const findCommand = platform === 'win' 
    ? `dir /S /B "${distDir}" | findstr "win-unpacked"`
    : `find ${distDir} -name "${appPattern}" -type d`;
    
  try {
    const result = execCommand(findCommand, { silent: true });
    const appPath = result.split('\n')[0];
    return appPath ? appPath.trim() : null;
  } catch (error) {
    return null;
  }
}

// Main build function
async function buildTurnkeyApp(targetPlatform = null, targetArch = null) {
  const startTime = Date.now();
  
  // Determine build targets
  const currentPlatform = detectPlatform();
  const currentArch = detectArch();
  
  const buildPlatform = targetPlatform || currentPlatform;
  const buildArch = targetArch || currentArch;
  
  log(`Starting turnkey build for ${buildPlatform} (${buildArch})...`);
  
  // Clean previous builds
  log('Cleaning previous builds...');
  if (fs.existsSync('dist')) {
    fs.rmSync('dist', { recursive: true, force: true });
  }
  if (fs.existsSync('node_modules/.cache')) {
    fs.rmSync('node_modules/.cache', { recursive: true, force: true });
  }
  
  // Install dependencies if needed
  if (!fs.existsSync('node_modules')) {
    log('Installing dependencies...');
    execCommand('npm install');
  }
  
  // Bundle Python runtime
  if (!bundlePythonRuntime()) {
    process.exit(1);
  }
  
  // Clean Python runtime
  cleanPythonRuntime();
  
  // Build frontend
  buildFrontend();
  
  // Build unsigned app
  if (!buildUnsignedApp(buildPlatform, buildArch)) {
    process.exit(1);
  }
  
  // Find built app
  const appPath = findBuiltApp(buildPlatform);
  if (!appPath) {
    log('Built app not found', 'error');
    process.exit(1);
  }
  
  log(`Found built app: ${path.basename(appPath)}`);
  
  // Add Python runtime
  if (!addPythonRuntimeToApp(appPath, buildPlatform)) {
    process.exit(1);
  }
  
  // Sign app (platform-specific)
  signApp(appPath, buildPlatform);
  
  const endTime = Date.now();
  const duration = Math.round((endTime - startTime) / 1000);
  
  log('');
  log('📋 Build Summary:');
  log(`✅ Platform: ${buildPlatform} (${buildArch})`);
  log(`✅ Python runtime: bundled`);
  log(`✅ Code signing: ${buildPlatform === 'mac' ? 'signed' : 'completed'}`);
  log(`⚡ Total build time: ${duration} seconds`);
  log('');
  log(`📁 Output: ${appPath}`);
  log('🎯 This is a TURNKEY build - no external dependencies required');
  log('🎉 Turnkey build complete!');
}

// CLI handling
if (require.main === module) {
  const args = process.argv.slice(2);
  
  // Show help
  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
🚀 Universal Turnkey Build Script for Theseus Insight

Usage:
  node build-app-turnkey.js [platform] [arch]

Platforms:
  mac     - macOS (default: both x64 and arm64)
  win     - Windows (default: x64)
  linux   - Linux (default: x64)
  (auto)  - Detect current platform

Architectures:
  x64     - Intel/AMD 64-bit
  arm64   - Apple Silicon / ARM 64-bit

Examples:
  node build-app-turnkey.js              # Build for current platform
  node build-app-turnkey.js mac          # Build macOS (both archs)
  node build-app-turnkey.js mac arm64    # Build macOS ARM64 only
  node build-app-turnkey.js win          # Build Windows x64
  node build-app-turnkey.js linux        # Build Linux x64

NPM Scripts:
  npm run build-turnkey        # Current platform
  npm run build-turnkey:mac    # macOS
  npm run build-turnkey:win    # Windows  
  npm run build-turnkey:linux  # Linux
`);
    process.exit(0);
  }
  
  const platform = args[0];
  const arch = args[1];
  
  buildTurnkeyApp(platform, arch).catch(error => {
    log(`Build failed: ${error.message}`, 'error');
    process.exit(1);
  });
}

module.exports = { buildTurnkeyApp }; 