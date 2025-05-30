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
let postgresProcess = null;
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
  win.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error(`Failed to load page: ${errorCode} - ${errorDescription}`);
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

  // Open DevTools for debugging (remove this in production)
  if (process.env.NODE_ENV === 'development') {
    win.webContents.openDevTools();
  }

  // In development, load Vite dev server; in production, load FastAPI backend
  const developmentUrl = 'http://localhost:5173'; // Vite default port
  const productionUrl = 'http://localhost:8000';
  const loadUrl = process.env.NODE_ENV === 'development' ? developmentUrl : productionUrl;
  
  console.log(`Loading URL: ${loadUrl}`);
  win.loadURL(loadUrl);
  
  return win;
}

function startPostgres() {
  const platform = process.platform;
  const searchDirs = [];

  if (app.isPackaged) {
    // In packaged apps the postgres folder is bundled as an extraResource
    searchDirs.push(path.join(process.resourcesPath, 'app', 'postgres', platform, 'bin'));
    searchDirs.push(path.join(process.resourcesPath, 'postgres', platform, 'bin'));
  }

  // Development fallback
  searchDirs.push(path.join(__dirname, 'postgres', platform, 'bin'));

  let binDir = null;
  for (const dir of searchDirs) {
    if (fs.existsSync(dir)) {
      binDir = dir;
      break;
    }
  }

  if (!binDir) {
    console.error('PostgreSQL binaries not found in any of:', searchDirs);
    return null;
  }

  const pgPath = path.join(binDir, platform === 'win32' ? 'postgres.exe' : 'postgres');
  const initdbPath = path.join(binDir, platform === 'win32' ? 'initdb.exe' : 'initdb');
  const dataDir = path.join(app.getPath('userData'), 'postgres-data');
  const lockFile = path.join(dataDir, 'postmaster.pid');

  if (!fs.existsSync(pgPath)) {
    console.error('postgres executable not found:', pgPath);
    return null;
  }

  // Clean up stale lock file if it exists but no process is actually running
  if (fs.existsSync(lockFile)) {
    try {
      const lockContent = fs.readFileSync(lockFile, 'utf8');
      const pid = parseInt(lockContent.split('\n')[0]);
      
      if (pid) {
        // Check if the process is actually running
        try {
          process.kill(pid, 0); // Signal 0 just checks if process exists
          console.log(`PostgreSQL is already running with PID ${pid}. Stopping it first...`);
          try {
            process.kill(pid, 'SIGTERM');
            // Wait a moment for graceful shutdown
            setTimeout(() => {
              try {
                process.kill(pid, 0);
                // If still running, force kill
                console.log('Force killing PostgreSQL...');
                process.kill(pid, 'SIGKILL');
              } catch (e) {
                // Process already stopped, good
              }
              // Remove the lock file
              if (fs.existsSync(lockFile)) {
                fs.unlinkSync(lockFile);
                console.log('Removed stale PostgreSQL lock file');
              }
            }, 2000);
          } catch (e) {
            console.log('Failed to stop existing PostgreSQL process:', e.message);
          }
        } catch (e) {
          // Process doesn't exist, remove stale lock file
          fs.unlinkSync(lockFile);
          console.log('Removed stale PostgreSQL lock file (process not running)');
        }
      }
    } catch (error) {
      console.warn('Error checking PostgreSQL lock file:', error.message);
      // Try to remove it anyway
      try {
        fs.unlinkSync(lockFile);
        console.log('Removed problematic lock file');
      } catch (e) {
        console.error('Could not remove lock file:', e.message);
      }
    }
  }

  // Clean up stale shared memory segments with health checks
  function cleanupOrphanedSharedMemory(dataDir) {
    try {
      const { execSync } = require('child_process');
      const username = require('os').userInfo().username;
      
      console.log('Running shared memory health checks...');
      
      // Get list of all shared memory segments
      const ipcsOutput = execSync('ipcs -m', { encoding: 'utf8' });
      const lines = ipcsOutput.split('\n');
      
      // Look for segments that might belong to PostgreSQL
      const potentialPgSegments = [];
      
      for (const line of lines) {
        if (line.includes(username) && line.includes('--rw-------')) {
          const parts = line.trim().split(/\s+/);
          if (parts.length >= 3) {
            const shmid = parts[1];
            const key = parts[2];
            potentialPgSegments.push({ shmid, key, line });
          }
        }
      }
      
      if (potentialPgSegments.length === 0) {
        console.log('No shared memory segments found for cleanup');
        return;
      }
      
      console.log(`Found ${potentialPgSegments.length} potential shared memory segments to check`);
      
      // Health check each segment
      for (const segment of potentialPgSegments) {
        const isOrphaned = checkIfSharedMemoryOrphaned(segment, dataDir);
        if (isOrphaned) {
          try {
            console.log(`Cleaning up orphaned shared memory segment: ${segment.shmid} (key: ${segment.key})`);
            execSync(`ipcrm -m ${segment.shmid}`, { stdio: 'ignore' });
            console.log(`Successfully removed shared memory segment ${segment.shmid}`);
          } catch (e) {
            console.warn(`Failed to remove shared memory segment ${segment.shmid}: ${e.message}`);
          }
        } else {
          console.log(`Shared memory segment ${segment.shmid} appears to be in use, skipping`);
        }
      }
      
    } catch (error) {
      console.log('Shared memory health check failed, skipping cleanup:', error.message);
    }
  }
  
  function checkIfSharedMemoryOrphaned(segment, dataDir) {
    try {
      const { execSync } = require('child_process');
      
      // Check 1: Look for any PostgreSQL processes that might be using this segment
      try {
        const pgProcesses = execSync('pgrep -f postgres', { encoding: 'utf8' }).trim();
        if (pgProcesses) {
          const pids = pgProcesses.split('\n');
          
          // Check if any PostgreSQL process is using our data directory
          for (const pid of pids) {
            try {
              const cmdline = execSync(`ps -p ${pid} -o args=`, { encoding: 'utf8' }).trim();
              if (cmdline.includes(dataDir)) {
                console.log(`Found active PostgreSQL process using our data directory: PID ${pid}`);
                return false; // Not orphaned, process is using our data dir
              }
            } catch (e) {
              // Process might have disappeared, continue checking
            }
          }
        }
      } catch (e) {
        // No PostgreSQL processes found, continue with other checks
      }
      
      // Check 2: Verify if shared memory segment is actually accessible
      try {
        // macOS doesn't support ipcs -i, use alternative approach
        const platform = require('os').platform();
        let attachCount = 0;
        
        if (platform === 'darwin') {
          // On macOS, use ipcs -m and parse the nattch column
          const shmInfo = execSync('ipcs -m', { encoding: 'utf8' });
          const lines = shmInfo.split('\n');
          
          for (const line of lines) {
            const parts = line.trim().split(/\s+/);
            if (parts.length >= 6 && parts[1] === segment.shmid) {
              // Column layout: T ID KEY MODE OWNER GROUP [NATTCH]
              attachCount = parseInt(parts[6] || '0');
              break;
            }
          }
        } else {
          // On Linux, use ipcs -i
          const shmInfo = execSync(`ipcs -m -i ${segment.shmid}`, { encoding: 'utf8' });
          const lines = shmInfo.split('\n');
          for (const line of lines) {
            if (line.includes('nattch')) {
              attachCount = parseInt(line.split('=')[1]?.trim() || '0');
              break;
            }
          }
        }
        
        if (attachCount > 0) {
          console.log(`Shared memory segment ${segment.shmid} has ${attachCount} attachments, not orphaned`);
          return false;
        }
      } catch (e) {
        // If we can't get info about the segment, it might already be cleaned up
        console.log(`Cannot get attachment info for shared memory segment ${segment.shmid}: ${e.message}`);
        return false;
      }
      
      // Check 3: Look for specific PostgreSQL shared memory key patterns
      // PostgreSQL typically uses keys in specific ranges for different purposes
      const key = parseInt(segment.key, 16);
      
      // PostgreSQL main shared memory usually has predictable key patterns
      // If this doesn't look like a PostgreSQL key, be cautious
      if (key < 0x1000000 || key > 0xFFFFFFFF) {
        console.log(`Shared memory key ${segment.key} doesn't match PostgreSQL patterns, skipping`);
        return false;
      }
      
      // Check 4: Final safety check - look for lock file association
      if (fs.existsSync(path.join(dataDir, 'postmaster.pid'))) {
        console.log('PostgreSQL lock file exists, shared memory might still be needed');
        return false;
      }
      
      console.log(`Shared memory segment ${segment.shmid} appears to be orphaned`);
      return true;
      
    } catch (error) {
      console.warn(`Error during health check for segment ${segment.shmid}: ${error.message}`);
      return false; // When in doubt, don't clean up
    }
  }
  
  // Run the health-checked cleanup
  cleanupOrphanedSharedMemory(dataDir);

  if (!fs.existsSync(path.join(dataDir, 'PG_VERSION'))) {
    spawnSync(initdbPath, ['-D', dataDir]);
  }

  try {
    postgresProcess = spawn(pgPath, ['-D', dataDir, '-p', '55432']);
  } catch (err) {
    console.error('Failed to spawn postgres:', err);
    return null;
  }

  postgresProcess.stdout.on('data', (data) => {
    console.log(`postgres: ${data}`);
  });

  postgresProcess.stderr.on('data', (data) => {
    console.error(`postgres err: ${data}`);
  });

  postgresProcess.on('error', (err) => {
    console.error('postgres process error:', err);
  });

  postgresProcess.on('exit', (code, signal) => {
    console.log(`PostgreSQL process exited with code ${code} and signal ${signal}`);
    postgresProcess = null;
  });

  return postgresProcess;
}

function initializeDatabase() {
  return new Promise((resolve, reject) => {
    console.log('Initializing database...');
    
    // Handle path resolution for packaged vs development
    const isPackaged = app.isPackaged;
    let initScript;
    
    if (isPackaged) {
      // In packaged app, extract script from asar to temp location
      const originalScript = path.join(__dirname, 'init_db.sh');
      const tempScript = path.join(os.tmpdir(), 'theseus_init_db.sh');
      
      try {
        // Copy script from asar to temp location
        const scriptContent = fs.readFileSync(originalScript, 'utf8');
        fs.writeFileSync(tempScript, scriptContent, { mode: 0o755 });
        initScript = tempScript;
        tempFiles.push(tempScript); // Track for cleanup
        console.log(`Extracted init script to: ${initScript}`);
      } catch (error) {
        console.error('Failed to extract init script:', error);
        return reject(error);
      }
    } else {
      // In development
      initScript = path.join(__dirname, 'init_db.sh');
    }
    
    console.log(`Using init script: ${initScript}`);
    
    const initProcess = spawn('bash', [initScript], {
      stdio: 'inherit',
      env: {
        ...process.env,
        ELECTRON_IS_PACKAGED: isPackaged ? 'true' : 'false',
        ELECTRON_RESOURCES_PATH: isPackaged ? process.resourcesPath : ''
      }
    });

    initProcess.on('close', (code) => {
      // Clean up temp file if created
      if (isPackaged && fs.existsSync(initScript)) {
        try {
          fs.unlinkSync(initScript);
        } catch (e) {
          console.warn('Could not clean up temp init script:', e.message);
        }
      }
      
      if (code === 0) {
        console.log('Database initialization completed successfully');
        resolve();
      } else {
        console.error(`Database initialization failed with code ${code}`);
        reject(new Error(`Database initialization failed with code ${code}`));
      }
    });

    initProcess.on('error', (error) => {
      console.error('Failed to start database initialization:', error);
      reject(error);
    });
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
  
  // Try to detect conda environment
  let pythonCmd = 'python';
  let condaEnvPath = null;
  
  // Common conda installation paths
  const condaPaths = [
    '/Users/c/miniforge3/envs/theseus/bin/python',
    '/Users/c/anaconda3/envs/theseus/bin/python',
    '/Users/c/miniconda3/envs/theseus/bin/python',
    '/opt/homebrew/anaconda3/envs/theseus/bin/python'
  ];
  
  // Check if CONDA_PREFIX is set (user has activated environment)
  if (process.env.CONDA_PREFIX && fs.existsSync(path.join(process.env.CONDA_PREFIX, 'bin', 'python'))) {
    condaEnvPath = path.join(process.env.CONDA_PREFIX, 'bin', 'python');
    pythonCmd = condaEnvPath;
  } else {
    // Try common paths
    for (const condaPath of condaPaths) {
      if (fs.existsSync(condaPath)) {
        condaEnvPath = condaPath;
        pythonCmd = condaPath;
        break;
      }
    }
  }
  
  console.log(`Using Python interpreter: ${pythonCmd}`);
  
  // Choose the startup method based on packaging
  let startupArgs;
  if (isPackaged) {
    // Extract the start_backend.py script from asar to temp location
    const originalScript = path.join(__dirname, 'start_backend.py');
    const tempScript = path.join(os.tmpdir(), 'theseus_start_backend.py');
    
    try {
      const scriptContent = fs.readFileSync(originalScript, 'utf8');
      fs.writeFileSync(tempScript, scriptContent, { mode: 0o755 });
      console.log(`Extracted backend script to: ${tempScript}`);
      startupArgs = [tempScript];
      tempFiles.push(tempScript); // Track for cleanup
    } catch (error) {
      console.error('Failed to extract backend script:', error);
      // Fallback to trying the asar path
      startupArgs = [path.join(__dirname, 'start_backend.py')];
    }
  } else {
    // Use uvicorn directly for development
    startupArgs = ['-m', 'uvicorn', 'theseus_insight.main:app', '--host', '0.0.0.0', '--port', '8000'];
  }
  
  console.log(`Startup args: ${startupArgs.join(' ')}`);
  
  pythonProcess = spawn(pythonCmd, startupArgs, {
    cwd: projectRoot,  // Set working directory to project root
    env: {
      ...process.env,
      DATABASE_URL: 'postgresql://theseus:theseus@localhost:55432/theseusdb',
      ELECTRON_IS_PACKAGED: isPackaged ? 'true' : 'false',
      ELECTRON_RESOURCES_PATH: isPackaged ? process.resourcesPath : '',
      // Add conda environment paths if detected
      PATH: condaEnvPath ? 
        `${path.dirname(condaEnvPath)}:${process.env.PATH}` : 
        process.env.PATH,
      CONDA_DEFAULT_ENV: 'theseus',
      PYTHONPATH: projectRoot
    }
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
    // Start PostgreSQL
    startPostgres();
    
    // Wait a moment for PostgreSQL to fully start
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Initialize the database
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
    pythonProcess.kill('SIGTERM');
    pythonProcess = null;
  }
  
  if (postgresProcess) {
    console.log('Shutting down PostgreSQL...');
    postgresProcess.kill('SIGTERM');
    
    // Give it a moment to shut down gracefully
    setTimeout(() => {
      if (postgresProcess && !postgresProcess.killed) {
        console.log('Force killing PostgreSQL...');
        postgresProcess.kill('SIGKILL');
      }
      postgresProcess = null;
    }, 3000);
  }
  
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
