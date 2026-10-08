import { apiClient } from '../api/client';
import { notifyCacheUpdate } from './cacheStore';

// Single source of truth: FastAPI /api/gmail/overview — stats and extracted
// decision/risk/action records are derived server-side from the dataset.
let cache = {
  stats: null,
  threads: [],
  emails: [],
  extracted: { decisions: [], risks: [], actions: [] },
  loaded: false
};

export const syncGmailDataFromBackend = async () => {
  const overview = await apiClient.get('/gmail/overview');
  if (overview) {
    cache.stats = overview.stats;
    cache.threads = overview.threads || [];
    cache.emails = overview.emails || [];
    cache.extracted = {
      decisions: overview.extracted_decisions || [],
      risks: overview.extracted_risks || [],
      actions: overview.extracted_actions || []
    };
    cache.loaded = true;
    notifyCacheUpdate();
  }
};

syncGmailDataFromBackend();

const TYPE_COLORS = { Decision: 'purple', Risk: 'amber', Action: 'blue' };

export const gmailService = {
  fetchThreads: () => apiClient.get('/gmail/threads'),
  fetchEmails: () => apiClient.get('/gmail/emails'),

  isLoaded: () => cache.loaded,
  sync: syncGmailDataFromBackend,

  getRelevantEmailCount: (projectId = null) => {
    const list = projectId
      ? cache.emails.filter((e) => e.project_id === projectId)
      : cache.emails;
    return list.length;
  },

  getReceivedThisWeekCount: () =>
    cache.stats ? cache.stats.emails_received_this_week : 0,

  getThreads: () => cache.threads,

  getPriorityThreads: () =>
    [...cache.threads]
      .sort((a, b) => {
        if (a.is_release_blocker !== b.is_release_blocker) {
          return a.is_release_blocker ? -1 : 1;
        }
        return (b.last_message_at || '').localeCompare(a.last_message_at || '');
      })
      .slice(0, 5),

  getThreadById: (threadId) => {
    const thread =
      cache.threads.find(t => t.id === threadId) || cache.threads[0];
    if (!thread) return null;
    const messages = cache.emails.filter(e => e.thread_id === thread.id);
    return { ...thread, messages };
  },

  getExtractedIntelligence: (threadId) => {
    const items = [];
    for (const d of cache.extracted.decisions) {
      if (d.source_thread !== threadId) continue;
      items.push({
        type: 'Decision',
        typeColor: TYPE_COLORS.Decision,
        title: d.decision,
        description: `Recorded by ${d.owner} · ${d.date}.`,
        source: `Gmail · ${d.source_thread}`
      });
    }
    for (const r of cache.extracted.risks) {
      if (r.source_thread !== threadId) continue;
      items.push({
        type: 'Risk',
        typeColor: TYPE_COLORS.Risk,
        title: r.risk,
        description: `${r.impact}. Severity: ${r.severity}.`,
        source: `Gmail · ${r.source_thread}`
      });
    }
    for (const a of cache.extracted.actions) {
      if (a.source_thread !== threadId) continue;
      items.push({
        type: 'Action',
        typeColor: TYPE_COLORS.Action,
        title: a.action,
        suggestedOwners: a.owner,
        due: a.due,
        status: 'Draft recommendation · Not sent'
      });
    }
    return items;
  },

  getExtractedCounts: () => ({
    decisions: cache.extracted.decisions.length,
    risks: cache.extracted.risks.length,
    actions: cache.extracted.actions.length
  }),

  getStats: () => {
    if (cache.stats) return cache.stats;
    return {
      relevant_email_count: 0,
      emails_received_this_week: 0,
      project_risks_count: 0,
      priority_threads_count: 0
    };
  },

  getExtractedSummary: () => ({
    risks: cache.extracted.risks.length,
    risksHigh: cache.extracted.risks.filter(r => r.severity === 'High').length,
    actions: cache.extracted.actions.length,
    actionsToday: cache.extracted.actions.filter(a => a.due === 'Today').length,
    decisions: cache.extracted.decisions.length
  }),

  getLatestReceived: () => {
    const received = cache.emails.map(e => e.received_at || '').filter(Boolean).sort();
    return received.length ? received[received.length - 1] : '';
  },

  getSyncedLabel: () => {
    const received = cache.emails.map(e => e.received_at || '').filter(Boolean).sort();
    const iso = received.length ? received[received.length - 1] : '';
    if (!iso) return '…';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    let h = d.getUTCHours() % 12;
    if (h === 0) h = 12;
    const mm = String(d.getUTCMinutes()).padStart(2, '0');
    return `${h}:${mm} ${d.getUTCHours() < 12 ? 'AM' : 'PM'}`;
  }
};
