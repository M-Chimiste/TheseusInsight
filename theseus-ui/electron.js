const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let backendProcess;

function startBackend() {
  const rootDir = path.join(__dirname, '..');
  backendProcess = spawn('python', ['-m', 'uvicorn', 'theseus_insight.main:app', '--port', '8000'], {
    cwd: rootDir,
  });

  backendProcess.stdout.on('data', (data) => {
    console.log(`[backend]: ${data}`.trim());
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[backend error]: ${data}`.trim());
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      contextIsolation: true,
    },
  });

  const isDev = !app.isPackaged;
  if (isDev) {
    win.loadURL('http://localhost:5173');
    win.webContents.openDevTools();
  } else {
    win.loadFile(path.join(__dirname, 'dist', 'index.html'));
  }
}

app.whenReady().then(() => {
  startBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill();
  }
});
