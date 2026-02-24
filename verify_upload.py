#!/usr/bin/env python3
"""
Verify data upload by querying row counts from Supabase.
"""

from supabase import create_client, Client

SUPABASE_URL = "https://mybdvsxiynpdbuzmtquu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im15YmR2c3hpeW5wZGJ1em10cXV1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTMyMTA2OSwiZXhwIjoyMDg2ODk3MDY5fQ.zEZzOt2G_zSqJka9_z68KDj5z7dhhgMLSY1-A_uz6Ac"

TABLES = [
    "nep_master_user_table_sample_data",
    "nep_master_live_events_data",
    "nep_liftoffx_data_sample",
    "nep_mentor_profiles_sample_data"
]


def main():
    """Verify row counts in Supabase tables."""
    print("\n" + "="*60)
    print("Supabase Data Verification")
    print("="*60)
    
    # Connect to Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✓ Connected to Supabase\n")
    
    total_rows = 0
    
    for table in TABLES:
        try:
            # Query row count
            response = supabase.table(table).select("*", count="exact").limit(0).execute()
            count = response.count
            total_rows += count
            print(f"✓ {table}: {count} rows")
        except Exception as e:
            print(f"✗ {table}: Error - {e}")
    
    print("\n" + "="*60)
    print(f"Total rows across all tables: {total_rows}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
