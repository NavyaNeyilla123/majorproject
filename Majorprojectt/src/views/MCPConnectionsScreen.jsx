import React, { useEffect, useState } from 'react';
import { 
  Sparkles, 
  RefreshCw, 
  Info, 
  Copy, 
  Zap, 
  Settings,
  Database,
  ArrowRight
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { GitHubIcon, GmailIcon, QdrantIcon } from '../components/Icons';
import { fetchMcpStatus, fetchRagStatus } from '../services/api';
import { gmailService } from '../services/gmailService';
import { githubService } from '../services/githubService';
import useCacheTick from '../hooks/useCacheTick';

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function shortDate(iso) {
  if (!iso) return '';
  const [, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}`;
}

export default function MCPConnectionsScreen({ navigateTo }) {
  const [ghSync, setGhSync] = useState(true);
  const [gmSync, setGmSync] = useState(true);
  const [safeguard1, setSafeguard1] = useState(true);
  const [safeguard2, setSafeguard2] = useState(true);
  const [safeguard3, setSafeguard3] = useState(true);
  const [mcpStatus, setMcpStatus] = useState(null);
  const [mcpLoading, setMcpLoading] = useState(true);
  const [mcpError, setMcpError] = useState(null);
  const [ragStatus, setRagStatus] = useState(null);
  const [ragLoading, setRagLoading] = useState(true);
  const [ragError, setRagError] = useState(null);

  const loadMcpStatus = () => {
    setMcpLoading(true);
    setMcpError(null);
    fetchMcpStatus()
      .then((data) => setMcpStatus(data))
      .catch((err) => setMcpError(err.message))
      .finally(() => setMcpLoading(false));
  };

  const loadRagStatus = () => {
    setRagLoading(true);
    setRagError(null);
    fetchRagStatus()
      .then((data) => setRagStatus(data))
      .catch((err) => setRagError(err.message))
      .finally(() => setRagLoading(false));
  };

  useEffect(() => {
    loadMcpStatus();
    loadRagStatus();
    githubService.sync();
    gmailService.sync();
  }, []);
  useCacheTick();

  const gh = mcpStatus?.github;
  const gm = mcpStatus?.gmail;
  const ghRepos = githubService.getRepositories();
  const ghOpen = githubService.getOpenIssuesCount();
  const ghPrs = githubService.getActivePRsCount();
  const ghConn = githubService.getConnectionStatus();
  const ghLoaded = githubService.isLoaded();
  const gmLoaded = gmailService.isLoaded();
  const ghSyncedIso = ghRepos.map(r => r.synced_at || '').filter(Boolean).sort().pop() || '';
  const gmLatestIso = gmailService.getLatestReceived();
  const gmThreads = gmailService.getThreads();
  const blockerThread = gmThreads.find(t => t.is_release_blocker);
  const connectionBadge = (server) => {
    if (mcpLoading && !mcpStatus) return <span className="badge">Checking…</span>;
    if (!server) return <span className="badge badge-red">Unknown</span>;
    if (server.status === 'mock_connected' && server.healthy) {
      return <span className="badge badge-amber">Mock connected</span>;
    }
    if (server.status === 'unconfigured') return <span className="badge badge-amber">Unconfigured</span>;
    if (server.status === 'unavailable') return <span className="badge badge-red">Unavailable</span>;
    if (server.status === 'error') return <span className="badge badge-red">Error</span>;
    if (server.healthy) return <span className="badge badge-green">Connected</span>;
    return <span className="badge badge-red">Disconnected</span>;
  };

  const ragBadge = () => {
    if (ragLoading && !ragStatus && !ragError) return <span className="badge">Checking…</span>;
    if (ragError) return <span className="badge badge-red">Unavailable</span>;
    if (ragStatus?.status === 'healthy') return <span className="badge badge-green">Connected</span>;
    return <span className="badge badge-red">Unavailable</span>;
  };

  const formatTimestamp = (iso) => {
    if (!iso) return 'Never — not indexed yet';
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  return (
    <div>
      <PageHeader 
        breadcrumb={['Workspace', 'MCP Connections']}
        title="MCP Connections"
        subtitle="Manage the two trusted sources that power project intelligence."
        actions={
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary" onClick={() => { loadMcpStatus(); loadRagStatus(); }}>
              <RefreshCw size={15} />
              <span>Sync now</span>
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

      {/* Info Banner */}
      <div className={`alert-box ${mcpError ? 'alert-red' : 'alert-blue'}`} style={{ marginBottom: '20px' }}>
        <Info size={18} color={mcpError ? '#DC2626' : '#2563EB'} style={{ flexShrink: 0 }} />
        <div>
          {mcpError ? (
            <>
              <strong style={{ display: 'block', marginBottom: '2px', color: '#991B1B' }}>MCP status unavailable</strong>
              {mcpError}
            </>
          ) : (
            <>
              <strong style={{ display: 'block', marginBottom: '2px', color: '#1E40AF' }}>
                {mcpStatus ? `${mcpStatus.mode} · ${mcpStatus.environment} · ${mcpStatus.data_source}` : 'Loading MCP status…'}
              </strong>
              {mcpStatus
                ? `${mcpStatus.detail} Provider: ${mcpStatus.provider}.`
                : 'Querying GET /api/mcp/status for the active MCP provider.'}
            </>
          )}
        </div>
      </div>

      {/* 2 Main Source Connection Cards Side-by-Side */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
        {/* GitHub Card */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <GitHubIcon size={20} />
              <strong style={{ fontSize: '1rem', color: '#0F172A' }}>GitHub</strong>
              <span style={{ fontSize: '0.75rem', color: '#64748B' }}>
                {ghLoaded && ghConn.org ? `${ghConn.org} · GitHub App` : 'GitHub App'}
              </span>
            </div>
            {connectionBadge(gh)}
          </div>

          <p style={{ fontSize: '0.775rem', color: '#64748B', marginBottom: '16px' }}>
            Repository code, issues, pull requests, and review metadata.
          </p>

          <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', fontSize: '0.775rem', display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Indexed content:</span>
              <strong style={{ color: '#0F172A' }}>
                {ghLoaded
                  ? `${ghRepos.length} repos · ${ghOpen} open issues · ${ghPrs} active PRs`
                  : 'Loading…'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Last successful sync:</span>
              <strong style={{ color: '#0F172A' }}>
                {ghLoaded && ghSyncedIso
                  ? `${shortDate(ghSyncedIso)} · ${ghConn.synced}`
                  : 'N/A — not synced'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Health / latency:</span>
              <strong style={{ color: gh?.healthy ? '#059669' : '#DC2626' }}>
                {gh ? `${gh.healthy ? 'Healthy' : 'Unhealthy'} · ${gh.status}` : 'Checking…'}
              </strong>
            </div>
            {gh && !gh.healthy && gh.message && (
              <div style={{ fontSize: '0.7rem', color: '#DC2626' }}>{gh.message}</div>
            )}
          </div>

          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>
              MCP endpoint
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input type="text" className="input" value={gh?.endpoint || '…'} readOnly style={{ fontFamily: 'var(--font-mono)', fontSize: '0.775rem' }} />
              <button className="btn btn-secondary btn-sm"><Copy size={13} /></button>
            </div>
          </div>

          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>
              Retrieval scope
            </label>
            <select className="select" style={{ fontSize: '0.8rem' }}>
              <option>{ghLoaded ? `${ghRepos.length} selected repositories` : 'Loading scope…'}</option>
            </select>
            <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '4px' }}>
              Permissions: Contents: read · Issues: read · Pull requests: read
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderTop: '1px solid #F1F5F9', borderBottom: '1px solid #F1F5F9', marginBottom: '16px' }}>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#0F172A' }}>Automatic synchronization</div>
              <div style={{ fontSize: '0.7rem', color: '#64748B' }}>Incremental sync every 5 minutes</div>
            </div>
            <label className="toggle-switch">
              <input type="checkbox" checked={ghSync} onChange={(e) => setGhSync(e.target.checked)} />
              <span className="toggle-slider"></span>
            </label>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary btn-sm" style={{ flex: 1 }} onClick={loadMcpStatus}>
              <Zap size={13} /> ⚡ Test connection
            </button>
            <button className="btn btn-secondary btn-sm" style={{ flex: 1 }}>
              <Settings size={13} /> ⚙ Configure
            </button>
          </div>
        </div>

        {/* Gmail Card */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <GmailIcon size={20} />
              <strong style={{ fontSize: '1rem', color: '#0F172A' }}>Gmail</strong>
              <span style={{ fontSize: '0.75rem', color: '#64748B' }}>project-inbox@acme.com · OAuth 2.0</span>
            </div>
            {connectionBadge(gm)}
          </div>

          <p style={{ fontSize: '0.775rem', color: '#64748B', marginBottom: '16px' }}>
            Project conversations, release decisions, and action requests.
          </p>

          <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', fontSize: '0.775rem', display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Indexed content:</span>
              <strong style={{ color: '#0F172A' }}>
                {gmLoaded
                  ? `${gmailService.getRelevantEmailCount()} relevant emails · ${gmThreads.length} threads`
                  : 'Loading…'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Latest email received:</span>
              <strong style={{ color: '#0F172A' }}>
                {gmLoaded && gmLatestIso
                  ? `${shortDate(gmLatestIso)} · ${gmailService.getSyncedLabel()}`
                  : 'N/A — not received'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Health / latency:</span>
              <strong style={{ color: gm?.healthy ? '#059669' : '#DC2626' }}>
                {gm ? `${gm.healthy ? 'Healthy' : 'Unhealthy'} · ${gm.status}` : 'Checking…'}
              </strong>
            </div>
            {gm && !gm.healthy && gm.message && (
              <div style={{ fontSize: '0.7rem', color: '#DC2626' }}>{gm.message}</div>
            )}
          </div>

          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>
              MCP endpoint
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input type="text" className="input" value={gm?.endpoint || '…'} readOnly style={{ fontFamily: 'var(--font-mono)', fontSize: '0.775rem' }} />
              <button className="btn btn-secondary btn-sm"><Copy size={13} /></button>
            </div>
          </div>

          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '0.725rem', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>
              Retrieval scope
            </label>
            <select className="select" style={{ fontSize: '0.8rem' }}>
              <option>Project inbox · Labeled conversations</option>
            </select>
            <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '4px' }}>
              Permissions: gmail.readonly · Metadata and selected message bodies
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderTop: '1px solid #F1F5F9', borderBottom: '1px solid #F1F5F9', marginBottom: '16px' }}>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#0F172A' }}>Automatic synchronization</div>
              <div style={{ fontSize: '0.7rem', color: '#64748B' }}>Incremental sync every 5 minutes</div>
            </div>
            <label className="toggle-switch">
              <input type="checkbox" checked={gmSync} onChange={(e) => setGmSync(e.target.checked)} />
              <span className="toggle-slider"></span>
            </label>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary btn-sm" style={{ flex: 1 }} onClick={loadMcpStatus}>
              <Zap size={13} /> ⚡ Test connection
            </button>
            <button className="btn btn-secondary btn-sm" style={{ flex: 1 }}>
              <Settings size={13} /> ⚙ Configure
            </button>
          </div>
        </div>
      </div>

      {/* Middle Row: Retrieval & Index Health vs Safeguards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
        {/* Left Card: Retrieval and Index Health */}
        <div className="card">
          <div style={{ marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Retrieval and index health</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B' }}>Content flows into one permission-aware knowledge index</div>
          </div>

          <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <QdrantIcon size={18} />
                <strong style={{ fontSize: '0.85rem', color: '#0F172A' }}>
                  Qdrant · {ragStatus?.collection || 'knowledgeops_projects'}
                </strong>
              </div>
              {ragBadge()}
            </div>
            <div style={{ fontSize: '0.725rem', color: '#64748B' }}>
              Hybrid retrieval · vector + keyword + metadata
            </div>
            {(ragError || (ragStatus && ragStatus.status !== 'healthy')) && (
              <div style={{ fontSize: '0.7rem', color: '#DC2626', marginTop: '6px' }}>
                {ragError || ragStatus?.message || 'RAG status unavailable'}
              </div>
            )}
          </div>

          <div style={{ fontSize: '0.775rem', color: '#475569', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Indexed content:</span>
              <strong style={{ color: '#0F172A' }}>
                {ragStatus?.documents != null && ragStatus?.chunks != null
                  ? `${ragStatus.documents} documents · ${ragStatus.chunks} chunks`
                  : ragError ? 'Unavailable' : 'Loading…'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Last indexed:</span>
              <strong style={{ color: '#0F172A' }}>
                {ragLoading && !ragStatus && !ragError
                  ? 'Loading…'
                  : ragStatus?.last_indexed
                    ? formatTimestamp(ragStatus.last_indexed)
                    : ragStatus?.documents > 0
                      ? 'Indexed (earlier session)'
                      : 'Never — not indexed yet'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Embedding:</span>
              <strong style={{ color: '#0F172A' }}>
                {ragStatus?.embedding || '…'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Mode / provider:</span>
              <strong style={{ color: '#0F172A' }}>
                {ragStatus ? `${ragStatus.mode} · ${ragStatus.provider}` : '—'}
              </strong>
            </div>
          </div>
        </div>

        {/* Right Card: Connection Safeguards */}
        <div className="card">
          <div style={{ marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Connection safeguards</h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <strong style={{ fontSize: '0.825rem', color: '#0F172A', display: 'block' }}>Honor source permissions</strong>
                <span style={{ fontSize: '0.725rem', color: '#64748B' }}>Enforced for every retrieval request</span>
              </div>
              <label className="toggle-switch">
                <input type="checkbox" checked={safeguard1} onChange={(e) => setSafeguard1(e.target.checked)} />
                <span className="toggle-slider"></span>
              </label>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <strong style={{ fontSize: '0.825rem', color: '#0F172A', display: 'block' }}>Redact sensitive fields</strong>
                <span style={{ fontSize: '0.725rem', color: '#64748B' }}>Secrets and personal identifiers excluded from prompts</span>
              </div>
              <label className="toggle-switch">
                <input type="checkbox" checked={safeguard2} onChange={(e) => setSafeguard2(e.target.checked)} />
                <span className="toggle-slider"></span>
              </label>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <strong style={{ fontSize: '0.825rem', color: '#0F172A', display: 'block' }}>Require approval for workflow actions</strong>
                <span style={{ fontSize: '0.725rem', color: '#64748B' }}>Connections remain read-only for this workspace</span>
              </div>
              <label className="toggle-switch">
                <input type="checkbox" checked={safeguard3} onChange={(e) => setSafeguard3(e.target.checked)} />
                <span className="toggle-slider"></span>
              </label>
            </div>
          </div>

          <div style={{ marginTop: '16px', fontSize: '0.725rem', color: '#64748B', borderTop: '1px solid #F1F5F9', paddingTop: '10px' }}>
            Credentials are encrypted and stored outside the application. Revoke source access at any time from connection settings.
          </div>
        </div>
      </div>

      {/* Bottom Table: Recent Synchronization Activity */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Recent synchronization activity</h3>
          <span style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}>View audit log →</span>
        </div>

        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Source</th>
                <th>Event</th>
                <th>Duration</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>{ghLoaded && ghSyncedIso ? `${shortDate(ghSyncedIso)} · ${ghConn.synced}` : 'N/A'}</strong></td>
                <td>GitHub</td>
                <td>
                  {ghLoaded
                    ? `${ghRepos.length} repositories synchronized · Issues and PRs refreshed`
                    : 'Waiting for GitHub sync…'}
                </td>
                <td>N/A — not measured</td>
                <td>
                  <span className={`badge ${gh?.healthy ? 'badge-green' : gh ? 'badge-red' : 'badge-gray'}`}>
                    {gh ? (gh.healthy ? 'Successful' : gh.status) : 'Checking…'}
                  </span>
                </td>
              </tr>
              <tr>
                <td><strong>{gmLoaded && gmLatestIso ? `${shortDate(gmLatestIso)} · ${gmailService.getSyncedLabel()}` : 'N/A'}</strong></td>
                <td>Gmail</td>
                <td>
                  {gmLoaded
                    ? (blockerThread
                        ? `${blockerThread.subject} added · ${blockerThread.message_count} messages indexed`
                        : `${gmThreads.length} threads · ${gmailService.getRelevantEmailCount()} emails indexed`)
                    : 'Waiting for Gmail sync…'}
                </td>
                <td>N/A — not measured</td>
                <td>
                  <span className={`badge ${gm?.healthy ? 'badge-green' : gm ? 'badge-red' : 'badge-gray'}`}>
                    {gm ? (gm.healthy ? 'Successful' : gm.status) : 'Checking…'}
                  </span>
                </td>
              </tr>
              <tr>
                <td><strong>{ragStatus?.last_indexed ? formatTimestamp(ragStatus.last_indexed) : 'N/A'}</strong></td>
                <td>Qdrant index</td>
                <td>
                  {ragStatus
                    ? `Embeddings updated · ${ragStatus.documents} documents · ${ragStatus.chunks} chunks`
                    : 'Waiting for index status…'}
                </td>
                <td>N/A — not measured</td>
                <td>
                  <span className={`badge ${ragStatus?.status === 'healthy' ? 'badge-green' : ragError ? 'badge-red' : 'badge-gray'}`}>
                    {ragStatus ? (ragStatus.status === 'healthy' ? 'Ready' : ragStatus.status) : 'Checking…'}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
