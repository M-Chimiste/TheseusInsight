import { useState, useEffect, useCallback } from 'react';
import { taskApi } from '../services/api';
import { useWebSocket } from './useWebSocket';

export interface TaskState {
  taskId: string | null;
  isRunning: boolean;
  stage: string;
  progress: number;
  message: string;
  error: string | null;
  result?: any;
}

export interface UseTaskStateReturn {
  taskState: TaskState;
  setTaskId: (taskId: string | null) => void;
  clearTask: () => void;
  isCheckingForActiveTasks: boolean;
}

const DEFAULT_TASK_STATE: TaskState = {
  taskId: null,
  isRunning: false,
  stage: '',
  progress: 0,
  message: "No active task. Configure and start a new task.",
  error: null,
};

export const useTaskState = (taskType: 'newsletter' | 'podcast' | 'visualizer'): UseTaskStateReturn => {
  const [taskState, setTaskState] = useState<TaskState>(DEFAULT_TASK_STATE);
  const [isCheckingForActiveTasks, setIsCheckingForActiveTasks] = useState(true);

  // WebSocket connection for real-time updates - only for running tasks
  const { lastMessage } = useWebSocket(taskState.isRunning ? taskState.taskId : null, taskType);

  // Check for active tasks on mount
  useEffect(() => {
    const checkForActiveTasks = async () => {
      try {
        setIsCheckingForActiveTasks(true);
        // Check for both the base type and the custom type (e.g., 'newsletter' and 'custom_newsletter_run')
        const taskTypesToCheck = [taskType, `custom_${taskType}_run`];
        
        // Check active tasks first
        const activeResponse = await taskApi.getActiveTasks(taskTypesToCheck);
        const activeTasks = activeResponse.data.active_tasks || [];
        
        console.log(`[useTaskState] Checking for active ${taskType} tasks:`, {
          taskTypesToCheck,
          activeTasks,
          totalFound: activeTasks.length
        });
        
        // Find the most recent active task for this type
        let activeTask = activeTasks.find((task: any) => 
          task.type === taskType || 
          task.type === `custom_${taskType}_run` ||
          task.task_type === taskType ||
          task.task_type === `custom_${taskType}_run`
        );
        
        // If no active task found, check sessionStorage for recent task info
        // This handles reconnection after page refresh
        if (!activeTask) {
          console.log(`[useTaskState] No active tasks found. Checking sessionStorage for recent task.`);
          
          try {
            // Look for stored task info in sessionStorage
            const storedTaskId = sessionStorage.getItem(`last_${taskType}_task_id`);
            const storedTaskTimestamp = sessionStorage.getItem(`last_${taskType}_task_timestamp`);
            
            if (storedTaskId && storedTaskTimestamp) {
              const timestamp = parseInt(storedTaskTimestamp);
              const now = Date.now();
              // Only consider if task was started within last 10 minutes
              if (now - timestamp < 10 * 60 * 1000) {
                console.log(`[useTaskState] Found recent task in sessionStorage: ${storedTaskId}`);
                
                // Verify this task still exists and get its current status
                try {
                  const taskResponse = await taskApi.getTaskStatus(storedTaskId);
                  const taskData = taskResponse.data;
                  
                  if (taskData && (taskData.status === 'processing' || taskData.status === 'pending')) {
                    console.log(`[useTaskState] Reconnecting to stored task: ${storedTaskId}`);
                    activeTask = {
                      task_id: storedTaskId,
                      type: taskType,
                      status: taskData.status,
                      progress: taskData.progress || 0,
                      current_step: taskData.current_step || '',
                      message: taskData.message || '',
                      error: taskData.error || null
                    };
                  } else {
                    // Task is no longer active, clean up sessionStorage
                    sessionStorage.removeItem(`last_${taskType}_task_id`);
                    sessionStorage.removeItem(`last_${taskType}_task_timestamp`);
                  }
                } catch (error) {
                  console.error(`[useTaskState] Error verifying stored task:`, error);
                  // Clean up invalid stored task
                  sessionStorage.removeItem(`last_${taskType}_task_id`);
                  sessionStorage.removeItem(`last_${taskType}_task_timestamp`);
                }
              }
            }
          } catch (error) {
            console.error(`[useTaskState] Error checking sessionStorage:`, error);
          }
        }
        
        console.log(`[useTaskState] Found task for ${taskType}:`, activeTask);

        if (activeTask) {
          // Restore task state from database
          setTaskState({
            taskId: activeTask.task_id,
            isRunning: activeTask.status === 'pending' || activeTask.status === 'processing',
            stage: activeTask.current_step || activeTask.status,
            progress: activeTask.progress || 0,
            message: activeTask.message || (activeTask.status === 'completed' ? 'Task completed successfully' : `Resuming ${taskType} task...`),
            error: activeTask.error || null,
            result: activeTask.result,
          });
        } else {
          // No active or recent completed tasks found
          setTaskState(DEFAULT_TASK_STATE);
        }
      } catch (error) {
        console.error(`Error checking for ${taskType} tasks:`, error);
        setTaskState(DEFAULT_TASK_STATE);
      } finally {
        setIsCheckingForActiveTasks(false);
      }
    };

    checkForActiveTasks();
  }, [taskType]);

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage && taskState.taskId) {
      console.log(`[useTaskState] WebSocket message received for ${taskType}:`, {
        taskId: taskState.taskId,
        overallStatus: lastMessage.overallStatus,
        hasResult: !!lastMessage.result,
        result: lastMessage.result,
        fullMessage: lastMessage  // Log the complete message structure
      });
      
      const mainNode = lastMessage.nodes && lastMessage.nodes.length > 0 ? lastMessage.nodes[0] : null;
      
      setTaskState(prev => ({
        ...prev,
        isRunning: lastMessage.overallStatus === 'processing' || lastMessage.overallStatus === 'pending',
        stage: mainNode?.message || lastMessage.overallStatus || prev.stage,
        progress: mainNode?.progress ?? (
          lastMessage.overallStatus === 'completed' ? 100 : 
          lastMessage.overallStatus === 'failed' ? 0 : 
          prev.progress
        ),
        message: mainNode?.message || lastMessage.error || (
          lastMessage.overallStatus === 'completed' ? 'Completed successfully' : 
          lastMessage.overallStatus === 'failed' ? 'Task failed' :
          'Processing...'
        ),
        error: lastMessage.error || null,
        result: lastMessage.result || (lastMessage.overallStatus === 'completed' ? { completed: true } : prev.result),
      }));

      // Don't automatically clear task when completed - let user manually dismiss or restart
      // This preserves the ability to download artifacts after completion
      if (lastMessage.overallStatus === 'failed') {
        // Only auto-clear failed tasks, keep completed ones for downloads
        setTimeout(() => {
          setTaskState(prev => ({
            ...prev,
            taskId: null,
            isRunning: false,
          }));
        }, 5000); // Give more time for failed tasks to be reviewed
      }
    }
  }, [lastMessage, taskState.taskId, taskType]);

  // Fallback: Periodically check task status if it seems stuck
  useEffect(() => {
    if (!taskState.taskId || !taskState.isRunning) return;

    const checkTaskStatus = async () => {
      try {
        if (!taskState.taskId) return; // Extra safety check
        
        console.log(`[useTaskState] Checking fallback status for stuck task: ${taskState.taskId}`);
        const response = await taskApi.getTaskStatus(taskState.taskId);
        const task = response.data;
        
        console.log(`[useTaskState] Fallback status check result:`, {
          taskId: taskState.taskId,
          status: task.status,
          progress: task.progress,
          currentIsRunning: taskState.isRunning
        });

        // If the task is actually completed but we're still showing as running
        if (task.status === 'completed' && taskState.isRunning) {
          console.warn(`[useTaskState] ⚠️  STUCK TASK DETECTED! Task ${taskState.taskId} is completed but UI still shows running. Fixing now...`);
          setTaskState(prev => ({
            ...prev,
            isRunning: false,
            stage: 'completed',
            progress: 100,
            message: 'Completed successfully',
            error: null,
            result: task.result || { completed: true },
          }));
        } else if (task.status === 'failed' && taskState.isRunning) {
          console.warn(`[useTaskState] ⚠️  STUCK TASK DETECTED! Task ${taskState.taskId} is failed but UI still shows running. Fixing now...`);
          setTaskState(prev => ({
            ...prev,
            isRunning: false,
            stage: 'failed',
            progress: 0,
            message: 'Task failed',
            error: task.error || 'Task failed',
          }));
        }
      } catch (error) {
        console.error(`[useTaskState] Fallback status check failed:`, error);
      }
    };

    // Check every 5 seconds if task is running (faster detection for debugging)
    const intervalId = setInterval(checkTaskStatus, 5000);
    
    return () => clearInterval(intervalId);
  }, [taskState.taskId, taskState.isRunning, taskType]);

  const setTaskId = useCallback((taskId: string | null) => {
    if (taskId) {
      // Store task info in sessionStorage for reconnection
      try {
        sessionStorage.setItem(`last_${taskType}_task_id`, taskId);
        sessionStorage.setItem(`last_${taskType}_task_timestamp`, Date.now().toString());
      } catch (e) {
        // Handle quota exceeded errors silently
      }
      
      setTaskState(prev => ({
        ...prev,
        taskId,
        isRunning: true,
        stage: 'Initiating...',
        progress: 5,
        message: `Starting ${taskType} task...`,
        error: null,
      }));
    } else {
      // Clear sessionStorage when task is cleared
      try {
        sessionStorage.removeItem(`last_${taskType}_task_id`);
        sessionStorage.removeItem(`last_${taskType}_task_timestamp`);
      } catch (e) {
        // Handle errors silently
      }
      
      setTaskState(DEFAULT_TASK_STATE);
    }
  }, [taskType]);

  const clearTask = useCallback(() => {
    setTaskState(DEFAULT_TASK_STATE);
  }, []);

  return {
    taskState,
    setTaskId,
    clearTask,
    isCheckingForActiveTasks,
  };
}; 