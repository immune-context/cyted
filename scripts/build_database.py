
"""
Build/populate the cytokine interaction PostgreSQL database from a raw parquet file.

Assumptions
-----------
1. PostgreSQL tables already exist using the schema discussed previously.
2. The database URL is supplied via the DATABASE_URL environment variable, e.g.
       postgresql+psycopg://postgres:password@localhost:5432/cytokine_db
3. The parquet contains the raw dataframe columns shown in the example.
4. This script rebuilds the CONTENT of the existing tables by deleting existing
   rows in dependency order, then loading the parquet data. It does not create
   or alter the table schema.

Install
-------
    pip install pandas pyarrow sqlalchemy psycopg[binary]

Run
---
    export DATABASE_URL='postgresql://molly@localhost:5432/cyted_dev'
    python build_database.py cyted.parquet

Optional:
    python build_database.py cyted.parquet --batch-size 50000
"""

import argparse
import json
import os
import re
import sys

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = [
    "cytokine_name",
    "cell_type",
    "cytokine_effect",
    "regulated_genes",
    "gene_response_type",
    "regulated_pathways",
    "pathway_response_type",
    "cell_process_category",
    "regulated_cell_processes",
    "cell_process_response_type",
    "chunk_id",
    "source_id",
    "key_sentences",
    "causality_description",
    "citation_id_classification",
    "mapped_citation_id",
    "species",
    "experimental_system_type",
    "experimental_system_details",
    "experimental_perturbation",
    "experimental_readout",
    "experimental_time_point",
    "experimental_concentration",
    "qc_basic_interaction",
    "qc_cell_type",
    "regulated_genes_human",
    "regulated_genes_mouse",
    "causality_type",
    "necessary_condition",
    "additional_info",
    "cytokine_name_original",
    "cell_type_original",
    "cytokine_effect_original",
    "regulated_pathways_original",
    "experimental_readout_original",
    "experimental_perturbation_original",
    "url",
]

# Columns stored in interactions. raw_row_id is deliberately retained so that
# every database interaction can be traced to exactly one raw parquet row.
INTERACTION_COLUMNS = [
    "raw_row_id",
    "cytokine_id",
    "cell_type_id",
    "chunk_id",
    "cytokine_effect",
    "gene_response_type",
    "pathway_response_type",
    "cell_process_response_type",
    "causality_description",
    "causality_type",
    "necessary_condition",
    "species",
    "experimental_system_type",
    "experimental_system_details",
    "experimental_perturbation",
    "experimental_readout",
    "experimental_time_point",
    "experimental_concentration",
    "citation_id_classification",
    "mapped_citation_id",
    "key_sentences",
    "qc_basic_interaction",
    "qc_cell_type",
    "additional_info",
    "cytokine_name_original",
    "cell_type_original",
    "cytokine_effect_original",
    "regulated_pathways_original",
    "experimental_readout_original",
    "experimental_perturbation_original",
]

# PostgreSQL tables are cleared in child-to-parent order.
TABLES_TO_CLEAR = [
    "interaction_cell_processes",
    "interaction_pathways",
    "interaction_genes",
    "interactions",
    "source_chunks",
    "sources",
    "cell_processes",
    "pathways",
    "genes",
    "cell_types",
    "cytokines",
]


# ---------------------------------------------------------------------------
# Cleaning / normalization
# ---------------------------------------------------------------------------

def split_semicolon(value) -> list[str]:
    """Split semicolon-delimited extracted values into clean strings."""
    value = clean_value(value)

    if value is None:
        return []

    return [
        item.strip()
        for item in str(value).split(";")
        if item.strip()
    ]


def clean_value(value):
    """
    Handle varying missing values and strip whitespace
    """
    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    missing_values = {
        "nan",
        "none",
        "null",
        "unknown",
        "unknown: unknown",
        "n/a",
    }

    if value.lower() in missing_values:
        return None

    return value


def clean_dataframe(df):
    df = df.copy()

    for col in df.columns:
        df[col] = df[col].apply(clean_value)

    return df


# ---------------------------------------------------------------------------
# Dataframe construction
# ---------------------------------------------------------------------------

def make_cytokines(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df[["cytokine_name"]]
        .dropna()
        .rename(columns={"cytokine_name": "name"})
        .drop_duplicates()
        .sort_values("name")
        .reset_index(drop=True)
    )


def make_cell_types(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df[["cell_type"]]
        .dropna()
        .rename(columns={"cell_type": "name"})
        .drop_duplicates()
        .sort_values("name")
        .reset_index(drop=True)
    )


def explode_semicolons(series: pd.Series) -> pd.Series:
    """Vectorized equivalent of applying split_semicolon() to every value."""
    exploded = series.dropna().str.split(";").explode().str.strip()
    return exploded[exploded != ""]


def make_genes(df: pd.DataFrame) -> pd.DataFrame:
    symbols = explode_semicolons(df["regulated_genes"])

    return (
        symbols.rename("symbol")
        .to_frame()
        .drop_duplicates()
        .sort_values("symbol")
        .reset_index(drop=True)
    )


def make_pathways(df: pd.DataFrame) -> pd.DataFrame:
    names = explode_semicolons(df["regulated_pathways"])

    if names.empty:
        return pd.DataFrame(columns=["name"])

    return (
        names.rename("name")
        .to_frame()
        .drop_duplicates()
        .sort_values("name")
        .reset_index(drop=True)
    )


def make_cell_processes(df: pd.DataFrame) -> pd.DataFrame:
    processes = (
        df[["regulated_cell_processes", "cell_process_category"]]
        .dropna(subset=["regulated_cell_processes"])
        .assign(name=lambda x: x["regulated_cell_processes"].str.split(";"))
        .explode("name")
        .assign(name=lambda x: x["name"].str.strip())
        .rename(columns={"cell_process_category": "category"})
    )
    processes = processes[processes["name"] != ""]

    if processes.empty:
        return pd.DataFrame(columns=["name", "category"])

    # cell_processes.name is UNIQUE in the schema, so a process name can only
    # have one category on record. If the raw data assigns the same process
    # name to multiple categories, keep the first one seen (deterministic
    # because of the sort below) rather than trying to store both.
    return (
        processes[["name", "category"]]
        .drop_duplicates()
        .sort_values(["name", "category"], na_position="last")
        .drop_duplicates(subset=["name"], keep="first")
        .reset_index(drop=True)
    )


def make_sources(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the source table. Note that mapped_citation_id is heterogenous; 
    can be DOI or PMID
    """
    sources = (
        df[
            ["source_id", "mapped_citation_id"]
        ]
        .drop_duplicates("source_id")
        .copy()
    )
    sources["pmc_id"] = sources["source_id"]
    sources.rename(columns={"mapped_citation_id": "alt_id"}, inplace=True)

    return sources


def make_source_chunks(df: pd.DataFrame) -> pd.DataFrame:
    chunks = (
        df[
            [
                "chunk_id",
                "source_id",
                "key_sentences",
                "url",
            ]
        ]
        .dropna(subset=["chunk_id", "source_id"])
        .drop_duplicates("chunk_id")
        .rename(columns={
            "key_sentences": "chunk_text",
        })
        .reset_index(drop=True)
    )

    return chunks



# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_engine() -> Engine:
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set.\n"
            "Example:\n"
            "  export DATABASE_URL="
            "'postgresql+psycopg://postgres:password@localhost:5432/cytokine_db'"
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


def test_connection(engine: Engine) -> None:
    with engine.connect() as conn:
        value = conn.execute(text("SELECT 1")).scalar_one()

    if value != 1:
        raise RuntimeError("PostgreSQL connection test failed.")

    print("✓ PostgreSQL connection successful")


def clear_existing_data(conn: Connection) -> None:
    """
    Clear existing rows without dropping tables.

    This makes the script a full rebuild of the database contents. Runs on
    the caller's connection/transaction so a later failure rolls this back
    along with everything else in the rebuild. Only tables that actually
    exist in the target database are cleared; anything else in
    TABLES_TO_CLEAR is skipped rather than raising.
    """
    print("Clearing existing database contents...")

    existing_tables = set(
        read_table(
            conn,
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'",
        )["tablename"]
    )

    for table in TABLES_TO_CLEAR:
        if table not in existing_tables:
            print(f"  {table}: does not exist; skipping")
            continue

        conn.execute(text(f"DELETE FROM {table}"))

    print("✓ Existing rows deleted")


def load_dataframe(
    df: pd.DataFrame,
    table_name: str,
    conn: Connection,
    chunksize: int = 10_000,
) -> None:
    """Append dataframe rows to an existing PostgreSQL table."""
    if df.empty:
        print(f"  {table_name}: empty; nothing to load")
        return

    df.to_sql(
        table_name,
        conn,
        if_exists="append",
        index=False,
        chunksize=chunksize,
        method="multi",
    )

    print(f"✓ Loaded {len(df):,} rows into {table_name}")


def read_table(conn: Connection, sql: str) -> pd.DataFrame:
    return pd.read_sql(text(sql), conn)


# ---------------------------------------------------------------------------
# Foreign-key mapping
# ---------------------------------------------------------------------------

def add_cytokine_ids(
    interactions: pd.DataFrame,
    conn: Connection,
) -> pd.DataFrame:
    lookup = read_table(
        conn,
        """
        SELECT cytokine_id, name
        FROM cytokines
        """
    )

    interactions = interactions.merge(
        lookup,
        left_on="cytokine_name",
        right_on="name",
        how="left",
        validate="many_to_one",
    )

    missing = interactions["cytokine_id"].isna()
    if missing.any():
        values = interactions.loc[missing, "cytokine_name"].drop_duplicates().tolist()
        raise ValueError(
            f"Could not map {missing.sum()} interaction rows to cytokines. "
            f"Missing values include: {values[:10]}"
        )

    interactions = interactions.drop(columns=["name"])

    return interactions


def add_cell_type_ids(
    interactions: pd.DataFrame,
    conn: Connection,
) -> pd.DataFrame:
    lookup = read_table(
        conn,
        """
        SELECT cell_type_id, name
        FROM cell_types
        """
    )

    interactions = interactions.merge(
        lookup,
        left_on="cell_type",
        right_on="name",
        how="left",
        validate="many_to_one",
    )

    missing = interactions["cell_type_id"].isna()
    if missing.any():
        values = interactions.loc[missing, "cell_type"].drop_duplicates().tolist()
        raise ValueError(
            f"Could not map {missing.sum()} interaction rows to cell types. "
            f"Missing values include: {values[:10]}"
        )

    interactions = interactions.drop(columns=["name"])

    return interactions


def add_interaction_ids(
    interactions: pd.DataFrame,
    conn: Connection,
) -> pd.DataFrame:
    """
    Retrieve PostgreSQL-generated interaction_id values.

    raw_row_id uniquely identifies each source dataframe row, so this creates
    an unambiguous mapping from the raw extraction to PostgreSQL.
    """
    lookup = read_table(
        conn,
        """
        SELECT interaction_id, raw_row_id
        FROM interactions
        """
    )

    interactions = interactions.merge(
        lookup,
        on="raw_row_id",
        how="left",
        validate="one_to_one",
    )

    missing = interactions["interaction_id"].isna()
    if missing.any():
        raise ValueError(
            f"{missing.sum()} interactions did not receive an interaction_id."
        )

    interactions["interaction_id"] = (
        interactions["interaction_id"].astype("int64")
    )

    return interactions


# ---------------------------------------------------------------------------
# Junction-table construction
# ---------------------------------------------------------------------------

def make_interaction_genes(
    df: pd.DataFrame,
    interactions: pd.DataFrame,
    conn: Connection,
) -> pd.DataFrame:

    interaction_id_by_raw_row = (
        interactions.set_index("raw_row_id")["interaction_id"]
    )

    links = (
        df[["raw_row_id", "regulated_genes", "gene_response_type"]]
        .dropna(subset=["regulated_genes"])
        .assign(symbol=lambda x: x["regulated_genes"].str.split(";"))
        .explode("symbol")
        .assign(symbol=lambda x: x["symbol"].str.strip())
        .rename(columns={"gene_response_type": "response_type"})
    )
    links = links[links["symbol"] != ""]
    links["interaction_id"] = links["raw_row_id"].map(interaction_id_by_raw_row)

    if links.empty:
        return pd.DataFrame(
            columns=["interaction_id", "gene_id", "response_type"]
        )

    links = links[["interaction_id", "symbol", "response_type"]].drop_duplicates(
        subset=["interaction_id", "symbol"]
    )

    gene_lookup = read_table(
        conn,
        """
        SELECT gene_id, symbol
        FROM genes
        """
    )

    links = links.merge(
        gene_lookup,
        on="symbol",
        how="left",
        validate="many_to_one",
    )

    missing = links["gene_id"].isna()
    if missing.any():
        bad = links.loc[
            missing,
            ["symbol"]
        ].drop_duplicates()

        raise ValueError(
            "Could not map genes to gene IDs:\n"
            f"{bad.head(20).to_string(index=False)}"
        )

    return (
        links[
            [
                "interaction_id",
                "gene_id",
                "response_type",
            ]
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )


def make_interaction_pathways(
    df: pd.DataFrame,
    interactions: pd.DataFrame,
    conn: Connection,
) -> pd.DataFrame:

    interaction_id_by_raw_row = (
        interactions.set_index("raw_row_id")["interaction_id"]
    )

    links = (
        df[["raw_row_id", "regulated_pathways", "pathway_response_type"]]
        .dropna(subset=["regulated_pathways"])
        .assign(pathway_name=lambda x: x["regulated_pathways"].str.split(";"))
        .explode("pathway_name")
        .assign(pathway_name=lambda x: x["pathway_name"].str.strip())
        .rename(columns={"pathway_response_type": "response_type"})
    )
    links = links[links["pathway_name"] != ""]
    links["interaction_id"] = links["raw_row_id"].map(interaction_id_by_raw_row)

    if links.empty:
        return pd.DataFrame(
            columns=["interaction_id", "pathway_id", "response_type"]
        )

    links = links[
        ["interaction_id", "pathway_name", "response_type"]
    ].drop_duplicates(subset=["interaction_id", "pathway_name"])

    pathway_lookup = read_table(
        conn,
        """
        SELECT pathway_id, name
        FROM pathways
        """
    )

    links = links.merge(
        pathway_lookup,
        left_on="pathway_name",
        right_on="name",
        how="left",
        validate="many_to_one",
    )

    missing = links["pathway_id"].isna()
    if missing.any():
        bad = links.loc[
            missing,
            ["pathway_name"]
        ].drop_duplicates()

        raise ValueError(
            "Could not map pathways to pathway IDs:\n"
            f"{bad.head(20).to_string(index=False)}"
        )

    return (
        links[
            [
                "interaction_id",
                "pathway_id",
                "response_type",
            ]
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )


def make_interaction_cell_processes(
    df: pd.DataFrame,
    interactions: pd.DataFrame,
    conn: Connection,
) -> pd.DataFrame:

    interaction_id_by_raw_row = (
        interactions.set_index("raw_row_id")["interaction_id"]
    )

    links = (
        df[
            [
                "raw_row_id",
                "regulated_cell_processes",
                "cell_process_category",
                "cell_process_response_type",
            ]
        ]
        .dropna(subset=["regulated_cell_processes"])
        .assign(
            process_name=lambda x: x["regulated_cell_processes"].str.split(";")
        )
        .explode("process_name")
        .assign(process_name=lambda x: x["process_name"].str.strip())
        .rename(columns={
            "cell_process_category": "category",
            "cell_process_response_type": "response_type",
        })
    )
    links = links[links["process_name"] != ""]
    links["interaction_id"] = links["raw_row_id"].map(interaction_id_by_raw_row)

    if links.empty:
        return pd.DataFrame(
            columns=[
                "interaction_id",
                "cell_process_id",
                "response_type",
            ]
        )

    links = links[
        ["interaction_id", "process_name", "category", "response_type"]
    ].drop_duplicates(subset=["interaction_id", "process_name"])

    process_lookup = read_table(
        conn,
        """
        SELECT cell_process_id, name, category
        FROM cell_processes
        """
    )

    # Usually name is enough. If your database deliberately allows the same
    # process name with multiple categories, this can be changed to merge on
    # ["name", "category"].
    links = links.merge(
        process_lookup[["cell_process_id", "name"]],
        left_on="process_name",
        right_on="name",
        how="left",
        validate="many_to_one",
    )

    missing = links["cell_process_id"].isna()
    if missing.any():
        bad = links.loc[
            missing,
            ["process_name"]
        ].drop_duplicates()

        raise ValueError(
            "Could not map cell processes to cell_process IDs:\n"
            f"{bad.head(20).to_string(index=False)}"
        )

    return (
        links[
            [
                "interaction_id",
                "cell_process_id",
                "response_type",
            ]
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_database(
    conn: Connection,
    raw_df: pd.DataFrame,
) -> None:

    print("\nDatabase validation")
    print("-------------------")

    tables = [
        "cytokines",
        "cell_types",
        "genes",
        "pathways",
        "cell_processes",
        "sources",
        "source_chunks",
        "interactions",
        "interaction_genes",
        "interaction_pathways",
        "interaction_cell_processes",
    ]

    counts = {}

    for table in tables:
        result = read_table(
            conn,
            f"SELECT COUNT(*) AS n FROM {table}"
        )

        counts[table] = int(result["n"].iloc[0])
        print(f"{table:35s} {counts[table]:,}")

    # Every raw dataframe row should become exactly one interaction.
    if counts["interactions"] != len(raw_df):
        raise AssertionError(
            "Interaction count does not equal raw dataframe row count: "
            f"{counts['interactions']:,} != {len(raw_df):,}"
        )

    # Check foreign-key relationships aren't dangling.
    checks = {
        "interaction cytokines": """
            SELECT COUNT(*)
            FROM interactions i
            LEFT JOIN cytokines c
                ON c.cytokine_id = i.cytokine_id
            WHERE c.cytokine_id IS NULL
        """,
        "interaction cell types": """
            SELECT COUNT(*)
            FROM interactions i
            LEFT JOIN cell_types ct
                ON ct.cell_type_id = i.cell_type_id
            WHERE ct.cell_type_id IS NULL
        """,
        "interaction chunks": """
            SELECT COUNT(*)
            FROM interactions i
            WHERE i.chunk_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM source_chunks sc
                  WHERE sc.chunk_id = i.chunk_id
              )
        """,
        "gene links": """
            SELECT COUNT(*)
            FROM interaction_genes ig
            LEFT JOIN interactions i
                ON i.interaction_id = ig.interaction_id
            LEFT JOIN genes g
                ON g.gene_id = ig.gene_id
            WHERE i.interaction_id IS NULL
               OR g.gene_id IS NULL
        """,
        "pathway links": """
            SELECT COUNT(*)
            FROM interaction_pathways ip
            LEFT JOIN interactions i
                ON i.interaction_id = ip.interaction_id
            LEFT JOIN pathways p
                ON p.pathway_id = ip.pathway_id
            WHERE i.interaction_id IS NULL
               OR p.pathway_id IS NULL
        """,
        "cell-process links": """
            SELECT COUNT(*)
            FROM interaction_cell_processes icp
            LEFT JOIN interactions i
                ON i.interaction_id = icp.interaction_id
            LEFT JOIN cell_processes cp
                ON cp.cell_process_id = icp.cell_process_id
            WHERE i.interaction_id IS NULL
               OR cp.cell_process_id IS NULL
        """,
    }

    for label, sql in checks.items():
        n = int(read_table(conn, sql).iloc[0, 0])

        if n != 0:
            raise AssertionError(
                f"Validation failed for {label}: {n} invalid rows"
            )

        print(f"✓ {label}")

    # Useful summary query matching your UI's second page.
    summary = read_table(
        conn,
        """
        SELECT
            c.name AS cytokine,
            ct.name AS cell_type,
            COUNT(DISTINCT sc.source_id) AS paper_count,
            COUNT(DISTINCT i.interaction_id) AS interaction_count
        FROM interactions i
        JOIN cytokines c
            ON c.cytokine_id = i.cytokine_id
        JOIN cell_types ct
            ON ct.cell_type_id = i.cell_type_id
        LEFT JOIN source_chunks sc
            ON sc.chunk_id = i.chunk_id
        GROUP BY
            c.cytokine_id,
            c.name,
            ct.cell_type_id,
            ct.name
        ORDER BY paper_count DESC, interaction_count DESC
        LIMIT 10
        """
    )

    print("\nTop cytokine/cell-type pairs:")
    if summary.empty:
        print("  No interactions found.")
    else:
        print(summary.to_string(index=False))

    print("\n✓ Database validation completed successfully")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_database(
    parquet_path: str,
    engine: Engine,
    chunksize: int = 10_000,
) -> None:

    # -----------------------------------------------------------------------
    # 1. Read parquet
    # -----------------------------------------------------------------------
    print(f"Reading parquet: {parquet_path}")

    df = pd.read_parquet(parquet_path)
    df.rename(columns={"regulated_pathways_orig": "regulated_pathways_original"}, inplace=True)

    print(f"✓ Read {len(df):,} raw rows")
    print(f"✓ Found {len(df.columns):,} columns")

    missing_columns = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "The parquet is missing required columns:\n"
            + "\n".join(f"  - {c}" for c in missing_columns)
        )

    # -----------------------------------------------------------------------
    # 2. Clean raw dataframe
    # -----------------------------------------------------------------------
    print("\nCleaning dataframe...")

    df_clean = clean_dataframe(df)

    # Assigned after cleaning so it stays an int64 column; clean_dataframe()
    # runs every column through clean_value(), which stringifies values.
    df_clean["raw_row_id"] = range(len(df_clean))

    print("✓ Cleaning complete")

    # -----------------------------------------------------------------------
    # 3. Build entity dataframes
    # -----------------------------------------------------------------------
    print("\nBuilding normalized dataframes...")

    cache_path = "/Users/molly/.cache/llm_science_reading_data"

    cell_type_index = {}

    with open(os.path.join(cache_path, "CL/cl_inverted_index.json"), "r") as f:
        cell_type_index.update(json.load(f))

    with open(os.path.join(cache_path, "NCIT/ncit_inverted_index.json"), "r") as f:
        cell_type_index.update(json.load(f))

    with open(os.path.join(cache_path, "CVCL/cvcl_inverted_index.json"), "r") as f:
        cell_type_index.update(json.load(f))

    with open(os.path.join(cache_path, "PW/pw_filtered_inverted_index.json"), "r") as f:
        pathway_index = json.load(f)

    cytokines = make_cytokines(df_clean)
    cell_types = make_cell_types(df_clean)
    pathways = make_pathways(df_clean)
    genes = make_genes(df_clean)
    cell_processes = make_cell_processes(df_clean)
    sources = make_sources(df_clean)
    source_chunks = make_source_chunks(df_clean)

    cell_types["ontology_id"] = cell_types["name"].apply(lambda x: cell_type_index.get(x))
    pathways["ontology_id"] = pathways["name"].apply(lambda x: pathway_index.get(x))
    del cell_type_index
    del pathway_index

    print(f"  cytokines:       {len(cytokines):,}")
    print(f"  cell types:      {len(cell_types):,}")
    print(f"  genes:            {len(genes):,}")
    print(f"  pathways:         {len(pathways):,}")
    print(f"  cell processes:   {len(cell_processes):,}")
    print(f"  sources:          {len(sources):,}")
    print(f"  source chunks:    {len(source_chunks):,}")

    # -----------------------------------------------------------------------
    # 4-11. Clear, load, and validate — all on one connection/transaction so
    # any failure rolls back the whole rebuild instead of leaving the
    # database cleared but only partially reloaded.
    # -----------------------------------------------------------------------
    with engine.begin() as conn:
        # 4. Clear existing database contents
        clear_existing_data(conn)

        # 5. Load entity/source tables
        print("\nLoading entity/source tables...")

        load_dataframe(
            cytokines,
            "cytokines",
            conn,
            chunksize,
        )

        load_dataframe(
            cell_types,
            "cell_types",
            conn,
            chunksize,
        )

        load_dataframe(
            genes,
            "genes",
            conn,
            chunksize,
        )

        load_dataframe(
            pathways,
            "pathways",
            conn,
            chunksize,
        )

        load_dataframe(
            cell_processes,
            "cell_processes",
            conn,
            chunksize,
        )

        load_dataframe(
            sources,
            "sources",
            conn,
            chunksize,
        )

        load_dataframe(
            source_chunks,
            "source_chunks",
            conn,
            chunksize,
        )

        # 6. Build interaction dataframe and map FK IDs
        print("\nBuilding interactions...")

        interactions = df_clean.copy()

        interactions = add_cytokine_ids(
            interactions,
            conn,
        )

        interactions = add_cell_type_ids(
            interactions,
            conn,
        )

        # Keep only the columns belonging to PostgreSQL interactions table.
        interactions_to_load = interactions[INTERACTION_COLUMNS].copy()

        # 7. Load interactions
        load_dataframe(
            interactions_to_load,
            "interactions",
            conn,
            chunksize,
        )

        # 8. Retrieve generated interaction IDs
        print("\nRetrieving generated interaction IDs...")

        interactions_with_ids = add_interaction_ids(
            interactions,
            conn,
        )

        print(
            f"✓ Mapped {len(interactions_with_ids):,} "
            "raw rows to interaction IDs"
        )

        # 9. Build junction tables
        print("\nBuilding junction tables...")

        interaction_genes = make_interaction_genes(
            df_clean,
            interactions_with_ids,
            conn,
        )

        interaction_pathways = make_interaction_pathways(
            df_clean,
            interactions_with_ids,
            conn,
        )

        interaction_cell_processes = make_interaction_cell_processes(
            df_clean,
            interactions_with_ids,
            conn,
        )

        print(f"  interaction_genes:          {len(interaction_genes):,}")
        print(f"  interaction_pathways:       {len(interaction_pathways):,}")
        print(
            f"  interaction_cell_processes: "
            f"{len(interaction_cell_processes):,}"
        )

        # 10. Load junction tables
        load_dataframe(
            interaction_genes,
            "interaction_genes",
            conn,
            chunksize,
        )

        load_dataframe(
            interaction_pathways,
            "interaction_pathways",
            conn,
            chunksize,
        )

        load_dataframe(
            interaction_cell_processes,
            "interaction_cell_processes",
            conn,
            chunksize,
        )

        # 11. Validate
        validate_database(
            conn,
            df_clean,
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Populate an existing PostgreSQL cytokine database "
            "from a raw parquet dataframe."
        )
    )

    parser.add_argument(
        "parquet",
        help="Path to the raw parquet file.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=10_000,
        help="Rows per pandas to_sql batch (default: 10000).",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.parquet):
        print(
            f"ERROR: parquet file does not exist: {args.parquet}",
            file=sys.stderr,
        )
        sys.exit(1)

    engine = get_engine()
    test_connection(engine)

    try:
        build_database(
            parquet_path=args.parquet,
            engine=engine,
            chunksize=args.batch_size,
        )
    except Exception:
        print(
            "\nERROR: database build failed.",
            file=sys.stderr,
        )
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
