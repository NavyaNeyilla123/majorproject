import { apiClient } from '../api/client';
import { notifyCacheUpdate } from './cacheStore';

// Single source of truth: FastAPI /api/github/* — no dataset JSON in the frontend.
const NA = 'N/A — not measured';

let cache = {
  stats: null,
  repos: [],
  issues: [],
  prs: [],
  commits: [],
  reviews: [],
  mcp: null,
  loaded: false
};

function timeOnly(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  let h = d.getUTCHours() % 12;
  if (h === 0) h = 12;
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return `${h}:${mm} ${d.getUTCHours() < 12 ? 'AM' : 'PM'}`;
}

export const syncGitHubDataFromBackend = async () => {
  const [overview, commits, reviews, mcp] = await Promise.all([
    apiClient.get('/github/overview'),
    apiClient.get('/github/commits'),
    apiClient.get('/github/reviews'),
    apiClient.get('/mcp/status')
  ]);
  if (overview) {
    cache.stats = overview.stats;
    cache.repos = overview.repositories || [];
    cache.issues = overview.issues || [];
    cache.prs = overview.pull_requests || [];
    cache.loaded = true;
  }
  if (commits) cache.commits = commits;
  if (reviews) cache.reviews = reviews;
  if (mcp) cache.mcp = mcp;
  notifyCacheUpdate();
};

syncGitHubDataFromBackend();

export const githubService = {
  fetchRepositories: () => apiClient.get('/github/repositories'),
  fetchIssues: () => apiClient.get('/github/issues'),
  fetchPullRequests: () => apiClient.get('/github/pull-requests'),

  isLoaded: () => cache.loaded,
  sync: syncGitHubDataFromBackend,

  getRepositories: () => cache.repos,

  getOpenIssues: () => cache.issues.filter(i => i.status === 'open'),

  getIssues: () => cache.issues,

  getOpenIssuesCount: () => cache.issues.filter(i => i.status === 'open').length,

  getIssueTrend: () => {
    const currentOpen = cache.issues.filter(i => i.status === 'open').length;
    return {
      previous: null,
      current: currentOpen,
      decreasePercent: 'N/A'
    };
  },

  getPullRequests: () => cache.prs,

  getActivePRsCount: () => cache.prs.length,

  getPRPipelineBreakdown: () => {
    const awaitingReview = cache.prs.filter(p => p.pipeline_stage === 'awaiting_review').length;
    const readyToMerge = cache.prs.filter(p => p.pipeline_stage === 'ready_to_merge').length;
    const draftChecks = cache.prs.filter(p => p.pipeline_stage === 'draft_checks').length;
    return {
      total: cache.prs.length,
      awaitingReview,
      readyToMerge,
      draftChecks
    };
  },

  getMedianReviewTime: () => ({
    time: cache.stats ? cache.stats.median_review_time : NA,
    change: ''
  }),

  getRepositoryOverview: () => cache.repos,

  getReviewQueue: () => {
    const priority = {
      awaiting_security_review: 0,
      review_pending: 1,
      awaiting_review: 2
    };
    return [...cache.prs]
      .sort((a, b) => {
        const pa = priority[a.status] ?? 9;
        const pb = priority[b.status] ?? 9;
        if (pa !== pb) return pa - pb;
        return (b.review_wait_hours || 0) - (a.review_wait_hours || 0);
      })
      .slice(0, 3)
      .map(pr => ({
        number: pr.number,
        title: pr.title,
        repository: pr.repository,
        owner: pr.author,
        status: pr.status === 'awaiting_security_review' ? `Security review · ${pr.age_hours}h` :
                pr.status === 'review_pending' ? `Review pending · ${pr.age_hours}h` :
                'Ready to merge',
        statusType: pr.status === 'awaiting_security_review' ? 'red' :
                    pr.status === 'review_pending' ? 'purple' : 'green',
        nextStep: pr.next_step
      }));
  },

  getCommits: () => cache.commits,
  getReviews: () => cache.reviews,

  getConnectionStatus: () => {
    const orgs = [...new Set(cache.repos.map(r => r.org).filter(Boolean))];
    const synced = cache.repos.map(r => r.synced_at || '').sort().pop() || '';
    const gh = cache.mcp ? cache.mcp.github : null;
    return {
      badge: gh ? (gh.healthy ? 'Connected' : gh.status) : '…',
      org: orgs.join(', '),
      synced: timeOnly(synced),
      mode: cache.mcp ? cache.mcp.mode : ''
    };
  }
};
