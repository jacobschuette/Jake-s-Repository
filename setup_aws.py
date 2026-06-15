"""
Provision AWS infrastructure for the ticket system:
  - DynamoDB table
  - IAM role for Lambda
  - Four Lambda functions
  - API Gateway (HTTP API)
  - CloudWatch log groups with 30-day retention

Run once before first deploy:
    python infrastructure/setup_aws.py
"""

import json
import os
import time
import zipfile
from io import BytesIO
from pathlib import Path

import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
TABLE_NAME = "Tickets"
LAMBDA_ROLE_NAME = "ticket-system-lambda-role"
LOG_RETENTION_DAYS = 30

FUNCTIONS = [
    {"name": "ticket-create",  "handler": "create_ticket.handler",  "method": "POST",   "path": "/tickets"},
    {"name": "ticket-get",     "handler": "get_ticket.handler",     "method": "GET",    "path": "/tickets/{ticket_id}"},
    {"name": "ticket-update",  "handler": "update_ticket.handler",  "method": "PUT",    "path": "/tickets/{ticket_id}"},
    {"name": "ticket-list",    "handler": "list_tickets.handler",   "method": "GET",    "path": "/tickets"},
    {"name": "ticket-delete",  "handler": "delete_ticket.handler",  "method": "DELETE", "path": "/tickets/{ticket_id}"},
]

LAMBDA_TRUST = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
})

LAMBDA_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem",
                       "dynamodb:DeleteItem", "dynamodb:Scan"],
            "Resource": f"arn:aws:dynamodb:{REGION}:*:table/{TABLE_NAME}",
        },
        {
            "Effect": "Allow",
            "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": "arn:aws:logs:*:*:*",
        },
    ],
})


def zip_lambda_code() -> bytes:
    lambda_dir = Path(__file__).parent.parent / "lambda"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in lambda_dir.rglob("*.py"):
            zf.write(path, path.relative_to(lambda_dir))
    return buf.getvalue()


def create_dynamodb_table(client):
    try:
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "ticket_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "ticket_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        client.get_waiter("table_exists").wait(TableName=TABLE_NAME)
        print(f"  Created DynamoDB table: {TABLE_NAME}")
    except client.exceptions.ResourceInUseException:
        print(f"  DynamoDB table already exists: {TABLE_NAME}")


def create_iam_role(iam) -> str:
    try:
        role = iam.create_role(
            RoleName=LAMBDA_ROLE_NAME,
            AssumeRolePolicyDocument=LAMBDA_TRUST,
            Description="Execution role for ticket-system Lambda functions",
        )
        iam.put_role_policy(
            RoleName=LAMBDA_ROLE_NAME,
            PolicyName="ticket-system-policy",
            PolicyDocument=LAMBDA_POLICY,
        )
        arn = role["Role"]["Arn"]
        print(f"  Created IAM role: {arn}")
        time.sleep(10)  # IAM propagation delay
        return arn
    except iam.exceptions.EntityAlreadyExistsException:
        arn = iam.get_role(RoleName=LAMBDA_ROLE_NAME)["Role"]["Arn"]
        print(f"  IAM role already exists: {arn}")
        return arn


def deploy_lambda(client, func: dict, role_arn: str, code: bytes) -> str:
    env = {"Variables": {"DYNAMODB_TABLE": TABLE_NAME, "AWS_REGION": REGION}}
    try:
        response = client.create_function(
            FunctionName=func["name"],
            Runtime="python3.12",
            Role=role_arn,
            Handler=func["handler"],
            Code={"ZipFile": code},
            Environment=env,
            Timeout=30,
            MemorySize=256,
        )
        arn = response["FunctionArn"]
        print(f"  Created Lambda: {func['name']}")
    except client.exceptions.ResourceConflictException:
        client.update_function_code(FunctionName=func["name"], ZipFile=code)
        response = client.update_function_configuration(
            FunctionName=func["name"], Environment=env
        )
        arn = response["FunctionArn"]
        print(f"  Updated Lambda: {func['name']}")
    return arn


def create_log_group(logs, func_name: str):
    group = f"/aws/lambda/{func_name}"
    try:
        logs.create_log_group(logGroupName=group)
    except logs.exceptions.ResourceAlreadyExistsException:
        pass
    logs.put_retention_policy(logGroupName=group, retentionInDays=LOG_RETENTION_DAYS)
    print(f"  Log group ready: {group} (retention={LOG_RETENTION_DAYS}d)")


def create_api_gateway(apigw, lambda_client, function_arns: dict) -> str:
    api = apigw.create_api(
        Name="ticket-system-api",
        ProtocolType="HTTP",
        CorsConfiguration={
            "AllowOrigins": ["*"],
            "AllowMethods": ["GET", "POST", "PUT", "DELETE"],
            "AllowHeaders": ["Content-Type"],
        },
    )
    api_id = api["ApiId"]
    print(f"  Created API Gateway: {api_id}")

    for func in FUNCTIONS:
        arn = function_arns[func["name"]]
        integration = apigw.create_integration(
            ApiId=api_id,
            IntegrationType="AWS_PROXY",
            IntegrationUri=arn,
            PayloadFormatVersion="2.0",
        )
        apigw.create_route(
            ApiId=api_id,
            RouteKey=f"{func['method']} {func['path']}",
            Target=f"integrations/{integration['IntegrationId']}",
        )
        # Allow API Gateway to invoke this Lambda
        lambda_client.add_permission(
            FunctionName=func["name"],
            StatementId=f"apigw-{func['name']}",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:{REGION}:*:{api_id}/*/*",
        )

    stage = apigw.create_stage(ApiId=api_id, StageName="$default", AutoDeploy=True)
    endpoint = stage.get("ApiGatewayManaged", {})
    url = f"https://{api_id}.execute-api.{REGION}.amazonaws.com"
    print(f"  API endpoint: {url}")
    return url


def main():
    print("=== Ticket System — AWS Setup ===\n")
    session = boto3.Session(region_name=REGION)

    print("[1/5] DynamoDB table")
    create_dynamodb_table(session.client("dynamodb"))

    print("\n[2/5] IAM role")
    role_arn = create_iam_role(session.client("iam"))

    print("\n[3/5] Lambda functions")
    lambda_client = session.client("lambda")
    logs_client = session.client("logs")
    code = zip_lambda_code()
    function_arns = {}
    for func in FUNCTIONS:
        arn = deploy_lambda(lambda_client, func, role_arn, code)
        create_log_group(logs_client, func["name"])
        function_arns[func["name"]] = arn

    print("\n[4/5] API Gateway")
    endpoint = create_api_gateway(session.client("apigatewayv2"), lambda_client, function_arns)

    print("\n[5/5] Done!")
    print(f"\nBase URL: {endpoint}")
    print("  POST   /tickets")
    print("  GET    /tickets")
    print("  GET    /tickets/{{ticket_id}}")
    print("  PUT    /tickets/{{ticket_id}}")
    print("  DELETE /tickets/{{ticket_id}}")


if __name__ == "__main__":
    main()
