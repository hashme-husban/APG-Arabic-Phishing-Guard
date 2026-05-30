from __future__ import annotations

import json
from typing import Any
from sqlalchemy.orm import Session
from app.models import AdminAction, User


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def record_admin_action(
    db: Session,
    admin: User | None,
    action_type: str,
    target_type: str,
    target_id: int | None = None,
    *,
    old_value: Any = None,
    new_value: Any = None,
    note: str | None = None,
    metadata: Any = None,
) -> AdminAction:
    action = AdminAction(
        admin_id=admin.id if admin else None,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        old_value=_dump(old_value),
        new_value=_dump(new_value),
        note=note,
        metadata_json=metadata if isinstance(metadata, dict) else None,
    )
    db.add(action)
    return action
