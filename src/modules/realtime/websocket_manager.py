import logging
import asyncio
from fastapi import WebSocket
from typing import Dict, Set, Optional

logger = logging.getLogger("wareops_erp.modules.realtime.websocket_manager")


class WebSocketManager:
    """Thread-safe Multi-tenant WebSocket Connection Manager."""
    def __init__(self):
        # active_connections[tenant_id][warehouse_id] -> set of WebSocket connections
        # warehouse_id can be "global" for super admins
        self.active_connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, tenant_id: str, warehouse_id: Optional[str] = None):
        async with self._lock:
            await websocket.accept()
            wh_key = warehouse_id if warehouse_id else "global"
            
            if tenant_id not in self.active_connections:
                self.active_connections[tenant_id] = {}
            if wh_key not in self.active_connections[tenant_id]:
                self.active_connections[tenant_id][wh_key] = set()
                
            self.active_connections[tenant_id][wh_key].add(websocket)
            logger.info(f"WebSocket client connected: tenant={tenant_id}, warehouse={wh_key}")

    async def disconnect(self, websocket: WebSocket, tenant_id: str, warehouse_id: Optional[str] = None):
        async with self._lock:
            wh_key = warehouse_id if warehouse_id else "global"
            if tenant_id in self.active_connections and wh_key in self.active_connections[tenant_id]:
                self.active_connections[tenant_id][wh_key].discard(websocket)
                if not self.active_connections[tenant_id][wh_key]:
                    del self.active_connections[tenant_id][wh_key]
                if not self.active_connections[tenant_id]:
                    del self.active_connections[tenant_id]
            logger.info(f"WebSocket client disconnected: tenant={tenant_id}, warehouse={wh_key}")

    async def broadcast_event(
        self, 
        tenant_id: str, 
        event_type: str, 
        data: dict, 
        warehouse_id: Optional[str] = None
    ):
        """
        Broadcast event to matching clients.
        - If warehouse_id is specified: broadcast to standard clients in that warehouse,
          AND to all "global" (Super Admin) clients of that tenant.
        - If warehouse_id is None: broadcast to all clients of that tenant globally.
        """
        async with self._lock:
            if tenant_id not in self.active_connections:
                return

            payload = {
                "type": event_type,
                "data": data
            }
            
            target_sockets = set()
            wh_key = warehouse_id if warehouse_id else "global"

            if warehouse_id:
                if wh_key in self.active_connections[tenant_id]:
                    target_sockets.update(self.active_connections[tenant_id][wh_key])
                if "global" in self.active_connections[tenant_id]:
                    target_sockets.update(self.active_connections[tenant_id]["global"])
            else:
                for wh_scope in self.active_connections[tenant_id].values():
                    target_sockets.update(wh_scope)

        if not target_sockets:
            return

        # Perform socket sends outside of lock to avoid bottleneck
        async def send_json(ws: WebSocket):
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.debug(f"Failed to send websocket payload: {e}")

        await asyncio.gather(*(send_json(ws) for ws in target_sockets), return_exceptions=True)


manager = WebSocketManager()
