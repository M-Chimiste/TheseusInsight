const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const crypto = require('crypto');

// Load environment variables from bundled .env file in production
function loadEnvironmentFile() {
  const isPackaged = app.isPackaged;
  let envPath;
  
  if (isPackaged) {
    // In packaged app, look for .env in resources
    envPath = path.join(process.resourcesPath, '.env');
  } else {
    // In development, look for .env in project root
    envPath = path.join(__dirname, '..', '.env');
  }
  
  console.log(`Looking for .env at: ${envPath}`);
  
  if (fs.existsSync(envPath)) {
    console.log('Loading environment file...');
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
  } else {
    console.log('No .env file found');
  }
}

// Generate or load APP_SECRET_KEY
function ensureAppSecretKey() {
  const secretKeyPath = path.join(app.getPath('userData'), 'app_secret.key');
  
  try {
    // Check if secret key file already exists
    if (fs.existsSync(secretKeyPath)) {
      const existingKey = fs.readFileSync(secretKeyPath, 'utf8').trim();
      if (existingKey && existingKey.length > 0) {
        console.log('Using existing APP_SECRET_KEY from user data');
        process.env.APP_SECRET_KEY = existingKey;
        return existingKey;
      }
    }
    
    // Generate new secure random key
    const newSecretKey = crypto.randomBytes(32).toString('hex');
    
    // Ensure userData directory exists
    const userDataDir = app.getPath('userData');
    if (!fs.existsSync(userDataDir)) {
      fs.mkdirSync(userDataDir, { recursive: true });
    }
    
    // Save the new key
    fs.writeFileSync(secretKeyPath, newSecretKey, { mode: 0o600 }); // Readable only by owner
    process.env.APP_SECRET_KEY = newSecretKey;
    
    console.log(`Generated new APP_SECRET_KEY and saved to: ${secretKeyPath}`);
    return newSecretKey;
    
  } catch (error) {
    console.error('Error managing APP_SECRET_KEY:', error);
    // Fallback to a session-only key if file operations fail
    const fallbackKey = crypto.randomBytes(32).toString('hex');
    process.env.APP_SECRET_KEY = fallbackKey;
    console.warn('Using session-only APP_SECRET_KEY due to file access error');
    return fallbackKey;
  }
}

// Load environment before anything else
loadEnvironmentFile();

// Ensure APP_SECRET_KEY is set before starting any services
ensureAppSecretKey();

// Add global exception handlers
process.on('uncaughtException', (error) => {
  if (error.code === 'EPIPE') {
    console.warn('Ignoring EPIPE error (broken pipe):', error.message);
    return;
  }
  console.error('Uncaught Exception:', error);
  // Don't exit on EPIPE errors, but log others
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

let pythonProcess = null;
// let postgresProcess = null; // PostgreSQL process no longer needed
let tempFiles = []; // Track temp files for cleanup

function createWindow () {
  // Get platform-specific icon
  function getAppIcon() {
    const platform = process.platform;
    switch (platform) {
      case 'win32':
        return path.join(__dirname, 'icons', 'win', 'icon.ico');
      case 'darwin':
        return path.join(__dirname, 'icons', 'mac', 'icon.icns');
      case 'linux':
        return path.join(__dirname, 'icons', 'png', '512x512.png');
      default:
        return path.join(__dirname, 'icons', 'png', '512x512.png');
    }
  }

  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    icon: getAppIcon(),
    title: 'Theseus Insight',
    show: false, // Don't show until ready
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // Add error handling and debugging for loading issues
  win.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    console.error(`Failed to load page: ${errorCode} - ${errorDescription} (URL: ${validatedURL})`);
    
    // Show user-friendly error page
    const errorHtml = `
      <html>
        <head>
          <title>Theseus Insight - Loading Error</title>
        </head>
        <body style="font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; color: #333;">
          <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h1 style="color: #d32f2f; margin-bottom: 20px;">🚫 Connection Error</h1>
            <p><strong>The application could not load the user interface.</strong></p>
            <p>This usually happens when:</p>
            <ul style="margin: 20px 0;">
              <li>The backend server is still starting up</li>
              <li>Required dependencies are missing</li>
              <li>The frontend files are not properly bundled</li>
            </ul>
            <p><strong>Error Details:</strong></p>
            <p style="background: #f5f5f5; padding: 10px; border-radius: 4px; font-family: monospace;">
              Code: ${errorCode}<br>
              Description: ${errorDescription}<br>
              URL: ${validatedURL}
            </p>
            <p style="margin-top: 30px;">
              <strong>💡 Troubleshooting:</strong><br>
              1. Wait 30 seconds and try restarting the app<br>
              2. Check if all Python dependencies are installed<br>
              3. Ensure the application data directory is accessible<br>
              4. Contact support if the issue persists
            </p>
          </div>
        </body>
      </html>
    `;
    win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(errorHtml)}`);
  });

  win.webContents.on('did-finish-load', () => {
    console.log('Page loaded successfully');
  });

  win.webContents.on('dom-ready', () => {
    console.log('DOM ready');
  });

  // Add console message handler for debugging
  win.webContents.on('console-message', (event, level, message, line, sourceId) => {
    console.log(`Console [${level}]: ${message}`);
  });

  // Show window when ready to prevent flash
  win.once('ready-to-show', () => {
    win.show();
    
    // Focus the window on macOS
    if (process.platform === 'darwin') {
      win.focus();
    }
  });

  // Open DevTools for debugging in development
  if (process.env.NODE_ENV === 'development') {
    win.webContents.openDevTools();
  }

  // Show initial loading screen
  const loadingHtml = `
    <html>
      <head>
        <title>Theseus Insight</title>
      </head>
      <body style="font-family: Arial, sans-serif; background: linear-gradient(135deg, #1976d2, #42a5f5); color: white; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh;">
        <div style="text-align: center; padding: 40px;">
          <h1 style="margin-bottom: 20px; font-size: 2.5em; font-weight: 300;">Theseus Insight</h1>
          <div style="margin: 20px 0;">
            <div style="display: inline-block; width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: white; animation: spin 1s ease-in-out infinite;"></div>
          </div>
          <p style="font-size: 1.1em; opacity: 0.9;">Starting services...</p>
          <style>
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          </style>
        </div>
      </body>
    </html>
  `;

  win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(loadingHtml)}`);

  // Attempt to load the actual application after services start
  function tryLoadApp(attempts = 0) {
    const maxAttempts = 15; // 30 seconds total (2 second intervals)
    const appUrl = process.env.NODE_ENV === 'development' ? 'http://localhost:5173' : 'http://localhost:8000';
    
    console.log(`Attempt ${attempts + 1}/${maxAttempts}: Loading app at ${appUrl}`);
    
    win.loadURL(appUrl).catch((error) => {
      console.error(`Load attempt ${attempts + 1} failed:`, error.message);
      
      if (attempts < maxAttempts - 1) {
        // Update loading screen with progress
        const progressHtml = `
          <html>
            <head>
              <title>Theseus Insight</title>
            </head>
            <body style="font-family: Arial, sans-serif; background: linear-gradient(135deg, #1976d2, #42a5f5); color: white; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh;">
              <div style="text-align: center; padding: 40px;">
                <h1 style="margin-bottom: 20px; font-size: 2.5em; font-weight: 300;">Theseus Insight</h1>
                <div style="margin: 20px 0;">
                  <div style="display: inline-block; width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: white; animation: spin 1s ease-in-out infinite;"></div>
                </div>
                <p style="font-size: 1.1em; opacity: 0.9;">Starting services... (${attempts + 1}/${maxAttempts})</p>
                <p style="font-size: 0.9em; opacity: 0.7;">Please wait while the backend initializes</p>
                <style>
                  @keyframes spin {
                    to { transform: rotate(360deg); }
                  }
                </style>
              </div>
            </body>
          </html>
        `;
        win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(progressHtml)}`);
        
        setTimeout(() => tryLoadApp(attempts + 1), 2000);
      } else {
        // Final failure - show detailed error
        const finalErrorHtml = `
          <html>
            <head>
              <title>Theseus Insight - Connection Failed</title>
            </head>
            <body style="font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; color: #333;">
              <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h1 style="color: #d32f2f; margin-bottom: 20px;">⚠️ Failed to Connect</h1>
                <p><strong>The application could not connect to the backend server after ${maxAttempts} attempts.</strong></p>
                
                <h3 style="color: #1976d2; margin-top: 30px;">Possible Solutions:</h3>
                <ol style="line-height: 1.6;">
                  <li><strong>Restart the application</strong> - Close and reopen Theseus Insight</li>
                  <li><strong>Check dependencies</strong> - Ensure Python and required packages are installed</li>
                  <li><strong>Check database file</strong> - Ensure the database file in the application data directory is accessible and not corrupted.</li>
                  <li><strong>Run debug script</strong> - Use the debug-app.sh script for detailed diagnostics</li>
                </ol>
                
                <h3 style="color: #1976d2; margin-top: 30px;">Debug Information:</h3>
                <div style="background: #f5f5f5; padding: 15px; border-radius: 4px; font-family: monospace; font-size: 0.9em;">
                  <strong>Target URL:</strong> ${appUrl}<br>
                  <strong>Environment:</strong> ${process.env.NODE_ENV || 'production'}<br>
                  <strong>Platform:</strong> ${process.platform}<br>
                  <strong>Packaged:</strong> ${app.isPackaged}<br>
                  <strong>Last Error:</strong> ${error.message}
                </div>
                
                <div style="margin-top: 30px; padding: 15px; background: #e3f2fd; border-left: 4px solid #1976d2; border-radius: 4px;">
                  <strong>💡 Need Help?</strong><br>
                  If this problem persists, please check the console logs or run the app from Terminal to see detailed error messages.
                </div>
              </div>
            </body>
          </html>
        `;
        win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(finalErrorHtml)}`);
      }
    });
  }

  // Start loading attempts after a brief delay
  setTimeout(() => tryLoadApp(), 3000);
  
  return win;
}

// function startPostgres() { ... } // Removed entire startPostgres function

function initializeDatabase() {
  return new Promise((resolve, reject) => {
    console.log('Ensuring user data directory exists for SQLite database...');
    try {
      const userDataPath = app.getPath('userData');
      if (!fs.existsSync(userDataPath)) {
        fs.mkdirSync(userDataPath, { recursive: true });
      }
      console.log('User data directory ensured.');
      resolve();
    } catch (error) {
      console.error('Failed to ensure user data directory:', error);
      reject(error);
    }
  });
}

function startBackend() {
  // Determine if we're running in a built app or development
  const isPackaged = app.isPackaged;
  let projectRoot;
  
  if (isPackaged) {
    // In packaged app, resources are in app.getPath('resources')
    projectRoot = path.join(process.resourcesPath, 'app');
  } else {
    // In development, use the parent directory
    projectRoot = path.join(__dirname, '..');
  }
  
  console.log(`Project root: ${projectRoot}`);
  console.log(`Is packaged: ${isPackaged}`);

  function findPythonCommand() {
    try {
      spawnSync('python3', ['--version']);
      return 'python3';
    } catch (e) {
      try {
        spawnSync('python', ['--version']);
        return 'python';
      } catch (e2) {
        console.error('Neither python3 nor python found in PATH.');
        return null; // Or handle error appropriately
      }
    }
  }

  let pythonCmd = findPythonCommand();

  if (!pythonCmd) {
    console.error('No Python interpreter found. The backend cannot be started.');
    // Optionally, you could show an error dialog to the user or quit the app
    // For now, just log the error and the backend won't start.
    return;
  }

  console.log(`Using Python interpreter: ${pythonCmd}`);

  // Choose the startup method based on packaging
  let startupArgs;
  if (isPackaged) {
    // Try the robust backend script first
    const robustScript = path.join(__dirname, 'start_backend_robust.py');
    const fallbackScript = path.join(__dirname, 'start_backend.py');
    
    let scriptToUse = robustScript;
    if (!fs.existsSync(robustScript)) {
      console.log('Robust backend script not found, using fallback');
      scriptToUse = fallbackScript;
    }
    
    // Extract the script from asar to temp location
    const tempScript = path.join(os.tmpdir(), 'theseus_start_backend.py');
    
    try {
      const scriptContent = fs.readFileSync(scriptToUse, 'utf8');
      fs.writeFileSync(tempScript, scriptContent, { mode: 0o755 });
      console.log(`Extracted backend script to: ${tempScript}`);
      startupArgs = [tempScript];
      tempFiles.push(tempScript); // Track for cleanup
    } catch (error) {
      console.error('Failed to extract backend script:', error);
      // Fallback to trying the asar path
      startupArgs = [scriptToUse];
    }
  } else {
    // Use uvicorn directly for development
    startupArgs = ['-m', 'uvicorn', 'theseus_insight.main:app', '--host', '0.0.0.0', '--port', '8000'];
  }
  
  console.log(`Startup args: ${startupArgs.join(' ')}`);
  
  const pythonDepsPath = path.join(projectRoot, 'python_deps');
  const pythonPathParts = [projectRoot, pythonDepsPath];
  if (process.env.PYTHONPATH) {
    pythonPathParts.push(process.env.PYTHONPATH);
  }

  const dbPath = path.join(app.getPath('userData'), 'theseus.db');
  console.log(`SQLite database path will be: ${dbPath}`);

  // --- Logic for setting dynamic library path for sqlite-vec ---
  const sqliteVecPackageDir = path.join(pythonDepsPath, 'sqlite_vec');
  // Common places for shared libs: directly in package dir, or in a 'lib' subdir.
  const potentialLibPaths = [
      sqliteVecPackageDir,
      path.join(sqliteVecPackageDir, 'lib')
  ];

  let finalSqliteVecLibPath = null;
  for (const p of potentialLibPaths) {
      // A more robust check would be to list files and find .so/.dylib/.dll
      if (fs.existsSync(p)) {
          console.log(`DEBUG: Found potential sqlite-vec lib dir: ${p}`);
          // Check if this directory actually contains relevant library files
          // This is a simplified check; actual files might be deeper or have specific names
          const files = fs.readdirSync(p);
          if (files.some(f => f.endsWith('.so') || f.endsWith('.dylib') || f.endsWith('.dll'))) {
            finalSqliteVecLibPath = p;
            console.log(`DEBUG: Confirmed sqlite-vec lib dir with shared objects: ${finalSqliteVecLibPath}`);
            break;
          } else {
            console.log(`DEBUG: Directory ${p} exists but contains no shared library files directly.`);
          }
      }
  }

  const platform = process.platform;
  let newEnv = {
    ...process.env,
    DATABASE_URL: `sqlite:///${dbPath}`,
    ELECTRON_IS_PACKAGED: isPackaged ? 'true' : 'false',
    ELECTRON_RESOURCES_PATH: isPackaged ? process.resourcesPath : '',
    PATH: process.env.PATH, // Original PATH
    CONDA_DEFAULT_ENV: 'theseus',
    PYTHONPATH: pythonPathParts.join(path.delimiter)
  };

  if (finalSqliteVecLibPath) {
      console.log(`Attempting to set library path for sqlite-vec using: ${finalSqliteVecLibPath}`);
      if (platform === 'darwin') { // macOS
          newEnv.DYLD_LIBRARY_PATH = `${finalSqliteVecLibPath}${path.delimiter}${process.env.DYLD_LIBRARY_PATH || ''}`;
          console.log(`DEBUG: New DYLD_LIBRARY_PATH: ${newEnv.DYLD_LIBRARY_PATH}`);
      } else if (platform === 'linux') {
          newEnv.LD_LIBRARY_PATH = `${finalSqliteVecLibPath}${path.delimiter}${process.env.LD_LIBRARY_PATH || ''}`;
          console.log(`DEBUG: New LD_LIBRARY_PATH: ${newEnv.LD_LIBRARY_PATH}`);
      } else if (platform === 'win32') { // Windows
          newEnv.PATH = `${finalSqliteVecLibPath}${path.delimiter}${process.env.PATH || ''}`;
          console.log(`DEBUG: New PATH for DLLs: ${newEnv.PATH}`);
      }
  } else {
      console.warn(`WARN: Could not determine sqlite-vec library path within ${pythonDepsPath}. Python's ability to load sqlite-vec extensions might rely on system pre-configuration or RPATH settings in the extensions themselves.`);
  }
  // --- End of dynamic library path logic ---

  pythonProcess = spawn(pythonCmd, startupArgs, {
    cwd: projectRoot,  // Set working directory to project root
    env: newEnv // Use the potentially modified environment
  });

  // Add error handling for the python process
  pythonProcess.on('error', (error) => {
    console.error('Python process error:', error);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`Python process exited with code ${code} and signal ${signal}`);
    if (code !== 0 && code !== null) {
      console.error('Python process crashed! Code:', code);
    }
  });

  pythonProcess.stdout.on('data', (data) => {
    try {
      console.log(`backend: ${data}`);
    } catch (error) {
      // Ignore EPIPE errors when logging
      if (error.code !== 'EPIPE') {
        console.error('Error logging backend stdout:', error);
      }
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    try {
      console.error(`backend err: ${data}`);
    } catch (error) {
      // Ignore EPIPE errors when logging
      if (error.code !== 'EPIPE') {
        console.error('Error logging backend stderr:', error);
      }
    }
  });

  pythonProcess.stdout.on('error', (error) => {
    if (error.code !== 'EPIPE') {
      console.error('Python process stdout error:', error);
    }
  });

  pythonProcess.stderr.on('error', (error) => {
    if (error.code !== 'EPIPE') {
      console.error('Python process stderr error:', error);
    }
  });
}

function waitForServer(url, maxAttempts = 20, delay = 2000) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    
    const checkServer = () => {
      attempts++;
      console.log(`Checking server readiness (attempt ${attempts}/${maxAttempts})...`);
      
      const http = require('http');
      const urlParts = new URL(url);
      
      const req = http.get({
        hostname: urlParts.hostname,
        port: urlParts.port,
        path: '/', // Use root path
        timeout: 8000 // Longer timeout
      }, (res) => {
        // Consume the response to prevent hanging
        res.on('data', () => {});
        res.on('end', () => {
          if (res.statusCode === 200) {
            console.log('Server is ready!');
            resolve();
          } else {
            console.log(`Server responded with status ${res.statusCode}, retrying...`);
            scheduleNextCheck();
          }
        });
      });
      
      req.on('error', (err) => {
        console.log(`Server not ready: ${err.message}`);
        scheduleNextCheck();
      });
      
      req.on('timeout', () => {
        console.log('Server check timed out, retrying...');
        req.destroy();
        scheduleNextCheck();
      });
    };
    
    const scheduleNextCheck = () => {
      if (attempts >= maxAttempts) {
        console.log(`Server failed to start after ${maxAttempts} attempts, proceeding anyway...`);
        resolve(); // Resolve anyway to let the app continue
      } else {
        setTimeout(checkServer, delay);
      }
    };
    
    checkServer();
  });
}

async function startServices() {
  try {
    // Initialize the database (ensure user data directory exists)
    await initializeDatabase();
    
    // Start the backend
    startBackend();
    
    // Wait for the backend to be fully ready
    console.log('Waiting for FastAPI server to be ready...');
    await waitForServer('http://localhost:8000');
    
    // Create the window
    createWindow();
  } catch (error) {
    console.error('Failed to start services:', error);
    app.quit();
  }
}

function cleanupTempFiles() {
  console.log('Cleaning up temporary files...');
  tempFiles.forEach(tempFile => {
    try {
      if (fs.existsSync(tempFile)) {
        fs.unlinkSync(tempFile);
        console.log(`Cleaned up: ${tempFile}`);
      }
    } catch (error) {
      console.warn(`Failed to cleanup ${tempFile}:`, error.message);
    }
  });
  tempFiles = [];
}

function cleanupProcesses() {
  console.log('Cleaning up processes...');
  
  if (pythonProcess) {
    console.log('Shutting down Python backend...');
    pythonProcess.kill('SIGTERM'); // SIGTERM is preferred for graceful shutdown
    pythonProcess = null;
  }
  
  // No PostgreSQL process to manage
  
  cleanupTempFiles();
}

app.whenReady().then(() => {
  // Set app name for better OS integration
  app.setName('Theseus Insight');
  
  startServices();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On macOS it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  if (BrowserWindow.getAllWindows().length === 0) {
    startServices();
  }
});

app.on('will-quit', () => {
  cleanupProcesses();
});
