import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  BarChart2,
  ArrowUpRight,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Info
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { GitHubIcon, GmailIcon, QdrantIcon } from '../components/Icons';

import { dashboardService } from '../services/dashboardService';
import useCacheTick from '../hooks/useCacheTick';

export default function DashboardScreen({ navigateTo }) {
  const [checkedActions, setCheckedActions] = useState({});
  const [projectFilter, setProjectFilter] = useState('All projects');
  useCacheTick();

  useEffect(() => {
    dashboardService.sync();
  }, []);

  const overview = dashboardService.getOverview();
  const metrics = dashboardService.getSummaryMetrics();
  const health = dashboardService.getProjectHealthOverview();
  const connectionCards = dashboardService.getConnectionCards();
  const recentActivity = dashboardService.getRecentActivity();
  const aiActivity = recentActivity.find((a) => a.type === 'ai');

  let insights = dashboardService.getEvidenceBackedInsights();
  let pendingActions = dashboardService.getPendingActions();
  if (projectFilter !== 'All projects') {
    insights = insights.filter((i) => i.project === projectFilter);
    pendingActions = pendingActions.filter((a) => a.project === projectFilter);
  }

  const toggleAction = (id) => {
    setCheckedActions(prev => ({ ...prev, [id]: !prev[id] }));
  };

  if (!overview) {
    return (
      <div>
        <PageHeader
          breadcrumb={['Workspace', 'Dashboard']}
          title="Good morning, Project Manager"
          subtitle="Ask questions across your GitHub repositories and Gmail conversations."
        />
        <div className="card" style={{ padding: '24px', color: '#64748B', fontSize: '0.875rem' }}>
          Loading live workspace data from the KnowledgeOps API…
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Top Page Header */}
      <PageHeader 
        breadcrumb={['Workspace', 'Dashboard']}
        title="Good morning, Project Manager"
        subtitle="Ask questions across your GitHub repositories and Gmail conversations."
        actions={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button 
              onClick={() => navigateTo('ask')}
              className="btn btn-primary"
            >
              <Sparkles size={15} />
              <span>Ask KnowledgeOps</span>
            </button>
            <button 
              onClick={() => navigateTo('project-details')}
              className="btn btn-secondary"
            >
              <BarChart2 size={15} />
              <span>View Project Insights</span>
            </button>
          </div>
        }
      />

      {/* Scope Filter Controls */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginBottom: '16px' }}>
        <select
          className="select"
          style={{ width: 'auto', fontSize: '0.775rem', padding: '4px 10px' }}
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value)}
        >
          <option>All projects</option>
          <option>Platform API</option>
          <option>Customer Portal</option>
        </select>
        <select className="select" style={{ width: 'auto', fontSize: '0.775rem', padding: '4px 10px' }}>
          <option>Last 7 days</option>
          <option>Last 30 days</option>
        </select>
      </div>

      {/* Top 6 Metric Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(6, 1fr)',
        gap: '14px',
        marginBottom: '20px'
      }}>
        {/* Card 1 */}
        <div className="card card-sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#64748B', fontSize: '0.75rem', marginBottom: '6px' }}>
            <GitHubIcon size={14} />
            <span>GitHub Repositories</span>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', lineHeight: '1.1' }}>
            {metrics.githubRepos}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '4px' }}>
            All repositories synced
          </div>
        </div>

        {/* Card 2 */}
        <div className="card card-sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#64748B', fontSize: '0.75rem', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.8rem' }}>⊙</span>
            <span>Open Issues</span>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', lineHeight: '1.1' }}>
            {metrics.openIssues}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#059669', marginTop: '4px', fontWeight: 600 }}>
            {metrics.issuesTrend}
          </div>
        </div>

        {/* Card 3 */}
        <div className="card card-sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#64748B', fontSize: '0.75rem', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.8rem' }}>⑂</span>
            <span>Active Pull Requests</span>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', lineHeight: '1.1' }}>
            {metrics.activePRs}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '4px' }}>
            {metrics.prsAwaitingReview} awaiting review
          </div>
        </div>

        {/* Card 4 */}
        <div className="card card-sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#64748B', fontSize: '0.75rem', marginBottom: '6px' }}>
            <GmailIcon size={14} />
            <span>Relevant Emails</span>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', lineHeight: '1.1' }}>
            {metrics.relevantEmails}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '4px' }}>
            {metrics.emailsReceivedThisWeek} received this week
          </div>
        </div>

        {/* Card 5 */}
        <div className="card card-sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#64748B', fontSize: '0.75rem', marginBottom: '6px' }}>
            <AlertTriangle size={14} color="#D97706" />
            <span>Project Risks</span>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', lineHeight: '1.1' }}>
            {metrics.projectRisks}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#D97706', marginTop: '4px', fontWeight: 600 }}>
            {metrics.risksNeedAttention} need attention
          </div>
        </div>

        {/* Card 6 */}
        <div className="card card-sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#64748B', fontSize: '0.75rem', marginBottom: '6px' }}>
            <CheckCircle2 size={14} color="#2563EB" />
            <span>Pending Actions</span>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', lineHeight: '1.1' }}>
            {metrics.pendingActions}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#2563EB', marginTop: '4px', fontWeight: 600 }}>
            {metrics.actionsDueToday} due today
          </div>
        </div>
      </div>

      {/* Middle Section: Project Health & MCP Connections */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px', marginBottom: '20px' }}>
        {/* Left Card: Project Health */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Project Health</h3>
            <span 
              onClick={() => navigateTo('project-details')}
              style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px' }}
            >
              View breakdown <ArrowUpRight size={12} />
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr 180px', gap: '20px', alignItems: 'center' }}>
            {/* Health Score Gauge */}
            <div style={{ textAlign: 'center' }}>
              <div style={{
                position: 'relative',
                width: '100px',
                height: '100px',
                margin: '0 auto',
                borderRadius: '50%',
                background: health.score === null
                  ? 'conic-gradient(#E2E8F0 0% 100%)'
                  : `conic-gradient(#2563EB 0% ${health.score}%, #E2E8F0 ${health.score}% 100%)`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <div style={{
                  width: '80px',
                  height: '80px',
                  borderRadius: '50%',
                  background: '#FFFFFF',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: health.score === null ? '#94A3B8' : '#0F172A', lineHeight: '1' }}>
                    {health.score === null ? 'N/A' : health.score}
                  </div>
                  <div style={{ fontSize: '0.65rem', color: '#64748B' }}>
                    {health.score === null ? 'not measured' : `out of ${health.maxScore}`}
                  </div>
                </div>
              </div>
              <div style={{ marginTop: '10px' }}>
                <span className={`badge ${health.badge === 'On track' ? 'badge-green' : 'badge-amber'}`}>{health.badge}</span>
              </div>
            </div>

            {/* Line Chart Component */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px', fontSize: '0.75rem' }}>
                <span style={{ fontWeight: 600, color: '#0F172A' }}>Open issues</span>
                <span style={{ fontSize: '0.7rem', color: health.issueDecreasePercent === 'N/A' ? '#94A3B8' : '#059669', fontWeight: 600 }}>
                  {health.issueDecreasePercent === 'N/A' ? 'N/A — not measured' : `↓ ${health.issueDecreasePercent}`}
                </span>
              </div>
              <div style={{ fontSize: '0.875rem', fontWeight: 700, color: '#0F172A', marginBottom: '8px' }}>
                {health.openIssues}{' '}
                <span style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 400 }}>
                  {health.previousOpenIssues !== null
                    ? `vs. ${health.previousOpenIssues} last week`
                    : '· prior-week trend N/A'}
                </span>
              </div>

              {/* Trend history: only rendered when a prior-week datapoint exists */}
              {health.previousOpenIssues !== null ? (
                <>
                  <div style={{ height: '60px', width: '100%', position: 'relative' }}>
                    <svg width="100%" height="100%" viewBox="0 0 200 60" preserveAspectRatio="none">
                      <path
                        d="M0,15 Q50,10 100,35 T200,45"
                        fill="none"
                        stroke="#2563EB"
                        strokeWidth="3"
                      />
                      <circle cx="200" cy="45" r="4" fill="#2563EB" />
                    </svg>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.675rem', color: '#94A3B8', marginTop: '4px' }}>
                    <span>Oct 1</span>
                    <span>Oct 4</span>
                    <span>Oct 7</span>
                  </div>
                </>
              ) : (
                <div style={{
                  height: '60px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: '#F8FAFC',
                  border: '1px dashed #E2E8F0',
                  borderRadius: '8px',
                  fontSize: '0.725rem',
                  color: '#94A3B8'
                }}>
                  Trend history not measured — no prior-week data in workspace.
                </div>
              )}
            </div>

            {/* Pull Requests Status Breakdown */}
            <div style={{ borderLeft: '1px solid #F1F5F9', paddingLeft: '16px' }}>
              <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A', marginBottom: '8px' }}>
                Pull requests <span style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 400 }}>{health.activePRsTotal} active</span>
              </div>

              {/* Progress bar */}
              <div style={{ display: 'flex', height: '6px', borderRadius: '3px', overflow: 'hidden', marginBottom: '10px' }}>
                <div style={{ width: `${(health.awaitingReview / (health.activePRsTotal || 1)) * 100}%`, background: '#7C3AED' }}></div>
                <div style={{ width: `${(health.readyToMerge / (health.activePRsTotal || 1)) * 100}%`, background: '#2563EB' }}></div>
                <div style={{ width: `${(health.draftChecks / (health.activePRsTotal || 1)) * 100}%`, background: '#94A3B8' }}></div>
              </div>

              <div style={{ fontSize: '0.725rem', color: '#475569', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span><span style={{ color: '#7C3AED' }}>•</span> Awaiting review</span>
                  <strong>{health.awaitingReview}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span><span style={{ color: '#2563EB' }}>•</span> Ready to merge</span>
                  <strong>{health.readyToMerge}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span><span style={{ color: '#94A3B8' }}>•</span> Draft / checks running</span>
                  <strong>{health.draftChecks}</strong>
                </div>
              </div>
              <div style={{ fontSize: '0.675rem', color: '#64748B', marginTop: '8px' }}>
                Median review time: <strong>{health.medianReviewTime}</strong>
              </div>
            </div>
          </div>

          <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #F1F5F9', fontSize: '0.725rem', color: '#64748B', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Info size={13} color="#94A3B8" />
            <span>Based on issue velocity, review latency, and evidence-backed risk signals.</span>
          </div>
        </div>

        {/* Right Card: MCP Connections */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>MCP Connections</h3>
            <span 
              onClick={() => navigateTo('mcp')}
              style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px' }}
            >
              Manage <ArrowUpRight size={12} />
            </span>
          </div>

          {/* Connection List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* GitHub Connection */}
            <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <GitHubIcon size={16} />
                  <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A' }}>GitHub</span>
                  <span style={{ fontSize: '0.725rem', color: '#64748B' }}>{connectionCards.github.subtitle}</span>
                </div>
                <span className={`badge ${connectionCards.github.badge === 'Connected' ? 'badge-green' : 'badge-gray'}`}>
                  {connectionCards.github.badge}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#64748B' }}>
                <span>{connectionCards.github.synced}{connectionCards.github.mode ? ` · ${connectionCards.github.mode}` : ''}</span>
                <span style={{ color: connectionCards.github.health === 'Healthy' ? '#059669' : '#94A3B8', fontWeight: 500 }}>
                  {connectionCards.github.health}
                </span>
              </div>
            </div>

            {/* Gmail Connection */}
            <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <GmailIcon size={16} />
                  <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A' }}>Gmail</span>
                  <span style={{ fontSize: '0.725rem', color: '#64748B' }}>{connectionCards.gmail.subtitle}</span>
                </div>
                <span className={`badge ${connectionCards.gmail.badge === 'Connected' ? 'badge-green' : 'badge-gray'}`}>
                  {connectionCards.gmail.badge}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#64748B' }}>
                <span>{connectionCards.gmail.synced}{connectionCards.gmail.mode ? ` · ${connectionCards.gmail.mode}` : ''}</span>
                <span style={{ color: connectionCards.gmail.health === 'Healthy' ? '#059669' : '#94A3B8', fontWeight: 500 }}>
                  {connectionCards.gmail.health}
                </span>
              </div>
            </div>

            {/* RAG Index Status */}
            <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <QdrantIcon size={16} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.825rem', color: '#0F172A' }}>
                    {connectionCards.rag.title}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#64748B' }}>
                    {connectionCards.rag.subtitle}
                  </div>
                </div>
              </div>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: connectionCards.rag.ready ? '#10B981' : '#94A3B8' }}></span>
            </div>
          </div>
        </div>
      </div>

      {/* Lower Section: Evidence-backed Insights & Pending Actions */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px', marginBottom: '20px' }}>
        {/* Left: Evidence-backed Insights */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Evidence-backed insights</h3>
            <span 
              onClick={() => navigateTo('evidence')}
              style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px' }}
            >
              View all insights <ArrowRight size={12} />
            </span>
          </div>

          <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Sparkles size={12} color="#7C3AED" />
            <span>
              Retrieved with RAG · Cross-checked by specialist agents · Updated{' '}
              {aiActivity ? aiActivity.timestamp : 'N/A'}
            </span>
          </div>

          {insights.length === 0 && (
            <div style={{ padding: '14px', borderRadius: '8px', background: '#F8FAFC', border: '1px solid #E2E8F0', fontSize: '0.775rem', color: '#64748B' }}>
              No open risks recorded for {projectFilter === 'All projects' ? 'the workspace' : projectFilter}.
            </div>
          )}

          {insights.map((insight) => (
            <div 
              key={insight.id} 
              style={{ 
                padding: '14px', 
                borderRadius: '8px', 
                background: insight.priorityColor === 'amber' ? '#FFFBEB' : '#ECFDF5', 
                border: `1px solid ${insight.priorityColor === 'amber' ? '#FDE68A' : '#A7F3D0'}`, 
                marginBottom: '12px' 
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <span className={`badge badge-${insight.priorityColor}`}>{insight.priority}</span>
                  <span className="badge badge-gray">{insight.project}</span>
                </div>
                <span style={{ fontSize: '0.7rem', color: insight.priorityColor === 'amber' ? '#D97706' : '#059669', fontWeight: 600 }}>{insight.confidence}</span>
              </div>
              <div style={{ fontWeight: 700, fontSize: '0.875rem', color: insight.priorityColor === 'amber' ? '#78350F' : '#065F46', marginBottom: '4px' }}>
                {insight.title}
              </div>
              <p style={{ fontSize: '0.775rem', color: insight.priorityColor === 'amber' ? '#92400E' : '#047857', marginBottom: '8px' }}>
                {insight.description}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.725rem', color: insight.priorityColor === 'amber' ? '#B45309' : '#065F46' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {insight.sources.map((s, idx) => (
                    <React.Fragment key={idx}>
                      {idx > 0 && <span>•</span>}
                      <span>{s}</span>
                    </React.Fragment>
                  ))}
                </div>
                <span 
                  onClick={() => navigateTo(insight.targetRoute)}
                  style={{ fontWeight: 700, color: '#2563EB', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px' }}
                >
                  View evidence <ArrowRight size={12} />
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Right: Pending Actions */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Pending Actions</h3>
              <span className="badge badge-blue">{metrics.pendingActions}</span>
            </div>
            <span 
              onClick={() => navigateTo('workflows')}
              style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px' }}
            >
              View all <ArrowRight size={12} />
            </span>
          </div>

          <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '16px' }}>
            {metrics.actionsDueToday} due today · Prioritized from project evidence
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {pendingActions.length === 0 && (
              <div style={{ padding: '14px', borderRadius: '8px', background: '#F8FAFC', border: '1px solid #E2E8F0', fontSize: '0.775rem', color: '#64748B' }}>
                No pending actions recorded for {projectFilter === 'All projects' ? 'the workspace' : projectFilter}.
              </div>
            )}
            {pendingActions.map((action) => (
              <div key={action.id} style={{ padding: '12px', background: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0', display: 'flex', gap: '12px' }}>
                <input 
                  type="checkbox" 
                  checked={!!checkedActions[action.id]} 
                  onChange={() => toggleAction(action.id)} 
                  style={{ marginTop: '2px' }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: '0.825rem', color: checkedActions[action.id] ? '#94A3B8' : '#0F172A', textDecoration: checkedActions[action.id] ? 'line-through' : 'none' }}>
                    {action.title}
                  </div>
                  <div style={{ fontSize: '0.725rem', color: '#64748B', margin: '2px 0 6px 0' }}>
                    {action.subtitle}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="badge badge-gray" style={{ fontSize: '0.65rem' }}>{action.ownerBadge}</span>
                    <span className="badge badge-amber" style={{ fontSize: '0.65rem' }}>{action.dueBadge}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ textAlign: 'center', fontSize: '0.75rem', color: '#64748B', marginTop: '12px' }}>
            {metrics.actionsDueToday} of {metrics.pendingActions} actions due today · derived from workspace evidence
          </div>
        </div>
      </div>

      {/* Bottom Bar: Recent Activity */}
      <div className="card" style={{ padding: '14px 20px', background: '#FFFFFF' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A' }}>Recent activity</div>
          <span 
            onClick={() => navigateTo('workflows')}
            style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px' }}
          >
            Open activity log <ArrowRight size={12} />
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px', marginTop: '12px' }}>
          {recentActivity.map((act, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
              {act.type === 'github' && <GitHubIcon size={16} style={{ marginTop: '2px' }} />}
              {act.type === 'gmail' && <GmailIcon size={16} style={{ marginTop: '2px' }} />}
              {act.type === 'ai' && <Sparkles size={16} color="#7C3AED" style={{ marginTop: '2px' }} />}
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#0F172A' }}>{act.title}</div>
                <div style={{ fontSize: '0.725rem', color: '#64748B' }}>{act.description}</div>
              </div>
              <span style={{ fontSize: '0.7rem', color: '#94A3B8', marginLeft: 'auto' }}>{act.timestamp}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
