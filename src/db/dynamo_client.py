import logging

import boto3
from botocore.exceptions import ClientError

from src.core.config import settings
from src.core.exceptions import InfrastructureError

logger = logging.getLogger(__name__)


class DynamoDBManager:
    def __init__(self):
        self.dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url=settings.DYNAMO_ENDPOINT,
            region_name=settings.DYNAMO_REGION,
            aws_access_key_id=settings.DYNAMO_ACCESS_KEY_ID,
            aws_secret_access_key=settings.DYNAMO_SECRET_ACCESS_KEY,
        )
        self.table_name = settings.DYNAMO_TABLE_NAME
        self.table = None

    def create_table_if_not_exists(self):
        try:
            existing_tables = [table.name for table in self.dynamodb.tables.all()]
            if self.table_name in existing_tables:
                logger.info("DynamoDB table '%s' already exists.", self.table_name)
                self.table = self.dynamodb.Table(self.table_name)
                return self.table

            logger.info("DynamoDB table '%s' not found. Creating...", self.table_name)
            self.table = self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {
                        "AttributeName": "chunk_id",
                        "KeyType": "HASH",
                    }
                ],
                AttributeDefinitions=[
                    {
                        "AttributeName": "chunk_id",
                        "AttributeType": "S",
                    }
                ],
                ProvisionedThroughput={
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            )
            self.table.meta.client.get_waiter("table_exists").wait(TableName=self.table_name)
            logger.info("DynamoDB table '%s' created successfully.", self.table_name)
            return self.table
        except ClientError as e:
            raise InfrastructureError(f"DynamoDB operation failed: {e}") from e
