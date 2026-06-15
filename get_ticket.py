"""GET /tickets/{ticket_id} — retrieve a single ticket."""

import logging

from utils.db import get_item
from utils.response import error, ok

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    logger.info("get_ticket invoked", extra={"request_id": context.aws_request_id})

    ticket_id = (event.get("pathParameters") or {}).get("ticket_id", "").strip()
    if not ticket_id:
        return error("'ticket_id' path parameter is required")

    ticket = get_item(ticket_id)
    if ticket is None:
        return error(f"Ticket '{ticket_id}' not found", status=404)

    return ok(ticket)
