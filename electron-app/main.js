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
}

function startBackend() {
  const scriptPath = path.join(__dirname, 'app', 'run_theseus_insight.py');
  pythonProcess = spawn('python', [scriptPath], {
    env: {
      ...process.env,
      DATABASE_URL: 'postgresql://theseus:theseus@localhost:55432/theseusdb'
    }
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`backend: ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`backend err: ${data}`);
  });
}

app.whenReady().then(() => {
  startPostgres();
  startBackend();
  createWindow();
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
