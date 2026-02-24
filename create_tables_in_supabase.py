#!/usr/bin/env python3
"""
Create tables in Supabase using PostgreSQL connection.
"""

import psycopg2
import sys

# Database connection details
DB_HOST = "db.mybdvsxiynpdbuzmtquu.supabase.co"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PORT = "5432"

# You'll need the database password - this is different from the API keys
# The password can be found in Supabase Dashboard -> Project Settings -> Database -> Connection string


def main():
    """Create tables using direct PostgreSQL connection."""
    print("="*60)
    print("Table Creation via PostgreSQL")
    print("="*60)
    
    # Prompt for password
    db_password = input("\nEnter your Supabase database password: ")
    
    if not db_password:
        print("Error: Password is required")
        sys.exit(1)
    
    try:
        # Connect to database
        print("\nConnecting to database...")
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=db_password,
            port=DB_PORT
        )
        print("✓ Connected successfully")
        
        # Read SQL file
        with open("create_tables.sql", "r") as f:
            sql_content = f.read()
        
        # Execute SQL
        cursor = conn.cursor()
        print("\nExecuting SQL statements...")
        cursor.execute(sql_content)
        conn.commit()
        print("✓ All tables created successfully")
        
        # Close connection
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        print("Success! Tables are ready for data upload.")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
