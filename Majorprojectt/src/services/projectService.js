import { apiClient } from '../api/client';
import { notifyCacheUpdate } from './cacheStore';

// Single source of truth: FastAPI /api/projects + /api/github + /api/gmail.
// Readiness, health and timeline are derived here from fetched records only.

const MONTHS = ['January','February','March','April','May','June','July',
  'August','September','October','November','December'];

let cache = {
  projects: [],
  repos: [],
  issues: [],
  prs: [],
  threads: [],
  emails: [],
  loaded: false
};

function toLongDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

function toShortDate(iso) {
  if (!iso) return '';
  const [, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!m || !d) return iso;
  return `${MONTHS[m - 1].slice(0, 3)} ${d}`;
}

export const syncProjectsDataFromBackend = async () => {
  const [projects, repos, issues, prs, threads, emails] = await Promise.all([
    apiClient.get('/projects'),
    apiClient.get('/github/repositories'),
    apiClient.get('/github/issues'),
    apiClient.get('/github/pull-requests'),
    apiClient.get('/gmail/threads'),
    apiClient.get('/gmail/emails')
  ]);
  if (projects) cache.projects = projects;
  if (repos) cache.repos = repos;
  if (issues) cache.issues = issues;
  if (prs) cache.prs = prs;
  if (threads) cache.threads = threads;
  if (emails) cache.emails = emails;
  cache.loaded = Boolean(projects);
  notifyCacheUpdate();
};

syncProjectsDataFromBackend();

function matchProject(id) {
  return cache.projects.find(p => p.id === id || p.name === id) || null;
}

function projectPRs(proj) {
  if (!proj) return [];
  return cache.prs.filter(
    p => p.project_id === proj.id || (proj.repositories || []).includes(p.repository)
  );
}

function projectThreads(proj) {
  if (!proj) return [];
  return cache.threads.filter(t => t.project_id === proj.id);
}

function projectIssues(proj) {
  if (!proj) return [];
  return cache.issues.filter(
    i => i.project_id === proj.id || (proj.repositories || []).includes(i.repository)
  );
}

function projectEmails(proj) {
  if (!proj) return [];
  return cache.emails.filter(e => e.project_id === proj.id);
}

export const projectService = {
  fetchProjects: () => apiClient.get('/projects'),
  fetchProjectDetail: (id) => apiClient.get(`/projects/${id}`),

  isLoaded: () => cache.loaded,
  sync: syncProjectsDataFromBackend,

  getProjects: () => cache.projects,

  getProjectById: (id = 'proj-platform-api') =>
    matchProject(id) || cache.projects[0] || null,

  getProjectHealth: (id = 'proj-platform-api') => {
    const proj = matchProject(id) || cache.projects[0];
    if (!proj) return { score: null, overall: null, status: '…' };
    return {
      score: typeof proj.health_score === 'number' ? proj.health_score : null,
      overall: null,
      status: proj.status || 'N/A — not measured'
    };
  },

  getReleaseReadiness: (id = 'proj-platform-api') => {
    const proj = matchProject(id) || cache.projects[0];
    if (!proj) {
      return { version: '…', targetDate: '', pipeline: [], blockerNotice: '' };
    }
    const prs = projectPRs(proj);
    const threads = projectThreads(proj);
    const secPr = prs.find(p => p.status === 'awaiting_security_review');
    const blockerThread = threads.find(t => t.is_release_blocker);
    const readyCount = prs.filter(p => p.status === 'approved').length;

    let ci = 'Running';
    let ciColor = 'blue';
    if (prs.length > 0 && prs.every(p => p.ci_status === 'passed')) {
      ci = 'Passed';
      ciColor = 'green';
    } else if (prs.some(p => p.ci_status === 'failed')) {
      ci = 'Failed';
      ciColor = 'red';
    }

    const pipeline = [
      {
        name: 'Implementation',
        status: ci === 'Passed' ? 'Complete' : ci === 'Failed' ? 'Failed' : 'In progress',
        color: ci === 'Passed' ? 'gray' : ci === 'Failed' ? 'red' : 'blue'
      },
      { name: 'CI checks', status: ci, color: ciColor },
      {
        name: 'Security review',
        status: secPr ? 'Blocked' : 'Passed',
        color: secPr ? 'red' : 'green'
      },
      {
        name: 'Release scope',
        status: blockerThread ? 'Confirm today' : 'Confirmed',
        color: blockerThread ? 'blue' : 'green'
      }
    ];

    let blockerNotice;
    let blockerTitle;
    if (secPr) {
      blockerTitle = 'Security review is the critical release gate';
      blockerNotice =
        `Security review is the critical release gate. Checks ${secPr.ci_status} ` +
        `on PR #${secPr.number}, but no security reviewer is assigned.`;
    } else if (blockerThread) {
      blockerTitle = 'Release scope confirmation pending';
      blockerNotice =
        `${blockerThread.subject} · ${blockerThread.message_count} messages ` +
        `awaiting confirmation for ${proj.target_release}.`;
    } else {
      blockerTitle = 'No open release blockers';
      blockerNotice =
        `No open release blockers for ${proj.target_release}. ` +
        `${readyCount} pull requests ready to merge.`;
    }

    return {
      version: proj.target_release || 'N/A',
      targetDate: toLongDate(proj.target_date),
      pipeline,
      blockerTitle,
      blockerNotice
    };
  },

  getLinkedRepositories: (id = 'proj-platform-api') => {
    const proj = matchProject(id) || cache.projects[0];
    if (!proj) return [];
    return cache.repos.filter(r => r.project_id === proj.id);
  },

  getProjectIssues: (id = 'proj-platform-api') =>
    projectIssues(matchProject(id) || cache.projects[0]),

  getProjectPRs: (id = 'proj-platform-api') =>
    projectPRs(matchProject(id) || cache.projects[0]),

  getProjectEvidence: (id = 'proj-platform-api') => {
    const proj = matchProject(id) || cache.projects[0];
    const prs = projectPRs(proj);
    const issues = projectIssues(proj);
    const threads = projectThreads(proj);
    const securityPr = prs.find(p => p.status === 'awaiting_security_review') || null;
    const linkedIssue = securityPr && securityPr.linked_issue_number
      ? issues.find(i => i.number === securityPr.linked_issue_number) || null
      : null;
    const blockerThread = threads.find(t => t.is_release_blocker) || null;
    return { securityPr, linkedIssue, blockerThread };
  },

  getLatestDecision: (id = 'proj-platform-api') => {
    const proj = matchProject(id) || cache.projects[0];
    const decisions = projectEmails(proj)
      .filter(e => e.category === 'Decision')
      .sort((a, b) => (b.received_at || '').localeCompare(a.received_at || ''));
    return decisions[0] || null;
  },

  getReleaseTimeline: (id = 'proj-platform-api') => {
    const proj = matchProject(id) || cache.projects[0];
    if (!proj) return [];
    const threads = projectThreads(proj);
    const emails = projectEmails(proj);
    const prs = projectPRs(proj);
    const blocked =
      threads.some(t => t.is_release_blocker) ||
      prs.some(p => p.status === 'awaiting_security_review');

    const entries = [];

    const decisions = emails.filter(e => e.category === 'Decision');
    const byDate = {};
    for (const e of decisions) {
      const key = (e.received_at || '').slice(0, 10);
      if (!key) continue;
      (byDate[key] = byDate[key] || []).push(e);
    }
    for (const [iso, group] of Object.entries(byDate).slice(-2)) {
      const threadIds = [...new Set(group.map(e => e.thread_id))];
      entries.push({
        iso,
        date: toShortDate(iso),
        title: `${group.length} scope decision${group.length > 1 ? 's' : ''} recorded`,
        subtitle: `Gmail · ${threadIds.join(', ')}`,
        icon: 'check'
      });
    }

    const blockerThread = threads.find(t => t.is_release_blocker);
    if (blockerThread) {
      entries.push({
        iso: (blockerThread.last_message_at || '').slice(0, 10),
        date: toShortDate(blockerThread.last_message_at),
        title: 'Release readiness thread',
        subtitle: `${blockerThread.message_count} messages · release blocker`,
        icon: blocked ? 'clock-orange' : 'check'
      });
    }

    if (proj.target_date) {
      entries.push({
        iso: proj.target_date.slice(0, 10),
        date: toShortDate(proj.target_date),
        title: `${proj.target_release} target release`,
        subtitle: blocked ? 'Pending approval' : 'On track',
        icon: blocked ? 'clock-orange' : 'clock-gray'
      });
    }

    return entries
      .filter(e => e.date)
      .sort((a, b) => a.iso.localeCompare(b.iso))
      .map(({ iso, ...rest }) => rest);
  }
};
