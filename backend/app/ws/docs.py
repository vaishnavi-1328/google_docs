"""Yjs sync websocket endpoint.

Implements the y-websocket wire protocol minimally so the official JS client
in the frontend can connect directly. The server:

  * authenticates the connection via the session cookie
    (guardrail 3: tenant_id comes from the signed JWT, nothing else)
  * verifies the user is a member of the tenant AND the document belongs to
    that tenant (guardrail 2 + 4 via SET LOCAL app.tenant_id + membership check)
  * seeds the connecting client with the latest persisted Yjs state from
    Postgres, and broadcasts updates to all other connected clients
  * persists the merged Yjs state on the last disconnect so the next session
    starts from where the room left off

Wire protocol (matches y-protocols/sync + y-protocols/awareness):
  message[0] == 0  -> sync message (sub-messages 0=step1, 1=step2, 2=update)
  message[0] == 1  -> awareness update (opaque; broadcast as-is)

Only these two message types are forwarded; anything else is dropped.
"""
from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Cookie, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select, text, update

from ..authz import effective_role, has_at_least
from ..db import SessionLocal
from ..models import ROLE_EDITOR, ROLE_VIEWER, Document, DocumentSnapshot, Membership
from ..security import decode_session_token
from ..settings import get_settings

SNAPSHOT_INTERVAL_SECONDS = 300  # 5 minutes

try:
    # pycrdt is the actively-maintained successor to y-py; same Yjs wire format.
    from pycrdt import Doc as _PyCrdtDoc  # type: ignore[import-untyped]

    def _new_ydoc():
        return _PyCrdtDoc()

    def apply_update(doc, update: bytes) -> None:
        doc.apply_update(update)

    def encode_state_as_update(doc, _sv: bytes | None = None) -> bytes:
        # pycrdt's get_update() with no state vector returns the full state as
        # a single update, which is the behavior we want for persistence +
        # new-client seeding.
        if _sv is None or _sv == b"\x00":
            return bytes(doc.get_update())
        return bytes(doc.get_update(_sv))

    def encode_state_vector(doc) -> bytes:
        return bytes(doc.get_state())

    YDoc = _PyCrdtDoc  # type: ignore[assignment]
except Exception:  # pragma: no cover - import error surfaces on first connect
    YDoc = None  # type: ignore[assignment]

router = APIRouter()

MSG_SYNC = 0
MSG_AWARENESS = 1
SYNC_STEP1 = 0
SYNC_STEP2 = 1
SYNC_UPDATE = 2


class _Room:
    """One Yjs document kept in memory while anyone is connected."""

    def __init__(self, doc_id: UUID, initial_state: bytes | None):
        if YDoc is None:
            raise RuntimeError("pycrdt is required for realtime collab")
        self.doc_id = doc_id
        self.ydoc = _new_ydoc()
        if initial_state:
            apply_update(self.ydoc, initial_state)
        self.clients: set[WebSocket] = set()
        self.lock = asyncio.Lock()


_rooms: dict[UUID, _Room] = {}
_rooms_lock = asyncio.Lock()


def _encode_varuint(n: int) -> bytes:
    out = bytearray()
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n & 0x7F)
    return bytes(out)


def _decode_varuint(buf: bytes, i: int) -> tuple[int, int]:
    n = 0
    shift = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not (b & 0x80):
            return n, i
        shift += 7


def _encode_bytes(payload: bytes) -> bytes:
    return _encode_varuint(len(payload)) + payload


def _decode_bytes(buf: bytes, i: int) -> tuple[bytes, int]:
    n, i = _decode_varuint(buf, i)
    return buf[i : i + n], i + n


def _build_sync_step1(ydoc) -> bytes:
    sv = encode_state_vector(ydoc)
    return bytes([MSG_SYNC, SYNC_STEP1]) + _encode_bytes(sv)


def _build_sync_step2(ydoc, remote_sv: bytes) -> bytes:
    update = encode_state_as_update(ydoc, remote_sv)
    return bytes([MSG_SYNC, SYNC_STEP2]) + _encode_bytes(update)


def _build_sync_update(update: bytes) -> bytes:
    return bytes([MSG_SYNC, SYNC_UPDATE]) + _encode_bytes(update)


async def _get_or_create_room(doc_id: UUID, tenant_id: UUID) -> _Room:
    async with _rooms_lock:
        room = _rooms.get(doc_id)
        if room is not None:
            return room
        # Load initial state from Postgres under the correct tenant GUC.
        state: bytes | None = None
        s = SessionLocal()
        try:
            s.begin()
            s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
            doc = s.get(Document, doc_id)
            if doc is not None:
                state = doc.ydoc_state
            s.commit()
        finally:
            s.close()
        room = _Room(doc_id, state)
        _rooms[doc_id] = room
        asyncio.create_task(_periodic_snapshotter(room, tenant_id))
        return room


async def _persist_and_maybe_evict(room: _Room, tenant_id: UUID, snapshot: bool = False) -> None:
    """Write the room's merged state back to Postgres; drop room if empty."""
    update_bytes = encode_state_as_update(room.ydoc, b"\x00")
    s = SessionLocal()
    try:
        s.begin()
        s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
        s.execute(
            update(Document)
            .where(Document.id == room.doc_id)
            .values(ydoc_state=update_bytes)
        )
        if snapshot:
            s.add(
                DocumentSnapshot(
                    tenant_id=tenant_id,
                    document_id=room.doc_id,
                    ydoc_state=update_bytes,
                    label="Autosave",
                )
            )
            # Prune: keep 30 most recent autosaves + all user-labeled snapshots.
            s.execute(
                text(
                    """
                    DELETE FROM document_snapshots
                    WHERE document_id = :d
                      AND label = 'Autosave'
                      AND id NOT IN (
                          SELECT id FROM document_snapshots
                          WHERE document_id = :d AND label = 'Autosave'
                          ORDER BY created_at DESC LIMIT 30
                      )
                    """
                ),
                {"d": str(room.doc_id)},
            )
        s.commit()
    finally:
        s.close()
    async with _rooms_lock:
        if not room.clients:
            _rooms.pop(room.doc_id, None)


async def _periodic_snapshotter(room: _Room, tenant_id: UUID) -> None:
    try:
        while True:
            await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)
            if not room.clients:
                return
            await _persist_and_maybe_evict(room, tenant_id, snapshot=True)
    except asyncio.CancelledError:
        pass


async def _broadcast(room: _Room, data: bytes, origin: WebSocket) -> None:
    dead: list[WebSocket] = []
    for ws in room.clients:
        if ws is origin:
            continue
        try:
            await ws.send_bytes(data)
        except Exception:
            dead.append(ws)
    for d in dead:
        room.clients.discard(d)


def _authorize(session_cookie: str | None, doc_id: UUID) -> tuple[UUID, UUID, str]:
    if not session_cookie:
        raise PermissionError("no session")
    try:
        user_id, tenant_id = decode_session_token(session_cookie)
    except ValueError as exc:
        raise PermissionError("invalid session") from exc

    s = SessionLocal()
    try:
        s.begin()
        # Membership check (guardrail 3) — memberships has NO FORCE RLS so
        # this lookup works without a tenant GUC.
        m = s.execute(
            select(Membership).where(
                Membership.user_id == user_id, Membership.tenant_id == tenant_id
            )
        ).scalar_one_or_none()
        if m is None:
            s.rollback()
            raise PermissionError("not a member")
        # Set tenant GUC so RLS policies filter correctly.
        s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
        doc = s.get(Document, doc_id)
        if doc is None:
            s.rollback()
            raise PermissionError("not found")
        role = effective_role(s, user_id=user_id, document_id=doc_id)
        s.commit()
        if not has_at_least(role, ROLE_VIEWER):
            raise PermissionError("no access")
    except PermissionError:
        raise
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
    return user_id, tenant_id, role or ROLE_VIEWER


@router.websocket("/ws/docs/{doc_id}")
async def ws_doc(
    websocket: WebSocket,
    doc_id: UUID,
    session: str | None = Cookie(default=None, alias="session"),
) -> None:
    # Origin check — refuse upgrades from untrusted origins.
    origin = websocket.headers.get("origin")
    allowed = set(get_settings().allowed_origins_list)
    if origin is not None and origin not in allowed:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        _user_id, tenant_id, role = _authorize(session, doc_id)
    except PermissionError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    can_write = has_at_least(role, ROLE_EDITOR)

    await websocket.accept()
    room = await _get_or_create_room(doc_id, tenant_id)
    async with room.lock:
        room.clients.add(websocket)

    # Seed the new client: send sync-step1 so it can reply with what we lack.
    try:
        await websocket.send_bytes(_build_sync_step1(room.ydoc))
    except Exception:
        async with room.lock:
            room.clients.discard(websocket)
        return

    try:
        while True:
            msg = await websocket.receive_bytes()
            if not msg:
                continue
            kind = msg[0]
            if kind == MSG_SYNC:
                if len(msg) < 2:
                    continue
                sub = msg[1]
                payload, _ = _decode_bytes(msg, 2)
                if sub == SYNC_STEP1:
                    await websocket.send_bytes(_build_sync_step2(room.ydoc, payload))
                elif sub == SYNC_STEP2 or sub == SYNC_UPDATE:
                    if not can_write:
                        # Viewers/commenters can observe but not mutate the Yjs state.
                        continue
                    apply_update(room.ydoc, payload)
                    await _broadcast(room, _build_sync_update(payload), origin=websocket)
            elif kind == MSG_AWARENESS:
                # Opaque; just relay to peers.
                await _broadcast(room, msg, origin=websocket)
            # anything else: drop
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        async with room.lock:
            room.clients.discard(websocket)
        await _persist_and_maybe_evict(room, tenant_id)
