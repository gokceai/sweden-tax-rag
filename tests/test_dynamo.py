import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.dynamo_client import dynamo_db

def run_test():
    print("--- DynamoDB Connection Test ---")
    try:
        table = dynamo_db.create_table_if_not_exists()
        print(f"The system verified the table's status.: {table.table_status}")
    except Exception as e:
        print(f"Connection failed.: {e}")

if __name__ == "__main__":
    run_test()