import { useCallback, useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Search, X } from 'lucide-react';

const BROWSE_LIMIT = 50;

const API_BASE_URL = import.meta.env.VITE_APP_API_BASE || 'http://localhost:8000';

const SEARCH_FIELD_KEYS = ['cytokine', 'cell_type', 'gene', 'cell_process', 'pathway', 'source_id'];

const EMPTY_FILTERS = Object.fromEntries(SEARCH_FIELD_KEYS.map((key) => [key, []]));

const fetchHeaders = { 'ngrok-skip-browser-warning': '69420' };

function formatColumnName(col) {
  return col
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
    .replace('Id', 'ID')
    .replace('Url', 'URL');
}

function filtersToParams(filters) {
  const params = new URLSearchParams();
  for (const key of SEARCH_FIELD_KEYS) {
    for (const value of filters[key] || []) {
      params.append(key, value);
    }
  }
  return params;
}

function hasFilters(filters) {
  return SEARCH_FIELD_KEYS.some((key) => (filters[key]?.length ?? 0) > 0);
}

function truncateText(text, maxLength = 120) {
  if (text == null || text === '') return '-';
  const str = String(text);
  return str.length > maxLength ? `${str.slice(0, maxLength)}...` : str;
}

function SuggestionBrowserModal({ fieldKey, label, values, onToggleValue, otherFilters, onClose, query = '' }) {
  const [page, setPage] = useState(1);
  const [browseValues, setBrowseValues] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, limit: BROWSE_LIMIT, total: 0, total_pages: 0 });
  const [loadingBrowse, setLoadingBrowse] = useState(false);
  const [browseError, setBrowseError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingBrowse(true);
      setBrowseError('');
      try {
        const params = filtersToParams(otherFilters);
        params.set('field', fieldKey);
        if (query.trim()) params.set('q', query.trim());
        params.set('page', String(page));
        params.set('limit', String(BROWSE_LIMIT));
        const response = await fetch(`${API_BASE_URL}/api/suggestions/browse?${params}`, {
          headers: fetchHeaders,
        });
        if (!response.ok) throw new Error('Failed to load suggestions');
        const result = await response.json();
        if (cancelled) return;
        setBrowseValues(result.values || []);
        setPagination(result.pagination || { page: 1, limit: BROWSE_LIMIT, total: 0, total_pages: 0 });
      } catch (err) {
        if (!cancelled) {
          setBrowseValues([]);
          setBrowseError(err.message || 'Failed to load suggestions');
        }
      } finally {
        if (!cancelled) setLoadingBrowse(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [fieldKey, query, page, otherFilters]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg max-h-[80vh] flex flex-col rounded-lg bg-white dark:bg-gray-800 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">
            {query.trim() ? `${label} matching "${query.trim()}"` : `All values: ${label}`}
          </h3>
          <button type="button" onClick={onClose} className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1">
          {browseError && <p className="text-sm text-red-600 dark:text-red-400">{browseError}</p>}
          {loadingBrowse && <p className="text-sm text-gray-500">Loading...</p>}
          {!loadingBrowse && !browseError && browseValues.length === 0 && (
            <p className="text-sm text-gray-500">No matches</p>
          )}
          {!loadingBrowse && browseValues.map((value) => {
            const selected = values.includes(value);
            return (
              <button
                key={value}
                type="button"
                onClick={() => onToggleValue(value)}
                className={`flex w-full items-center justify-between gap-2 text-left px-3 py-2 text-sm rounded-lg truncate ${
                  selected
                    ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
                title={value}
              >
                <span className="truncate">{value}</span>
                {selected && <span className="text-xs shrink-0">Selected</span>}
              </button>
            );
          })}
        </div>
        {pagination.total_pages > 1 && (
          <div className="flex items-center justify-between gap-4 text-sm px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <span className="text-gray-600 dark:text-gray-400">
              {((pagination.page - 1) * pagination.limit) + 1}–
              {Math.min(pagination.page * pagination.limit, pagination.total)} of {pagination.total}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={pagination.page <= 1 || loadingBrowse}
                onClick={() => setPage((p) => p - 1)}
                className="inline-flex items-center gap-1 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50"
              >
                <ChevronLeft size={14} />
              </button>
              <span>
                Page {pagination.page} of {pagination.total_pages}
              </span>
              <button
                type="button"
                disabled={pagination.page >= pagination.total_pages || loadingBrowse}
                onClick={() => setPage((p) => p + 1)}
                className="inline-flex items-center gap-1 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SearchField({ fieldKey, label, values, onChange, otherFilters }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [browserOpen, setBrowserOpen] = useState(false);
  const [browserQuery, setBrowserQuery] = useState('');

  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      return undefined;
    }

    const timer = setTimeout(async () => {
      setLoadingSuggestions(true);
      try {
        const params = filtersToParams(otherFilters);
        params.set('field', fieldKey);
        params.set('q', query.trim());
        params.set('limit', '15');
        const response = await fetch(`${API_BASE_URL}/api/suggestions?${params}`, {
          headers: fetchHeaders,
        });
        if (!response.ok) throw new Error('Failed to load suggestions');
        const result = await response.json();
        setSuggestions(result.values.filter((value) => !values.includes(value)));
      } catch {
        setSuggestions([]);
      } finally {
        setLoadingSuggestions(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [fieldKey, query, values, otherFilters]);

  const addValue = (value) => {
    if (!values.includes(value)) {
      onChange([...values, value]);
    }
    setQuery('');
    setSuggestions([]);
  };

  const removeValue = (value) => {
    onChange(values.filter((item) => item !== value));
  };

  const toggleValue = (value) => {
    if (values.includes(value)) {
      removeValue(value);
    } else {
      onChange([...values, value]);
      setBrowserQuery('');
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{label}</label>
        <button
          type="button"
          onClick={() => {
            setBrowserQuery('');
            setBrowserOpen(true);
          }}
          title={`Browse all ${label} values`}
          className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400"
        >
          <Search size={14} />
          Browse all
        </button>
      </div>
      <div className="flex flex-wrap gap-2 min-h-[2.25rem] p-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800">
        {values.map((value) => (
          <span
            key={value}
            className="inline-flex items-center gap-1 px-2 py-1 text-sm rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200"
          >
            <span className="max-w-[12rem] truncate" title={value}>{value}</span>
            <button type="button" onClick={() => removeValue(value)} className="hover:text-blue-600">
              <X size={14} />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={values.length ? 'Add another...' : 'Type to search...'}
          className="flex-1 min-w-[8rem] bg-transparent outline-none text-sm text-gray-900 dark:text-gray-100"
        />
      </div>
      {query.trim() && (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 shadow-sm max-h-40 overflow-y-auto">
          {loadingSuggestions && (
            <p className="px-3 py-2 text-sm text-gray-500">Loading...</p>
          )}
          {!loadingSuggestions && suggestions.length === 0 && (
            <p className="px-3 py-2 text-sm text-gray-500">No matches</p>
          )}
          {suggestions.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => addValue(value)}
              className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 truncate"
              title={value}
            >
              {value}
            </button>
          ))}
          {!loadingSuggestions && (
            <button
              type="button"
              onClick={() => {
                setBrowserQuery(query.trim());
                setBrowserOpen(true);
              }}
              className="block w-full text-left px-3 py-2 text-sm text-blue-600 dark:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700 border-t border-gray-200 dark:border-gray-700"
            >
              See more...
            </button>
          )}
        </div>
      )}
      {browserOpen && (
        <SuggestionBrowserModal
          fieldKey={fieldKey}
          label={label}
          values={values}
          otherFilters={otherFilters}
          onToggleValue={toggleValue}
          onClose={() => setBrowserOpen(false)}
          query={browserQuery}
        />
      )}
    </div>
  );
}

const Database = () => {
  const [step, setStep] = useState('search');
  const [searchFields, setSearchFields] = useState([]);
  const [columns, setColumns] = useState([]);
  const [filterDraft, setFilterDraft] = useState(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(EMPTY_FILTERS);
  const [summaryGroups, setSummaryGroups] = useState([]);
  const [selectedPair, setSelectedPair] = useState(null);
  const [detailRows, setDetailRows] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0, total_pages: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadMeta() {
      try {
        const [fieldsRes, columnsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/api/search-fields`, { headers: fetchHeaders }),
          fetch(`${API_BASE_URL}/api/columns`, { headers: fetchHeaders }),
        ]);
        if (fieldsRes.ok) {
          const fieldsData = await fieldsRes.json();
          setSearchFields(fieldsData.fields || []);
        }
        if (columnsRes.ok) {
          const columnsData = await columnsRes.json();
          setColumns(columnsData.columns || []);
        }
      } catch {
        // Meta endpoints are optional for rendering; search still works with defaults.
      }
    }
    loadMeta();
  }, []);

  const fieldLabels = searchFields.length
    ? Object.fromEntries(searchFields.map(({ key, label }) => [key, label]))
    : {
        cytokine: 'Cytokine Name',
        cell_type: 'Cell Type',
        gene: 'Regulated Gene',
        cell_process: 'Cell Process',
        pathway: 'Pathway',
        source_id: 'Source ID',
      };

  const fetchSummary = useCallback(async (filters) => {
    setLoading(true);
    setError('');
    try {
      const params = filtersToParams(filters);
      const response = await fetch(`${API_BASE_URL}/api/summary?${params}`, {
        headers: fetchHeaders,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || 'Failed to load summary');
      }
      const result = await response.json();
      setSummaryGroups(result.groups || []);
      setStep('summary');
    } catch (err) {
      setError(err.message || 'Failed to load summary');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDetail = useCallback(async (filters, pair, page = 1) => {
    setLoading(true);
    setError('');
    try {
      const params = filtersToParams(filters);
      params.set('cytokine_id', String(pair.cytokine_id));
      params.set('cell_type_id', String(pair.cell_type_id));
      params.set('page', String(page));
      params.set('limit', '50');

      const response = await fetch(`${API_BASE_URL}/api/interactions?${params}`, {
        headers: fetchHeaders,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || 'Failed to load interactions');
      }
      const result = await response.json();
      setDetailRows(result.data || []);
      setPagination(result.pagination || { page: 1, limit: 50, total: 0, total_pages: 0 });
      setStep('detail');
    } catch (err) {
      setError(err.message || 'Failed to load interactions');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    if (!hasFilters(filterDraft)) {
      setError('Add at least one search term before searching.');
      return;
    }
    setAppliedFilters(filterDraft);
    setSelectedPair(null);
    fetchSummary(filterDraft);
  };

  const handleSelectPair = (group) => {
    const pair = {
      cytokine_id: group.cytokine_id,
      cell_type_id: group.cell_type_id,
      cytokine_name: group.cytokine_name,
      cell_type: group.cell_type,
    };
    setSelectedPair(pair);
    fetchDetail(appliedFilters, pair, 1);
  };

  const handleBackToSearch = () => {
    setStep('search');
    setError('');
  };

  const handleBackToSummary = () => {
    setStep('summary');
    setError('');
  };

  const updateDraft = (key, values) => {
    setFilterDraft((prev) => ({ ...prev, [key]: values }));
  };

  const clearAll = () => {
    setFilterDraft(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setSummaryGroups([]);
    setSelectedPair(null);
    setDetailRows([]);
    setStep('search');
    setError('');
  };

  const activeFilterChips = SEARCH_FIELD_KEYS.flatMap((key) =>
    (appliedFilters[key] || []).map((value) => ({ key, value }))
  );

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-wrap items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
        <span className={step === 'search' ? 'font-semibold text-blue-600 dark:text-blue-400' : ''}>1. Search</span>
        <span>→</span>
        <span className={step === 'summary' ? 'font-semibold text-blue-600 dark:text-blue-400' : ''}>2. Summary</span>
        <span>→</span>
        <span className={step === 'detail' ? 'font-semibold text-blue-600 dark:text-blue-400' : ''}>3. Details</span>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {step === 'search' && (
        <form onSubmit={handleSearch} className="space-y-6">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Add one or more exact-match terms per field. Autocomplete uses substring matching.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {SEARCH_FIELD_KEYS.map((key) => (
              <SearchField
                key={key}
                fieldKey={key}
                label={fieldLabels[key] || key}
                values={filterDraft[key] || []}
                onChange={(values) => updateDraft(key, values)}
                otherFilters={filterDraft}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60"
            >
              <Search size={18} />
              {loading ? 'Searching...' : 'Search'}
            </button>
            {hasFilters(filterDraft) && (
              <button
                type="button"
                onClick={clearAll}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                Clear all
              </button>
            )}
          </div>
        </form>
      )}

      {step !== 'search' && activeFilterChips.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm text-gray-600 dark:text-gray-400">Active filters:</span>
          {activeFilterChips.map(({ key, value }) => (
            <span
              key={`${key}-${value}`}
              className="px-2 py-1 text-sm rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200"
            >
              {fieldLabels[key]}: {value}
            </span>
          ))}
        </div>
      )}

      {step === 'summary' && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleBackToSearch}
              className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-sm"
            >
              <ChevronLeft size={16} />
              Back to search
            </button>
          </div>

          {loading ? (
            <p className="text-gray-600 dark:text-gray-400">Loading summary...</p>
          ) : summaryGroups.length === 0 ? (
            <p className="text-gray-600 dark:text-gray-400">No results match your search.</p>
          ) : (
            <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-gray-100 dark:bg-gray-800">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold">Cytokine</th>
                    <th className="px-4 py-3 text-left font-semibold">Cell Type</th>
                    <th className="px-4 py-3 text-right font-semibold">Paper Count</th>
                    <th className="px-4 py-3 text-right font-semibold">Interactions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {summaryGroups.map((group) => (
                    <tr
                      key={`${group.cytokine_id}-${group.cell_type_id}`}
                      onClick={() => handleSelectPair(group)}
                      className="cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-900/20"
                    >
                      <td className="px-4 py-3">{group.cytokine_name}</td>
                      <td className="px-4 py-3">{group.cell_type}</td>
                      <td className="px-4 py-3 text-right">{group.paper_count}</td>
                      <td className="px-4 py-3 text-right">{group.interaction_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {step === 'detail' && selectedPair && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3 items-center">
            <button
              type="button"
              onClick={handleBackToSummary}
              className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-sm"
            >
              <ChevronLeft size={16} />
              Back to summary
            </button>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {selectedPair.cytokine_name} · {selectedPair.cell_type}
            </p>
          </div>

          {loading ? (
            <p className="text-gray-600 dark:text-gray-400">Loading interactions...</p>
          ) : (
            <>
              <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-lg">
                <table className="w-full text-sm">
                  <thead className="bg-gray-100 dark:bg-gray-800">
                    <tr>
                      {(columns.length ? columns : Object.keys(detailRows[0] || {})).map((col) => (
                        <th
                          key={col}
                          className="px-3 py-2 text-left font-semibold whitespace-nowrap"
                        >
                          {formatColumnName(col)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {detailRows.map((row) => (
                      <tr key={row.interaction_id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        {(columns.length ? columns : Object.keys(row)).map((col) => (
                          <td key={col} className="px-3 py-2 align-top max-w-xs break-words">
                            {col === 'url' && row[col] ? (
                              <a
                                href={row[col]}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:underline"
                              >
                                Link
                              </a>
                            ) : (
                              truncateText(row[col], 200)
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {pagination.total_pages > 1 && (
                <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
                  <span className="text-gray-600 dark:text-gray-400">
                    Showing {((pagination.page - 1) * pagination.limit) + 1}–
                    {Math.min(pagination.page * pagination.limit, pagination.total)} of {pagination.total}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={pagination.page <= 1 || loading}
                      onClick={() => fetchDetail(appliedFilters, selectedPair, pagination.page - 1)}
                      className="inline-flex items-center gap-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50"
                    >
                      <ChevronLeft size={16} />
                      Previous
                    </button>
                    <span>
                      Page {pagination.page} of {pagination.total_pages}
                    </span>
                    <button
                      type="button"
                      disabled={pagination.page >= pagination.total_pages || loading}
                      onClick={() => fetchDetail(appliedFilters, selectedPair, pagination.page + 1)}
                      className="inline-flex items-center gap-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50"
                    >
                      Next
                      <ChevronRight size={16} />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default Database;
