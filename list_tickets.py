"""GET /tickets — list all tickets, optionally filtered by status."""

import logging

from utils.db import scan_items
from utils.response import error, ok

logger = logging.getLogger()
logger.setLevel(logging.INFO)

VALID_STATUSES = {"open", "in-progress", "closed"}


def handler(event, context):
    logger.info("list_tickets invoked", extra={"request_id": context.aws_request_id})

    params = event.get("queryStringParameters") or {}
    status_filter = params.get("status")

    if status_filter and status_filter not in VALID_STATUSES:
        return error(f"'status' must be one of: {', '.join(sorted(VALID_STATUSES))}")

    tickets = scan_items(status_filter=status_filter)
    tickets.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    logger.info("Returning %d tickets (filter=%s)", len(tickets), status_filter)
    return ok({"tickets": tickets, "count": len(tickets)})
