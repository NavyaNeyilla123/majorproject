import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Download, 
  FileCode, 
  AlertTriangle,
  CheckCircle2
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { reportService } from '../services/reportService';
import { apiClient } from '../api/client';
import useCacheTick from '../hooks/useCacheTick';

const SEVERITY_COLORS = {
  High: '#DC2626',
  Medium: '#D97706',
  Low: '#059669'
};

const cite = (refs) => (refs && refs.length ? `[${refs.join(', ')}]` : '');

export default function ReportsScreen({ navigateTo }) {
  const [projectId, setProjectId] = useState('proj-platform-api');
  const [projects, setProjects] = useState([]);
  useCacheTick();

  const report = reportService.getReport();
  const recent = reportService.getRecent();
  const generating = reportService.isGenerating();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const existing = await reportService.sync(projectId);
      if (!cancelled && !existing) {
        await reportService.generate(projectId);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    apiClient.get('/projects').then((data) => {
      if (!cancelled && Array.isArray(data)) {
        setProjects(data.map((p) => ({ id: p.id, name: p.name })));
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const onGenerate = () => {
    reportService.generate(projectId);
  };

  const onExportJson = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${report.report_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const onExportPdf = () => {
    window.print();
  };

  const gRefs = report
    ? report.evidence_citations
        .filter((c) => c.kind === 'Risk' || c.kind === 'Repository snapshot')
        .map((c) => c.index)
    : [];
  const mRefs = report
    ? report.evidence_citations
        .filter((c) => c.kind === 'Email' || c.kind === 'Decision')
        .map((c) => c.index)
    : [];

  return (
    <div>
      <PageHeader 
        breadcrumb={['Workspace', 'Reports']}
        title="Reports"
        subtitle="Evidence-backed project reports, ready for stakeholders and release reviews."
        actions={
          <div style={{ display: 'flex', gap: '10px' }}>
            <select
              className="select"
              style={{ width: 'auto' }}
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
            >
              {(projects.length
                ? projects
                : [{ id: 'proj-platform-api', name: 'Platform API' }]
              ).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>

            <select className="select" style={{ width: 'auto' }}>
              <option>{report ? report.reporting_period : 'Loading…'}</option>
            </select>

            <button
              className="btn btn-primary"
              onClick={onGenerate}
              disabled={generating}
            >
              <Sparkles size={15} />
              <span>{generating ? 'Generating…' : 'Generate Report'}</span>
            </button>

            <button className="btn btn-secondary" onClick={onExportPdf} disabled={!report}>
              <Download size={15} />
              <span>Export PDF</span>
            </button>

            <button className="btn btn-secondary" onClick={onExportJson} disabled={!report}>
              <FileCode size={15} />
              <span>Export JSON</span>
            </button>
          </div>
        }
      />

      {!report ? (
        <div className="card" style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
          {generating
            ? 'Generating report from backend data…'
            : 'No report yet. Click Generate Report to build one from the current dataset.'}
        </div>
      ) : (
      /* Main 2-Column Split */
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '24px' }}>
        {/* Left Column: Full Report Document */}
        <div className="card" style={{ padding: '32px', background: '#FFFFFF' }}>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <span className="badge badge-blue" style={{ fontSize: '0.7rem' }}>AI-GENERATED PROJECT REPORT</span>
            <span className="badge badge-green">{report.status}</span>
          </div>

          <h1 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', marginBottom: '4px' }}>
            {report.title}
          </h1>
          <div style={{ fontSize: '0.775rem', color: '#64748B', marginBottom: '4px' }}>
            Reporting period {report.reporting_period} · Generated {report.generated_at}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#94A3B8', marginBottom: '24px', paddingBottom: '16px', borderBottom: '1px solid #E2E8F0' }}>
            Report {report.report_id} · {report.generated_by} · Snapshot {report.snapshot_time} · Run {report.provenance.agent_run}
          </div>

          {/* Section 1: Executive Summary */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '8px' }}>
              Executive Summary
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#334155', lineHeight: 1.6 }}>
              {report.executive_summary}
            </p>
          </div>

          {/* Section 2: Project Health */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '12px' }}>
              Project Health
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '10px' }}>
              <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', textAlign: 'center' }}>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0F172A' }}>{report.metrics.health_score}</div>
                <div style={{ fontSize: '0.7rem', color: '#64748B' }}>Project health</div>
              </div>

              <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', textAlign: 'center' }}>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0F172A' }}>{report.metrics.open_issues}</div>
                <div style={{ fontSize: '0.7rem', color: '#64748B' }}>Open issues</div>
              </div>

              <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', textAlign: 'center' }}>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0F172A' }}>{report.metrics.active_prs}</div>
                <div style={{ fontSize: '0.7rem', color: '#64748B' }}>Active PRs</div>
              </div>

              <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', textAlign: 'center' }}>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0F172A' }}>{report.metrics.relevant_emails}</div>
                <div style={{ fontSize: '0.7rem', color: '#64748B' }}>Relevant emails</div>
              </div>
            </div>

            <div style={{ fontSize: '0.725rem', color: '#64748B' }}>
              Project scope: {report.project_scope}. Workspace context: {report.workspace_context}. Health score is a dataset project field, not a release approval.
            </div>
          </div>

          {/* Section 3: Major Risks */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '10px' }}>
              Major Risks
            </h3>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Risk</th>
                    <th>Impact</th>
                    <th>Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {report.major_risks.map((r, idx) => (
                    <tr key={idx}>
                      <td><strong>{r.risk}</strong></td>
                      <td>
                        <span style={{ color: SEVERITY_COLORS[r.impact_severity] || '#475569', fontWeight: 600 }}>
                          {r.impact_severity}
                        </span> · {r.impact}
                      </td>
                      <td>{r.evidence} {r.refs && r.refs.length > 0 && <span style={{ color: '#2563EB' }}>{cite(r.refs)}</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 4: Release Blockers */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '10px' }}>
              Release Blockers
            </h3>

            {report.release_blocker ? (
              <div className="alert-box alert-amber">
                <AlertTriangle size={18} color="#D97706" style={{ flexShrink: 0 }} />
                <div>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginBottom: '4px' }}>
                    <span className="badge badge-red" style={{ fontSize: '0.65rem' }}>{report.release_blocker.badge}</span>
                    <strong style={{ color: '#78350F' }}>{report.release_blocker.title}</strong>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: '#92400E', lineHeight: 1.5 }}>
                    {report.release_blocker.description}
                  </p>
                </div>
              </div>
            ) : (
              <div className="alert-box alert-blue">
                <CheckCircle2 size={18} color="#059669" style={{ flexShrink: 0 }} />
                <div>
                  <strong style={{ color: '#065F46' }}>No release blockers detected</strong>
                  <p style={{ fontSize: '0.8rem', color: '#047857', lineHeight: 1.5, margin: 0 }}>
                    No open release-blocking issue or unassigned security review exists for this project in the current dataset.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Section 5: GitHub Analysis */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '8px' }}>
              GitHub Analysis
            </h3>
            <p style={{ fontSize: '0.825rem', color: '#334155', lineHeight: 1.6 }}>
              {report.github_analysis} <span style={{ color: '#2563EB', fontWeight: 600 }}>{cite(gRefs)}</span>
            </p>
          </div>

          {/* Section 6: Gmail Analysis */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '8px' }}>
              Gmail Analysis
            </h3>
            <p style={{ fontSize: '0.825rem', color: '#334155', lineHeight: 1.6 }}>
              {report.gmail_analysis} <span style={{ color: '#2563EB', fontWeight: 600 }}>{cite(mRefs)}</span>
            </p>
          </div>

          {/* Section 7: Cross-Source Findings */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '8px' }}>
              Cross-Source Findings
            </h3>
            <ul style={{ paddingLeft: '18px', fontSize: '0.825rem', color: '#334155', display: 'flex', flexDirection: 'column', gap: '8px', lineHeight: 1.5 }}>
              {report.cross_source_findings.map((f, idx) => (
                <li key={idx}>
                  {f.text} <span style={{ color: '#2563EB', fontWeight: 600 }}>{cite(f.refs)}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Section 8: Recommended Actions */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '10px' }}>
              Recommended Actions
            </h3>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Owner / due</th>
                    <th>Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {report.recommended_actions.map((a, idx) => (
                    <tr key={idx}>
                      <td><strong>{a.action}</strong></td>
                      <td>{a.owner_due}</td>
                      <td>{a.evidence} {a.refs && a.refs.length > 0 && <span style={{ color: '#2563EB' }}>{cite(a.refs)}</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ fontSize: '0.725rem', color: '#64748B', marginTop: '6px' }}>
              {report.recommended_actions.length} proposed project actions · Draft only · No action sent automatically.
            </div>
          </div>

          {/* Section 9: Evidence */}
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '10px' }}>
              Evidence
            </h3>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Citation</th>
                    <th>Source record</th>
                    <th>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {report.evidence_citations.map((c) => (
                    <tr key={c.index}>
                      <td><strong>[{c.index}] {c.kind}</strong></td>
                      <td>{c.record}</td>
                      <td>{c.timestamp}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div 
              onClick={() => navigateTo('evidence')}
              style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, marginTop: '12px', cursor: 'pointer' }}
            >
              Inspect full source excerpts in Evidence Explorer →
            </div>
          </div>
        </div>

        {/* Right Column Sidebars */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Card 1: In this report */}
          <div className="card">
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0F172A', marginBottom: '12px' }}>
              In this report
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.775rem', color: '#475569' }}>
              <div style={{ display: 'flex', gap: '8px' }}><span style={{ color: '#94A3B8' }}>01</span><span>Executive Summary</span></div>
              <div style={{ display: 'flex', gap: '8px' }}><span style={{ color: '#94A3B8' }}>02</span><span>Project Health</span></div>
              <div style={{ display: 'flex', gap: '8px' }}><span style={{ color: '#94A3B8' }}>03</span><span>Major Risks</span></div>
              <div style={{ display: 'flex', gap: '8px' }}><span style={{ color: '#94A3B8' }}>04</span><span>Release Blockers</span></div>
              <div style={{ display: 'flex', gap: '8px' }}><span style={{ color: '#94A3B8' }}>05</span><span>GitHub Analysis</span></div>
              <div style={{ display: 'flex', gap: '8px' }}><span style={{ color: '#94A3B8' }}>06</span><span>Gmail Analysis</span></div>
              <div style={{ display: 'flex', gap: '8px' }}><span style={{ color: '#94A3B8' }}>07</span><span>Cross-Source Findings</span></div>
              <div style={{ display: 'flex', gap: '8px' }}><span style={{ color: '#94A3B8' }}>08</span><span>Recommended Actions</span></div>
              <div style={{ display: 'flex', gap: '8px' }}><span style={{ color: '#94A3B8' }}>09</span><span>Evidence</span></div>
            </div>
          </div>

          {/* Card 2: Report provenance */}
          <div className="card">
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0F172A', marginBottom: '12px' }}>
              Report provenance
            </h4>

            <div style={{ fontSize: '0.75rem', color: '#475569', display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Status:</span>
                <strong style={{ color: '#059669' }}>{report.provenance.status}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Sources:</span>
                <strong>{report.provenance.sources}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Agent run:</span>
                <strong>{report.provenance.agent_run}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Generation:</span>
                <strong>{report.provenance.generation}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>MCP:</span>
                <strong>{report.provenance.mcp}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>RAG:</span>
                <strong>{report.provenance.rag}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>LLM:</span>
                <strong>{report.provenance.llm}</strong>
              </div>
            </div>

            <div style={{ fontSize: '0.7rem', color: '#64748B', marginBottom: '10px' }}>
              {report.provenance.note}
            </div>

            <div 
              onClick={() => navigateTo('workflows')}
              style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}
            >
              View workflow trace →
            </div>
          </div>

          {/* Card 3: Recent reports */}
          <div className="card">
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0F172A', marginBottom: '12px' }}>
              Recent reports
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.775rem' }}>
              {recent.length === 0 && (
                <div style={{ fontSize: '0.725rem', color: '#94A3B8' }}>No reports generated yet.</div>
              )}
              {recent.slice(0, 3).map((r, idx) => (
                <div
                  key={r.report_id}
                  style={{
                    padding: '8px 10px',
                    background: idx === 0 ? '#EFF6FF' : '#F8FAFC',
                    borderRadius: '6px',
                    border: idx === 0 ? '1px solid #BFDBFE' : 'none'
                  }}
                >
                  <div style={{ fontWeight: idx === 0 ? 700 : 600, color: idx === 0 ? '#1E40AF' : '#0F172A' }}>
                    {r.title}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: idx === 0 ? '#3B82F6' : '#64748B' }}>
                    {r.generated_at} · {idx === 0 ? 'Current' : r.status}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
