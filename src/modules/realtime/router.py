import logging
import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from src.modules.auth.utils import decode_token
from src.modules.realtime.websocket_manager import manager

logger = logging.getLogger("wareops_erp.modules.realtime.router")

router = APIRouter(tags=["Realtime WebSockets"])


@router.websocket("/realtime/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    Scope-isolated WebSocket connection broker.
    Authenticates query parameters and routes updates per tenant and warehouse boundaries.
    """
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        logger.warning("Rejected WebSocket connection: Expired JWT token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session expired. Please reconnect.")
        return
    except jwt.InvalidTokenError:
        logger.warning("Rejected WebSocket connection: Invalid JWT token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid credentials.")
        return

    if payload.get("type") != "access":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token type context.")
        return

    tenant_id = payload.get("tenant_id")
    warehouse_id = payload.get("warehouse_id")
    user_id = payload.get("user_id")

    if not tenant_id or not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Malformed token claims.")
        return

    await manager.connect(websocket, tenant_id, warehouse_id)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket: user={user_id}")
    finally:
        await manager.disconnect(websocket, tenant_id, warehouse_id)
