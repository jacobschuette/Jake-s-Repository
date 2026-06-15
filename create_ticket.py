"""POST /tickets — create a new support ticket."""

import json
import logging
import uuid
from datetime import datetime, timezone

from utils.db import put_item
from utils.response import error, ok

logger = logging.getLogger()
logger.setLevel(logging.INFO)

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_STATUSES = {"open", "in-progress", "closed"}


def handler(event, context):
    logger.info("create_ticket invoked", extra={"request_id": context.aws_request_id})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Request body must be valid JSON")

    title = (body.get("title") or "").strip()
    if not title:
        return error("'title' is required")

    priority = body.get("priority", "medium").lower()
    if priority not in VALID_PRIORITIES:
        return error(f"'priority' must be one of: {', '.join(sorted(VALID_PRIORITIES))}")

    now = datetime.now(timezone.utc).isoformat()
    ticket = {
        "ticket_id": str(uuid.uuid4()),
        "title": title,
        "description": (body.get("description") or "").strip(),
        "status": "open",
        "priority": priority,
        "assigned_to": body.get("assigned_to", ""),
        "created_at": now,
        "updated_at": now,
    }

    put_item(ticket)
    logger.info("Ticket created: %s", ticket["ticket_id"])
    return ok(ticket, status=201)
