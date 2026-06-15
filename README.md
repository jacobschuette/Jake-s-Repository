[README.md](https://github.com/user-attachments/files/28977479/README.md)
# Jake-s-Repository
# Cloud-Based Ticket Automation System

REST API for ticket tracking built on AWS Lambda + DynamoDB + CloudWatch.

## Architecture

```
Client → API Gateway (HTTP API)
              │
    ┌─────────┴─────────┐
    │   Lambda Functions │
    │  create / get /    │
    │  update / list /   │
    │  delete            │
    └─────────┬─────────┘
              │
          DynamoDB
          (Tickets table)
              │
          CloudWatch Logs
          (30-day retention)
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /tickets | Create a ticket |
| GET | /tickets | List all tickets |
| GET | /tickets/{ticket_id} | Get a single ticket |
| PUT | /tickets/{ticket_id} | Update a ticket |
| DELETE | /tickets/{ticket_id} | Delete a ticket |

## Ticket Schema

```json
{
  "ticket_id":   "uuid",
  "title":       "string (required)",
  "description": "string",
  "status":      "open | in-progress | closed",
  "priority":    "low | medium | high",
  "assigned_to": "string",
  "created_at":  "ISO-8601",
  "updated_at":  "ISO-8601"
}
```

## Setup

1. Configure AWS credentials:
   ```
   aws configure
   ```

2. Deploy infrastructure + Lambda functions:
   ```powershell
   .\deploy.ps1
   ```
   The script prints the base URL when done.

3. Run tests:
   ```
   cd lambda
   python -m pytest ../tests/ -v
   ```

## Example Requests

```bash
BASE="https://<api-id>.execute-api.us-east-1.amazonaws.com"

# Create
curl -X POST $BASE/tickets \
  -H "Content-Type: application/json" \
  -d '{"title":"Server down","priority":"high","description":"DB unreachable"}'

# List open tickets
curl "$BASE/tickets?status=open"

# Update status
curl -X PUT $BASE/tickets/<ticket_id> \
  -H "Content-Type: application/json" \
  -d '{"status":"in-progress","assigned_to":"jschuette"}'

# Delete
curl -X DELETE $BASE/tickets/<ticket_id>
```
