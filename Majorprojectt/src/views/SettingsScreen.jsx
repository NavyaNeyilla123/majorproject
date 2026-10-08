import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Save, 
  Info, 
  Lock, 
  Zap, 
  Database, 
  User, 
  Shield, 
  ExternalLink 
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { GitHubIcon, GmailIcon, QdrantIcon } from '../components/Icons';
import { fetchLlmStatus, fetchMcpStatus } from '../services/api';
import { evaluationService } from '../services/evaluationService';
import { githubService } from '../services/githubService';
import useCacheTick from '../hooks/useCacheTick';

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function shortDate(iso) {
  if (!iso) return '';
  const [, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}, ${new Date(iso).getUTCFullYear()}`;
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

const PROVIDER_LABELS = {
  mock: 'Mock (built-in)',
  'openai-compatible': 'OpenAI-compatible HTTP',
  openai: 'OpenAI-compatible HTTP',
  http: 'OpenAI-compatible HTTP'
};

const STATUS_BADGES = {
  healthy: { className: 'badge-green', label: 'Healthy' },
  configured: { className: 'badge-blue', label: 'Configured' },
  unavailable: { className: 'badge-red', label: 'Unavailable' }
};

const MCP_BADGES = {
  mock_connected: { className: 'badge-amber', label: 'Mock connected' },
  connected: { className: 'badge-green', label: 'Connected' },
  unconfigured: { className: 'badge-amber', label: 'Unconfigured' },
  unavailable: { className: 'badge-red', label: 'Unavailable' },
  error: { className: 'badge-red', label: 'Error' },
  disconnected: { className: 'badge-red', label: 'Disconnected' }
};

export default function SettingsScreen({ navigateTo }) {
  const [llmEvidence, setLlmEvidence] = useState(true);
  const [llmStream, setLlmStream] = useState(true);
  const [ragRerank, setRagRerank] = useState(true);
  const [ragFilter, setRagFilter] = useState(true);
  const [mcpApproval, setMcpApproval] = useState(true);
  const [userNotify, setUserNotify] = useState(true);
  const [userDigest, setUserDigest] = useState(true);
  const [secSSO, setSecSSO] = useState(true);
  const [secMFA, setSecMFA] = useState(true);
  const [secRBAC, setSecRBAC] = useState(true);
  const [secRedact, setSecRedact] = useState(true);
  const [evalFreeze, setEvalFreeze] = useState(true);
  const [evalReview, setEvalReview] = useState(true);
  const [llmStatus, setLlmStatus] = useState(null);
  const [llmStatusError, setLlmStatusError] = useState('');
  const [mcpStatus, setMcpStatus] = useState(null);
  const [mcpStatusError, setMcpStatusError] = useState('');

  const loadLlmStatus = async () => {
    try {
      setLlmStatusError('');
      const status = await fetchLlmStatus();
      setLlmStatus(status);
    } catch (err) {
      setLlmStatusError(err.message || 'Failed to fetch LLM status');
      setLlmStatus(null);
    }
  };

  const loadMcpStatus = async () => {
    try {
      setMcpStatusError('');
      const status = await fetchMcpStatus();
      setMcpStatus(status);
    } catch (err) {
      setMcpStatusError(err.message || 'Failed to fetch MCP status');
      setMcpStatus(null);
    }
  };

  useEffect(() => {
    loadLlmStatus();
    loadMcpStatus();
    evaluationService.sync();
    githubService.sync();
  }, []);
  useCacheTick();

  const evalOverview = evaluationService.getOverview();
  const ghSnapshotIso = githubService.getRepositories()
    .map(r => r.synced_at || '')
    .filter(Boolean)
    .sort()
    .pop() || '';

  const mcpBadge = (server) => {
    if (mcpStatusError) return { className: 'badge-red', label: 'Unknown' };
    if (!mcpStatus) return { className: 'badge-gray', label: 'Checking…' };
    return MCP_BADGES[server.status] || MCP_BADGES.disconnected;
  };

  const llmBadge = llmStatus ? (STATUS_BADGES[llmStatus.status] || STATUS_BADGES.unavailable) : { className: 'badge-gray', label: 'Checking…' };
  const llmProviderLabel = llmStatus ? (PROVIDER_LABELS[llmStatus.provider] || llmStatus.provider || 'Not configured') : '…';
  const llmModelLabel = llmStatus && llmStatus.model ? llmStatus.model : '…';
  const llmCredential = !llmStatus
    ? '…'
    : llmStatus.provider === 'mock'
      ? 'Not required · built-in mock provider (no external calls)'
      : llmStatus.configured
        ? 'Configured via LLM_API_KEY (value never exposed to the client)'
        : 'Not configured · deterministic fallback answer in use';

  return (
    <div>
      <PageHeader 
        breadcrumb={['Workspace', 'Settings']}
        title="Settings"
        subtitle="Configure intelligence, retrieval, access, and evaluation for Acme Engineering."
        actions={
          <div style={{ display: 'flex', gap: '10px' }}>
            <select className="select" style={{ width: 'auto', fontWeight: 600 }}>
              <option>Acme Engineering · Workspace settings</option>
            </select>
            <button className="btn btn-secondary">
              <Save size={15} />
              <span>Save changes</span>
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

      {/* Subheader Metadata */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#64748B', marginBottom: '16px' }}>
        <span style={{ color: '#059669', fontWeight: 600 }}>Configuration saved · v12</span>
        <span>Last updated by Alex Shah · Oct 6</span>
      </div>

      {/* Info Callout Banner */}
      <div className="alert-box alert-blue" style={{ marginBottom: '20px' }}>
        <Info size={18} color="#2563EB" style={{ flexShrink: 0 }} />
        <div>
          <strong style={{ display: 'block', marginBottom: '2px', color: '#1E40AF' }}>Workspace-level configuration</strong>
          Changes apply to future runs. Existing answers and reports retain their original model, retrieval configuration, and source snapshot for reproducibility.
        </div>
      </div>

      {/* 4 Rows of 2 Cards Each */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '40px' }}>
        {/* ROW 1: LLM Settings & RAG Settings */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Card 1: LLM Settings */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2px' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>LLM settings</h3>
              <span className={`badge ${llmBadge.className}`}>{llmBadge.label}</span>
            </div>
            <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '14px' }}>Grounded synthesis and specialist reasoning</div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Provider</label>
                <select className="select" style={{ fontSize: '0.8rem' }}><option>{llmProviderLabel}</option></select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Model</label>
                <select className="select" style={{ fontSize: '0.8rem' }}><option>{llmModelLabel}</option></select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Temperature</label>
                <input type="text" className="input" defaultValue="0.2" style={{ fontSize: '0.8rem' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Max output tokens</label>
                <input type="text" className="input" defaultValue="4,096" style={{ fontSize: '0.8rem' }} />
              </div>
            </div>

            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>API credential</label>
              <div style={{ position: 'relative' }}>
                <input type="text" className="input" value={llmCredential} readOnly style={{ fontSize: '0.8rem', paddingRight: '30px' }} />
                <Lock size={14} color="#94A3B8" style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)' }} />
              </div>
              {llmStatusError && (
                <div style={{ fontSize: '0.7rem', color: '#DC2626', marginTop: '4px' }}>{llmStatusError}</div>
              )}
              {!llmStatusError && llmStatus && (
                <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '4px' }}>{llmStatus.message}</div>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Require evidence for material claims</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Include claim-level source citations in answers and reports</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={llmEvidence} onChange={(e) => setLlmEvidence(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Stream answers</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Show grounded output as it is generated</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={llmStream} onChange={(e) => setLlmStream(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '10px', borderTop: '1px solid #F1F5F9' }}>
              <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Timeout 30 s · Retry limit 2</span>
              <button className="btn btn-secondary btn-sm" onClick={loadLlmStatus}><Zap size={12} /> ⚡ Test model</button>
            </div>
          </div>

          {/* Card 2: RAG Settings */}
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '2px' }}>RAG settings</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '14px' }}>Permission-aware retrieval across GitHub and Gmail</div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Retrieval strategy</label>
                <select className="select" style={{ fontSize: '0.8rem' }}><option>Hybrid · Dense + sparse</option></select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Top K</label>
                <input type="text" className="input" defaultValue="8 chunks" style={{ fontSize: '0.8rem' }} />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Chunk size</label>
                <input type="text" className="input" defaultValue="512 tokens" style={{ fontSize: '0.8rem' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Chunk overlap</label>
                <input type="text" className="input" defaultValue="64 tokens" style={{ fontSize: '0.8rem' }} />
              </div>
            </div>

            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Embedding model</label>
              <select className="select" style={{ fontSize: '0.8rem' }}><option>text-embedding-3-small · 1,536 dimensions</option></select>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Rerank retrieved content</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Rerank up to 40 candidates before selecting top 8</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={ragRerank} onChange={(e) => setRagRerank(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Filter by project and permissions</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Source ACLs and selected project are mandatory filters</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={ragFilter} onChange={(e) => setRagFilter(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>

            <div style={{ fontSize: '0.7rem', color: '#64748B', paddingTop: '10px', borderTop: '1px solid #F1F5F9' }}>
              Similarity threshold 0.72 · Preserve source timestamps · Cite original record IDs
            </div>
          </div>
        </div>

        {/* ROW 2: Vector DB & MCP Connection Settings */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Card 1: Vector DB Settings */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2px' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Vector database settings</h3>
              <span className="badge badge-green">Healthy</span>
            </div>
            <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '14px' }}>Qdrant is the workspace vector database</div>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Endpoint</label>
              <input type="text" className="input" defaultValue="https://qdrant.internal:6333" style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }} />
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Collection</label>
              <input type="text" className="input" defaultValue="knowledgeops_projects" style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Vector size</label>
                <input type="text" className="input" defaultValue="1,536 dimensions" style={{ fontSize: '0.8rem' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Distance metric</label>
                <select className="select" style={{ fontSize: '0.8rem' }}><option>Cosine</option></select>
              </div>
            </div>

            <div style={{ fontSize: '0.725rem', color: '#475569', marginBottom: '12px' }}>
              Payload indexes: <code>project_id</code> · <code>source</code> · <code>access_roles</code>
            </div>

            <div style={{ fontSize: '0.725rem', color: '#475569', marginBottom: '14px' }}>
              Backup policy: Daily · 30-day retention
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '10px', borderTop: '1px solid #F1F5F9' }}>
              <span style={{ fontSize: '0.7rem', color: '#64748B' }}>TLS enabled · API key stored in vault</span>
              <button className="btn btn-secondary btn-sm"><Zap size={12} /> ⚡ Test Qdrant</button>
            </div>
          </div>

          {/* Card 2: MCP Connection Settings */}
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '2px' }}>MCP connection settings</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '14px' }}>
              Only GitHub and Gmail are enabled for this workspace
              {mcpStatus ? ` · ${mcpStatus.mode} · ${mcpStatus.data_source}` : ''}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '14px' }}>
              <div style={{ padding: '8px 10px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.775rem' }}>
                  <GitHubIcon size={16} />
                  <strong>GitHub</strong>
                  <span style={{ color: '#64748B' }}>
                    {mcpStatus?.github?.endpoint || 'not configured'}
                  </span>
                </div>
                <span className={`badge ${mcpBadge(mcpStatus?.github || {}).className}`}>
                  {mcpBadge(mcpStatus?.github || {}).label}
                </span>
              </div>

              <div style={{ padding: '8px 10px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.775rem' }}>
                  <GmailIcon size={16} />
                  <strong>Gmail</strong>
                  <span style={{ color: '#64748B' }}>
                    {mcpStatus?.gmail?.endpoint || 'not configured'}
                  </span>
                </div>
                <span className={`badge ${mcpBadge(mcpStatus?.gmail || {}).className}`}>
                  {mcpBadge(mcpStatus?.gmail || {}).label}
                </span>
              </div>
              {mcpStatusError && (
                <div style={{ fontSize: '0.7rem', color: '#DC2626' }}>{mcpStatusError}</div>
              )}
              {!mcpStatusError && mcpStatus && (
                <div style={{ fontSize: '0.7rem', color: '#64748B' }}>{mcpStatus.detail}</div>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Sync interval</label>
                <select className="select" style={{ fontSize: '0.8rem' }}><option>Every 5 minutes</option></select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Tool timeout</label>
                <select className="select" style={{ fontSize: '0.8rem' }}><option>10 seconds</option></select>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
              <div>
                <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Require approval for source actions</strong>
                <span style={{ fontSize: '0.7rem', color: '#64748B' }}>No automatic GitHub mutations or Gmail sends</span>
              </div>
              <label className="toggle-switch">
                <input type="checkbox" checked={mcpApproval} onChange={(e) => setMcpApproval(e.target.checked)} />
                <span className="toggle-slider"></span>
              </label>
            </div>

            <div 
              onClick={() => navigateTo('mcp')}
              style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}
            >
              Manage MCP Connections →
            </div>
          </div>
        </div>

        {/* ROW 3: User Settings & Security */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Card 1: User Settings */}
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '2px' }}>User settings</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '14px' }}>Your profile and workspace preferences</div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: '#DDD6FE', color: '#7C3AED', fontWeight: 700, fontSize: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                AS
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A' }}>Alex Shah</div>
                <div style={{ fontSize: '0.7rem', color: '#64748B' }}>Project Manager · Workspace admin</div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Name</label>
                <input type="text" className="input" defaultValue="Alex Shah" style={{ fontSize: '0.8rem' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Email</label>
                <input type="email" className="input" defaultValue="alex.shah@acme.com" style={{ fontSize: '0.8rem' }} />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Timezone</label>
                <select className="select" style={{ fontSize: '0.8rem' }}><option>America/New_York</option></select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Default project</label>
                <select className="select" style={{ fontSize: '0.8rem' }}><option>All projects</option></select>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Release-risk notifications</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Notify when a high-priority risk changes</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={userNotify} onChange={(e) => setUserNotify(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Daily intelligence digest</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Send a project summary at 9:00 AM</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={userDigest} onChange={(e) => setUserDigest(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
          </div>

          {/* Card 2: Security */}
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '2px' }}>Security</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '14px' }}>Workspace access, sessions, and auditability</div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Enforce enterprise SSO</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>SAML 2.0 · acme.com identity domain</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={secSSO} onChange={(e) => setSecSSO(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Require multi-factor authentication</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Required for administrators and project managers</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={secMFA} onChange={(e) => setSecMFA(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Role-based access control</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Admin · Project Manager · Viewer</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={secRBAC} onChange={(e) => setSecRBAC(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Sensitive-data redaction</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Strip secrets and personal identifiers before LLM calls</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={secRedact} onChange={(e) => setSecRedact(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>

            <div style={{ fontSize: '0.7rem', color: '#64748B', display: 'flex', flexDirection: 'column', gap: '2px', marginBottom: '10px' }}>
              <div>Session timeout: 8 hours</div>
              <div>Audit log retention: 90 days</div>
              <div>Data encryption: in transit + at rest</div>
            </div>

            <div style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}>
              View access and audit log →
            </div>
          </div>
        </div>

        {/* ROW 4: Evaluation Configuration */}
        <div className="card">
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '2px' }}>Evaluation configuration</h3>
          <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '14px' }}>Reproducible demo benchmarks and review thresholds</div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '14px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Benchmark dataset</label>
                <select className="select" style={{ fontSize: '0.8rem' }}>
                  <option>{evalOverview.dataset} · {evalOverview.questionsCount} questions</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Comparison baseline</label>
                <select className="select" style={{ fontSize: '0.8rem' }}>
                  <option>Single-pass Baseline RAG · not configured (N/A)</option>
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Freeze source snapshot</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>
                    {ghSnapshotIso
                      ? `${shortDate(ghSnapshotIso)} · ${timeOnly(ghSnapshotIso)} · GitHub + Gmail`
                      : 'N/A — not synced · GitHub + Gmail'}
                  </span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={evalFreeze} onChange={(e) => setEvalFreeze(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Retrieval precision target</label>
                  <input type="text" className="input" defaultValue="≥ 85%" style={{ fontSize: '0.8rem' }} />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Answer accuracy target</label>
                  <input type="text" className="input" defaultValue="≥ 90%" style={{ fontSize: '0.8rem' }} />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Evidence accuracy target</label>
                  <input type="text" className="input" defaultValue="≥ 90%" style={{ fontSize: '0.8rem' }} />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>Response time budget</label>
                  <input type="text" className="input" defaultValue="≤ 6.0 seconds" style={{ fontSize: '0.8rem' }} />
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.775rem', color: '#0F172A', display: 'block' }}>Require human review of expected answers</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Version labels and preserve source citations</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={evalReview} onChange={(e) => setEvalReview(e.target.checked)} />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid #F1F5F9', paddingTop: '10px' }}>
            <span style={{ fontSize: '0.7rem', color: '#64748B' }}>Demo scores are illustrative, not validated research results. F1 is calculated from precision and recall.</span>
            <span 
              onClick={() => navigateTo('evaluation')}
              style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}
            >
              Open Evaluation →
            </span>
          </div>
        </div>
      </div>

      {/* Bottom Sticky Action Bar */}
      <div style={{
        position: 'sticky',
        bottom: '16px',
        background: '#FFFFFF',
        padding: '14px 20px',
        borderRadius: '8px',
        border: '1px solid #E2E8F0',
        boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        zIndex: 8
      }}>
        <div style={{ fontSize: '0.775rem', color: '#64748B' }}>
          No unsaved changes · Applies to future runs only
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary btn-sm">Reset to saved</button>
          <button className="btn btn-primary btn-sm">💾 Save changes</button>
        </div>
      </div>
    </div>
  );
}
