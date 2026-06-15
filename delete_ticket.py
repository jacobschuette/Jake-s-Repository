"""DELETE /tickets/{ticket_id} — permanently remove a ticket."""

import logging

from utils.db import delete_item, get_item
from utils.response import error, ok

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    logger.info("delete_ticket invoked", extra={"request_id": context.aws_request_id})

    ticket_id = (event.get("pathParameters") or {}).get("ticket_id", "").strip()
    if not ticket_id:
        return error("'ticket_id' path parameter is required")

    if get_item(ticket_id) is None:
        return error(f"Ticket '{ticket_id}' not found", status=404)

    delete_item(ticket_id)
    logger.info("Ticket deleted: %s", ticket_id)
    return ok({"deleted": ticket_id})
