"""
Migration Runner
Executes SQL migration files against the database
"""
import os
import sys
from database import get_connection

def run_migration(sql_file):
    """Run a SQL migration file against the database"""
    
    if not os.path.exists(sql_file):
        print(f"❌ Migration file not found: {sql_file}")
        return False
    
    # Read the SQL file
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # Connect to database
    conn = get_connection()
    if not conn:
        print("❌ Could not connect to database")
        return False
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()
        print(f"✅ Migration successful: {sql_file}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default to running the notifications migration
        migration_file = "migrations/001_add_notifications.sql"
    else:
        migration_file = sys.argv[1]
    
    print(f"🔄 Running migration: {migration_file}")
    success = run_migration(migration_file)
    sys.exit(0 if success else 1)
