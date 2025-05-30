const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const crypto = require('crypto');

// Add global error handling that shows errors to users
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  if (app && !app.isReady()) {
    // If app hasn't started yet, show error and quit
    dialog.showErrorBox('Startup Error', 
      `The application failed to start:\n\n${error.message}\n\nPlease check if all dependencies are installed.`);
    app.quit();
  }
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection:', reason);
});

// Improved environment loading with error checking
function loadEnvironmentFile() {
  const isPackaged = app.isPackaged;
  let envPath;
  
  if (isPackaged) {
    envPath = path.join(process.resourcesPath, '.env');
  } else {
    envPath = path.join(__dirname, '..', '.env');
  }
  
  console.log(`Looking for .env at: ${envPath}`);
  
  if (fs.existsSync(envPath)) {
    console.log('Loading environment file...');
    try {
      const envContent = fs.readFileSync(envPath, 'utf8');
      const envLines = envContent.split('\n');
      
      envLines.forEach(line => {
        line = line.trim();
        if (line && !line.startsWith('#') && line.includes('=')) {
          const [key, ...valueParts] = line.split('=');
          const value = valueParts.join('=');
          if (key && !process.env[key]) {
            process.env[key] = value;
          }
        }
      });
    } catch (error) {
      console.error('Error loading .env file:', error);
    }
  } else {
    console.log('No .env file found');
  }
}

// More robust Python detection
function findPythonInterpreter() {
  const candidates = [
    // System Python
    'python3',
    'python',
    // Common macOS paths
    '/usr/bin/python3',
    '/usr/local/bin/python3',
    '/opt/homebrew/bin/python3',
    // Look in PATH
    which('python3'),
    which('python')
  ].filter(Boolean); // Remove null/undefined values

  for (const candidate of candidates) {
    try {
      const result = spawnSync(candidate, ['--version'], { encoding: 'utf8' });
      if (result.status === 0) {
        const version = result.stdout || result.stderr;
        console.log(`Found Python: ${candidate} (${version.trim()})`);
        return candidate;
      }
    } catch (error) {
      // Continue trying other candidates
    }
  }

  return null;
}

// Simple which implementation
function which(command) {
  try {
    const result = spawnSync('which', [command], { encoding: 'utf8' });
    if (result.status === 0) {
      return result.stdout.trim();
    }
  } catch (error) {
    // Command not found or which command doesn't exist
  }
  return null;
}

// Check if required Python packages are available
function checkPythonDependencies(pythonCmd) {
  const requiredPackages = ['fastapi', 'uvicorn', 'psycopg2'];
  
  for (const pkg of requiredPackages) {
    try {
      const result = spawnSync(pythonCmd, ['-c', `import ${pkg.replace('-', '_')}`], 
        { encoding: 'utf8' });
      if (result.status !== 0) {
        console.error(`Missing Python package: ${pkg}`);
        return false;
      }
    } catch (error) {
      console.error(`Error checking package ${pkg}:`, error);
      return false;
    }
  }
  
  console.log('All required Python packages found');
  return true;
}

// More robust backend startup
function startBackend() {
  const isPackaged = app.isPackaged;
  let projectRoot;
  
  if (isPackaged) {
    projectRoot = path.join(process.resourcesPath, 'app');
  } else {
    projectRoot = path.join(__dirname, '..');
  }
  
  console.log(`Project root: ${projectRoot}`);
  console.log(`Is packaged: ${isPackaged}`);
  
  // Find Python interpreter
  const pythonCmd = findPythonInterpreter();
  if (!pythonCmd) {
    const error = 'Python interpreter not found. Please install Python 3.8 or later.';
    console.error(error);
    dialog.showErrorBox('Python Not Found', 
      `${error}\n\nYou can download Python from https://python.org`);
    app.quit();
    return null;
  }
  
  // Check if required packages are installed
  if (!checkPythonDependencies(pythonCmd)) {
    const error = 'Required Python packages are missing.';
    console.error(error);
    dialog.showErrorBox('Missing Dependencies', 
      `${error}\n\nPlease install the required packages:\npip install fastapi uvicorn psycopg2-binary`);
    app.quit();
    return null;
  }
  
  // Determine startup args
  let startupArgs;
  if (isPackaged) {
    // Use the bundled script
    const scriptPath = path.join(__dirname, 'start_backend.py');
    if (fs.existsSync(scriptPath)) {
      startupArgs = [scriptPath];
    } else {
      // Fallback to direct module execution
      startupArgs = ['-m', 'uvicorn', 'theseus_insight.main:app', '--host', '0.0.0.0', '--port', '8000'];
    }
  } else {
    startupArgs = ['-m', 'uvicorn', 'theseus_insight.main:app', '--host', '0.0.0.0', '--port', '8000'];
  }
  
  console.log(`Starting backend with: ${pythonCmd} ${startupArgs.join(' ')}`);
  
  try {
    const pythonProcess = spawn(pythonCmd, startupArgs, {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONPATH: projectRoot,
        ELECTRON_IS_PACKAGED: isPackaged ? 'true' : 'false',
        ELECTRON_RESOURCES_PATH: isPackaged ? process.resourcesPath : ''
      }
    });

    pythonProcess.on('error', (error) => {
      console.error('Failed to start Python backend:', error);
      dialog.showErrorBox('Backend Error', 
        `Failed to start the application backend:\n\n${error.message}`);
      app.quit();
    });

    pythonProcess.on('exit', (code, signal) => {
      console.log(`Backend exited with code ${code}, signal ${signal}`);
      if (code !== 0 && code !== null) {
        dialog.showErrorBox('Backend Crashed', 
          `The application backend stopped unexpectedly (code: ${code})`);
      }
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log(`backend: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`backend err: ${data}`);
    });

    return pythonProcess;
    
  } catch (error) {
    console.error('Error spawning Python process:', error);
    dialog.showErrorBox('Startup Error', 
      `Failed to start backend process:\n\n${error.message}`);
    app.quit();
    return null;
  }
}

// Simplified window creation
function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    icon: getAppIcon(),
    title: 'Theseus Insight',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // Show loading page first
  win.loadURL('data:text/html,<html><body style="background:#1976d2;color:white;font-family:Arial;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;"><div style="text-align:center;"><h1>Theseus Insight</h1><p>Starting up...</p></div></body></html>');
  
  win.once('ready-to-show', () => {
    win.show();
  });

  // Try to load the main app after a delay
  setTimeout(() => {
    const appUrl = 'http://localhost:8000';
    console.log(`Loading app at: ${appUrl}`);
    
    win.loadURL(appUrl).catch((error) => {
      console.error('Failed to load app:', error);
      // Show error page
      win.loadURL(`data:text/html,<html><body style="background:#f44336;color:white;font-family:Arial;padding:20px;"><h1>Connection Error</h1><p>Could not connect to the application server.</p><p>Please check that all dependencies are installed and try restarting the application.</p><p>Error: ${error.message}</p></body></html>`);
    });
  }, 3000); // Give backend time to start

  return win;
}

function getAppIcon() {
  const platform = process.platform;
  switch (platform) {
    case 'win32':
      return path.join(__dirname, 'icons', 'win', 'icon.ico');
    case 'darwin':
      return path.join(__dirname, 'icons', 'mac', 'icon.icns');
    default:
      return path.join(__dirname, 'icons', 'png', '512x512.png');
  }
}

// Initialize app with better error handling
loadEnvironmentFile();

let pythonProcess = null;

app.whenReady().then(() => {
  console.log('Electron app ready, starting backend...');
  
  try {
    pythonProcess = startBackend();
    createWindow();
  } catch (error) {
    console.error('Error during app initialization:', error);
    dialog.showErrorBox('Initialization Error', 
      `Failed to initialize the application:\n\n${error.message}`);
    app.quit();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (pythonProcess) {
    console.log('Terminating backend process...');
    pythonProcess.kill('SIGTERM');
  }
  
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (pythonProcess) {
    console.log('Terminating backend process before quit...');
    pythonProcess.kill('SIGTERM');
  }
}); 