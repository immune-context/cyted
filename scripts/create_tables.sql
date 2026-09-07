-- Biological entity tables

CREATE TABLE cytokines (
    cytokine_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE cell_types (
    cell_type_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    ontology_id TEXT
);

CREATE TABLE genes (
    gene_id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    species TEXT,
    UNIQUE (symbol, species)
);

CREATE TABLE pathways (
    pathway_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    ontology_id TEXT
);

CREATE TABLE cell_processes (
    cell_process_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT
);


-- Publication/source tables

CREATE TABLE sources (
    source_id TEXT PRIMARY KEY, -- PMC ID
    pmc_id TEXT,
    alt_id TEXT
);

CREATE TABLE source_chunks (
    chunk_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL
        REFERENCES sources(source_id)
        ON DELETE CASCADE,

    chunk_text TEXT,
    url TEXT
);


-- ============================================================
-- Central extracted interaction table
-- ============================================================

CREATE TABLE interactions (
    interaction_id BIGSERIAL PRIMARY KEY,

    raw_row_id BIGINT NOT NULL UNIQUE,

    cytokine_id BIGINT NOT NULL
        REFERENCES cytokines(cytokine_id),

    cell_type_id BIGINT NOT NULL
        REFERENCES cell_types(cell_type_id),

    chunk_id TEXT
        REFERENCES source_chunks(chunk_id),

    cytokine_effect TEXT,
    gene_response_type TEXT,
    pathway_response_type TEXT,
    cell_process_response_type TEXT,

    causality_description TEXT,
    causality_type TEXT,
    necessary_condition TEXT,

    species TEXT,

    experimental_system_type TEXT,
    experimental_system_details TEXT,
    experimental_perturbation TEXT,
    experimental_readout TEXT,
    experimental_time_point TEXT,
    experimental_concentration TEXT,

    citation_id_classification TEXT,
    mapped_citation_id TEXT,

    key_sentences TEXT,

    qc_basic_interaction TEXT,
    qc_cell_type TEXT,

    additional_info TEXT,

    cytokine_name_original TEXT,
    cell_type_original TEXT,
    cytokine_effect_original TEXT,
    regulated_pathways_original TEXT,
    experimental_readout_original TEXT,
    experimental_perturbation_original TEXT
);


-- Many-to-many relationship tables

CREATE TABLE interaction_genes (
    interaction_id BIGINT NOT NULL
        REFERENCES interactions(interaction_id)
        ON DELETE CASCADE,

    gene_id BIGINT NOT NULL
        REFERENCES genes(gene_id),

    response_type TEXT,

    PRIMARY KEY (interaction_id, gene_id)
);


CREATE TABLE interaction_pathways (
    interaction_id BIGINT NOT NULL
        REFERENCES interactions(interaction_id)
        ON DELETE CASCADE,

    pathway_id BIGINT NOT NULL
        REFERENCES pathways(pathway_id),

    response_type TEXT,

    PRIMARY KEY (interaction_id, pathway_id)
);


CREATE TABLE interaction_cell_processes (
    interaction_id BIGINT NOT NULL
        REFERENCES interactions(interaction_id)
        ON DELETE CASCADE,

    cell_process_id BIGINT NOT NULL
        REFERENCES cell_processes(cell_process_id),

    response_type TEXT,

    PRIMARY KEY (interaction_id, cell_process_id)
);


-- Indexes for the application's search patterns

CREATE INDEX idx_interactions_cytokine
    ON interactions(cytokine_id);

CREATE INDEX idx_interactions_cell_type
    ON interactions(cell_type_id);

CREATE INDEX idx_interactions_chunk
    ON interactions(chunk_id);

CREATE INDEX idx_source_chunks_source
    ON source_chunks(source_id);

CREATE INDEX idx_interaction_genes_gene
    ON interaction_genes(gene_id);

CREATE INDEX idx_interaction_pathways_pathway
    ON interaction_pathways(pathway_id);

CREATE INDEX idx_interaction_processes_process
    ON interaction_cell_processes(cell_process_id);

CREATE INDEX idx_interactions_cytokine_cell
    ON interactions(cytokine_id, cell_type_id);