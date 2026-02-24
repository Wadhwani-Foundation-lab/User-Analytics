#!/usr/bin/env python3
"""
Generate SQL CREATE TABLE statements from CSV files.
"""

import pandas as pd
import os

CSV_FILES = {
    "nep_master_user_table_sample_data": "csvfiles/nep_master_user_table_sample_data.csv",
    "nep_master_live_events_data": "csvfiles/nep_master_live_events_data.csv",
    "nep_liftoffx_data_sample": "csvfiles/nep_liftoffX_data_sample.csv",
    "nep_mentor_profiles_sample_data": "csvfiles/nep_mentor_profiles_sample_data.csv"
}


def infer_postgres_type(series):
    """Infer PostgreSQL data type from pandas series."""
    dtype = series.dtype
    
    # Check for numeric types
    if pd.api.types.is_integer_dtype(dtype):
        return "BIGINT"
    elif pd.api.types.is_float_dtype(dtype):
        return "DOUBLE PRECISION"
    elif pd.api.types.is_bool_dtype(dtype):
        return "BOOLEAN"
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return "TIMESTAMP"
    else:
        # For text, check max length
        max_len = series.astype(str).str.len().max()
        if pd.isna(max_len) or max_len == 0:
            return "TEXT"
        elif max_len < 255:
            return "VARCHAR(500)"
        else:
            return "TEXT"


def generate_create_table_sql(table_name, csv_path):
    """Generate CREATE TABLE SQL statement from CSV file."""
    df = pd.read_csv(csv_path, low_memory=False, nrows=1000)  # Sample first 1000 rows
    
    columns = []
    for col in df.columns:
        col_type = infer_postgres_type(df[col])
        # Clean column name (replace spaces, special chars)
        clean_col = col.replace(' ', '_').replace('-', '_').replace('.', '_')
        columns.append(f'  "{clean_col}" {col_type}')
    
    sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
    sql += ",\n".join(columns)
    sql += "\n);\n"
    
    return sql


def main():
    """Generate SQL for all tables."""
    print("-- SQL statements to create tables in Supabase")
    print("-- Copy and paste these into the Supabase SQL Editor\n")
    
    for table_name, csv_path in CSV_FILES.items():
        if not os.path.exists(csv_path):
            print(f"-- Skipping {table_name}: file not found")
            continue
        
        print(f"-- Table: {table_name}")
        print(f"-- Source: {csv_path}")
        sql = generate_create_table_sql(table_name, csv_path)
        print(sql)
        print()


if __name__ == "__main__":
    main()
