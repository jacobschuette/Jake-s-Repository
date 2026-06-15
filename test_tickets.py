"""Unit tests — Lambda handlers with a mocked DynamoDB table."""

import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Fake Lambda context
CTX = SimpleNamespace(aws_request_id="test-req-id")


def _event(method="GET", body=None, path_params=None, query_params=None):
    return {
        "httpMethod": method,
        "body": json.dumps(body) if body else None,
        "pathParameters": path_params or {},
        "queryStringParameters": query_params or {},
    }


class TestCreateTicket(unittest.TestCase):
    @patch("create_ticket.put_item")
    def test_happy_path(self, mock_put):
        mock_put.side_effect = lambda item: item
        import create_ticket

        evt = _event("POST", body={"title": "Server down", "priority": "high"})
        resp = create_ticket.handler(evt, CTX)
        self.assertEqual(resp["statusCode"], 201)
        data = json.loads(resp["body"])
        self.assertEqual(data["title"], "Server down")
        self.assertEqual(data["priority"], "high")
        self.assertEqual(data["status"], "open")
        self.assertIn("ticket_id", data)

    @patch("create_ticket.put_item")
    def test_missing_title(self, _):
        import create_ticket

        evt = _event("POST", body={"priority": "low"})
        resp = create_ticket.handler(evt, CTX)
        self.assertEqual(resp["statusCode"], 400)

    @patch("create_ticket.put_item")
    def test_invalid_priority(self, _):
        import create_ticket

        evt = _event("POST", body={"title": "Bug", "priority": "urgent"})
        resp = create_ticket.handler(evt, CTX)
        self.assertEqual(resp["statusCode"], 400)


class TestGetTicket(unittest.TestCase):
    @patch("get_ticket.get_item")
    def test_found(self, mock_get):
        mock_get.return_value = {"ticket_id": "abc", "title": "Test"}
        import get_ticket

        evt = _event(path_params={"ticket_id": "abc"})
        resp = get_ticket.handler(evt, CTX)
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(json.loads(resp["body"])["ticket_id"], "abc")

    @patch("get_ticket.get_item")
    def test_not_found(self, mock_get):
        mock_get.return_value = None
        import get_ticket

        evt = _event(path_params={"ticket_id": "missing"})
        resp = get_ticket.handler(evt, CTX)
        self.assertEqual(resp["statusCode"], 404)


class TestUpdateTicket(unittest.TestCase):
    @patch("update_ticket.update_item")
    @patch("update_ticket.get_item")
    def test_update_status(self, mock_get, mock_update):
        mock_get.return_value = {"ticket_id": "abc", "status": "open"}
        mock_update.return_value = {"ticket_id": "abc", "status": "closed"}
        import update_ticket

        evt = _event("PUT", body={"status": "closed"}, path_params={"ticket_id": "abc"})
        resp = update_ticket.handler(evt, CTX)
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(json.loads(resp["body"])["status"], "closed")

    @patch("update_ticket.get_item")
    def test_invalid_status(self, mock_get):
        mock_get.return_value = {"ticket_id": "abc"}
        import update_ticket

        evt = _event("PUT", body={"status": "pending"}, path_params={"ticket_id": "abc"})
        resp = update_ticket.handler(evt, CTX)
        self.assertEqual(resp["statusCode"], 400)

    @patch("update_ticket.get_item")
    def test_no_valid_fields(self, mock_get):
        mock_get.return_value = {"ticket_id": "abc"}
        import update_ticket

        evt = _event("PUT", body={"foo": "bar"}, path_params={"ticket_id": "abc"})
        resp = update_ticket.handler(evt, CTX)
        self.assertEqual(resp["statusCode"], 400)


class TestListTickets(unittest.TestCase):
    @patch("list_tickets.scan_items")
    def test_list_all(self, mock_scan):
        mock_scan.return_value = [
            {"ticket_id": "1", "created_at": "2026-01-02"},
            {"ticket_id": "2", "created_at": "2026-01-01"},
        ]
        import list_tickets

        evt = _event()
        resp = list_tickets.handler(evt, CTX)
        self.assertEqual(resp["statusCode"], 200)
        data = json.loads(resp["body"])
        self.assertEqual(data["count"], 2)

    @patch("list_tickets.scan_items")
    def test_filter_by_status(self, mock_scan):
        mock_scan.return_value = []
        import list_tickets

        evt = _event(query_params={"status": "open"})
        resp = list_tickets.handler(evt, CTX)
        mock_scan.assert_called_once_with(status_filter="open")
        self.assertEqual(resp["statusCode"], 200)

    @patch("list_tickets.scan_items")
    def test_invalid_status_filter(self, _):
        import list_tickets

        evt = _event(query_params={"status": "bogus"})
        resp = list_tickets.handler(evt, CTX)
        self.assertEqual(resp["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
