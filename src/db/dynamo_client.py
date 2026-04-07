import boto3
from botocore.exceptions import ClientError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DynamoDBManager:
    def __init__(self):
        # boto3 sussun ve sadece localhost'a gitsin diye her şeye 'test' yazıp geçiyoruz.
        self.dynamodb = boto3.resource(
            'dynamodb',
            endpoint_url='http://localhost:8000',
            region_name='eu-north-1',
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        self.table_name = 'SwedishTaxDocuments'
        self.table = None

    def create_table_if_not_exists(self):
        try:
            existing_tables = [table.name for table in self.dynamodb.tables.all()]
            
            if self.table_name in existing_tables:
                logger.info(f"Tablo '{self.table_name}' is available. Connected.")
                self.table = self.dynamodb.Table(self.table_name)
                return self.table

            logger.info(f"Tablo '{self.table_name}' not found. Creating....")
            self.table = self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {
                        'AttributeName': 'chunk_id', 
                        'KeyType': 'HASH'  
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'chunk_id',
                        'AttributeType': 'S' 
                    }
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            self.table.meta.client.get_waiter('table_exists').wait(TableName=self.table_name)
            logger.info(f"Table '{self.table_name}' created successfully!")
            return self.table

        except ClientError as e:
            logger.error(f"DynamoDB Error: {e}")
            raise e

dynamo_db = DynamoDBManager()