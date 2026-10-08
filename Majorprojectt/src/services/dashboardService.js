import { apiClient } from '../api/client';
import { notifyCacheUpdate } from './cacheStore';

// Single source of truth: FastAPI /api/dashboard derives every count, risk,
// action and activity entry from repositories; MCP/RAG cards read live status.
// No dataset JSON is read in the frontend.

const NA = 'N/A — not measured';

let cache = {
  loaded: false,
  overview: null,
  mcp: null,
  rag: null
};

function placeholderMetrics() {
  return {
    githubRepos: '…',
    openIssues: '…',
    issuesTrend: NA,
    activePRs: '…',
    prsAwaitingReview: '…',
    relevantEmails: '…',
    emailsReceivedThisWeek: '…',
    projectRisks: '…',
    risksNeedAttention: '…',
    pendingActions: '…',
    actionsDueToday: '…'
  };
}

export const dashboardService = {
  sync: async () => {
    const [overview, mcp, rag] = await Promise.all([
      apiClient.get('/dashboard'),
      apiClient.get('/mcp/status'),
      apiClient.get('/rag/status')
    ]);
    if (overview) {
      cache.overview = overview;
      cache.loaded = true;
    }
    if (mcp) cache.mcp = mcp;
    if (rag) cache.rag = rag;
    notifyCacheUpdate();
    return cache.overview;
  },

  isLoaded: () => cache.loaded,

  getOverview: () => cache.overview,

  getSummaryMetrics: () => {
    const o = cache.overview;
    if (!o) return placeholderMetrics();
    const m = o.metrics;
    return {
      githubRepos: m.repositories_count,
      openIssues: m.open_issues_count,
      issuesTrend: NA,
      activePRs: m.active_prs_count,
      prsAwaitingReview: m.prs_awaiting_review_count,
      relevantEmails: m.relevant_emails_count,
      emailsReceivedThisWeek: m.emails_received_this_week,
      projectRisks: m.project_risks_count,
      risksNeedAttention: m.risks_need_attention,
      pendingActions: m.pending_actions_count,
      actionsDueToday: m.actions_due_today
    };
  },

  getProjectHealthOverview: () => {
    const o = cache.overview;
    if (!o) {
      return {
        score: null,
        maxScore: 100,
        badge: '…',
        openIssues: '…',
        previousOpenIssues: null,
        issueDecreasePercent: 'N/A',
        activePRsTotal: '…',
        awaitingReview: '…',
        readyToMerge: '…',
        draftChecks: '…',
        medianReviewTime: NA
      };
    }
    const m = o.metrics;
    return {
      score: m.overall_health_score,
      maxScore: 100,
      badge: m.overall_health,
      openIssues: m.open_issues_count,
      previousOpenIssues: null,
      issueDecreasePercent: 'N/A',
      activePRsTotal: m.active_prs_count,
      awaitingReview: m.prs_awaiting_review_count,
      readyToMerge: m.prs_ready_to_merge_count,
      draftChecks: m.prs_draft_checks_count,
      medianReviewTime: NA
    };
  },

  getEvidenceBackedInsights: () => {
    const o = cache.overview;
    if (!o) return [];
    return o.top_risks.slice(0, 2).map((r, idx) => {
      const high = r.severity === 'High';
      return {
        id: r.id,
        priority: high ? 'High priority' : 'Medium priority',
        priorityColor: 'amber',
        project: r.project,
        confidence: 'Evidence-backed',
        title: r.title,
        description: `${r.impact}. Source: ${r.evidence_citation}.`,
        sources: r.evidence_citation.split(' · '),
        targetRoute: idx === 0 ? 'answer' : 'evidence'
      };
    });
  },

  getPendingActions: () => {
    const o = cache.overview;
    if (!o) return [];
    return o.pending_actions.map((a, idx) => {
      const initials = (a.owner || '')
        .split(/\s+/)
        .filter(Boolean)
        .map((w) => w[0])
        .join('')
        .toUpperCase();
      return {
        id: a.id || idx + 1,
        title: a.title,
        subtitle: a.subtitle,
        ownerBadge: `${initials} ${a.project}`.trim(),
        dueBadge: a.due,
        isDueToday: a.due === 'Today',
        completed: a.status === 'Completed'
      };
    });
  },

  getRecentActivity: () => {
    const o = cache.overview;
    if (!o) return [];
    return o.recent_activity;
  },

  getConnectionCards: () => {
    const o = cache.overview;
    const mcp = cache.mcp;
    const rag = cache.rag;
    const activity = o ? o.recent_activity : [];
    const githubActivity = activity.find((a) => a.type === 'github');
    const gmailActivity = activity.find((a) => a.type === 'gmail');
    const org = o ? o.metrics.github_org : '';
    const repoLine = o
      ? `${o.metrics.repositories_count} repositories${org ? ` · ${org}` : ''}`
      : '…';
    const emailLine = o ? `${o.metrics.relevant_emails_count} relevant emails` : '…';
    const healthyBadge = (server) =>
      server && server.healthy ? 'Connected' : server ? server.status : '…';
    return {
      github: {
        subtitle: repoLine,
        badge: mcp ? healthyBadge(mcp.github) : '…',
        synced: githubActivity ? `Last synced ${githubActivity.timestamp}` : 'Last synced …',
        mode: mcp ? mcp.mode : '',
        health: mcp && mcp.github && mcp.github.healthy ? 'Healthy' : mcp ? mcp.github.status : '…'
      },
      gmail: {
        subtitle: `${emailLine} · project inbox`,
        badge: mcp ? healthyBadge(mcp.gmail) : '…',
        synced: gmailActivity ? `Last synced ${gmailActivity.timestamp}` : 'Last synced …',
        mode: mcp ? mcp.mode : '',
        health: mcp && mcp.gmail && mcp.gmail.healthy ? 'Healthy' : mcp ? mcp.gmail.status : '…'
      },
      rag: rag
        ? {
            title:
              rag.status === 'healthy'
                ? 'RAG index ready for retrieval'
                : `RAG index ${rag.status}`,
            subtitle:
              rag.status === 'healthy'
                ? `${rag.documents} docs · ${rag.chunks} chunks · ${rag.collection}`
                : rag.message || 'Index unavailable',
            ready: rag.status === 'healthy'
          }
        : { title: 'RAG status …', subtitle: '', ready: false }
    };
  }
};
