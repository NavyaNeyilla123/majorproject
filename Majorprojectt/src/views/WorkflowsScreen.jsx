import React, { useState, useEffect, useCallback } from 'react';
import { 
  Sparkles, 
  Play, 
  AlertTriangle, 
  Brain,
  Search,
  Workflow,
  Shield
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { workflowService } from '../services/workflowService';

const STAGE_ICONS = {
  brain: Brain,
  search: Search,
  workflow: Workflow,
  sparkles: Sparkles,
  shield: Shield
};

const STATUS_COLORS = {
  Completed: '#059669',
  Failed: '#EF4444',
  'Not executed': '#94A3B8',
  Skipped: '#94A3B8'
};

export default function WorkflowsScreen({ navigateTo, setQueryResult }) {
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await workflowService.listRuns();
      setRuns(list);
      if (list.length > 0) {
        setSelectedRunId((current) => current && list.some((r) => r.runId === current) ? current : list[0].runId);
      } else {
        setSelectedRunId(null);
        setRun(null);
      }
    } catch (err) {
      setError(err.message || 'Failed to load workflow runs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    if (!selectedRunId) return;
    let cancelled = false;
    workflowService.getWorkflowRun(selectedRunId)
      .then((detail) => { if (!cancelled) setRun(detail); })
      .catch((err) => { if (!cancelled) setError(err.message || 'Failed to load run detail'); });
    return () => { cancelled = true; };
  }, [selectedRunId]);

  const openAnswer = () => {
    if (run && run.asQueryResult && setQueryResult) {
      setQueryResult(run.asQueryResult);
    }
    navigateTo('answer');
  };

  if (loading && !run) {
    return (
      <div>
        <PageHeader
          breadcrumb={['Workspace', 'Workflows', 'Agent Monitoring']}
          title="Workflows / Agent Monitoring"
          subtitle="Follow each agent, inspect run provenance, and review proposed actions before execution."
        />
        <div className="card" style={{ padding: '24px', color: '#64748B', fontSize: '0.85rem' }}>
          Loading agent runs…
        </div>
      </div>
    );
  }

  if (error && !run) {
    return (
      <div>
        <PageHeader
          breadcrumb={['Workspace', 'Workflows', 'Agent Monitoring']}
          title="Workflows / Agent Monitoring"
          subtitle="Follow each agent, inspect run provenance, and review proposed actions before execution."
        />
        <div className="alert-box alert-amber" style={{ marginBottom: '16px' }}>
          <AlertTriangle size={18} color="#D97706" style={{ flexShrink: 0 }} />
          <div>
            <strong style={{ display: 'block', marginBottom: '2px' }}>Could not load workflow runs</strong>
            {error}
          </div>
        </div>
        <button className="btn btn-secondary" onClick={loadRuns}>Retry</button>
      </div>
    );
  }

  if (!run) {
    return (
      <div>
        <PageHeader
          breadcrumb={['Workspace', 'Workflows', 'Agent Monitoring']}
          title="Workflows / Agent Monitoring"
          subtitle="Follow each agent, inspect run provenance, and review proposed actions before execution."
          actions={
            <button onClick={() => navigateTo('ask')} className="btn btn-primary">
              <Sparkles size={15} />
              <span>Ask KnowledgeOps</span>
            </button>
          }
        />
        <div className="card" style={{ padding: '24px', textAlign: 'center', color: '#64748B' }}>
          <div style={{ fontWeight: 700, color: '#0F172A', marginBottom: '6px' }}>No workflow run available</div>
          <div style={{ fontSize: '0.8rem', marginBottom: '14px' }}>
            Ask a question in Ask KnowledgeOps to execute the Planner → Retrieval → Analysis → LLM → Workflow → Evidence pipeline. Every run is stored with its real run ID.
          </div>
          <button className="btn btn-primary" onClick={() => navigateTo('ask')}>
            <Sparkles size={15} />
            <span>Ask KnowledgeOps</span>
          </button>
        </div>
      </div>
    );
  }

  const totalStages = run.stages.length;

  return (
    <div>
      <PageHeader 
        breadcrumb={['Workspace', 'Workflows', 'Agent Monitoring']}
        title="Workflows / Agent Monitoring"
        subtitle="Follow each agent, inspect run provenance, and review proposed actions before execution."
        actions={
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary" onClick={() => navigateTo('ask')}>
              <Play size={15} />
              <span>Run workflow</span>
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

      {error && (
        <div className="alert-box alert-amber" style={{ marginBottom: '16px' }}>
          <AlertTriangle size={18} color="#D97706" style={{ flexShrink: 0 }} />
          <div>{error}</div>
        </div>
      )}

      {/* Flow Selector Header Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <select 
            className="select" 
            style={{ fontSize: '0.85rem', fontWeight: 700, minWidth: '320px' }}
            value={selectedRunId || ''}
            onChange={(e) => setSelectedRunId(e.target.value)}
          >
            {runs.map((item) => (
              <option key={item.runId} value={item.runId}>
                {item.runId} · {item.project || 'Agent run'} · {item.timestamp}
              </option>
            ))}
          </select>
          <span className={`badge ${run.statusType === 'green' ? 'badge-green' : 'badge-red'}`}>{run.status}</span>
          <span className="badge badge-amber">{run.actionsAwaitingCount} actions awaiting approval</span>
        </div>
        <span style={{ fontSize: '0.75rem', color: '#64748B' }}>{run.timestamp}</span>
      </div>

      {/* Main Sequential Multi-Agent Workflow Visualizer */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#0F172A' }}>Sequential multi-agent workflow</h3>
        </div>
        <div style={{ fontSize: '0.75rem', color: '#64748B', marginBottom: '14px' }}>
          Selected run {run.runId} · {totalStages} stages · {run.totalTime} end-to-end
        </div>

        {/* Question Prompt Callout */}
        <div style={{ padding: '10px 14px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', fontSize: '0.8rem', color: '#334155', marginBottom: '20px' }}>
          <strong>Question:</strong> {run.question}
        </div>

        {/* Agent Cards Flow Container */}
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${totalStages}, 1fr)`, gap: '10px', position: 'relative', marginBottom: '20px' }}>
          {run.stages.map((stage) => {
            const Icon = STAGE_ICONS[stage.icon] || Workflow;
            const statusColor = STATUS_COLORS[stage.status] || '#64748B';
            return (
              <div key={stage.id} style={{ padding: '12px', background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '8px', position: 'relative' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '0.8rem', color: '#0F172A' }}>
                    <Icon size={14} color="#2563EB" />
                    <span>{stage.agent}</span>
                  </div>
                </div>
                <div style={{ fontSize: '0.675rem', color: statusColor, fontWeight: 600, marginBottom: '6px' }}>• {stage.status}</div>
                <div style={{ fontSize: '0.725rem', color: '#64748B', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div><strong style={{ color: '#0F172A' }}>Task:</strong> {stage.task}</div>
                  <div><strong style={{ color: '#0F172A' }}>Input:</strong> {stage.input}</div>
                  <div><strong style={{ color: '#0F172A' }}>Output:</strong> {stage.output}</div>
                  <div><strong style={{ color: '#0F172A' }}>Start:</strong> {stage.startedAt} · <strong style={{ color: '#0F172A' }}>End:</strong> {stage.endedAt}</div>
                  {stage.error && (
                    <div style={{ color: '#EF4444', fontWeight: 600 }}>Error: {stage.error}</div>
                  )}
                  <div style={{ marginTop: '4px', color: '#2563EB', fontWeight: 700 }}>Execution: {stage.duration}</div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Warning Alert Box */}
        <div className="alert-box alert-amber">
          <AlertTriangle size={18} color="#D97706" style={{ flexShrink: 0 }} />
          <div>
            <strong style={{ display: 'block', marginBottom: '2px', color: '#78350F' }}>Completed reasoning does not mean actions were executed</strong>
            The Workflow Agent drafted {run.actionsAwaitingCount} project actions. Human approval is required; no GitHub changes or Gmail messages were sent.
          </div>
        </div>
      </div>

      {/* Middle Section: Run Provenance & Outputs */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
        {/* Run Provenance */}
        <div className="card">
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '14px' }}>Run provenance</h3>

          <div style={{ fontSize: '0.775rem', color: '#475569', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Run ID:</span>
              <strong style={{ color: '#0F172A' }}>{run.runId}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Triggered by:</span>
              <strong style={{ color: '#0F172A' }}>{run.provenance.triggeredBy}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Started → completed:</span>
              <strong style={{ color: '#0F172A' }}>{run.provenance.timeSpan}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Project:</span>
              <strong style={{ color: '#0F172A' }}>{run.provenance.projectSnapshot}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Retrieval configuration:</span>
              <strong style={{ color: '#0F172A' }}>{run.provenance.retrievalConfig}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Model usage:</span>
              <strong style={{ color: '#0F172A' }}>{run.provenance.modelUsage}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Evidence records:</span>
              <strong style={{ color: '#0F172A' }}>{run.provenance.evidenceCount}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Usage:</span>
              <strong style={{ color: '#0F172A' }}>{run.provenance.tokenUsage}</strong>
            </div>
          </div>
        </div>

        {/* Outputs and Action Review */}
        <div className="card">
          <div style={{ marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Outputs and action review</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B' }}>Claim-level citations retained across all artifacts</div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem', marginBottom: '16px' }}>
            <div 
              onClick={openAnswer}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', background: '#F8FAFC', borderRadius: '6px', cursor: 'pointer' }}
            >
              <span style={{ fontWeight: 600, color: '#0F172A' }}>Evidence-based answer</span>
              <span style={{ color: '#2563EB', fontWeight: 600 }}>Open →</span>
            </div>

            <div 
              onClick={() => navigateTo('evidence')}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', background: '#F8FAFC', borderRadius: '6px', cursor: 'pointer' }}
            >
              <span style={{ fontWeight: 600, color: '#0F172A' }}>{run.project || 'Project'} · {run.evidence.length} evidence records</span>
              <span style={{ color: '#2563EB', fontWeight: 600 }}>Open →</span>
            </div>
          </div>

          <div style={{ padding: '10px', background: '#FFFBEB', borderRadius: '6px', border: '1px solid #FDE68A', fontSize: '0.75rem', marginBottom: '14px' }}>
            <div style={{ fontWeight: 700, color: '#78350F', marginBottom: '4px' }}>Proposed Actions (draft only):</div>
            <ul style={{ paddingLeft: '16px', color: '#92400E', display: 'flex', flexDirection: 'column', gap: '2px' }}>
              {run.recommendedActions.length > 0 ? run.recommendedActions.map((action, index) => (
                <li key={index}>{action}</li>
              )) : <li>No actions were drafted for this run</li>}
            </ul>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-primary btn-sm" style={{ flex: 1 }} onClick={openAnswer}>
              Review {run.actionsAwaitingCount} actions
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => navigateTo('ask')}>Ask again</button>
          </div>
        </div>
      </div>

      {/* Execution Log Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: '24px' }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid #E2E8F0' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Execution log</h3>
          <div style={{ fontSize: '0.725rem', color: '#64748B' }}>Traceable inputs, decisions, and outputs · measured durations</div>
        </div>

        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Elapsed</th>
                <th>Agent</th>
                <th>Event</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {run.executionLogs.map((log, index) => (
                <tr key={index}>
                  <td><strong>{log.elapsed}</strong></td>
                  <td>{log.agent}</td>
                  <td>{log.event}</td>
                  <td>
                    <span className={`badge ${log.resultType === 'green' ? 'badge-green' : log.resultType === 'red' ? 'badge-red' : 'badge-gray'}`}>
                      {log.result}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* System Architecture Diagram Card */}
      <div className="card">
        <div style={{ marginBottom: '16px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>System architecture</h3>
          <div style={{ fontSize: '0.725rem', color: '#64748B' }}>Deployment and data flow · Complementary to the sequential run above</div>
        </div>

        {/* Visual Diagram Box */}
        <div style={{ padding: '20px', background: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0', fontSize: '0.775rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', textAlign: 'center' }}>
            <div style={{ padding: '10px', background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: '6px' }}>
              <strong style={{ color: '#0F172A' }}>USER</strong>
              <div style={{ fontSize: '0.675rem', color: '#64748B' }}>Project manager</div>
            </div>

            <div style={{ padding: '10px', background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: '6px' }}>
              <strong style={{ color: '#2563EB' }}>REACT WEB DASHBOARD</strong>
              <div style={{ fontSize: '0.675rem', color: '#64748B' }}>Question, scope, session</div>
            </div>

            <div style={{ padding: '10px', background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: '6px' }}>
              <strong style={{ color: '#7C3AED' }}>FASTAPI BACKEND</strong>
              <div style={{ fontSize: '0.675rem', color: '#64748B' }}>Orchestration + agents</div>
            </div>

            <div style={{ padding: '10px', background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: '6px' }}>
              <strong style={{ color: '#059669' }}>AGENT PIPELINE</strong>
              <div style={{ fontSize: '0.675rem', color: '#64748B' }}>Planner → Evidence</div>
            </div>
          </div>

          <div style={{ textAlign: 'center', margin: '12px 0', color: '#94A3B8', fontSize: '0.7rem' }}>
            ↓ Planner dispatches to specialists
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', textAlign: 'center', marginBottom: '12px' }}>
            <div style={{ padding: '8px', background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: '6px' }}>
              <strong>RETRIEVAL AGENT</strong>
            </div>
            <div style={{ padding: '8px', background: '#F3E8FF', border: '1px solid #DDD6FE', borderRadius: '6px' }}>
              <strong>ANALYSIS AGENT</strong>
            </div>
            <div style={{ padding: '8px', background: '#FEF3C7', border: '1px solid #FDE68A', borderRadius: '6px' }}>
              <strong>LLM AGENT</strong>
            </div>
            <div style={{ padding: '8px', background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: '6px' }}>
              <strong>WORKFLOW AGENT</strong>
            </div>
            <div style={{ padding: '8px', background: '#F1F5F9', border: '1px solid #CBD5E1', borderRadius: '6px' }}>
              <strong>EVIDENCE AGENT</strong>
            </div>
          </div>

          <div style={{ textAlign: 'center', margin: '12px 0', color: '#94A3B8', fontSize: '0.7rem' }}>
            ↓ Records retrieved from the existing FastAPI service/repository layer (synthetic GitHub + Gmail dataset)
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', textAlign: 'center' }}>
            <div style={{ padding: '8px', background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: '6px' }}>
              <strong>SERVICE / REPOSITORY LAYER</strong>
            </div>
            <div style={{ padding: '8px', background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: '6px' }}>
              <strong>Synthetic JSON dataset</strong>
            </div>
            <div style={{ padding: '8px', background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: '6px' }}>
              <strong>EVIDENCE OUTPUT</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
