// ============================================================================
// CORTEX — Main Process (electron-vite entry)
// Bezpieczny BrowserWindow z contextIsolation: true + preload.ts
// Inicjalizuje StorageEngine + ElectronIpcBridge
// ============================================================================

import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { StorageEngine } from './storage/StorageEngine';
import { CortexDb } from './db/cortexDb';
import { ElectronIpcBridge } from './ipc/ElectronIpcBridge';

// === Constants =============================================================
const IS_DEV = !app.isPackaged;
const ROOT_DIR = path.join(__dirname, '..', '..');
const DATA_DIR = !IS_DEV
  ? path.join(app.getPath('userData'), 'CortexData')
  : path.join(ROOT_DIR, 'data');

// === State =================================================================
let mainWindow: BrowserWindow | null = null;
let storage: StorageEngine | null = null;
let cortexDb: CortexDb | null = null;
let ipcBridge: ElectronIpcBridge | null = null;

// ============================================================================
// Create Window
// ============================================================================
function createMainWindow(): BrowserWindow {
  const preloadPath = path.join(__dirname, '..', 'preload', 'index.cjs');

  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: 'Cortex — Agent Orchestration System',
    backgroundColor: '#0a0e14',
    show: false,
    frame: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true,
      preload: preloadPath,
    },
  });

  win.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'; " +
          "script-src 'self' " + (IS_DEV ? "'unsafe-inline' " : "") + "; " +
          "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
          "font-src 'self' https://fonts.gstatic.com; " +
          "img-src 'self' data: blob:; " +
          "connect-src 'self' ws: http://localhost:* http://127.0.0.1:* https://generativelanguage.googleapis.com https://api.deepseek.com https://openrouter.ai; " +
          "frame-src 'none'; " +
          "object-src 'none'; ",
        ],
      },
    });
  });

  win.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    console.log(`[RENDERER:${level}] ${message} (${sourceId}:${line})`);
  });
  win.webContents.on('did-fail-load', (_event, code, desc) => {
    console.error(`[RENDERER FAIL] ${code}: ${desc}`);
  });
  win.webContents.on('render-process-gone', (_event, details) => {
    console.error(`[RENDERER GONE] ${details.reason}`);
  });

  win.once('ready-to-show', () => {
    win.show();
  });

  if (IS_DEV) {
    win.webContents.on('before-input-event', (_event, input) => {
      if (
        input.type === 'keyDown' &&
        (input.key === 'F12' || (input.control && input.shift && input.key.toLowerCase() === 'i'))
      ) {
        win.webContents.toggleDevTools();
      }
    });
  }

  if (IS_DEV) {
    win.loadURL('http://localhost:3000');
  } else {
    win.loadFile(path.join(ROOT_DIR, 'out', 'renderer', 'index.html'));
  }

  return win;
}

// ============================================================================
// Bootstrap
// ============================================================================
async function bootstrap(): Promise<void> {
  console.log('====================================================');
  console.log('  Cortex — Notatki');
  console.log('====================================================\n');

  storage = new StorageEngine(DATA_DIR);
  await storage.init();

  cortexDb = new CortexDb(path.join(DATA_DIR, 'cortex.db'));
  cortexDb.open();

  ipcBridge = new ElectronIpcBridge(ipcMain, storage, cortexDb);
  ipcBridge.registerHandlers();

  // Kontrola okna rejestrowana raz — przy re-aktywacji (macOS) nie wywoła drugiej rejestracji.
  ipcMain.handle('window:minimize', () => mainWindow?.minimize());
  ipcMain.handle('window:maximize', () => {
    if (!mainWindow) return false;
    if (mainWindow.isMaximized()) mainWindow.unmaximize();
    else mainWindow.maximize();
    return mainWindow.isMaximized();
  });
  ipcMain.handle('window:close', () => mainWindow?.close());
  ipcMain.handle('window:is-maximized', () => mainWindow?.isMaximized() ?? false);

  mainWindow = createMainWindow();
}

// ============================================================================
// App Lifecycle
// ============================================================================

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    if (!fs.existsSync(DATA_DIR)) {
      fs.mkdirSync(DATA_DIR, { recursive: true });
    }

    try {
      await bootstrap();
    } catch (err) {
      console.error('[CORTEX] Bootstrap failed:', err);
      dialog.showErrorBox('Cortex Bootstrap Error', String(err));
      app.quit();
      return;
    }

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        mainWindow = createMainWindow();
      }
    });
  }).catch(err => {
    console.error('[CORTEX] App ready failed:', err);
    dialog.showErrorBox('Cortex Error', String(err));
    app.quit();
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      app.quit();
    }
  });

  app.on('before-quit', () => {
    storage?.destroy();
    ipcBridge?.destroy();
    cortexDb?.close();
  });
}