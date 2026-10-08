import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  ArrowUpRight,
  Shield,
  Lightbulb,
  ArrowRight,
  Clock,
  ChevronDown,
  AlertTriangle
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { GitHubIcon, GmailIcon } from '../components/Icons';
import { postQuery } from '../services/api';
import { projectService } from '../services/projectService';
import { gmailService } from '../services/gmailService';
import { githubService } from '../services/githubService';
import useCacheTick from '../hooks/useCacheTick';

const MONTHS = ['January','February','March','April','May','June','July',
  'August','September','October','November','December'];

function longDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}, ${y}`;
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

const CONTEXT_PROJECT_ID = 'proj-platform-api';

export default function AskScreen({ navigateTo, setQueryResult }) {
  const [queryText, setQueryText] = useState("What could delay the Platform API v2.4 release, and what should we do next?");
  const [scope, setScope] = useState("Platform API");
  const [timeRange, setTimeRange] = useState("Last 7 days");
  const [useGithub, setUseGithub] = useState(true);
  const [useGmail, setUseGmail] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  useCacheTick();
  useEffect(() => {
    projectService.sync();
    gmailService.sync();
    githubService.sync();
  }, []);

  const contextProject = projectService.getProjectById(CONTEXT_PROJECT_ID);
  const contextRepos = projectService.getLinkedRepositories(CONTEXT_PROJECT_ID);
  const contextTotalRepos = githubService.getRepositories().length;
  const contextProjectEmails = gmailService.getRelevantEmailCount(CONTEXT_PROJECT_ID);
  const contextTotalEmails = gmailService.getRelevantEmailCount();
  const contextIndexed = contextRepos
    .map(r => r.synced_at || '')
    .filter(Boolean)
    .sort()
    .pop() || '';

  const submitQuery = async (text) => {
    const question = (text || '').trim();
    if (!question || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const sources = [];
      if (useGithub) sources.push('GitHub');
      if (useGmail) sources.push('Gmail');
      const result = await postQuery(
        question,
        sources.length > 0 ? sources : null,
        scope === 'All projects' ? null : scope
      );
      if (setQueryResult) setQueryResult(result);
      navigateTo('answer');
    } catch (err) {
      setError(err.message || 'The agent pipeline failed to answer this question.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    submitQuery(queryText);
  };

  const handleSuggestedClick = (text) => {
    setQueryText(text);
  };

  return (
    <div>
      <PageHeader 
        breadcrumb={['Workspace', 'Ask KnowledgeOps']}
        title="Ask KnowledgeOps"
        subtitle="One question. Connected project knowledge. An answer backed by evidence."
        actions={
          <button 
            onClick={() => navigateTo('ask')}
            className="btn btn-primary"
          >
            <Sparkles size={15} />
            <span>Ask KnowledgeOps</span>
          </button>
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '24px' }}>
        {/* Main Content Left */}
        <div>
          {/* Query Composer Card */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0F172A', marginBottom: '2px' }}>
              What would you like to know?
            </h3>
            <p style={{ fontSize: '0.8rem', color: '#64748B', marginBottom: '16px' }}>
              Ask naturally about delivery, decisions, risks, or next steps.
            </p>

            {/* Controls Bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '14px', flexWrap: 'wrap' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>
                  Project scope
                </label>
                <select 
                  className="select" 
                  value={scope} 
                  onChange={(e) => setScope(e.target.value)}
                  style={{ fontSize: '0.8rem', padding: '6px 10px', minWidth: '160px' }}
                >
                  <option>Platform API</option>
                  <option>Customer Portal</option>
                  <option>All projects</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>
                  Time range
                </label>
                <select 
                  className="select" 
                  value={timeRange} 
                  onChange={(e) => setTimeRange(e.target.value)}
                  style={{ fontSize: '0.8rem', padding: '6px 10px', minWidth: '140px' }}
                >
                  <option>Last 7 days</option>
                  <option>Last 14 days</option>
                  <option>Last 30 days</option>
                </select>
              </div>

              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '12px', paddingTop: '16px' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Sources</span>
                <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.775rem', cursor: 'pointer', color: '#2563EB', fontWeight: 600 }}>
                  <input type="checkbox" checked={useGithub} onChange={(e) => setUseGithub(e.target.checked)} />
                  <GitHubIcon size={14} /> GitHub
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.775rem', cursor: 'pointer', color: '#EA4335', fontWeight: 600 }}>
                  <input type="checkbox" checked={useGmail} onChange={(e) => setUseGmail(e.target.checked)} />
                  <GmailIcon size={14} /> Gmail
                </label>
                <span style={{ fontSize: '0.725rem', color: '#059669', fontWeight: 600 }}>Both sources ready</span>
              </div>
            </div>

            {/* Query Textarea Box */}
            <form onSubmit={handleSubmit}>
              <div style={{ position: 'relative', marginBottom: '14px' }}>
                <textarea 
                  className="textarea" 
                  rows={4}
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  placeholder="Ask a follow-up, compare sources, or request a report"
                  style={{ fontSize: '0.95rem', padding: '14px', lineHeight: 1.5 }}
                />
                <span style={{ position: 'absolute', right: '12px', bottom: '12px', fontSize: '0.7rem', color: '#94A3B8' }}>
                  {queryText.length} / 2,000
                </span>
              </div>

              {error && (
                <div className="alert-box alert-amber" style={{ marginBottom: '12px' }}>
                  <AlertTriangle size={16} color="#D97706" style={{ flexShrink: 0 }} />
                  <div>
                    <strong style={{ display: 'block', marginBottom: '2px' }}>Query failed</strong>
                    {error}
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#64748B' }}>
                  <Shield size={14} color="#64748B" />
                  <span>Only knowledge you have access to</span>
                </div>
                <button type="submit" className="btn btn-primary btn-lg" disabled={submitting}>
                  <Sparkles size={16} />
                  <span>{submitting ? 'Agents analyzing…' : 'Ask KnowledgeOps'}</span>
                </button>
              </div>
            </form>
          </div>

          {/* Suggested Questions Grid */}
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0F172A' }}>Start with a useful question</h4>
              <span style={{ fontSize: '0.75rem', color: '#64748B' }}>Suggested for your workspace</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              {/* Suggestion 1 */}
              <div 
                onClick={() => handleSuggestedClick("What could delay our v2.4 release?")}
                style={{ padding: '14px', background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '8px', cursor: 'pointer', transition: 'border-color 0.15s' }}
                onMouseEnter={(e) => e.currentTarget.style.borderColor = '#2563EB'}
                onMouseLeave={(e) => e.currentTarget.style.borderColor = '#E2E8F0'}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A' }}>
                    What could delay our v2.4 release?
                  </div>
                  <ArrowUpRight size={14} color="#2563EB" />
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
                  Identify blockers across code and conversations.
                </div>
              </div>

              {/* Suggestion 2 */}
              <div 
                onClick={() => handleSuggestedClick("Which pull requests need attention?")}
                style={{ padding: '14px', background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '8px', cursor: 'pointer', transition: 'border-color 0.15s' }}
                onMouseEnter={(e) => e.currentTarget.style.borderColor = '#2563EB'}
                onMouseLeave={(e) => e.currentTarget.style.borderColor = '#E2E8F0'}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A' }}>
                    Which pull requests need attention?
                  </div>
                  <ArrowUpRight size={14} color="#2563EB" />
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
                  Find review bottlenecks and the right owners.
                </div>
              </div>

              {/* Suggestion 3 */}
              <div 
                onClick={() => handleSuggestedClick("What decisions were made this week?")}
                style={{ padding: '14px', background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '8px', cursor: 'pointer', transition: 'border-color 0.15s' }}
                onMouseEnter={(e) => e.currentTarget.style.borderColor = '#2563EB'}
                onMouseLeave={(e) => e.currentTarget.style.borderColor = '#E2E8F0'}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A' }}>
                    What decisions were made this week?
                  </div>
                  <ArrowUpRight size={14} color="#2563EB" />
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
                  Trace project decisions to the original email.
                </div>
              </div>

              {/* Suggestion 4 */}
              <div 
                onClick={() => handleSuggestedClick("Is Customer Portal ready to ship?")}
                style={{ padding: '14px', background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '8px', cursor: 'pointer', transition: 'border-color 0.15s' }}
                onMouseEnter={(e) => e.currentTarget.style.borderColor = '#2563EB'}
                onMouseLeave={(e) => e.currentTarget.style.borderColor = '#E2E8F0'}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A' }}>
                    Is Customer Portal ready to ship?
                  </div>
                  <ArrowUpRight size={14} color="#2563EB" />
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
                  Cross-check checks, QA handoff, and approvals.
                </div>
              </div>
            </div>
          </div>

          {/* Recent Questions */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0F172A' }}>Recent questions</h4>
              <span style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}>View history →</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div 
                onClick={() => submitQuery("Why is the auth migration blocked?")}
                style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', cursor: 'pointer' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.825rem', color: '#0F172A' }}>Why is the auth migration blocked?</span>
                  <span style={{ fontSize: '0.7rem', color: '#94A3B8' }}>Today, 9:32 AM</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', fontSize: '0.7rem', color: '#64748B' }}>
                  <span>GitHub · Issue #142 · PR #284</span>
                  <span>•</span>
                  <span>Gmail · Release readiness · Oct 6</span>
                </div>
              </div>

              <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.825rem', color: '#0F172A' }}>Summarize the Customer Portal QA handoff</span>
                  <span style={{ fontSize: '0.7rem', color: '#94A3B8' }}>Yesterday</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', fontSize: '0.7rem', color: '#64748B' }}>
                  <span>Customer Portal · 5 ready-to-merge PRs · QA handoff email</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Sidebars */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Card 1: Your retrieval context */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '0.85rem', color: '#0F172A' }}>
                <GitHubIcon size={16} />
                <span>{contextProject ? contextProject.name : '…'}</span>
              </div>
              <span className={`badge ${contextProject && contextProject.status === 'At risk' ? 'badge-amber' : 'badge-green'}`}>
                {contextProject ? contextProject.status : '…'}
              </span>
            </div>
            <p style={{ fontSize: '0.75rem', color: '#64748B', marginBottom: '16px' }}>
              {contextProject
                ? `${contextProject.target_release} · Target ${longDate(contextProject.target_date)}`
                : 'Loading project context…'}
            </p>

            <div style={{ fontSize: '0.775rem', color: '#475569', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>GitHub repositories:</span>
                <strong>{contextRepos.length} of {contextTotalRepos || '…'}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Relevant emails:</span>
                <strong>{contextProjectEmails} of {contextTotalEmails || '…'}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Last indexed:</span>
                <strong>{contextIndexed ? timeOnly(contextIndexed) : 'N/A'}</strong>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.7rem' }}>
              {contextRepos.map((r) => (
                <div key={r.id} style={{ padding: '6px 10px', background: '#F1F5F9', borderRadius: '4px', color: '#475569' }}>
                  GitHub · {r.org}/{r.name}
                </div>
              ))}
              <div style={{ padding: '6px 10px', background: '#F1F5F9', borderRadius: '4px', color: '#475569' }}>
                Gmail · Project inbox · {contextProject ? contextProject.name : '…'}
              </div>
            </div>
          </div>

          {/* Card 2: How your answer is built */}
          <div className="card">
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0F172A', marginBottom: '14px' }}>
              How your answer is built
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '0.775rem' }}>
              <div style={{ display: 'flex', gap: '10px' }}>
                <span style={{ width: '20px', height: '20px', borderRadius: '4px', background: '#EFF6FF', color: '#2563EB', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem' }}>1</span>
                <div>
                  <div style={{ fontWeight: 700, color: '#0F172A' }}>Retrieve relevant evidence</div>
                  <div style={{ color: '#64748B', fontSize: '0.725rem' }}>Search GitHub and Gmail through MCP.</div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                <span style={{ width: '20px', height: '20px', borderRadius: '4px', background: '#F3E8FF', color: '#7C3AED', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem' }}>2</span>
                <div>
                  <div style={{ fontWeight: 700, color: '#0F172A' }}>Reason across sources</div>
                  <div style={{ color: '#64748B', fontSize: '0.725rem' }}>Specialist agents compare signals and conflicts.</div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                <span style={{ width: '20px', height: '20px', borderRadius: '4px', background: '#ECFDF5', color: '#059669', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem' }}>3</span>
                <div>
                  <div style={{ fontWeight: 700, color: '#0F172A' }}>Cite every key claim</div>
                  <div style={{ color: '#64748B', fontSize: '0.725rem' }}>Open the source behind each insight.</div>
                </div>
              </div>
            </div>
          </div>

          {/* Card 3: Tip note */}
          <div style={{ padding: '14px', background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: '8px', display: 'flex', gap: '10px', fontSize: '0.75rem', color: '#1E40AF' }}>
            <Lightbulb size={18} color="#2563EB" style={{ flexShrink: 0 }} />
            <div>
              Be specific about a project, release, or date to get more relevant evidence.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
