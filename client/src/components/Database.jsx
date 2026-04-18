import React, { useState, useEffect, useCallback } from 'react';
import { Search as SearchIcon, Filter, Download, ChevronLeft, ChevronRight, X, Settings } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_APP_API_BASE ?? 'http://localhost:8000';
console.log(API_BASE_URL);

// Must match ALL_COLUMNS from server/main.py (excluding 'id' for display/selector)
const ALL_COLUMNS = [
  'cytokine_name', 'cell_type', 'cytokine_effect', 'regulated_genes',
  'gene_response_type', 'regulated_pathways', 'pathway_response_type',
  'cell_process_category', 'regulated_cell_processes',
  'cell_process_response_type', 'chunk_id', 'source_id', 'key_sentences',
  'causality_description', 'citation_id_classification',
  'mapped_citation_id', 'species', 'experimental_system_type',
  'experimental_system_details', 'experimental_perturbation',
  'experimental_readout', 'experimental_time_point',
  'experimental_concentration',
  'regulated_genes_human', 'regulated_genes_mouse', 'causality_type',
  'necessary_condition', 'additional_info', 'cytokine_name_original',
  'cell_type_original', 'cytokine_effect_original',
  'experimental_readout_original',
  'experimental_perturbation_original', 'url',
];

const DEFAULT_VISIBLE_COLUMNS = [
  'cytokine_name', 'cell_type', 'cytokine_effect', 'regulated_genes',
  'gene_response_type', 'regulated_pathways', 'pathway_response_type',
  'cell_process_category', 'regulated_cell_processes',
  'cell_process_response_type', 'source_id', 'url',
  'citation_id_classification', 'mapped_citation_id', 'species',
  'experimental_system_type', 'experimental_system_details',
  'experimental_perturbation', 'experimental_readout',
];

const FILTERABLE_COLUMNS = [
  { key: 'cytokine_name', label: 'Cytokine Name' },
  { key: 'cell_type', label: 'Cell Type' },
  { key: 'species', label: 'Species' },
  { key: 'regulated_genes', label: 'Regulated Genes' },
  { key: 'experimental_system_type', label: 'Experimental System Type' },
  { key: 'regulated_pathways', label: 'Regulated Pathways' },
  { key: 'cell_process_category', label: 'Cell Process Category' },
  { key: 'causality_type', label: 'Causality Type' },
];

const EXTRA_FILTERABLE_COLUMNS = [
  { key: 'cytokine_effect', label: 'Cytokine Effect' },
  { key: 'necessary_condition', label: 'Necessary Condition' },
  { key: 'experimental_readout', label: 'Experimental Readout' },
];

const Database = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0, total_pages: 0 });
  const [filters, setFilters] = useState({});
  const [searchTerm, setSearchTerm] = useState('');
  const [filterOptions, setFilterOptions] = useState({});
  const [filterDraft, setFilterDraft] = useState({});
  const [showFilters, setShowFilters] = useState(true);
  const [showColumnSelector, setShowColumnSelector] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState(DEFAULT_VISIBLE_COLUMNS);

  const hasAppliedFilters =
    Object.values(filters).some(Boolean) || (searchTerm && searchTerm.trim().length > 0);

  const formatColumnName = (col) => {
    return col.split('_').map(word =>
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ').replace('Id', 'ID').replace('Url', 'URL');
  };

  const fetchData = useCallback(async (page = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: '50',
        fields: visibleColumns.join(','),
      });
      if (searchTerm) params.append('search', searchTerm);
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });

      const response = await fetch(
        `${API_BASE_URL}/api/interactions?${params}`,
        { headers: new Headers({ 'ngrok-skip-browser-warning': '69420' }) },
      );
      const result = await response.json();
      setData(result.data);
      setPagination(result.pagination);
    } catch (error) {
      console.error('Error fetching data:', error);
      alert('Error loading data. Make sure the backend server is running.');
    } finally {
      setLoading(false);
    }
  }, [filters, searchTerm, visibleColumns]);

  useEffect(() => {
    if (!hasAppliedFilters) {
      setData([]);
      setPagination({ page: 1, limit: 50, total: 0, total_pages: 0 });
      setLoading(false);
      return;
    }
    fetchData(1);
  }, [fetchData, hasAppliedFilters]);

  useEffect(() => {
    if (!hasAppliedFilters) {
      setShowFilters(true);
      setShowColumnSelector(false);
    }
  }, [hasAppliedFilters]);

  const fetchFilterOptions = useCallback(async (column) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/filters/${column}`,
        { headers: new Headers({ 'ngrok-skip-browser-warning': '69420' }) },
      );
      const result = await response.json();
      setFilterOptions((prev) => (prev[column] ? prev : { ...prev, [column]: result.values }));
    } catch (error) {
      console.error(`Error fetching filter options for ${column}:`, error);
    }
  }, []);

  useEffect(() => {
    if (showFilters) setFilterDraft(filters);
  }, [showFilters, filters]);

  // Fetch unique values for dropdowns when filter panel opens
  useEffect(() => {
    if (!showFilters) return;
    const cols = FILTERABLE_COLUMNS.map((c) => c.key);
    cols.forEach((col) => {
      if (!filterOptions[col]) fetchFilterOptions(col);
    });
  }, [showFilters, filterOptions, fetchFilterOptions]);

  const handleFilterSubmit = (e) => {
    e.preventDefault();
    setFilters(filterDraft);
  };

  const clearFilter = (column) => {
    const newFilters = { ...filters };
    delete newFilters[column];
    setFilters(newFilters);
  };

  const clearAllFilters = () => {
    setFilters({});
    setSearchTerm('');
  };

  const toggleColumn = (column) => {
    setVisibleColumns(prev =>
      prev.includes(column)
        ? prev.filter(c => c !== column)
        : [...prev, column]
    );
  };

  const exportToCSV = async () => {
    setExportLoading(true);
    try {
      const params = new URLSearchParams({
        fields: visibleColumns.join(','),
        limit: '50000',
      });
      if (searchTerm) params.append('search', searchTerm);
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });

      const response = await fetch(
        `${API_BASE_URL}/api/interactions/export?${params}`,
        { headers: new Headers({ 'ngrok-skip-browser-warning': '69420' }) },
      );
      const result = await response.json();
      const rows = result.data || [];

      if (rows.length === 0) {
        alert('No data to export. Try adjusting your filters.');
        return;
      }

      const headers = visibleColumns.join(',');
      const csvRows = rows.map(row =>
        visibleColumns.map(col => {
          const val = row[col] ?? '';
          return `"${String(val).replace(/"/g, '""')}"`;
        }).join(',')
      );
      const csv = [headers, ...csvRows].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cytokine_data_export_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error exporting:', error);
      alert('Error exporting data. Please try again.');
    } finally {
      setExportLoading(false);
    }
  };

  const truncateText = (text, maxLength = 100) => {
    if (!text || text === 'nan') return '-';
    const str = String(text);
    return str.length > maxLength ? str.substring(0, maxLength) + '...' : str;
  };

  const formatUrlPreview = (url) => {
    if (!url) return '-';
    try {
      const urlObj = new URL(url);
      const preview = urlObj.hostname + urlObj.pathname;
      return preview.length > 50 ? preview.substring(0, 50) + '...' : preview;
    } catch {
      return url.length > 50 ? url.substring(0, 50) + '...' : url;
    }
  };

  return (
    <div className="space-y-4">
      {/* Action buttons */}
      {hasAppliedFilters && (
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="px-4 py-2 bg-blue-100 hover:bg-gray-300 rounded-lg flex items-center gap-2 transition-colors dark:text-gray-900"
          >
            <Filter size={18} />
            Filters {Object.keys(filters).length > 0 && `(${Object.keys(filters).length})`}
          </button>
          <button
            onClick={() => setShowColumnSelector(!showColumnSelector)}
            className="px-4 py-2 bg-blue-100 hover:bg-gray-300 rounded-lg flex items-center gap-2 transition-colors dark:text-gray-900"
          >
            <Settings size={18} />
            Columns
          </button>
          <button
            onClick={exportToCSV}
            disabled={exportLoading}
            className="px-4 py-2 bg-blue-100 hover:bg-gray-300 rounded-lg flex items-center gap-2 transition-colors dark:text-gray-900 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <Download size={18} />
            {exportLoading ? 'Exporting...' : 'Export CSV'}
          </button>
        </div>
      )}

      {/* Active filters */}
      {(Object.keys(filters).length > 0 || searchTerm) && (
        <div className="flex flex-wrap gap-2 items-center">
          {searchTerm && (
            <span className="bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200 px-3 py-1 rounded-full text-sm flex items-center gap-2">
              Search: {searchTerm}
              <button onClick={() => setSearchTerm('')} className="hover:text-blue-600">
                <X size={14} />
              </button>
            </span>
          )}
          {Object.entries(filters).map(([key, value]) => (
            value && (
              <span key={key} className="bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200 px-3 py-1 rounded-full text-sm flex items-center gap-2">
                {formatColumnName(key)}: {value}
                <button onClick={() => clearFilter(key)} className="hover:text-blue-600">
                  <X size={14} />
                </button>
              </span>
            )
          ))}
          {hasAppliedFilters && (
            <button
              onClick={clearAllFilters}
              className="text-sm text-red-600 hover:text-red-700 font-medium"
            >
              Clear All
            </button>
          )}
        </div>
      )}

      {/* Filter panel */}
      {showFilters && (
        <form
          onSubmit={handleFilterSubmit}
          className={`bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700 ${
            hasAppliedFilters
              ? 'flex flex-wrap gap-x-6 gap-y-4 p-4'
              : 'grid grid-cols-2 gap-x-4 gap-y-6 max-w-xl mx-auto w-full min-h-[min(70vh,34rem)] px-6 py-8'
          }`}
        >
          {FILTERABLE_COLUMNS.map(({ key, label }) => (
            <div key={key} className={hasAppliedFilters ? 'w-fit' : 'min-w-0'}>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
              <select
                className={`w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ${
                  hasAppliedFilters ? 'min-w-[180px] max-w-[220px]' : 'min-w-0'
                }`}
                value={filterDraft[key] ?? ''}
                onChange={(e) => setFilterDraft(prev => ({ ...prev, [key]: e.target.value || undefined }))}
              >
                <option value="">All</option>
                {(filterOptions[key] ?? []).map((val) => (
                  <option key={val} value={val}>
                    {String(val).length > 60 ? `${String(val).slice(0, 57)}...` : val}
                  </option>
                ))}
              </select>
            </div>
          ))}
          {EXTRA_FILTERABLE_COLUMNS.map(({ key, label }) => (
            <div key={key} className={hasAppliedFilters ? 'w-fit' : 'min-w-0'}>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
              <input
                type="text"
                placeholder="Free text search..."
                className={`w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ${
                  hasAppliedFilters ? 'min-w-[180px] max-w-[220px]' : 'min-w-0'
                }`}
                value={filterDraft[key] ?? ''}
                onChange={(e) => setFilterDraft(prev => ({ ...prev, [key]: e.target.value || undefined }))}
              />
            </div>
          ))}
          <div
            className={
              hasAppliedFilters
                ? 'w-full flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between'
                : 'col-span-2 flex flex-col gap-3 pt-2'
            }
          >
            <button
              type="submit"
              className="px-4 py-2 bg-gray-300 rounded-lg hover:bg-blue-700 focus:ring-2 focus:ring-blue-500"
            >
              Apply filters
            </button>
            {!hasAppliedFilters && (
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Select at least one filter and click Apply to browse the database.
              </p>
            )}
          </div>
        </form>
      )}

      {/* Column selector */}
      {hasAppliedFilters && showColumnSelector && (
        <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Select columns to display</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 max-h-64 overflow-y-auto">
            {ALL_COLUMNS.map(col => (
              <label key={col} className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={visibleColumns.includes(col)}
                  onChange={() => toggleColumn(col)}
                  className="rounded text-blue-600 focus:ring-blue-500"
                />
                {formatColumnName(col)}
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Data table */}
      {hasAppliedFilters && (
        <div className="bg-white dark:bg-gray-800 shadow-md rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
          {loading ? (
            <div className="p-12 text-center">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="mt-4 text-gray-600 dark:text-gray-400">Loading data...</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-100 dark:bg-gray-700">
                    <tr>
                      {visibleColumns.map(col => (
                        <th
                          key={col}
                          className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap"
                        >
                          {formatColumnName(col)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-600">
                    {data.map((row, idx) => (
                      <tr key={row.id ?? idx} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        {visibleColumns.map(col => (
                          <td
                            key={col}
                            className="px-4 py-3 text-sm text-gray-800 dark:text-gray-200 break-words"
                          >
                            {col === 'url' && row[col] ? (
                              <a
                                href={row[col]}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:text-blue-800 hover:underline"
                                title={row[col]}
                              >
                                {formatUrlPreview(row[col])}
                              </a>
                            ) : (
                              truncateText(row[col])
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 flex flex-wrap items-center justify-between gap-4">
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Showing {((pagination.page - 1) * pagination.limit) + 1} to{' '}
                  {Math.min(pagination.page * pagination.limit, pagination.total)} of{' '}
                  {pagination.total?.toLocaleString() ?? 0} results
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => fetchData(pagination.page - 1)}
                    disabled={pagination.page <= 1}
                    className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-gray-700 dark:text-gray-300"
                  >
                    <ChevronLeft size={16} />
                    Previous
                  </button>
                  <span className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400">
                    Page {pagination.page} of {pagination.total_pages || 1}
                  </span>
                  <button
                    onClick={() => fetchData(pagination.page + 1)}
                    disabled={pagination.page >= pagination.total_pages}
                    className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-gray-700 dark:text-gray-300"
                  >
                    Next
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default Database;
