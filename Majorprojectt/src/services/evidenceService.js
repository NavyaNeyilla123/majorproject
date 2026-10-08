import { apiClient } from '../api/client';
import { notifyCacheUpdate } from './cacheStore';

// Single source of truth: FastAPI /api/evidence derives every record, count,
// excerpt, claim and citation from the repository layer. This service holds
// only API responses - it never reads the JSON dataset directly.

let cache = {
  loaded: false,
  counts: { allRecords: null, email: null, decision: null, risk: null },
  records: [],
  detailsById: {},
  crossSourceLinks: []
};

function mapDetail(item) {
  const d = item.detail || {};
  const linked = d.linked_intel || {};
  const meta = d.metadata || {};
  return {
    title: d.title || '',
    thread: d.thread || '',
    author: d.author || '',
    receivedAt: d.received_display || '',
    project: d.project || '',
    sourceAccess: d.source_access || '',
    excerptLines: d.excerpt_label || '',
    originalExcerpt: d.excerpt || '',
    claimsSupported: d.claims || [],
    contextNote: d.context_note || '',
    linkedIntelligence: {
      title: linked.title || '',
      sources: linked.sources || '',
      context: linked.context || ''
    },
    metadata: {
      citationId: meta.citation_id || '',
      chunk: meta.chunk || '',
      snapshot: meta.snapshot || '',
      index: meta.index || ''
    },
    openLabel: d.open_label || 'Open original ↗',
    sourceIcon:
      item.source_type && item.source_type.startsWith('Gmail') ? 'gmail' : 'github',
    badges: item.badges || []
  };
}

export const syncEvidenceFromBackend = async () => {
  const data = await apiClient.get('/evidence');
  if (!data || !Array.isArray(data.items)) return;
  cache.counts = {
    allRecords: data.total_records,
    email: data.email_records_count,
    decision: data.decision_records_count,
    risk: data.risk_records_count
  };
  cache.records = data.items.map((i) => ({
    id: i.id,
    type: i.kind,
    typeColor: i.kind_color,
    project: i.project_name,
    title: i.title,
    subtitle: i.subtitle,
    source: i.source_line
  }));
  const details = {};
  data.items.forEach((i) => {
    details[i.id] = mapDetail(i);
  });
  cache.detailsById = details;
  cache.crossSourceLinks = data.cross_source_links || [];
  cache.loaded = true;
  notifyCacheUpdate();
};

syncEvidenceFromBackend();

export const evidenceService = {
  fetchEvidence: () => apiClient.get('/evidence'),

  sync: syncEvidenceFromBackend,

  isLoaded: () => cache.loaded,

  getCounts: () => ({ ...cache.counts }),

  getPriorityRecords: () => cache.records.slice(),

  getEvidenceDetail: (recordId) => {
    if (recordId != null && cache.detailsById[recordId]) {
      return cache.detailsById[recordId];
    }
    const first = cache.records[0];
    return first ? cache.detailsById[first.id] : null;
  },

  getCrossSourceLinks: () => cache.crossSourceLinks
};
