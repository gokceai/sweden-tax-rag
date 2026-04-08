from src.core.config import settings
from src.db.dynamo_client import DynamoDBManager


class FakeTables:
    def all(self):
        return []


class FakeWaiter:
    def wait(self, TableName):
        return None


class FakeClient:
    def get_waiter(self, _):
        return FakeWaiter()


class FakeTableMeta:
    def __init__(self):
        self.client = FakeClient()


class FakeTable:
    def __init__(self):
        self.meta = FakeTableMeta()


class FakeResource:
    def __init__(self):
        self.tables = FakeTables()

    def Table(self, name):
        return FakeTable()

    def create_table(self, **kwargs):
        return FakeTable()


def test_dynamo_manager_uses_settings(monkeypatch):
    captured = {}

    def fake_resource(service_name, endpoint_url, region_name, aws_access_key_id, aws_secret_access_key):
        captured["service_name"] = service_name
        captured["endpoint_url"] = endpoint_url
        captured["region_name"] = region_name
        captured["aws_access_key_id"] = aws_access_key_id
        captured["aws_secret_access_key"] = aws_secret_access_key
        return FakeResource()

    monkeypatch.setattr("src.db.dynamo_client.boto3.resource", fake_resource)

    manager = DynamoDBManager()

    assert manager.table_name == settings.DYNAMO_TABLE_NAME
    assert captured["endpoint_url"] == settings.DYNAMO_ENDPOINT
