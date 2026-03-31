#!/usr/bin/env python3
"""
Operator Management CLI
Create and manage operators for production use

Usage:
    python manage_operators.py create <webhook_url> [--uuid <custom-uuid>]
    python manage_operators.py list
    python manage_operators.py delete <uuid>
    python manage_operators.py update <uuid> <new_webhook_url>
"""

import sys
import uuid
from datetime import datetime
from src.database import db_connection, DatabaseSchema, UnitOfWork
from src.database.models import Operator


def create_operator(webhook_url: str, custom_uuid: str = None):
    """Create a new operator"""
    # Initialize database
    conn = db_connection.get_connection()
    DatabaseSchema.initialize_database(conn)
    
    uow = UnitOfWork()
    
    operator_uuid = custom_uuid if custom_uuid else str(uuid.uuid4())
    
    operator = Operator(
        id=str(uuid.uuid4()),
        uuid=operator_uuid,
        webhook_url=webhook_url,
        created_at=datetime.now()
    )
    
    try:
        uow.operators.create(operator)
        print("\n" + "=" * 70)
        print("✓ Operator created successfully!")
        print("=" * 70)
        print(f"Operator ID:    {operator.id}")
        print(f"UUID (Token):   {operator.uuid}")
        print(f"Webhook URL:    {operator.webhook_url}")
        print(f"Created:        {operator.created_at}")
        print("=" * 70)
        print("\n🔑 Use this token for authentication:")
        print(f"   Authorization: Basic {operator.uuid}")
        print("\n📝 Example curl command:")
        print(f'''
curl -u "api:{operator.uuid}" \\
  -X POST "https://your-domain.com/omr:parse-sheet" \\
  -F "userId=student_001" \\
  -F "image=@sheet.jpg"
''')
        return operator
    except Exception as e:
        print(f"❌ Error creating operator: {e}")
        sys.exit(1)


def list_operators():
    """List all operators"""
    conn = db_connection.get_connection()
    DatabaseSchema.initialize_database(conn)
    
    uow = UnitOfWork()
    operators = uow.operators.find_all()
    
    if not operators:
        print("\n📭 No operators found in database")
        return
    
    print("\n" + "=" * 120)
    print(f"{'Operator ID':<38} {'UUID (Token)':<38} {'Webhook URL':<40}")
    print("=" * 120)
    
    for op in operators:
        print(f"{op.id:<38} {op.uuid:<38} {op.webhook_url:<40}")
    
    print("=" * 120)
    print(f"\nTotal operators: {len(operators)}\n")


def delete_operator(operator_uuid: str):
    """Delete an operator by UUID"""
    conn = db_connection.get_connection()
    DatabaseSchema.initialize_database(conn)
    
    uow = UnitOfWork()
    
    # Find operator first
    operator = uow.operators.find_by_uuid(operator_uuid)
    if not operator:
        print(f"❌ Operator with UUID '{operator_uuid}' not found")
        sys.exit(1)
    
    # Confirm deletion
    print(f"\n⚠️  About to delete operator:")
    print(f"   ID: {operator.id}")
    print(f"   UUID: {operator.uuid}")
    print(f"   Webhook: {operator.webhook_url}")
    
    confirm = input("\nType 'yes' to confirm deletion: ")
    if confirm.lower() != 'yes':
        print("❌ Deletion cancelled")
        return
    
    try:
        uow.operators.delete(operator.id)
        print(f"✓ Operator deleted successfully")
    except Exception as e:
        print(f"❌ Error deleting operator: {e}")
        sys.exit(1)


def update_operator(operator_uuid: str, new_webhook_url: str):
    """Update operator webhook URL"""
    conn = db_connection.get_connection()
    DatabaseSchema.initialize_database(conn)
    
    uow = UnitOfWork()
    
    # Find operator
    operator = uow.operators.find_by_uuid(operator_uuid)
    if not operator:
        print(f"❌ Operator with UUID '{operator_uuid}' not found")
        sys.exit(1)
    
    # Update
    operator.webhook_url = new_webhook_url
    
    try:
        uow.operators.update(operator)
        print(f"✓ Operator updated successfully")
        print(f"   UUID: {operator.uuid}")
        print(f"   New Webhook URL: {new_webhook_url}")
    except Exception as e:
        print(f"❌ Error updating operator: {e}")
        sys.exit(1)


def print_usage():
    """Print usage instructions"""
    print("""
Operator Management CLI

Commands:
  create <webhook_url> [--uuid <custom-uuid>]
      Create a new operator with the specified webhook URL
      Optionally specify a custom UUID (otherwise auto-generated)
      
  list
      List all operators in the database
      
  delete <uuid>
      Delete an operator by UUID (with confirmation)
      
  update <uuid> <new_webhook_url>
      Update an operator's webhook URL

Examples:
  # Create operator with auto-generated UUID
  python manage_operators.py create https://myapp.com/webhook
  
  # Create operator with custom UUID
  python manage_operators.py create https://myapp.com/webhook --uuid my-custom-token
  
  # List all operators
  python manage_operators.py list
  
  # Delete operator
  python manage_operators.py delete abc-123-def
  
  # Update webhook URL
  python manage_operators.py update abc-123-def https://newurl.com/webhook
""")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "create":
        if len(sys.argv) < 3:
            print("❌ Error: webhook_url is required")
            print("Usage: python manage_operators.py create <webhook_url> [--uuid <custom-uuid>]")
            sys.exit(1)
        
        webhook_url = sys.argv[2]
        custom_uuid = None
        
        # Check for --uuid flag
        if len(sys.argv) >= 5 and sys.argv[3] == "--uuid":
            custom_uuid = sys.argv[4]
        
        create_operator(webhook_url, custom_uuid)
    
    elif command == "list":
        list_operators()
    
    elif command == "delete":
        if len(sys.argv) < 3:
            print("❌ Error: UUID is required")
            print("Usage: python manage_operators.py delete <uuid>")
            sys.exit(1)
        
        operator_uuid = sys.argv[2]
        delete_operator(operator_uuid)
    
    elif command == "update":
        if len(sys.argv) < 4:
            print("❌ Error: UUID and new webhook URL are required")
            print("Usage: python manage_operators.py update <uuid> <new_webhook_url>")
            sys.exit(1)
        
        operator_uuid = sys.argv[2]
        new_webhook_url = sys.argv[3]
        update_operator(operator_uuid, new_webhook_url)
    
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
