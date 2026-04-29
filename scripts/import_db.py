import argparse
import pandas as pd
import os
import sys
import pyarrow.parquet as pq
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from tqdm import tqdm
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# Configuration
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
assert DATABASE_URL is not None, "please set environment variable DATABASE_URL"

CHUNK_SIZE = 10000  # Process 10k rows at a time
FIELDS = ['cytokine_name', 'cell_type', 'cytokine_effect', 'regulated_genes',
       'gene_response_type', 'regulated_pathways', 'pathway_response_type',
       'cell_process_category', 'regulated_cell_processes',
       'cell_process_response_type', 'chunk_id', 'source_id', 'key_sentences',
       'causality_description', 'citation_id_classification',
       'mapped_citation_id', 'species', 'experimental_system_type',
       'experimental_system_details', 'experimental_perturbation',
       'experimental_readout', 'experimental_time_point',
       'experimental_concentration', 'qc_basic_interaction', 'qc_cell_type',
       'regulated_genes_human', 'regulated_genes_mouse', 'causality_type',
       'necessary_condition', 'additional_info', 'cytokine_name_original',
       'cell_type_original', 'cytokine_effect_original',
       'regulated_pathways_orig', 'experimental_readout_original',
       'experimental_perturbation_original', 'url']

def prepare_chunk(chunk, explode=True, col_name="cytokine_name"):
    """Normalize a dataframe chunk for DB insert"""
    chunk = chunk.where(pd.notnull(chunk), None)

    def normalize(x):
        if pd.isna(x) or x is None:
            return []
        if isinstance(x, str):
            return x.split(";") if explode else x
        if isinstance(x, list):
            return x if explode else ";".join(x)
        return [x]

    chunk[col_name] = chunk[col_name].apply(normalize)
    if explode:
        chunk = chunk.explode(col_name).reset_index(drop=True)
    if not "url" in chunk.columns:
        chunk["url"] = chunk["chunk_id"].apply(lambda x: f"https://pmc.ncbi.nlm.nih.gov/articles/{x.split('_')[0]}")
    return chunk[FIELDS] if len(chunk) else chunk


def ensure_database_exists(database_url):
    """Create the database if it doesn't exist"""
    try:
        # Parse the database URL
        parsed = urlparse(database_url)
        db_name = parsed.path.lstrip('/')
        
        if not db_name:
            print("⚠ Warning: No database name found in DATABASE_URL")
            return database_url
        
        # Create a connection URL to the default 'postgres' database
        default_db_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            '/postgres',  # Connect to default postgres database
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        # Try to connect to the target database first
        try:
            test_engine = create_engine(database_url)
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"✓ Database '{db_name}' already exists")
            return database_url
        except OperationalError as e:
            # Check if the error is specifically about database not existing
            error_msg = str(e).lower()
            if 'does not exist' in error_msg or 'database' in error_msg and 'not exist' in error_msg:
                # Database doesn't exist, create it
                print(f"Database '{db_name}' does not exist. Creating it...")
            else:
                # Some other connection error - re-raise it
                raise
            
            # Connect to default postgres database to create the new database
            if not PSYCOPG2_AVAILABLE:
                print(f"⚠ Warning: psycopg2 not available. Cannot auto-create database.")
                print(f"  Please create the database manually:")
                print(f"  createdb {db_name}")
                return database_url
            
            # Parse connection details for psycopg2
            parsed_default = urlparse(default_db_url)
            conn_params = {
                'host': parsed_default.hostname,
                'port': parsed_default.port or 5432,
                'user': parsed_default.username,
                'password': parsed_default.password,
                'database': 'postgres'
            }
            
            # Remove None values
            conn_params = {k: v for k, v in conn_params.items() if v is not None}
            
            try:
                conn = psycopg2.connect(**conn_params)
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                cursor = conn.cursor()
                
                # Check if database exists
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (db_name,)
                )
                if cursor.fetchone():
                    print(f"✓ Database '{db_name}' already exists")
                else:
                    # Create the database
                    # Escape the database name (psycopg2 will handle quoting)
                    cursor.execute(f'CREATE DATABASE "{db_name}"')
                    print(f"✓ Created database '{db_name}'")
                
                cursor.close()
                conn.close()
            except Exception as e:
                print(f"⚠ Warning: Could not create database: {e}")
                print(f"  You may need to create the database manually:")
                print(f"  createdb {db_name}")
                # Continue anyway - the connection attempt will show the actual error
            return database_url
            
    except Exception as e:
        print(f"⚠ Warning: Could not ensure database exists: {e}")
        print("  Attempting to continue with existing connection...")
        return database_url

# SQL types for each field (fields not listed default to TEXT)
FIELD_SQL_TYPES = {}


def create_tables(engine):
    """Create the interactions table with proper schema"""
    print("Creating database tables...")

    # Build column definitions from FIELDS so schema stays in sync
    columns = ["        id BIGSERIAL PRIMARY KEY"]
    for field in FIELDS:
        sql_type = FIELD_SQL_TYPES.get(field, "TEXT")
        columns.append(f"        {field} {sql_type}")
    columns_sql = ",\n".join(columns)

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS public.cytokine_effects (
{columns_sql}
    );
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
    
    print("✓ Tables created successfully")

def create_indexes(engine):
    """Create indexes on frequently queried columns"""
    print("Creating indexes for better query performance...")
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_cytokine_name ON cytokine_effects(cytokine_name);",
        "CREATE INDEX IF NOT EXISTS idx_cell_type ON cytokine_effects(cell_type);",
        "CREATE INDEX IF NOT EXISTS idx_species ON cytokine_effects(species);",
        "CREATE INDEX IF NOT EXISTS idx_experimental_system_type ON cytokine_effects(experimental_system_type);",
        # Full-text search indexes for text columns
        "CREATE INDEX IF NOT EXISTS idx_regulated_genes_fts ON cytokine_effects USING gin(to_tsvector('english', COALESCE(regulated_genes, '')));",
        "CREATE INDEX IF NOT EXISTS idx_regulated_pathways_fts ON cytokine_effects USING gin(to_tsvector('english', COALESCE(regulated_pathways, '')));",
        "CREATE INDEX IF NOT EXISTS idx_necessary_condition_fts ON cytokine_effects USING gin(to_tsvector('english', COALESCE(necessary_condition, '')));",
        "CREATE INDEX IF NOT EXISTS idx_cell_process_category_fts ON cytokine_effects USING gin(to_tsvector('english', COALESCE(cell_process_category, '')));",
    ]
    
    with engine.connect() as conn:
        for idx_sql in indexes:
            try:
                conn.execute(text(idx_sql))
                conn.commit()
                print(f"✓ Created index")
            except Exception as e:
                print(f"⚠ Index creation warning: {e}")
    
    print("✓ All indexes created")

def import_csv(csv_file, engine):
    """Import CSV file into database in chunks."""
    if not os.path.exists(csv_file):
        print(f"❌ Error: CSV file '{csv_file}' not found!")
        sys.exit(1)

    print(f"Starting import of {csv_file}...")
    print(f"Chunk size: {CHUNK_SIZE} rows")

    # Get total rows for progress bar (source rows, before explode)
    print("Counting total rows...")
    total_rows = sum(1 for _ in open(csv_file)) - 1  # Subtract header
    print(f"Total rows to import: {total_rows:,}")

    chunk_iterator = pd.read_csv(csv_file, chunksize=CHUNK_SIZE, engine='python')
    rows_imported = 0
    with tqdm(total=total_rows, desc="Importing") as pbar:
        for chunk_num, chunk in enumerate(chunk_iterator, 1):
            n_read = len(chunk)
            chunk = prepare_chunk(chunk, explode=True, col_name="cytokine_name")
            chunk = chunk.fillna('') # replace NaN/None with an empty string
            if len(chunk):
                chunk.to_sql(
                    "cytokine_effects",
                    engine,
                    if_exists="append",
                    index=False,
                    method="multi",
                    schema="public",
                )
            rows_imported += len(chunk)
            pbar.update(n_read)
            if chunk_num % 10 == 0:
                print(f"  Processed ~{rows_imported:,} rows...")
    print(f"✓ Import complete! Total rows imported: {rows_imported:,}")


def import_parquet(parquet_file, engine):
    """Import Parquet file into database in chunks (row groups / batches)."""
    if not os.path.exists(parquet_file):
        print(f"❌ Error: Parquet file '{parquet_file}' not found!")
        sys.exit(1)

    print(f"Starting import of {parquet_file}...")
    print(f"Chunk size: {CHUNK_SIZE} rows")

    pf = pq.ParquetFile(parquet_file)
    total_rows = pf.metadata.num_rows
    print(f"Total rows to import: {total_rows:,}")

    rows_imported = 0
    with tqdm(total=total_rows, desc="Importing") as pbar:
        for batch in pf.iter_batches(batch_size=CHUNK_SIZE):
            n_read = batch.num_rows
            chunk = batch.to_pandas()
            chunk = prepare_chunk(chunk)
            if len(chunk):
                chunk.to_sql(
                    "cytokine_effects",
                    engine,
                    if_exists="append",
                    index=False,
                    method="multi",
                    schema="public",
                )
            rows_imported += len(chunk)
            pbar.update(n_read)
    print(f"✓ Import complete! Total rows imported: {rows_imported:,}")

def verify_import(engine):
    """Verify the import was successful"""
    print("\nVerifying import...")
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM cytokine_effects"))
        count = result.scalar()
        print(f"✓ Total rows in database: {count:,}")
        
        # Sample query
        result = conn.execute(text("SELECT cytokine_name, cell_type, species FROM cytokine_effects LIMIT 5"))
        print("\nSample data:")
        for row in result:
            print(f"  Cytokine: {row[0]}, Cell Type: {row[1]}, Species: {row[2]}")

def main(args):
    print("=" * 60)
    print("Cytokine Knowledgebase - Data Import Tool")
    print("=" * 60)
    print()
    data_file = args.file
    if not os.path.exists(data_file):
        print(f"❌ Error: File '{data_file}' does not exist")
        sys.exit(1)
    if data_file.lower().endswith(".csv"):
        import_fn = import_csv
    elif data_file.lower().endswith(".parquet"):
        import_fn = import_parquet
    else:
        print("❌ Error: File must be .csv or .parquet")
        sys.exit(1)

    # Ensure database exists
    if not DATABASE_URL:
        print("❌ Error: DATABASE_URL environment variable is not set!")
        sys.exit(1)

    print("Checking database connection...")
    database_url = ensure_database_exists(DATABASE_URL)
    print()

    # Create engine
    try:
        engine = create_engine(database_url)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"✓ Connected to database: {database_url.split('@')[1] if '@' in database_url else 'local'}")
    except Exception as e:
        print(f"❌ Error connecting to database: {str(e)[:100]}")
        sys.exit(1)
    print()

    # Execute import steps
    try:
        # Step 1: Create tables
        create_tables(engine)
        print()

        # Step 2: Import data (CSV or Parquet)
        import_fn(data_file, engine)
        print()

        # Step 3: Create indexes
        create_indexes(engine)
        print()

        # Step 4: Verify
        verify_import(engine)
        print()

        print("=" * 60)
        print("✓ IMPORT COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error during import: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import CSV or Parquet file into PostgreSQL database"
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        required=True,
        help="Path to the CSV or Parquet file to import",
    )
    args = parser.parse_args()
    main(args)
