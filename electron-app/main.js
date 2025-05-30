const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const fs = require('fs');

let pythonProcess = null;
let postgresProcess = null;

function createWindow () {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
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

  // Open DevTools for debugging
  win.webContents.openDevTools();

  console.log('Loading URL: http://localhost:8000');
  win.loadURL('http://localhost:8000');
}

function startPostgres() {
  const platform = process.platform;
  // expected postgres binaries under electron-app/postgres/<platform>/bin
  const binDir = path.join(__dirname, 'postgres', platform, 'bin');
  const pgPath = path.join(binDir, platform === 'win32' ? 'postgres.exe' : 'postgres');
  const initdbPath = path.join(binDir, platform === 'win32' ? 'initdb.exe' : 'initdb');
  const dataDir = path.join(app.getPath('userData'), 'postgres-data');

  if (!fs.existsSync(path.join(dataDir, 'PG_VERSION'))) {
    spawnSync(initdbPath, ['-D', dataDir]);
  }

  postgresProcess = spawn(pgPath, ['-D', dataDir, '-p', '55432']);

  postgresProcess.stdout.on('data', (data) => {
    console.log(`postgres: ${data}`);
  });

  postgresProcess.stderr.on('data', (data) => {
    console.error(`postgres err: ${data}`);
  });

  return postgresProcess;
}

function initializeDatabase() {
  return new Promise((resolve, reject) => {
    console.log('Initializing database...');
    const initScript = path.join(__dirname, 'init_db.sh');
    
    const initProcess = spawn('bash', [initScript], {
      stdio: 'inherit'
    });

    initProcess.on('close', (code) => {
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
  // Change working directory to the project root where the Python modules are located
  const projectRoot = path.join(__dirname, '..');
  
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
  
  pythonProcess = spawn(pythonCmd, ['-m', 'uvicorn', 'theseus_insight.main:app', '--host', '0.0.0.0', '--port', '8000'], {
    cwd: projectRoot,  // Set working directory to project root
    env: {
      ...process.env,
      DATABASE_URL: 'postgresql://theseus:theseus@localhost:55432/theseusdb',
      // Add conda environment paths if detected
      PATH: condaEnvPath ? 
        `${path.dirname(condaEnvPath)}:${process.env.PATH}` : 
        process.env.PATH,
      CONDA_DEFAULT_ENV: 'theseus',
      PYTHONPATH: projectRoot
    }
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`backend: ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`backend err: ${data}`);
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
    // Create window anyway to show error
    createWindow();
  }
}

app.whenReady().then(() => {
  startServices();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (pythonProcess) pythonProcess.kill();
  if (postgresProcess) postgresProcess.kill();
});
