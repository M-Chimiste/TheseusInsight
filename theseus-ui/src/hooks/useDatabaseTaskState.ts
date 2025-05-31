import { useState, useEffect, useCallback } from 'react';
import { taskApi } from '../services/api';

export interface DatabaseTaskState {
  exportTaskId: string | null;
  importTaskId: string | null;
  isExporting: boolean;
  isImporting: boolean;
  exportProgress: number;
  importProgress: number;
  exportStatus: string;
  importStatus: string;
  exportError: string | null;
  importError: string | null;
}

export interface UseDatabaseTaskStateReturn {
  taskState: DatabaseTaskState;
  setExportTaskId: (taskId: string | null) => void;
  setImportTaskId: (taskId: string | null) => void;
  updateExportProgress: (progress: number, status: string) => void;
  updateImportProgress: (progress: number, status: string) => void;
  setExportError: (error: string | null) => void;
  setImportError: (error: string | null) => void;
  clearExportTask: () => void;
  clearImportTask: () => void;
  isCheckingForActiveTasks: boolean;
}

const STORAGE_KEY = 'theseus_database_tasks';

const DEFAULT_TASK_STATE: DatabaseTaskState = {
  exportTaskId: null,
  importTaskId: null,
  isExporting: false,
  isImporting: false,
  exportProgress: 0,
  importProgress: 0,
  exportStatus: '',
  importStatus: '',
  exportError: null,
  importError: null,
};

// Helper functions for localStorage
const saveTaskState = (state: DatabaseTaskState) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (error) {
    console.warn('Failed to save database task state to localStorage:', error);
  }
};

const loadTaskState = (): DatabaseTaskState => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      // Validate the structure
      if (typeof parsed === 'object' && parsed !== null) {
        return { ...DEFAULT_TASK_STATE, ...parsed };
      }
    }
  } catch (error) {
    console.warn('Failed to load database task state from localStorage:', error);
  }
  return DEFAULT_TASK_STATE;
};

const clearTaskState = () => {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.warn('Failed to clear database task state from localStorage:', error);
  }
};

export const useDatabaseTaskState = (): UseDatabaseTaskStateReturn => {
  const [taskState, setTaskState] = useState<DatabaseTaskState>(loadTaskState);
  const [isCheckingForActiveTasks, setIsCheckingForActiveTasks] = useState(true);

  // Save to localStorage whenever state changes
  useEffect(() => {
    saveTaskState(taskState);
  }, [taskState]);

  // Check for active database tasks on mount and reconnect if needed
  useEffect(() => {
    const checkForActiveTasks = async () => {
      try {
        setIsCheckingForActiveTasks(true);
        
        // Check for active database export/import tasks
        const activeResponse = await taskApi.getActiveTasks(['database_export', 'database_import']);
        const activeTasks = activeResponse.data.active_tasks || [];
        
        console.log('[useDatabaseTaskState] Checking for active database tasks:', {
          activeTasks,
          currentState: taskState
        });
        
        let hasActiveExport = false;
        let hasActiveImport = false;
        
        // Check each active task
        for (const task of activeTasks) {
          if (task.task_type === 'database_export' || task.type === 'database_export') {
            hasActiveExport = true;
            // If we have a stored export task ID and it matches, reconnect
            if (taskState.exportTaskId === task.task_id) {
              console.log('[useDatabaseTaskState] Reconnecting to export task:', task.task_id);
              setTaskState(prev => ({
                ...prev,
                isExporting: true,
                exportProgress: task.progress || prev.exportProgress,
                exportStatus: task.message || prev.exportStatus || 'Reconnecting to export task...',
                exportError: null
              }));
            } else {
              // Found an active export task but it's not our stored one
              console.log('[useDatabaseTaskState] Found different active export task:', task.task_id);
              setTaskState(prev => ({
                ...prev,
                exportTaskId: task.task_id,
                isExporting: true,
                exportProgress: task.progress || 0,
                exportStatus: task.message || 'Export in progress...',
                exportError: null
              }));
            }
          } else if (task.task_type === 'database_import' || task.type === 'database_import') {
            hasActiveImport = true;
            // If we have a stored import task ID and it matches, reconnect
            if (taskState.importTaskId === task.task_id) {
              console.log('[useDatabaseTaskState] Reconnecting to import task:', task.task_id);
              setTaskState(prev => ({
                ...prev,
                isImporting: true,
                importProgress: task.progress || prev.importProgress,
                importStatus: task.message || prev.importStatus || 'Reconnecting to import task...',
                importError: null
              }));
            } else {
              // Found an active import task but it's not our stored one
              console.log('[useDatabaseTaskState] Found different active import task:', task.task_id);
              setTaskState(prev => ({
                ...prev,
                importTaskId: task.task_id,
                isImporting: true,
                importProgress: task.progress || 0,
                importStatus: task.message || 'Import in progress...',
                importError: null
              }));
            }
          }
        }
        
        // If we have stored task IDs but no active tasks, clear the running states
        if (!hasActiveExport && taskState.isExporting) {
          console.log('[useDatabaseTaskState] No active export task found, clearing export state');
          setTaskState(prev => ({
            ...prev,
            isExporting: false,
            exportProgress: 0,
            exportStatus: '',
          }));
        }
        
        if (!hasActiveImport && taskState.isImporting) {
          console.log('[useDatabaseTaskState] No active import task found, clearing import state');
          setTaskState(prev => ({
            ...prev,
            isImporting: false,
            importProgress: 0,
            importStatus: '',
          }));
        }
        
      } catch (error) {
        console.error('[useDatabaseTaskState] Error checking for active tasks:', error);
      } finally {
        setIsCheckingForActiveTasks(false);
      }
    };

    checkForActiveTasks();
  }, []); // Only run on mount

  // Periodically check task status if we have active tasks
  useEffect(() => {
    if (!taskState.isExporting && !taskState.isImporting) {
      return;
    }

    const checkTaskStatus = async () => {
      try {
        // Check export task status
        if (taskState.isExporting && taskState.exportTaskId) {
          const exportStatus = await taskApi.getTaskStatus(taskState.exportTaskId);
          if (exportStatus.data) {
            const status = exportStatus.data;
            if (status.status === 'completed') {
              setTaskState(prev => ({
                ...prev,
                isExporting: false,
                exportProgress: 100,
                exportStatus: 'Export completed successfully'
              }));
            } else if (status.status === 'failed') {
              setTaskState(prev => ({
                ...prev,
                isExporting: false,
                exportError: status.error || 'Export failed'
              }));
            } else {
              setTaskState(prev => ({
                ...prev,
                exportProgress: status.progress || prev.exportProgress,
                exportStatus: status.message || prev.exportStatus
              }));
            }
          }
        }

        // Check import task status
        if (taskState.isImporting && taskState.importTaskId) {
          const importStatus = await taskApi.getTaskStatus(taskState.importTaskId);
          if (importStatus.data) {
            const status = importStatus.data;
            if (status.status === 'completed') {
              setTaskState(prev => ({
                ...prev,
                isImporting: false,
                importProgress: 100,
                importStatus: 'Import completed successfully'
              }));
            } else if (status.status === 'failed') {
              setTaskState(prev => ({
                ...prev,
                isImporting: false,
                importError: status.error || 'Import failed'
              }));
            } else {
              setTaskState(prev => ({
                ...prev,
                importProgress: status.progress || prev.importProgress,
                importStatus: status.message || prev.importStatus
              }));
            }
          }
        }
      } catch (error) {
        console.error('[useDatabaseTaskState] Error checking task status:', error);
      }
    };

    // Check immediately and then every 2 seconds
    checkTaskStatus();
    const intervalId = setInterval(checkTaskStatus, 2000);

    return () => clearInterval(intervalId);
  }, [taskState.isExporting, taskState.isImporting, taskState.exportTaskId, taskState.importTaskId]);

  const setExportTaskId = useCallback((taskId: string | null) => {
    setTaskState(prev => ({
      ...prev,
      exportTaskId: taskId,
      isExporting: !!taskId,
      exportProgress: taskId ? 0 : prev.exportProgress,
      exportStatus: taskId ? 'Starting export...' : prev.exportStatus,
      exportError: null
    }));
  }, []);

  const setImportTaskId = useCallback((taskId: string | null) => {
    setTaskState(prev => ({
      ...prev,
      importTaskId: taskId,
      isImporting: !!taskId,
      importProgress: taskId ? 0 : prev.importProgress,
      importStatus: taskId ? 'Starting import...' : prev.importStatus,
      importError: null
    }));
  }, []);

  const updateExportProgress = useCallback((progress: number, status: string) => {
    setTaskState(prev => ({
      ...prev,
      exportProgress: progress,
      exportStatus: status
    }));
  }, []);

  const updateImportProgress = useCallback((progress: number, status: string) => {
    setTaskState(prev => ({
      ...prev,
      importProgress: progress,
      importStatus: status
    }));
  }, []);

  const setExportError = useCallback((error: string | null) => {
    setTaskState(prev => ({
      ...prev,
      exportError: error,
      isExporting: error ? false : prev.isExporting
    }));
  }, []);

  const setImportError = useCallback((error: string | null) => {
    setTaskState(prev => ({
      ...prev,
      importError: error,
      isImporting: error ? false : prev.isImporting
    }));
  }, []);

  const clearExportTask = useCallback(() => {
    setTaskState(prev => ({
      ...prev,
      exportTaskId: null,
      isExporting: false,
      exportProgress: 0,
      exportStatus: '',
      exportError: null
    }));
  }, []);

  const clearImportTask = useCallback(() => {
    setTaskState(prev => ({
      ...prev,
      importTaskId: null,
      isImporting: false,
      importProgress: 0,
      importStatus: '',
      importError: null
    }));
  }, []);

  return {
    taskState,
    setExportTaskId,
    setImportTaskId,
    updateExportProgress,
    updateImportProgress,
    setExportError,
    setImportError,
    clearExportTask,
    clearImportTask,
    isCheckingForActiveTasks,
  };
}; 