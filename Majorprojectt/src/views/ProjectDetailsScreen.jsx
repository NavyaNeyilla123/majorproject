import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Clock
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { projectService } from '../services/projectService';
import { githubService } from '../services/githubService';
import { gmailService } from '../services/gmailService';
import { dashboardService } from '../services/dashboardService';
import useCacheTick from '../hooks/useCacheTick';

const MONTHS = ['January','February','March','April','May','June','July',
  'August','September','October','November','December'];

function longDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

function shortDate(iso) {
  if (!iso) return '';
  const [, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!m || !d) return iso;
  return `${MONTHS[m - 1].slice(0, 3)} ${d}`;
}

function timeOnly(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  let h = d.getUTCHours() % 12;
  if (h === 0) h = 12;
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return `${h}:${mm} ${d.getUTCHours() < 12 ? 'AM' : 'PM'}`;
}

function firstSentence(text) {
  if (!text) return '';
  const parts = text.trim().split(/(?<=[.!?])\s+/);
  return parts[0];
}

const PROJECT_ID = 'proj-platform-api';

export default function ProjectDetailsScreen({ navigateTo }) {
  const [activeTab, setActiveTab] = useState('Overview');
  useCacheTick();
  useEffect(() => {
    projectService.sync();
    githubService.sync();
    gmailService.sync();
    dashboardService.sync();
  }, []);

  const project = projectService.getProjectById(PROJECT_ID);
  const health = projectService.getProjectHealth(PROJECT_ID);
  const readiness = projectService.getReleaseReadiness(PROJECT_ID);
  const linkedRepos = projectService.getLinkedRepositories(PROJECT_ID);
  const timeline = projectService.getReleaseTimeline(PROJECT_ID);
  const projectIssues = projectService.getProjectIssues(PROJECT_ID);
  const projectPRs = projectService.getProjectPRs(PROJECT_ID);
  const evidence = projectService.getProjectEvidence(PROJECT_ID);
  const latestDecision = projectService.getLatestDecision(PROJECT_ID);

  const overview = dashboardService.getOverview();
  const wsRisks = overview ? overview.top_risks : [];
  const wsActions = overview ? overview.pending_actions : [];
  const projName = project ? project.name : '';
  const projectRisks = wsRisks.filter(r => r.project === projName);
  const projectActions = wsActions.filter(a => a.project === projName);

  const openIssueCount = projectIssues.filter(i => i.status === 'open').length;
  const activePrList = projectPRs.filter(p => p.status !== 'merged' && p.status !== 'closed');
  const repoPrCounts = {};
  for (const p of activePrList) {
    repoPrCounts[p.repository] = (repoPrCounts[p.repository] || 0) + 1;
  }
  const topRepo = Object.entries(repoPrCounts).sort((a, b) => b[1] - a[1])[0];

  const allEmails = gmailService.getRelevantEmailCount();
  const projectEmailCount = gmailService.getRelevantEmailCount(PROJECT_ID);
  const lastIndexed = linkedRepos
    .map(r => r.synced_at || '')
    .filter(Boolean)
    .sort()
    .pop() || '';
  const decisionThread = latestDecision
    ? gmailService.getThreads().find(t => t.id === latestDecision.thread_id)
    : null;

  if (!projectService.isLoaded() || !project) {
    return (
      <div>
        <PageHeader
          breadcrumb={['Workspace', 'Projects']}
          title="Project"
          subtitle="Loading project data…"
        />
        <div className="card" style={{ padding: '24px', color: '#64748B', fontSize: '0.875rem' }}>
          Loading live project data from the KnowledgeOps API…
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader 
        breadcrumb={['Workspace', 'Projects', project.name]}
        title={project.name}
        subtitle={`${project.description} · Project owner ${project.owner}`}
        actions={
          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              onClick={() => navigateTo('reports')}
              className="btn btn-secondary"
            >
              <FileText size={15} />
              <span>Generate report</span>
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

      {/* Subheader Badges & Metadata */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span className={`badge ${project.status === 'At risk' ? 'badge-amber' : 'badge-green'}`}>{project.status}</span>
          <span className="badge badge-blue">Release {project.target_release} · {longDate(project.target_date)}</span>
          <span className="badge badge-gray">GitHub · {linkedRepos.length} repositories</span>
          <span className="badge badge-gray">Gmail · {projectEmailCount} relevant emails</span>
        </div>
        <span style={{ fontSize: '0.75rem', color: '#64748B' }}>Updated {timeOnly(project.updated_at)}</span>
      </div>

      {/* Navigation Tabs */}
      <div className="tabs-header">
        {['Overview', 'Issues & PRs', 'Conversations', 'Evidence', 'Activity'].map((tab) => (
          <div 
            key={tab}
            className={`tab-item ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </div>
        ))}
      </div>

      {/* 5 Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '14px', marginBottom: '20px' }}>
        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.725rem', marginBottom: '4px' }}>Project health</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: health.score === null ? '#94A3B8' : '#0F172A' }}>
            {health.score === null ? 'N/A' : `${health.score} / 100`}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '2px' }}>
            Workspace overall: {health.overall === null ? 'N/A — not measured' : `${health.overall} / 100`}
          </div>
        </div>

        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.725rem', marginBottom: '4px' }}>Open issues</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0F172A' }}>{openIssueCount}</div>
          <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '2px' }}>Across {linkedRepos.length} repositories</div>
        </div>

        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.725rem', marginBottom: '4px' }}>Active pull requests</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0F172A' }}>{activePrList.length}</div>
          <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '2px' }}>
            {topRepo ? `${topRepo[1]} in ${topRepo[0]}` : 'No active pull requests'}
          </div>
        </div>

        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.725rem', marginBottom: '4px' }}>Project risks</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0F172A' }}>{projectRisks.length}</div>
          <div style={{ fontSize: '0.7rem', color: '#D97706', fontWeight: 600, marginTop: '2px' }}>Of {wsRisks.length} workspace risks</div>
        </div>

        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.725rem', marginBottom: '4px' }}>Pending actions</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0F172A' }}>{projectActions.length}</div>
          <div style={{ fontSize: '0.7rem', color: '#2563EB', fontWeight: 600, marginTop: '2px' }}>Of {wsActions.length} workspace actions</div>
        </div>
      </div>

      {/* Middle Section: Release Readiness & Project Context */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '20px', marginBottom: '20px' }}>
        {/* Release Readiness Card */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <div>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Release readiness</h3>
              <div style={{ fontSize: '0.725rem', color: '#64748B' }}>{readiness.version} · Target {readiness.targetDate}</div>
            </div>
            <span 
              onClick={() => navigateTo('evidence')}
              style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}
            >
              View release evidence →
            </span>
          </div>

          <div className={`alert-box ${readiness.pipeline.some(s => s.status === 'Blocked') ? 'alert-amber' : 'alert-blue'}`} style={{ marginBottom: '16px' }}>
            <AlertTriangle size={18} color={readiness.pipeline.some(s => s.status === 'Blocked') ? '#D97706' : '#2563EB'} style={{ flexShrink: 0 }} />
            <div>
              <strong style={{ display: 'block', marginBottom: '2px', color: readiness.pipeline.some(s => s.status === 'Blocked') ? '#78350F' : '#1E40AF' }}>
                {readiness.blockerTitle}
              </strong>
              {readiness.blockerNotice}
            </div>
          </div>

          {/* 4 Pipeline Steps Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginBottom: '16px' }}>
            {readiness.pipeline.map((step, idx) => (
              <div key={idx} style={{ padding: '10px', background: step.color === 'red' ? '#FEF2F2' : step.color === 'blue' ? '#EFF6FF' : '#F8FAFC', borderRadius: '6px', border: `1px solid ${step.color === 'red' ? '#FCA5A5' : step.color === 'blue' ? '#BFDBFE' : '#E2E8F0'}` }}>
                <div style={{ fontSize: '0.7rem', color: step.color === 'red' ? '#991B1B' : step.color === 'blue' ? '#1E40AF' : '#64748B', marginBottom: '4px' }}>{step.name}</div>
                <span className={`badge badge-${step.color}`}>{step.status}</span>
              </div>
            ))}
          </div>

          <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '10px' }}>
            {evidence.securityPr
              ? 'Evidence supports a risk, not a confirmed delay. Reassess after reviewer assignment and final scope confirmation.'
              : 'No release blockers detected for this project.'}
          </div>

          <div style={{ display: 'flex', gap: '12px', fontSize: '0.725rem', color: '#2563EB', fontWeight: 600 }}>
            {evidence.securityPr && (
              <span style={{ cursor: 'pointer' }}>
                GitHub{evidence.linkedIssue ? ` · Issue #${evidence.linkedIssue.number}` : ''} · PR #{evidence.securityPr.number}
              </span>
            )}
            {evidence.securityPr && evidence.blockerThread && <span>•</span>}
            {evidence.blockerThread && (
              <span style={{ cursor: 'pointer' }}>
                Gmail · {evidence.blockerThread.subject} · {shortDate(evidence.blockerThread.last_message_at)}
              </span>
            )}
            {!evidence.securityPr && !evidence.blockerThread && (
              <span style={{ color: '#64748B', cursor: 'default' }}>No blocker evidence recorded</span>
            )}
          </div>
        </div>

        {/* Project Context Card */}
        <div className="card">
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '14px' }}>Project context</h3>

          <div style={{ fontSize: '0.775rem', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Owner:</span>
              <strong style={{ color: '#0F172A' }}>{project.owner}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Engineering lead:</span>
              <strong style={{ color: '#0F172A' }}>{project.engineering_lead}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Release lead:</span>
              <strong style={{ color: '#0F172A' }}>{project.release_lead}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Security:</span>
              <strong style={{ color: '#0F172A' }}>{project.security_lead}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Project emails:</span>
              <strong style={{ color: '#0F172A' }}>{projectEmailCount} of {allEmails}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Last indexed:</span>
              <strong style={{ color: '#0F172A' }}>
                {lastIndexed ? `${shortDate(lastIndexed)} · ${timeOnly(lastIndexed)}` : 'N/A'}
              </strong>
            </div>
          </div>

          <div style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}>
            Edit project scope →
          </div>
        </div>
      </div>

      {/* Lower Section */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '20px' }}>
        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Cross-source Insights */}
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '2px' }}>
              Cross-source insights
            </h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '14px' }}>
              Retrieved with RAG · Cross-checked by specialist agents
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {evidence.securityPr ? (
                <div style={{ padding: '12px', background: '#FFFBEB', borderRadius: '6px', border: '1px solid #FDE68A' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                    <span className="badge badge-amber" style={{ fontSize: '0.65rem' }}>Risk</span>
                    <strong style={{ fontSize: '0.85rem', color: '#78350F' }}>
                      {projName} release may slip without a security review on PR #{evidence.securityPr.number}
                    </strong>
                  </div>
                  <p style={{ fontSize: '0.775rem', color: '#92400E', marginBottom: '8px' }}>
                    GitHub PR #{evidence.securityPr.number} has CI status {evidence.securityPr.ci_status} and is awaiting security review.
                    {evidence.linkedIssue && ` Issue #${evidence.linkedIssue.number} remains ${evidence.linkedIssue.status}.`}
                    {evidence.blockerThread && ` Gmail ${evidence.blockerThread.id} (${evidence.blockerThread.message_count} messages) confirms the release gate.`}
                    {' '}Assign a reviewer before changing the release date.
                  </p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#B45309' }}>
                    <span>
                      GitHub · PR #{evidence.securityPr.number}
                      {evidence.blockerThread && ` · Gmail · ${evidence.blockerThread.id}`}
                    </span>
                    <span
                      onClick={() => navigateTo('evidence')}
                      style={{ color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}
                    >
                      View evidence →
                    </span>
                  </div>
                </div>
              ) : (
                <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', fontSize: '0.775rem', color: '#64748B' }}>
                  No open cross-source risks recorded for {projName}.
                </div>
              )}

              {latestDecision ? (
                <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                    <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>Decision</span>
                    <strong style={{ fontSize: '0.85rem', color: '#0F172A' }}>{latestDecision.subject}</strong>
                  </div>
                  <p style={{ fontSize: '0.775rem', color: '#475569', marginBottom: '6px' }}>
                    {firstSentence(latestDecision.body)}
                  </p>
                  <div style={{ fontSize: '0.7rem', color: '#64748B' }}>
                    Gmail · {decisionThread ? decisionThread.subject : 'Thread'} · {latestDecision.thread_id} · {shortDate(latestDecision.received_at)}
                  </div>
                </div>
              ) : (
                <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', fontSize: '0.775rem', color: '#64748B' }}>
                  No extracted decisions recorded for {projName}.
                </div>
              )}
            </div>
          </div>

          {/* Linked Repositories Table */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0F172A' }}>Linked repositories</h3>
              <span 
                onClick={() => navigateTo('github')}
                style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}
              >
                Open analytics →
              </span>
            </div>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Repository</th>
                    <th>Open issues</th>
                    <th>Active PRs</th>
                    <th>Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {linkedRepos.map((repo) => (
                    <tr key={repo.id}>
                      <td><strong>{repo.name}</strong></td>
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
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Next Actions Checklist */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0F172A' }}>Next actions</h3>
              <span style={{ fontSize: '0.725rem', color: '#64748B' }}>
                {projectActions.filter(a => a.due === 'Today').length} due today · {projectActions.length} total
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '12px', fontSize: '0.775rem' }}>
              {projectActions.length === 0 && (
                <div style={{ padding: '12px', borderRadius: '6px', background: '#F8FAFC', border: '1px solid #E2E8F0', fontSize: '0.775rem', color: '#64748B' }}>
                  {overview ? 'No pending actions recorded for this project.' : 'Loading actions…'}
                </div>
              )}
              {projectActions.map((action) => (
                <div key={action.id} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                  <input type="checkbox" style={{ marginTop: '2px' }} />
                  <div>
                    <div style={{ fontWeight: 600, color: '#0F172A' }}>{action.title}</div>
                    <div style={{ fontSize: '0.7rem', color: action.due === 'Today' ? '#D97706' : '#64748B', fontWeight: 600 }}>
                      {action.owner} · {action.due}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Release Timeline */}
          <div className="card">
            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0F172A', marginBottom: '14px' }}>Release timeline</h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {timeline.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', gap: '12px' }}>
                  {item.icon === 'check' ? (
                    <CheckCircle2 size={16} color="#059669" style={{ flexShrink: 0 }} />
                  ) : item.icon === 'clock-orange' ? (
                    <Clock size={16} color="#D97706" style={{ flexShrink: 0 }} />
                  ) : (
                    <Clock size={16} color="#94A3B8" style={{ flexShrink: 0 }} />
                  )}
                  <div>
                    <div style={{ fontSize: '0.7rem', color: item.icon === 'clock-orange' ? '#D97706' : '#64748B', fontWeight: 600 }}>{item.date}</div>
                    <div style={{ fontWeight: 700, fontSize: '0.8rem', color: '#0F172A' }}>{item.title}</div>
                    <div style={{ fontSize: '0.725rem', color: item.icon === 'clock-orange' ? '#D97706' : '#64748B', fontWeight: item.icon === 'clock-orange' ? 600 : 400 }}>{item.subtitle}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
