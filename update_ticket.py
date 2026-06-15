"""PUT /tickets/{ticket_id} — update status, priority, assignment, or description."""

import json
import logging
from datetime import datetime, timezone

from utils.db import get_item, update_item
from utils.response import error, ok

logger = logging.getLogger()
logger.setLevel(logging.INFO)

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_STATUSES = {"open", "in-progress", "closed"}
MUTABLE_FIELDS = {"title", "description", "status", "priority", "assigned_to"}


def handler(event, context):
    logger.info("update_ticket invoked", extra={"request_id": context.aws_request_id})

    ticket_id = (event.get("pathParameters") or {}).get("ticket_id", "").strip()
    if not ticket_id:
        return error("'ticket_id' path parameter is required")

    if get_item(ticket_id) is None:
        return error(f"Ticket '{ticket_id}' not found", status=404)

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Request body must be valid JSON")

    updates = {k: v for k, v in body.items() if k in MUTABLE_FIELDS}
    if not updates:
        return error(f"Provide at least one of: {', '.join(sorted(MUTABLE_FIELDS))}")

    if "status" in updates and updates["status"] not in VALID_STATUSES:
        return error(f"'status' must be one of: {', '.join(sorted(VALID_STATUSES))}")

    if "priority" in updates and updates["priority"] not in VALID_PRIORITIES:
        return error(f"'priority' must be one of: {', '.join(sorted(VALID_PRIORITIES))}")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updated = update_item(ticket_id, updates)
    logger.info("Ticket updated: %s fields=%s", ticket_id, list(updates.keys()))
    return ok(updated)
