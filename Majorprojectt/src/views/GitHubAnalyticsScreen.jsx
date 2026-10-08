import React, { useEffect } from 'react';
import {
  Sparkles,
  ExternalLink,
  AlertTriangle,
  ArrowRight
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { githubService } from '../services/githubService';
import { gmailService } from '../services/gmailService';
import { projectService } from '../services/projectService';
import useCacheTick from '../hooks/useCacheTick';

function shortDate(iso) {
  if (!iso) return '';
  const [, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!m || !d) return iso;
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[m - 1]} ${d}`;
}

export default function GitHubAnalyticsScreen({ navigateTo }) {
  useCacheTick();
  useEffect(() => {
    githubService.sync();
    gmailService.sync();
    projectService.sync();
  }, []);

  const repos = githubService.getRepositories();
  const openIssues = githubService.getOpenIssues();
  const openIssuesCount = openIssues.length;
  const issueTrend = githubService.getIssueTrend();
  const activePRsCount = githubService.getActivePRsCount();
  const prPipeline = githubService.getPRPipelineBreakdown();
  const medianReviewTime = githubService.getMedianReviewTime();
  const reviewQueue = githubService.getReviewQueue();
  const prs = githubService.getPullRequests();
  const allIssues = githubService.getIssues();
  const connection = githubService.getConnectionStatus();

  const secPr = prs.find(p => p.status === 'awaiting_security_review');
  const linkedIssue = secPr && secPr.linked_issue_number
    ? allIssues.find(i => i.number === secPr.linked_issue_number)
    : null;
  const threads = gmailService.getThreads();
  const blockerThread = threads.find(t => t.is_release_blocker);
  const releaseProject = secPr ? projectService.getProjectById(secPr.project_id) : null;

  const issueDates = openIssues
    .map(i => (i.updated_at || i.created_at || '').slice(0, 10))
    .filter(Boolean)
    .sort();
  const periodLabel = issueDates.length
    ? `${shortDate(issueDates[0])} – ${shortDate(issueDates[issueDates.length - 1])}`
    : 'current snapshot';

  const readyPRs = prs.filter(p => p.pipeline_stage === 'ready_to_merge');
  const readyByProject = {};
  for (const p of readyPRs) {
    const name = p.project_name || p.repository;
    readyByProject[name] = (readyByProject[name] || 0) + 1;
  }
  const readyEntries = Object.entries(readyByProject);
  let pipelineNote = '';
  if (readyPRs.length === 1) {
    pipelineNote = `1 pull request is ready to merge (${readyEntries[0][0]}).`;
  } else if (readyEntries.length === 1) {
    pipelineNote = `${readyEntries[0][0]} contributes all ${readyPRs.length} ready-to-merge PRs.`;
  } else if (readyPRs.length > 0) {
    pipelineNote = `${readyPRs.length} ready-to-merge PRs across ${readyEntries.length} projects.`;
  }
  if (secPr) {
    pipelineNote += ` PR #${secPr.number} is awaiting a security reviewer.`;
  }

  if (!githubService.isLoaded()) {
    return (
      <div>
        <PageHeader
          breadcrumb={['Workspace', 'GitHub Analytics']}
          title="GitHub Analytics"
          subtitle="Repository activity, review bottlenecks, and release signals."
        />
        <div className="card" style={{ padding: '24px', color: '#64748B', fontSize: '0.875rem' }}>
          Loading live GitHub data from the KnowledgeOps API…
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        breadcrumb={['Workspace', 'GitHub Analytics']}
        title="GitHub Analytics"
        subtitle={`Repository activity, review bottlenecks, and release signals across ${connection.org || 'the workspace'}.`}
        actions={
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary">
              <ExternalLink size={15} />
              <span>Open GitHub</span>
            </button>
            <button
              onClick={() => navigateTo('ask')}
              className="btn btn-primary"
            >
              <Sparkles size={15} />
              <span>Ask KnowledgeOps</span>
            </button>
          </div>
        }
      />

      {/* Subheader Status & Dropdowns */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem' }}>
          <span className={`badge ${connection.badge === 'Connected' ? 'badge-green' : 'badge-gray'}`}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: connection.badge === 'Connected' ? '#10B981' : '#94A3B8', display: 'inline-block' }}></span>
            {connection.badge}
          </span>
          <span style={{ color: '#64748B' }}>
            {connection.org} · Synced at {connection.synced}
            {connection.mode ? ` · ${connection.mode}` : ''}
          </span>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <select className="select" style={{ width: 'auto', fontSize: '0.775rem', padding: '4px 10px' }}>
            <option>All projects</option>
            <option>Platform API</option>
            <option>Customer Portal</option>
          </select>
          <select className="select" style={{ width: 'auto', fontSize: '0.775rem', padding: '4px 10px' }}>
            <option>Last 7 days</option>
            <option>Last 30 days</option>
          </select>
        </div>
      </div>

      {/* 4 Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '20px' }}>
        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.75rem', marginBottom: '4px' }}>GitHub Repositories</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A' }}>{repos.length}</div>
          <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '2px' }}>All repositories synced</div>
        </div>

        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.75rem', marginBottom: '4px' }}>Open Issues</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A' }}>{openIssuesCount}</div>
          <div style={{ fontSize: '0.7rem', color: issueTrend.decreasePercent === 'N/A' ? '#94A3B8' : '#059669', fontWeight: 600, marginTop: '2px' }}>
            {issueTrend.decreasePercent === 'N/A' ? 'Trend N/A — no prior-week data' : `↓ ${issueTrend.decreasePercent}% from last week`}
          </div>
        </div>

        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.75rem', marginBottom: '4px' }}>Active Pull Requests</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A' }}>{activePRsCount}</div>
          <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '2px' }}>{prPipeline.awaitingReview} awaiting review</div>
        </div>

        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.75rem', marginBottom: '4px' }}>Median review time</div>
          <div style={{ fontSize: medianReviewTime.time && medianReviewTime.time.startsWith('N/A') ? '0.95rem' : '1.6rem', fontWeight: 800, color: medianReviewTime.time && medianReviewTime.time.startsWith('N/A') ? '#94A3B8' : '#0F172A' }}>{medianReviewTime.time}</div>
          {medianReviewTime.change && (
            <div style={{ fontSize: '0.7rem', color: '#059669', fontWeight: 600, marginTop: '2px' }}>{medianReviewTime.change}</div>
          )}
        </div>
      </div>

      {/* Middle Row: Issue Trend & PR Pipeline */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
        {/* Issue Trend Chart */}
        <div className="card">
          <div style={{ marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Issue trend</h3>
            <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Open issues · {periodLabel}</div>
          </div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0F172A', marginBottom: '12px' }}>
            {issueTrend.previous !== null ? (
              <>
                {issueTrend.previous} → {issueTrend.current} open issues ·{' '}
                <span style={{ color: '#059669' }}>{issueTrend.decreasePercent}% decrease</span>
              </>
            ) : (
              <>
                {issueTrend.current} open issues ·{' '}
                <span style={{ color: '#94A3B8', fontWeight: 600 }}>prior-week trend N/A</span>
              </>
            )}
          </div>

          {issueTrend.previous !== null ? (
            <>
              <div style={{ height: '100px', width: '100%', position: 'relative' }}>
                <svg width="100%" height="100%" viewBox="0 0 300 80" preserveAspectRatio="none">
                  <path
                    d="M0,20 Q75,10 150,45 T300,60"
                    fill="none"
                    stroke="#2563EB"
                    strokeWidth="3"
                  />
                  <path
                    d="M0,20 Q75,10 150,45 T300,60 L300,80 L0,80 Z"
                    fill="url(#blueGrad)"
                    opacity="0.1"
                  />
                  <defs>
                    <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2563EB" />
                      <stop offset="100%" stopColor="#FFFFFF" />
                    </linearGradient>
                  </defs>
                </svg>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#94A3B8', marginTop: '6px' }}>
                <span>Oct 1</span>
                <span>Oct 4</span>
                <span>Oct 7</span>
              </div>
            </>
          ) : (
            <div style={{
              height: '100px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#F8FAFC',
              border: '1px dashed #E2E8F0',
              borderRadius: '8px',
              fontSize: '0.775rem',
              color: '#94A3B8',
              textAlign: 'center',
              padding: '0 12px'
            }}>
              Trend history not measured — no prior-week issue data in the workspace dataset.
            </div>
          )}
        </div>

        {/* PR Pipeline Bar */}
        <div className="card">
          <div style={{ marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Pull request pipeline</h3>
            <div style={{ fontSize: '0.75rem', color: '#64748B' }}>{prPipeline.total} active pull requests · All repositories</div>
          </div>

          <div style={{ display: 'flex', height: '14px', borderRadius: '6px', overflow: 'hidden', marginBottom: '20px', marginTop: '10px' }}>
            <div style={{ width: `${(prPipeline.awaitingReview / (prPipeline.total || 1)) * 100}%`, background: '#7C3AED' }}></div>
            <div style={{ width: `${(prPipeline.readyToMerge / (prPipeline.total || 1)) * 100}%`, background: '#2563EB' }}></div>
            <div style={{ width: `${(prPipeline.draftChecks / (prPipeline.total || 1)) * 100}%`, background: '#94A3B8' }}></div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem', color: '#334155' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#7C3AED' }}></span>
                <span>Awaiting review</span>
              </div>
              <strong>{prPipeline.awaitingReview}</strong>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#2563EB' }}></span>
                <span>Ready to merge</span>
              </div>
              <strong>{prPipeline.readyToMerge}</strong>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#94A3B8' }}></span>
                <span>Draft / checks running</span>
              </div>
              <strong>{prPipeline.draftChecks}</strong>
            </div>
          </div>

          <div style={{ marginTop: '16px', fontSize: '0.725rem', color: '#64748B' }}>
            {pipelineNote || 'No ready-to-merge pull requests in the workspace.'}
          </div>
        </div>
      </div>

      {/* Release Blocker Alert Box */}
      {secPr && (
        <div className="alert-box alert-amber" style={{ marginBottom: '20px' }}>
          <AlertTriangle size={18} color="#D97706" style={{ flexShrink: 0 }} />
          <div>
            <strong style={{ display: 'block', marginBottom: '2px', color: '#78350F' }}>Release blocker needs an owner</strong>
            <span style={{ fontSize: '0.8rem', color: '#92400E' }}>
              {secPr.project_name} · PR #{secPr.number}{' '}
              {secPr.ci_status === 'passed' ? 'has passed checks' : `has CI status ${secPr.ci_status}`}{' '}
              but is waiting for security review.
              {linkedIssue && ` Issue #${linkedIssue.number}`}
              {blockerThread && ` and the ${blockerThread.subject} thread`}
              {releaseProject && releaseProject.target_release
                ? ` confirm this is a ${releaseProject.target_release} release gate.`
                : ' confirm this is a release gate.'}
            </span>
          </div>
        </div>
      )}

      {/* Table 1: Repository Overview */}
      <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: '20px' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Repository overview</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B' }}>
              Showing {Math.min(6, repos.length)} of {repos.length} repositories · workspace totals include all {repos.length}
            </div>
          </div>
          <span style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}>Manage repository scope →</span>
        </div>

        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Repository / group</th>
                <th>Project</th>
                <th>Open issues</th>
                <th>Active PRs</th>
                <th>Health</th>
              </tr>
            </thead>
            <tbody>
              {repos.slice(0, 6).map((repo) => (
                <tr key={repo.id}>
                  <td><strong>{repo.name}</strong></td>
                  <td>{repo.project_name}</td>
                  <td>{repo.open_issues_count}</td>
                  <td>{repo.active_prs_count}</td>
                  <td>
                    <span className={`badge badge-${
                      repo.health_status === 'At risk' ? 'amber' :
                      repo.health_status === 'Ready for QA sign-off' ? 'green' :
                      repo.health_status === 'Review needed' ? 'purple' : 'gray'
                    }`}>
                      {repo.health_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Table 2: Review Queue and Blockers */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Review queue and blockers</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B' }}>Prioritized by delivery impact, not just age</div>
          </div>
          <span style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}>View all {prPipeline.total} PRs →</span>
        </div>

        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Pull request</th>
                <th>Repository</th>
                <th>Owner</th>
                <th>Status</th>
                <th>Next step</th>
              </tr>
            </thead>
            <tbody>
              {reviewQueue.map((item, idx) => (
                <tr key={idx}>
                  <td><strong>#{item.number} · {item.title}</strong></td>
                  <td>{item.repository}</td>
                  <td>{item.owner}</td>
                  <td><span className={`badge badge-${item.statusType}`}>{item.status}</span></td>
                  <td><a href="#action" style={{ color: '#2563EB', fontWeight: 600, textDecoration: 'none' }}>{item.nextStep}</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ padding: '12px 20px', background: '#F8FAFC', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.725rem' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            {secPr && (
              <span className="badge badge-purple">
                GitHub{linkedIssue ? ` · Issue #${linkedIssue.number}` : ''} · PR #{secPr.number}
              </span>
            )}
            {blockerThread && (
              <span className="badge badge-blue">
                Gmail · {blockerThread.subject} · {shortDate(blockerThread.last_message_at)}
              </span>
            )}
            {!secPr && !blockerThread && (
              <span className="badge badge-gray">No release blockers recorded</span>
            )}
          </div>
          <span style={{ color: '#64748B' }}>Read-only analysis · No repository changes</span>
        </div>
      </div>
    </div>
  );
}
