import logging
import jwt
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status, Depends
from src.modules.auth.utils import decode_token
from src.modules.realtime.websocket_manager import manager
from src.modules.auth.dependencies import get_current_user
from src.database import get_db

logger = logging.getLogger("wareops_erp.modules.realtime.router")

router = APIRouter(tags=["Realtime WebSockets & Notifications"])


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
            msg = await websocket.receive_json()
            if isinstance(msg, dict):
                event_type = msg.get("event")
                if event_type in ("row_lock", "row_unlock"):
                    table_id = msg.get("tableId")
                    row_id = msg.get("rowId")
                    user_name = msg.get("userName", "Someone")
                    if table_id and row_id:
                        # Broadcast lock/unlock status to other warehouse and global clients of this tenant
                        await manager.broadcast_event(
                            tenant_id=tenant_id,
                            event_type=event_type,
                            data={
                                "tableId": table_id,
                                "rowId": row_id,
                                "userId": user_id,
                                "userName": user_name
                            },
                            warehouse_id=warehouse_id
                        )
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket: user={user_id}")
    finally:
        await manager.disconnect(websocket, tenant_id, warehouse_id)


@router.get("/realtime/notifications")
async def get_notifications(
    unread_only: bool = Query(False, alias="unreadOnly"),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Retrieve notifications belonging to the logged-in user."""
    user_id = current_user.get("_id") or current_user.get("id")
    tenant_id = current_user["tenant_id"]
    
    query = {"userId": user_id, "tenant_id": tenant_id}
    if unread_only:
        query["read"] = False
        
    cursor = db.notifications.find(query).sort("timestamp", -1)
    notifications = await cursor.to_list(length=200)
    
    # Normalize _id keys
    for n in notifications:
        n["id"] = str(n["_id"])
        del n["_id"]
        
    return {
        "success": True,
        "data": notifications
    }


@router.post("/realtime/notifications", status_code=status.HTTP_201_CREATED)
async def create_notifications(
    payload: list[dict] | dict,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Create one or more notifications under user's tenant space."""
    tenant_id = current_user["tenant_id"]
    docs = []
    items = payload if isinstance(payload, list) else [payload]
    
    for item in items:
        doc = {
            "tenant_id": tenant_id,
            "type": item.get("type", "default"),
            "title": item.get("title", ""),
            "message": item.get("message", ""),
            "link": item.get("link", "/dashboard"),
            "userId": item.get("userId"),
            "warehouseId": item.get("targetWarehouseId"),
            "read": False,
            "timestamp": item.get("timestamp") or datetime.utcnow().isoformat()
        }
        docs.append(doc)
        
    if docs:
        await db.notifications.insert_many(docs)
        for doc in docs:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            
    return {
        "success": True,
        "data": docs
    }


@router.put("/realtime/notifications/{id}/read")
async def mark_notification_read(
    id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Mark a specific notification as read."""
    user_id = current_user.get("_id") or current_user.get("id")
    
    try:
        query = {"_id": ObjectId(id), "userId": user_id}
    except Exception:
        query = {"_id": id, "userId": user_id}
        
    await db.notifications.update_one(query, {"$set": {"read": True}})
    return {
        "success": True,
        "message": "Notification marked as read successfully."
    }


@router.put("/realtime/notifications/read-all")
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Mark all notifications of the caller as read."""
    user_id = current_user.get("_id") or current_user.get("id")
    await db.notifications.update_many({"userId": user_id, "read": False}, {"$set": {"read": True}})
    return {
        "success": True,
        "message": "All notifications successfully marked as read."
    }


@router.delete("/realtime/notifications/clear")
async def clear_notifications(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """De-register and remove all notifications of the caller."""
    user_id = current_user.get("_id") or current_user.get("id")
    await db.notifications.delete_many({"userId": user_id})
    return {
        "success": True,
        "message": "Notifications successfully cleared."
    }
