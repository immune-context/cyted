import React from 'react';
import { Database, FileText, Table, Search, CheckCircle } from 'lucide-react';

const COLUMN_DESCRIPTIONS = [
  { key: 'cytokine_name', label: 'Cytokine Name', desc: 'Standardized name of the cytokine involved in the interaction.' },
  { key: 'cell_type', label: 'Cell Type', desc: 'The type of cell that is affected by the cytokine.' },
  { key: 'cytokine_effect', label: 'Cytokine Effect', desc: 'Description of the effect the cytokine has on the cell (e.g., proliferation, apoptosis).' },
  { key: 'regulated_genes', label: 'Regulated Genes', desc: 'Genes whose expression is regulated by the cytokine in this context (semicolon-separated).' },
  { key: 'gene_response_type', label: 'Gene Response Type', desc: 'How genes respond to the cytokine (e.g., upregulated, downregulated).' },
  { key: 'regulated_pathways', label: 'Regulated Pathways', desc: 'Signaling or metabolic pathways affected by the cytokine.' },
  { key: 'pathway_response_type', label: 'Pathway Response Type', desc: 'Type of pathway response to the cytokine.' },
  { key: 'cell_process_category', label: 'Cell Process Category', desc: 'Category of cellular process affected (e.g., cell cycle, immune response).' },
  { key: 'regulated_cell_processes', label: 'Regulated Cell Processes', desc: 'Specific cell processes regulated by the cytokine.' },
  { key: 'cell_process_response_type', label: 'Cell Process Response Type', desc: 'How the cell process responds to the cytokine.' },
  { key: 'chunk_id', label: 'Chunk ID', desc: 'Unique identifier for the source text chunk from the article.' },
  { key: 'source_id', label: 'Source ID', desc: 'Identifier for the source document (typically PMC article ID).' },
  { key: 'key_sentences', label: 'Key Sentences', desc: 'Extracted sentences from the paper that support the interaction claim.' },
  { key: 'causality_description', label: 'Causality Description', desc: 'Description of the causal relationship between cytokine and effect.' },
  { key: 'citation_id_classification', label: 'Citation ID Classification', desc: 'Classification of the citation or evidence type.' },
  { key: 'mapped_citation_id', label: 'Mapped Citation ID', desc: 'Normalized or mapped identifier linking to external citation databases.' },
  { key: 'species', label: 'Species', desc: 'Species in which the interaction was studied (e.g., human, mouse).' },
  { key: 'experimental_system_type', label: 'Experimental System Type', desc: 'Type of experimental setup (e.g., in vitro, in vivo, in siliico, etc.).' },
  { key: 'experimental_system_details', label: 'Experimental System Details', desc: 'Detailed description of the experimental conditions and setup.' },
  { key: 'experimental_perturbation', label: 'Experimental Perturbation', desc: 'What was manipulated in the experiment.' },
  { key: 'experimental_readout', label: 'Experimental Readout', desc: 'What was measured or observed as the outcome (e.g. flow cytometry, RNA sequencing, etc.' },
  { key: 'experimental_time_point', label: 'Experimental Time Point', desc: 'Time point(s) at which measurements were taken.' },
  { key: 'experimental_concentration', label: 'Experimental Concentration', desc: 'Concentration of cytokine or treatment used in the experiment.' },
  { key: 'qc_basic_interaction', label: 'QC Basic Interaction', desc: 'Quality control flag for the basic cytokine-cell interaction.' },
  { key: 'qc_cell_type', label: 'QC Cell Type', desc: 'Quality control flag for the cell type assignment.' },
  { key: 'regulated_genes_human', label: 'Regulated Genes (Human)', desc: 'Human orthologs or identifiers for the regulated genes.' },
  { key: 'regulated_genes_mouse', label: 'Regulated Genes (Mouse)', desc: 'Mouse orthologs or identifiers for the regulated genes.' },
  { key: 'causality_type', label: 'Causality Type', desc: 'Classification of the causal relationship (direct, indirect, or unknown).' },
  { key: 'necessary_condition', label: 'Necessary Condition', desc: 'Description of conditions where the cytokine effect was observed.' },
  { key: 'additional_info', label: 'Additional Info', desc: 'Any additional contextual information about the interaction.' },
  { key: 'cytokine_name_original', label: 'Cytokine Name (Original)', desc: 'Original cytokine name as it appeared in the source text before normalization.' },
  { key: 'cell_type_original', label: 'Cell Type (Original)', desc: 'Original cell type text from the source before normalization.' },
  { key: 'cytokine_effect_original', label: 'Cytokine Effect (Original)', desc: 'Original effect description from the source text.' },
  { key: 'experimental_readout_original', label: 'Experimental Readout (Original)', desc: 'Original readout description from the source.' },
  { key: 'experimental_perturbation_original', label: 'Experimental Perturbation (Original)', desc: 'Original perturbation description from the source.' },
  { key: 'url', label: 'URL', desc: 'Link to the PubMed Central article (PMC) where the interaction was extracted.' },
];


const About = () => {
  return (
    <div className="w-full space-y-12">
      {/* Database Creation Process */}
      <section>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6 flex items-center gap-2">
          Description
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-6 text-lg">
          The <b>Cyt</b>okine <b>E</b>ffects <b>D</b>atabase is a collection of 1,012,726 cytokine-cell type 
          interaction statements extracted from 110,000 full-text PubMed Central papers using an LLM-based data extraction pipeline
          with multi-stage quality control. To facilitate downstream analysis and interoperability  with other knowledge bases,
          cell type, pathway, and gene symbols are standardized using canonical names from the Cell Ontology, Cellosaurus, 
          National Cancer Institute Thesaurus, NCBO Pathway Ontology, and Ensembl Gene database.
          PMC IDs of the original article for each extracted interaction is included for reference, with a link to the
          relevant section in the paper online.
        </p> 
      </section>

      {/* Column Descriptions */}
      <section>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6 flex items-center gap-2">
          Table Schema
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-6 text-lg">
          Each row in the <code className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-sm">cytokine_effects</code> table
          represents one cytokine–cell interaction extracted from the literature. Below is what each column represents:
        </p>
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 dark:bg-gray-800">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-300">Column</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-300">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {COLUMN_DESCRIPTIONS.map(({ key, label, desc }) => (
                <tr key={key} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-4 py-3 font-mono text-blue-600 dark:text-blue-400 whitespace-nowrap">{key}</td>
                  <td className="px-4 py-3">
                    <span className="font-medium text-gray-800 dark:text-gray-200">{label}:</span>{' '}
                    <span className="text-gray-600 dark:text-gray-400">{desc}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default About;
