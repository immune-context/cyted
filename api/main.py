import os
from contextlib import contextmanager
from enum import Enum
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

### PostgreSQL Connection

DATABASE_URL = os.getenv("DATABASE_URL")
PG_POOL_SIZE = int(os.getenv("PG_POOL_SIZE", '2'))
PG_MAX_OVERFLOW = int(os.getenv("PG_MAX_OVERFLOW", '0'))

assert DATABASE_URL is not None, "please set environment variable DATABASE_URL"

engine = create_engine(
    DATABASE_URL,
    pool_size=PG_POOL_SIZE,
    max_overflow=PG_MAX_OVERFLOW,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


SEARCH_FIELDS = [
    {"key": "cytokine", "label": "Cytokine Name"},
    {"key": "cell_type", "label": "Cell Type"},
    {"key": "gene", "label": "Regulated Gene"},
    {"key": "cell_process", "label": "Cell Process"},
    {"key": "pathway", "label": "Pathway"},
    {"key": "source_id", "label": "Source ID"},
]

ALL_COLUMNS = [
    "interaction_id",
    "raw_row_id",
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

INTERACTIONS_FROM = """
FROM interactions i
JOIN cytokines c
    ON c.cytokine_id = i.cytokine_id
JOIN cell_types ct
    ON ct.cell_type_id = i.cell_type_id
LEFT JOIN source_chunks sc
    ON sc.chunk_id = i.chunk_id
"""

DETAIL_FROM = """
FROM interactions i
JOIN cytokines c
    ON c.cytokine_id = i.cytokine_id
JOIN cell_types ct
    ON ct.cell_type_id = i.cell_type_id
LEFT JOIN source_chunks sc
    ON sc.chunk_id = i.chunk_id
LEFT JOIN interaction_genes ig
    ON ig.interaction_id = i.interaction_id
LEFT JOIN genes g
    ON g.gene_id = ig.gene_id
LEFT JOIN interaction_pathways ip
    ON ip.interaction_id = i.interaction_id
LEFT JOIN pathways p
    ON p.pathway_id = ip.pathway_id
LEFT JOIN interaction_cell_processes icp
    ON icp.interaction_id = i.interaction_id
LEFT JOIN cell_processes cp
    ON cp.cell_process_id = icp.cell_process_id
"""

DETAIL_SELECT = """
SELECT
    i.interaction_id,
    i.raw_row_id,
    c.name AS cytokine_name,
    ct.name AS cell_type,
    i.cytokine_effect,
    STRING_AGG(DISTINCT g.symbol, '; ' ORDER BY g.symbol) AS regulated_genes,
    i.gene_response_type,
    STRING_AGG(DISTINCT p.name, '; ' ORDER BY p.name) AS regulated_pathways,
    i.pathway_response_type,
    MAX(cp.category) AS cell_process_category,
    STRING_AGG(DISTINCT cp.name, '; ' ORDER BY cp.name) AS regulated_cell_processes,
    i.cell_process_response_type,
    i.chunk_id,
    sc.source_id,
    i.key_sentences,
    i.causality_description,
    i.citation_id_classification,
    i.mapped_citation_id,
    i.species,
    i.experimental_system_type,
    i.experimental_system_details,
    i.experimental_perturbation,
    i.experimental_readout,
    i.experimental_time_point,
    i.experimental_concentration,
    i.qc_basic_interaction,
    i.qc_cell_type,
    i.causality_type,
    i.necessary_condition,
    i.additional_info,
    i.cytokine_name_original,
    i.cell_type_original,
    i.cytokine_effect_original,
    i.regulated_pathways_original,
    i.experimental_readout_original,
    i.experimental_perturbation_original,
    sc.url
"""

DETAIL_GROUP_BY = """
GROUP BY
    i.interaction_id,
    i.raw_row_id,
    c.name,
    ct.name,
    i.cytokine_effect,
    i.gene_response_type,
    i.pathway_response_type,
    i.cell_process_response_type,
    i.chunk_id,
    sc.source_id,
    i.key_sentences,
    i.causality_description,
    i.citation_id_classification,
    i.mapped_citation_id,
    i.species,
    i.experimental_system_type,
    i.experimental_system_details,
    i.experimental_perturbation,
    i.experimental_readout,
    i.experimental_time_point,
    i.experimental_concentration,
    i.qc_basic_interaction,
    i.qc_cell_type,
    i.causality_type,
    i.necessary_condition,
    i.additional_info,
    i.cytokine_name_original,
    i.cell_type_original,
    i.cytokine_effect_original,
    i.regulated_pathways_original,
    i.experimental_readout_original,
    i.experimental_perturbation_original,
    sc.url
"""

# (alias, column, FROM clause reaching interactions i / cytokines c / cell_types ct / source_chunks sc)
# so that build_filter_sql's WHERE clauses (which reference those aliases) apply unchanged.
SUGGESTION_FROM: dict[str, tuple[str, str, str]] = {
    "cytokine": (
        "c",
        "name",
        """
        FROM cytokines c
        JOIN interactions i ON i.cytokine_id = c.cytokine_id
        JOIN cell_types ct ON ct.cell_type_id = i.cell_type_id
        LEFT JOIN source_chunks sc ON sc.chunk_id = i.chunk_id
        """,
    ),
    "cell_type": (
        "ct",
        "name",
        """
        FROM cell_types ct
        JOIN interactions i ON i.cell_type_id = ct.cell_type_id
        JOIN cytokines c ON c.cytokine_id = i.cytokine_id
        LEFT JOIN source_chunks sc ON sc.chunk_id = i.chunk_id
        """,
    ),
    "gene": (
        "g",
        "symbol",
        """
        FROM genes g
        JOIN interaction_genes ig ON ig.gene_id = g.gene_id
        JOIN interactions i ON i.interaction_id = ig.interaction_id
        JOIN cytokines c ON c.cytokine_id = i.cytokine_id
        JOIN cell_types ct ON ct.cell_type_id = i.cell_type_id
        LEFT JOIN source_chunks sc ON sc.chunk_id = i.chunk_id
        """,
    ),
    "cell_process": (
        "cp",
        "name",
        """
        FROM cell_processes cp
        JOIN interaction_cell_processes icp ON icp.cell_process_id = cp.cell_process_id
        JOIN interactions i ON i.interaction_id = icp.interaction_id
        JOIN cytokines c ON c.cytokine_id = i.cytokine_id
        JOIN cell_types ct ON ct.cell_type_id = i.cell_type_id
        LEFT JOIN source_chunks sc ON sc.chunk_id = i.chunk_id
        """,
    ),
    "pathway": (
        "p",
        "name",
        """
        FROM pathways p
        JOIN interaction_pathways ip ON ip.pathway_id = p.pathway_id
        JOIN interactions i ON i.interaction_id = ip.interaction_id
        JOIN cytokines c ON c.cytokine_id = i.cytokine_id
        JOIN cell_types ct ON ct.cell_type_id = i.cell_type_id
        LEFT JOIN source_chunks sc ON sc.chunk_id = i.chunk_id
        """,
    ),
    "source_id": (
        "sc",
        "source_id",
        """
        FROM source_chunks sc
        JOIN interactions i ON i.chunk_id = sc.chunk_id
        JOIN cytokines c ON c.cytokine_id = i.cytokine_id
        JOIN cell_types ct ON ct.cell_type_id = i.cell_type_id
        """,
    ),
}


class SearchField(str, Enum):
    cytokine = "cytokine"
    cell_type = "cell_type"
    gene = "gene"
    cell_process = "cell_process"
    pathway = "pathway"
    source_id = "source_id"


class SearchFilters(BaseModel):
    cytokine: list[str] = Field(default_factory=list)
    cell_type: list[str] = Field(default_factory=list)
    gene: list[str] = Field(default_factory=list)
    cell_process: list[str] = Field(default_factory=list)
    pathway: list[str] = Field(default_factory=list)
    source_id: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            [
                self.cytokine,
                self.cell_type,
                self.gene,
                self.cell_process,
                self.pathway,
                self.source_id,
            ]
        )

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "cytokine": self.cytokine,
            "cell_type": self.cell_type,
            "gene": self.gene,
            "cell_process": self.cell_process,
            "pathway": self.pathway,
            "source_id": self.source_id,
        }


class SummaryGroup(BaseModel):
    cytokine_id: int
    cytokine_name: str
    cell_type_id: int
    cell_type: str
    paper_count: int
    interaction_count: int


class SummaryResponse(BaseModel):
    filters: dict[str, list[str]]
    groups: list[SummaryGroup]
    total_groups: int


class SuggestionsResponse(BaseModel):
    field: str
    values: list[str]


class SuggestionsPageResponse(BaseModel):
    field: str
    values: list[str]
    pagination: dict[str, int]


class PaginatedInteractionsResponse(BaseModel):
    data: list[dict[str, Any]]
    pagination: dict[str, int]
    filters: dict[str, list[str]]
    cytokine_id: int
    cell_type_id: int


def build_suggestion_where(
    field: str, filters: SearchFilters, q: str = ""
) -> tuple[str, str, str, str, dict[str, Any]]:
    alias, column, from_sql = SUGGESTION_FROM[field]

    # Exclude the field's own filter so its suggestions still expand across
    # values compatible with everything else selected (multi-select support).
    other_filters = SearchFilters(**{**filters.as_dict(), field: []})
    where_sql, params = build_filter_sql(other_filters)

    q = q.strip()
    if q:
        pattern_clause = f"{alias}.{column} ILIKE :pattern"
        where_sql = (
            f"{where_sql} AND {pattern_clause}"
            if where_sql
            else f"WHERE {pattern_clause}"
        )
        params["pattern"] = f"%{q}%"

    return alias, column, from_sql, where_sql, params


def build_suggestion_sql(
    field: str, filters: SearchFilters, q: str
) -> tuple[str, dict[str, Any]]:
    alias, column, from_sql, where_sql, params = build_suggestion_where(field, filters, q)

    sql = f"""
        SELECT value FROM (
            SELECT DISTINCT {alias}.{column} AS value
            {from_sql}
            {where_sql}
        ) AS distinct_values
        ORDER BY value NOT ILIKE :prefix_pattern, length(value), value
        LIMIT :limit
    """
    return sql, params


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_list_params(values: Optional[list[str]]) -> list[str]:
    if not values:
        return []

    parsed: list[str] = []
    for value in values:
        parsed.extend(part.strip() for part in value.split(",") if part.strip())
    return parsed


def build_search_filters(
    cytokine: Optional[list[str]] = None,
    cell_type: Optional[list[str]] = None,
    gene: Optional[list[str]] = None,
    cell_process: Optional[list[str]] = None,
    pathway: Optional[list[str]] = None,
    source_id: Optional[list[str]] = None,
) -> SearchFilters:
    return SearchFilters(
        cytokine=parse_list_params(cytokine),
        cell_type=parse_list_params(cell_type),
        gene=parse_list_params(gene),
        cell_process=parse_list_params(cell_process),
        pathway=parse_list_params(pathway),
        source_id=parse_list_params(source_id),
    )


def require_filters(filters: SearchFilters) -> None:
    if filters.is_empty():
        raise HTTPException(
            status_code=400,
            detail="At least one search filter is required.",
        )


def build_filter_sql(filters: SearchFilters) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}

    if filters.cytokine:
        clauses.append("c.name = ANY(:cytokines)")
        params["cytokines"] = filters.cytokine

    if filters.cell_type:
        clauses.append("ct.name = ANY(:cell_types)")
        params["cell_types"] = filters.cell_type

    if filters.gene:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM interaction_genes ig
                JOIN genes g
                    ON g.gene_id = ig.gene_id
                WHERE ig.interaction_id = i.interaction_id
                  AND g.symbol = ANY(:genes)
            )
            """
        )
        params["genes"] = filters.gene

    if filters.cell_process:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM interaction_cell_processes icp
                JOIN cell_processes cp
                    ON cp.cell_process_id = icp.cell_process_id
                WHERE icp.interaction_id = i.interaction_id
                  AND cp.name = ANY(:cell_processes)
            )
            """
        )
        params["cell_processes"] = filters.cell_process

    if filters.pathway:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM interaction_pathways ip
                JOIN pathways p
                    ON p.pathway_id = ip.pathway_id
                WHERE ip.interaction_id = i.interaction_id
                  AND p.name = ANY(:pathways)
            )
            """
        )
        params["pathways"] = filters.pathway

    if filters.source_id:
        clauses.append("sc.source_id = ANY(:source_ids)")
        params["source_ids"] = filters.source_id

    if not clauses:
        return "", params

    return "WHERE " + " AND ".join(clauses), params


def row_to_dict(row) -> dict[str, Any]:
    return dict(row._mapping)



### FastAPI Endpoints

app = FastAPI(
    title="Cytokine Knowledgebase API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Cytokine Knowledgebase API", "version": "2.0.0"}


@app.get("/api/search-fields")
def get_search_fields():
    return {"fields": SEARCH_FIELDS}


@app.get("/api/columns")
def get_columns():
    return {"columns": ALL_COLUMNS}


@app.get("/api/suggestions", response_model=SuggestionsResponse)
def get_suggestions(
    field: SearchField = Query(...),
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    cytokine: Optional[list[str]] = Query(None),
    cell_type: Optional[list[str]] = Query(None),
    gene: Optional[list[str]] = Query(None),
    cell_process: Optional[list[str]] = Query(None),
    pathway: Optional[list[str]] = Query(None),
    source_id: Optional[list[str]] = Query(None),
):
    filters = build_search_filters(
        cytokine=cytokine,
        cell_type=cell_type,
        gene=gene,
        cell_process=cell_process,
        pathway=pathway,
        source_id=source_id,
    )
    sql, params = build_suggestion_sql(field.value, filters, q)

    params.update(
        {
            "limit": limit,
            "prefix_pattern": f"{q.strip()}%",
        }
    )

    with get_db() as db:
        rows = db.execute(text(sql), params).all()

    return {
        "field": field.value,
        "values": [row.value for row in rows],
    }


@app.get("/api/suggestions/browse", response_model=SuggestionsPageResponse)
def browse_suggestions(
    field: SearchField = Query(...),
    q: str = Query(""),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    cytokine: Optional[list[str]] = Query(None),
    cell_type: Optional[list[str]] = Query(None),
    gene: Optional[list[str]] = Query(None),
    cell_process: Optional[list[str]] = Query(None),
    pathway: Optional[list[str]] = Query(None),
    source_id: Optional[list[str]] = Query(None),
):
    filters = build_search_filters(
        cytokine=cytokine,
        cell_type=cell_type,
        gene=gene,
        cell_process=cell_process,
        pathway=pathway,
        source_id=source_id,
    )
    alias, column, from_sql, where_sql, params = build_suggestion_where(
        field.value, filters, q
    )

    count_sql = f"""
        SELECT COUNT(*) AS total FROM (
            SELECT DISTINCT {alias}.{column} AS value
            {from_sql}
            {where_sql}
        ) AS distinct_values
    """

    offset = (page - 1) * limit
    data_sql = f"""
        SELECT value FROM (
            SELECT DISTINCT {alias}.{column} AS value
            {from_sql}
            {where_sql}
        ) AS distinct_values
        ORDER BY value NOT ILIKE :prefix_pattern, length(value), value
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset
    params["prefix_pattern"] = f"{q.strip()}%"

    with get_db() as db:
        total = db.execute(text(count_sql), params).scalar_one()
        rows = db.execute(text(data_sql), params).all()

    total_pages = (total + limit - 1) // limit if total else 0

    return {
        "field": field.value,
        "values": [row.value for row in rows],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
        },
    }


@app.get("/api/summary", response_model=SummaryResponse)
def get_summary(
    cytokine: Optional[list[str]] = Query(None),
    cell_type: Optional[list[str]] = Query(None),
    gene: Optional[list[str]] = Query(None),
    cell_process: Optional[list[str]] = Query(None),
    pathway: Optional[list[str]] = Query(None),
    source_id: Optional[list[str]] = Query(None),
):
    filters = build_search_filters(
        cytokine=cytokine,
        cell_type=cell_type,
        gene=gene,
        cell_process=cell_process,
        pathway=pathway,
        source_id=source_id,
    )
    require_filters(filters)

    where_clause, params = build_filter_sql(filters)
    sql = f"""
        SELECT
            c.cytokine_id,
            c.name AS cytokine_name,
            ct.cell_type_id,
            ct.name AS cell_type,
            COUNT(DISTINCT sc.source_id) AS paper_count,
            COUNT(DISTINCT i.interaction_id) AS interaction_count
        {INTERACTIONS_FROM}
        {where_clause}
        GROUP BY
            c.cytokine_id,
            c.name,
            ct.cell_type_id,
            ct.name
        ORDER BY
            paper_count DESC,
            interaction_count DESC,
            cytokine_name ASC,
            cell_type ASC
    """

    with get_db() as db:
        rows = db.execute(text(sql), params).all()

    groups = [row_to_dict(row) for row in rows]
    active_filters = {
        key: value for key, value in filters.as_dict().items() if value
    }

    return {
        "filters": active_filters,
        "groups": groups,
        "total_groups": len(groups),
    }


@app.get("/api/interactions", response_model=PaginatedInteractionsResponse)
def get_interactions(
    cytokine_id: int = Query(...),
    cell_type_id: int = Query(...),
    cytokine: Optional[list[str]] = Query(None),
    cell_type: Optional[list[str]] = Query(None),
    gene: Optional[list[str]] = Query(None),
    cell_process: Optional[list[str]] = Query(None),
    pathway: Optional[list[str]] = Query(None),
    source_id: Optional[list[str]] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
):
    filters = build_search_filters(
        cytokine=cytokine,
        cell_type=cell_type,
        gene=gene,
        cell_process=cell_process,
        pathway=pathway,
        source_id=source_id,
    )
    require_filters(filters)

    where_clause, params = build_filter_sql(filters)
    pair_clause = "i.cytokine_id = :cytokine_id AND i.cell_type_id = :cell_type_id"
    if where_clause:
        where_clause = where_clause + f" AND {pair_clause}"
    else:
        where_clause = f"WHERE {pair_clause}"

    params["cytokine_id"] = cytokine_id
    params["cell_type_id"] = cell_type_id

    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM (
            SELECT i.interaction_id
            {DETAIL_FROM}
            {where_clause}
            {DETAIL_GROUP_BY}
        ) AS grouped_interactions
    """

    offset = (page - 1) * limit
    data_sql = f"""
        {DETAIL_SELECT}
        {DETAIL_FROM}
        {where_clause}
        {DETAIL_GROUP_BY}
        ORDER BY i.interaction_id ASC
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    with get_db() as db:
        total = db.execute(text(count_sql), params).scalar_one()
        rows = db.execute(text(data_sql), params).all()

    active_filters = {
        key: value for key, value in filters.as_dict().items() if value
    }
    total_pages = (total + limit - 1) // limit if total else 0

    return {
        "data": [row_to_dict(row) for row in rows],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
        },
        "filters": active_filters,
        "cytokine_id": cytokine_id,
        "cell_type_id": cell_type_id,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
