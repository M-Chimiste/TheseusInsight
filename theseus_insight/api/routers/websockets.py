from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List

from ..tasks import task_manager, TaskStatus

router = APIRouter(tags=["websockets"])

# Enhance the WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        """Connect a new WebSocket client."""
        try:
            await websocket.accept()
            if task_id not in self.active_connections:
                self.active_connections[task_id] = []
            self.active_connections[task_id].append(websocket)
        except Exception as e:
            print(f"Error connecting WebSocket: {e}")
            try:
                await websocket.close(code=4000, reason=str(e))
            except Exception:
                pass
            raise

    def disconnect(self, task_id: str, websocket: WebSocket):
        """Disconnect a WebSocket client."""
        try:
            if task_id in self.active_connections:
                if websocket in self.active_connections[task_id]:
                    self.active_connections[task_id].remove(websocket)
                if not self.active_connections[task_id]:
                    del self.active_connections[task_id]
        except Exception as e:
            print(f"Error disconnecting WebSocket: {e}")

    async def broadcast_status(self, task_id: str, status):
        """Broadcast status to all connected clients for a task."""
        if task_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(status.dict())
                except WebSocketDisconnect:
                    dead_connections.append(connection)
                except Exception as e:
                    print(f"Error broadcasting to WebSocket: {e}")
                    dead_connections.append(connection)
            
            # Clean up dead connections
            for dead in dead_connections:
                self.disconnect(task_id, dead)

    async def close_all(self, task_id: str):
        """Close all connections for a task."""
        if task_id in self.active_connections:
            connections_to_close = self.active_connections[task_id].copy()
            for connection in connections_to_close:
                try:
                    await connection.close(code=1000)
                except Exception:
                    pass
            del self.active_connections[task_id]
    
    async def cleanup_all(self):
        """Close all active connections."""
        task_ids = list(self.active_connections.keys())
        for task_id in task_ids:
            await self.close_all(task_id)

manager = ConnectionManager()

async def handle_websocket_connection(websocket: WebSocket, task_id: str, endpoint_name: str):
    """Generic WebSocket handler for all task types."""
    status_queue = None
    try:
        await manager.connect(task_id, websocket)
        
        # Subscribe to task updates
        status_queue = await task_manager.subscribe_to_updates(task_id)
        
        while True:
            # Wait for status updates
            status = await status_queue.get()
            
            # Check for cleanup sentinel
            if status is None:
                break
                
            await websocket.send_json(status.dict())
            
            # If task is completed or failed, close connection
            if status.overallStatus in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                break
                
    except WebSocketDisconnect:
        pass
    except ValueError as e:
        try:
            await websocket.close(code=4004, reason=str(e))
        except Exception:
            pass
    except Exception as e:
        try:
            await websocket.close(code=4000, reason=str(e))
        except Exception:
            pass
    finally:
        if status_queue:
            await task_manager.unsubscribe_from_updates(task_id, status_queue)
        manager.disconnect(task_id, websocket)

# WebSocket endpoints
@router.websocket("/ws/newsletter/{task_id}")
async def newsletter_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for newsletter generation status updates."""
    await handle_websocket_connection(websocket, task_id, "newsletter")

@router.websocket("/ws/podcast/{task_id}")
async def podcast_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for podcast generation status updates."""
    await handle_websocket_connection(websocket, task_id, "podcast")

@router.websocket("/ws/visualizer/{task_id}")
async def visualizer_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for visualizer generation status updates."""
    await handle_websocket_connection(websocket, task_id, "visualizer")

@router.websocket("/ws/database-import/{task_id}")
async def database_import_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for database import status updates."""
    await handle_websocket_connection(websocket, task_id, "database-import")

@router.websocket("/ws/database-export/{task_id}")
async def database_export_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for database export status updates."""
    await handle_websocket_connection(websocket, task_id, "database-export") 