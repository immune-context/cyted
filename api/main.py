import argparse
import os
import re
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
assert DATABASE_URL is not None, "please set environment variable DATABASE_URL"

engine_kwargs = {
    "pool_size": 20,
    "max_overflow": 40,
    "pool_timeout": 30,
    "pool_recycle": 1800,
}
engine = create_engine(DATABASE_URL, **engine_kwargs) if "supabase.com" in DATABASE_URL else create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

ALL_COLUMNS = ['id', 'cytokine_name', 'cell_type', 'cytokine_effect', 'regulated_genes',
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
       'experimental_readout_original',
       'experimental_perturbation_original', 'url']

# Database Model (columns must match ALL_COLUMNS)
class CytokineInteraction(Base):
    __tablename__ = "cytokine_effects"

    id = Column(Integer, primary_key=True, index=True)
    cytokine_name = Column(String(200), index=True)
    cell_type = Column(String(500), index=True)
    cytokine_effect = Column(String(500))
    regulated_genes = Column(Text)
    gene_response_type = Column(String(200))
    regulated_pathways = Column(Text)
    pathway_response_type = Column(String(200))
    cell_process_category = Column(String(200))
    regulated_cell_processes = Column(Text)
    cell_process_response_type = Column(String(200))
    chunk_id = Column(String(200))
    source_id = Column(String(200))
    key_sentences = Column(Text)
    causality_description = Column(Text)
    citation_id_classification = Column(String(200))
    mapped_citation_id = Column(String(200))
    species = Column(String(200), index=True)
    experimental_system_type = Column(String(200))
    experimental_system_details = Column(Text)
    experimental_perturbation = Column(String(500))
    experimental_readout = Column(String(500))
    experimental_time_point = Column(String(200))
    experimental_concentration = Column(String(200))
    qc_basic_interaction = Column(String(200))
    qc_cell_type = Column(String(200))
    regulated_genes_human = Column(Text)
    regulated_genes_mouse = Column(Text)
    causality_type = Column(String(200))
    necessary_condition = Column(String(500))
    additional_info = Column(Text)
    cytokine_name_original = Column(String(500))
    cell_type_original = Column(String(500))
    cytokine_effect_original = Column(String(500))
    experimental_readout_original = Column(String(500))
    experimental_perturbation_original = Column(String(500))
    url = Column(String(500))

# Pydantic models
class InteractionResponse(BaseModel):
    id: int
    data: Dict[str, Any]
    
    class Config:
        from_attributes = True

class PaginatedResponse(BaseModel):
    data: List[Dict[str, Any]]
    pagination: Dict[str, Any]
    filters: Dict[str, Any]

class FilterOptions(BaseModel):
    column: str
    values: List[str]

# FastAPI app
app = FastAPI(
    title="Cytokine Knowledgebase API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "Cytokine Knowledgebase API", "version": "1.0.0"}

@app.get("/api/interactions", response_model=PaginatedResponse)
def get_interactions(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    fields: Optional[str] = None,
    cytokine_name: Optional[str] = None,
    cell_type: Optional[str] = None,
    species: Optional[str] = None,
    regulated_genes: Optional[str] = None,
    causality_type: Optional[str] = None,
    experimental_system_type: Optional[str] = None,
    regulated_pathways: Optional[str] = None,
    cell_process_category: Optional[str] = None,
    cytokine_effect: Optional[str] = None,
    necessary_condition: Optional[str] = None,
    experimental_readout: Optional[str] = None,
):
    with get_db() as db:
        query = db.query(CytokineInteraction)
        filters = {}

        if cytokine_name:
            query = query.filter(CytokineInteraction.cytokine_name.ilike(f"%{cytokine_name}%"))
            filters["cytokine_name"] = cytokine_name
        if cell_type:
            query = query.filter(CytokineInteraction.cell_type.ilike(f"%{cell_type}%"))
            filters["cell_type"] = cell_type
        if species:
            query = query.filter(CytokineInteraction.species.ilike(f"%{species}%"))
            filters["species"] = species
        if causality_type:
            query = query.filter(CytokineInteraction.causality_type.ilike(f"%{causality_type}%"))
            filters["causality_type"] = causality_type
        if experimental_system_type:
            query = query.filter(CytokineInteraction.experimental_system_type.ilike(f"%{experimental_system_type}%"))
            filters['experimental_system_type'] = experimental_system_type
        if regulated_genes:
            query = query.filter(CytokineInteraction.regulated_genes.ilike(f"%{regulated_genes}%"))
            filters["regulated_genes"] = regulated_genes
        if cell_process_category:
            query = query.filter(CytokineInteraction.cell_process_category.ilike(f"%{cell_process_category}%"))
            filters["cell_process_category"] = cell_process_category
        if regulated_pathways:
            query = query.filter(CytokineInteraction.regulated_pathways.ilike(f"%{regulated_pathways}%"))
            filters["regulated_pathways"] = regulated_pathways
        if necessary_condition:
            query = query.filter(CytokineInteraction.necessary_condition.ilike(f"%{necessary_condition}%"))
            filters["necessary_condition"] = necessary_condition
        if experimental_readout:
            query = query.filter(CytokineInteraction.experimental_readout_original.ilike(f"%{experimental_readout}%"))
            filters["experimental_readout"] = experimental_readout
        if cytokine_effect:
            query = query.filter(CytokineInteraction.cytokine_effect.ilike(f"%{cytokine_effect}%"))
            filters["cytokine_effect"] = cytokine_effect

        total = query.count()

        # pagination
        offset = (page - 1) * limit
        results = query.offset(offset).limit(limit).all()

        requested_fields = (
            [f.strip() for f in fields.split(",") if f.strip() in ALL_COLUMNS]
            if fields else ALL_COLUMNS
        )

        data = [
            {field: getattr(row, field) for field in requested_fields}
            for row in results
        ]

        return {
            "data": data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit
            },
            "filters": filters
        }


@app.get("/api/filters/{column}")
def get_filter_options(column: str):
    """Get unique values for a specific column (for categorical dropdown filters)"""
    if column not in ALL_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Invalid column: {column}")

    # TODO: change this within the actual database instead of during the query
    cleanup_pattern = r' *\[.*?\]'
    
    with get_db() as db:
        col = getattr(CytokineInteraction, column, None)
        if col is None:
            raise HTTPException(status_code=400, detail=f"Column not found: {column}")
        
        # Get distinct values (some contain multiple items joined by ';' or '+')
        values = db.query(col).distinct().filter(col.isnot(None)).all()
        raw_values = [v[0] for v in values if v[0]]
        # Split on ';' or '+' and collect unique single entries
        seen = set()
        for val in raw_values:
            parts = re.split(r'[;+]', str(val)) if column == "cytokine_name" else str(val).split(';')
            for part in parts:
                part = part.strip()
                part = re.sub(cleanup_pattern, '', part)
                if part:
                    seen.add(part)
        return {"column": column, "values": sorted(seen)}

@app.get("/api/columns")
def get_columns():
    """Get all available columns"""
    return {"columns": ALL_COLUMNS}


@app.get("/api/interactions/export")
def export_interactions(
    fields: Optional[str] = None,
    limit: int = Query(50000, ge=1, le=100000),
    cytokine_name: Optional[str] = None,
    cell_type: Optional[str] = None,
    species: Optional[str] = None,
    regulated_genes: Optional[str] = None,
    causality_type: Optional[str] = None,
    experimental_system_type: Optional[str] = None,
    regulated_pathways: Optional[str] = None,
    cell_process_category: Optional[str] = None,
    cytokine_effect: Optional[str] = None,
    necessary_condition: Optional[str] = None,
    experimental_readout: Optional[str] = None,
):
    """Export filtered results as JSON (for CSV conversion on client)."""
    with get_db() as db:
        query = db.query(CytokineInteraction)

        if cytokine_name:
            query = query.filter(CytokineInteraction.cytokine_name.ilike(f"%{cytokine_name}%"))
        if cell_type:
            query = query.filter(CytokineInteraction.cell_type.ilike(f"%{cell_type}%"))
        if species:
            query = query.filter(CytokineInteraction.species.ilike(f"%{species}%"))
        if causality_type:
            query = query.filter(CytokineInteraction.causality_type.ilike(f"%{causality_type}%"))
        if experimental_system_type:
            query = query.filter(CytokineInteraction.experimental_system_type.ilike(f"%{experimental_system_type}%"))
        if regulated_genes:
            query = query.filter(CytokineInteraction.regulated_genes.ilike(f"%{regulated_genes}%"))
        if cell_process_category:
            query = query.filter(CytokineInteraction.cell_process_category.ilike(f"%{cell_process_category}%"))
        if regulated_pathways:
            query = query.filter(CytokineInteraction.regulated_pathways.ilike(f"%{regulated_pathways}%"))
        if necessary_condition:
            query = query.filter(CytokineInteraction.necessary_condition.ilike(f"%{necessary_condition}%"))
        if experimental_readout:
            query = query.filter(CytokineInteraction.experimental_readout_original.ilike(f"%{experimental_readout}%"))
        if cytokine_effect:
            query = query.filter(CytokineInteraction.cytokine_effect.ilike(f"%{cytokine_effect}%"))

        results = query.limit(limit).all()

        requested_fields = (
            [f.strip() for f in fields.split(",") if f.strip() in ALL_COLUMNS]
            if fields else ALL_COLUMNS
        )

        data = [
            {field: getattr(row, field) for field in requested_fields}
            for row in results
        ]

        return {"data": data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)