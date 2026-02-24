#!/usr/bin/env python3
"""
Upload CSV files from csvfiles folder to Supabase database.
Each CSV file will be uploaded as a separate table.
"""

import os
import sys
import pandas as pd
from supabase import create_client, Client
from typing import Dict, List
import json

# Supabase configuration
SUPABASE_URL = "https://mybdvsxiynpdbuzmtquu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im15YmR2c3hpeW5wZGJ1em10cXV1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTMyMTA2OSwiZXhwIjoyMDg2ODk3MDY5fQ.zEZzOt2G_zSqJka9_z68KDj5z7dhhgMLSY1-A_uz6Ac"

# CSV files to upload
CSV_FILES = {
    "nep_master_user_table_sample_data": "csvfiles/nep_master_user_table_sample_data.csv",
    "nep_master_live_events_data": "csvfiles/nep_master_live_events_data.csv",
    "nep_liftoffx_data_sample": "csvfiles/nep_liftoffX_data_sample.csv",
    "nep_mentor_profiles_sample_data": "csvfiles/nep_mentor_profiles_sample_data.csv"
}

BATCH_SIZE = 1000  # Number of rows to upload at a time


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean DataFrame for Supabase upload.
    - Replace NaN with None
    - Replace infinity with None
    - Convert timestamps to ISO format strings
    - Handle special characters in column names
    """
    # Replace NaN and infinity with None (NULL in database)
    df = df.replace([float('inf'), float('-inf')], None)
    df = df.where(pd.notna(df), None)
    
    # Convert datetime columns to ISO format strings
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        # Convert float columns to handle potential NaN/inf issues
        elif pd.api.types.is_float_dtype(df[col]):
            # Replace any remaining NaN or inf with None
            df[col] = df[col].apply(lambda x: None if pd.isna(x) or x == float('inf') or x == float('-inf') else x)
    
    return df


def make_json_safe(obj):
    """
    Convert pandas/numpy types to native Python types for JSON serialization.
    """
    import numpy as np
    
    if pd.isna(obj):
        return None
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    else:
        return obj


def upload_csv_to_supabase(
    supabase: Client,
    table_name: str,
    csv_path: str
) -> Dict[str, any]:
    """
    Upload a CSV file to Supabase table.
    
    Args:
        supabase: Supabase client instance
        table_name: Name of the table to upload to
        csv_path: Path to the CSV file
        
    Returns:
        Dictionary with upload statistics
    """
    print(f"\n{'='*60}")
    print(f"Processing: {table_name}")
    print(f"CSV File: {csv_path}")
    print(f"{'='*60}")
    
    # Read CSV file
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        print(f"✓ Loaded CSV: {len(df)} rows, {len(df.columns)} columns")
    except Exception as e:
        print(f"✗ Error reading CSV: {e}")
        return {"success": False, "error": str(e)}
    
    # Clean the dataframe
    df = clean_dataframe(df)
    
    # Convert to list of dictionaries with JSON-safe types
    records = []
    for _, row in df.iterrows():
        record = {col: make_json_safe(val) for col, val in row.items()}
        records.append(record)

    
    # Upload in batches
    total_rows = len(records)
    uploaded_count = 0
    failed_count = 0
    
    print(f"\nUploading {total_rows} rows in batches of {BATCH_SIZE}...")
    
    for i in range(0, total_rows, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total_rows + BATCH_SIZE - 1) // BATCH_SIZE
        
        try:
            # Insert batch into Supabase
            response = supabase.table(table_name).insert(batch).execute()
            uploaded_count += len(batch)
            print(f"  Batch {batch_num}/{total_batches}: ✓ Uploaded {len(batch)} rows")
        except Exception as e:
            failed_count += len(batch)
            print(f"  Batch {batch_num}/{total_batches}: ✗ Failed - {str(e)[:100]}")
            
            # If it's the first batch and table doesn't exist, provide helpful message
            if i == 0 and "relation" in str(e).lower() and "does not exist" in str(e).lower():
                print(f"\n⚠ Table '{table_name}' does not exist in Supabase.")
                print(f"  Please create the table first in Supabase dashboard or via SQL.")
                return {
                    "success": False,
                    "error": f"Table '{table_name}' does not exist",
                    "total_rows": total_rows,
                    "uploaded": 0,
                    "failed": total_rows
                }
    
    print(f"\n{'─'*60}")
    print(f"Upload Summary for {table_name}:")
    print(f"  Total rows: {total_rows}")
    print(f"  Uploaded: {uploaded_count}")
    print(f"  Failed: {failed_count}")
    print(f"{'─'*60}")
    
    return {
        "success": uploaded_count > 0,
        "total_rows": total_rows,
        "uploaded": uploaded_count,
        "failed": failed_count
    }


def main():
    """Main function to upload all CSV files to Supabase."""
    print("\n" + "="*60)
    print("CSV to Supabase Upload Tool")
    print("="*60)
    
    # Initialize Supabase client
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✓ Connected to Supabase")
    except Exception as e:
        print(f"✗ Failed to connect to Supabase: {e}")
        sys.exit(1)
    
    # Upload each CSV file
    results = {}
    for table_name, csv_path in CSV_FILES.items():
        if not os.path.exists(csv_path):
            print(f"\n✗ CSV file not found: {csv_path}")
            results[table_name] = {"success": False, "error": "File not found"}
            continue
        
        result = upload_csv_to_supabase(supabase, table_name, csv_path)
        results[table_name] = result
    
    # Print final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    total_uploaded = 0
    total_failed = 0
    successful_tables = 0
    
    for table_name, result in results.items():
        status = "✓" if result.get("success") else "✗"
        print(f"\n{status} {table_name}")
        if result.get("success"):
            successful_tables += 1
            print(f"  Uploaded: {result.get('uploaded', 0)} rows")
            total_uploaded += result.get('uploaded', 0)
            if result.get('failed', 0) > 0:
                print(f"  Failed: {result.get('failed', 0)} rows")
                total_failed += result.get('failed', 0)
        else:
            print(f"  Error: {result.get('error', 'Unknown error')}")
            total_failed += result.get('total_rows', 0)
    
    print(f"\n{'='*60}")
    print(f"Tables processed: {len(results)}")
    print(f"Successful uploads: {successful_tables}")
    print(f"Total rows uploaded: {total_uploaded}")
    print(f"Total rows failed: {total_failed}")
    print(f"{'='*60}\n")
    
    # Exit with appropriate code
    sys.exit(0 if successful_tables == len(results) else 1)


if __name__ == "__main__":
    main()
