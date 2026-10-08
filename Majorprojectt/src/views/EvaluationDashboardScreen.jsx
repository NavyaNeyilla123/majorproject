import React, { useEffect, useState } from 'react';
import { 
  Sparkles, 
  Play, 
  Info, 
  Loader2
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { evaluationService } from '../services/evaluationService';

const NA = 'N/A — not measured';

function fmtPct(value) {
  return (value === null || value === undefined) ? 'N/A' : `${Number(value).toFixed(1)}%`;
}

function fmtSeconds(value) {
  return (value === null || value === undefined) ? 'N/A' : `${value} s`;
}

function barWidth(value, max = 100) {
  if (value === null || value === undefined) return 0;
  return Math.max(0, Math.min(100, (Number(value) / max) * 100));
}

export default function EvaluationDashboardScreen({ navigateTo }) {
  const [overview, setOverview] = useState(evaluationService.getOverview());
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    evaluationService.refresh().then((data) => {
      if (!cancelled && data) setOverview(data);
    });
    return () => { cancelled = true; };
  }, []);

  const metrics = overview.metrics || {};
  const questions = overview.questions || [];
  const completed = overview.status === 'completed';

  const handleRun = async () => {
    setRunning(true);
    setRunError(null);
    const result = await evaluationService.runEvaluation();
    setRunning(false);
    if (result.ok) {
      setOverview(result.overview);
    } else {
      setRunError('Evaluation run failed — is the backend running?');
    }
  };

  const metricCards = [
    { label: 'Retrieval Precision', value: fmtPct(metrics.precision) },
    { label: 'Retrieval Recall', value: fmtPct(metrics.recall) },
    { label: 'F1 Score', value: fmtPct(metrics.f1Score) },
    { label: 'Answer Accuracy', value: fmtPct(metrics.answerAccuracy) },
    { label: 'Response Time', value: fmtSeconds(metrics.latencySeconds) },
    { label: 'Evidence Accuracy', value: fmtPct(metrics.evidenceAccuracy) },
    { label: 'User Satisfaction', value: metrics.satisfaction == null ? 'N/A' : `${metrics.satisfaction} / 5` }
  ];

  const chartRows = [
    { label: 'Retrieval Precision', current: metrics.precision },
    { label: 'Retrieval Recall', current: metrics.recall },
    { label: 'F1 Score', current: metrics.f1Score },
    { label: 'Answer Accuracy', current: metrics.answerAccuracy },
    { label: 'Evidence Accuracy', current: metrics.evidenceAccuracy }
  ];

  return (
    <div>
      <PageHeader 
        breadcrumb={['Workspace', 'Evaluation Dashboard']}
        title="Evaluation Dashboard"
        subtitle="Compare retrieval quality, grounded answers, and the trade-offs of multi-agent reasoning."
        actions={
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary" onClick={handleRun} disabled={running}>
              {running ? <Loader2 size={15} /> : <Play size={15} />}
              <span>{running ? 'Running…' : 'Run evaluation'}</span>
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

      {/* Info Callout Banner */}
      <div className="alert-box alert-blue" style={{ marginBottom: '20px' }}>
        <Info size={18} color="#2563EB" style={{ flexShrink: 0 }} />
        <div>
          {completed ? (
            <>
              <strong style={{ display: 'block', marginBottom: '2px', color: '#1E40AF' }}>
                Measured in this environment · run {overview.executedAt || ''}
              </strong>
              Values are measured from a real execution of the {overview.questionsCount} annotated
              questions through the agent pipeline. User satisfaction is not measured (no user study);
              baseline RAG is not configured, so baseline values show N/A.
            </>
          ) : (
            <>
              <strong style={{ display: 'block', marginBottom: '2px', color: '#1E40AF' }}>
                No evaluation run completed
              </strong>
              Metrics show N/A until an evaluation run is executed in this environment.
              Select “Run evaluation” to measure precision, recall, F1, answer accuracy, evidence
              grounding, and latency on the {overview.questionsCount} annotated questions.
            </>
          )}
          {runError && (
            <span style={{ display: 'block', marginTop: '4px', color: '#DC2626' }}>{runError}</span>
          )}
        </div>
      </div>

      {/* Scope Selector Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div style={{ display: 'flex', gap: '12px' }}>
          <select className="select" style={{ fontSize: '0.85rem', fontWeight: 600, minWidth: '320px' }}>
            <option>{overview.dataset}</option>
          </select>
          <select className="select" style={{ fontSize: '0.85rem' }}>
            <option>Snapshot · {overview.snapshotDate}</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '0.75rem', fontWeight: 600 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', background: '#CBD5E1', borderRadius: '2px' }}></span>
            <span style={{ color: '#64748B' }}>Baseline RAG (not measured)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', background: '#2563EB', borderRadius: '2px' }}></span>
            <span style={{ color: '#2563EB' }}>KnowledgeOps AI (measured)</span>
          </div>
        </div>
      </div>

      {/* 7 Top Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '12px', marginBottom: '20px' }}>
        {metricCards.map((card) => (
          <div className="card card-sm" key={card.label}>
            <div style={{ fontSize: '0.7rem', color: '#64748B', marginBottom: '2px' }}>{card.label}</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: card.value === 'N/A' ? '#94A3B8' : '#0F172A' }}>{card.value}</div>
            <div style={{ fontSize: '0.675rem', color: '#64748B', marginTop: '2px' }}>Baseline RAG: N/A</div>
            <div style={{ fontSize: '0.675rem', color: '#64748B', fontWeight: 700 }}>N/A</div>
          </div>
        ))}
      </div>

      {/* Middle Section: Quality Comparison Charts vs Latency & Protocol */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: '20px', marginBottom: '24px' }}>
        {/* Quality Comparison Bar Charts */}
        <div className="card">
          <div style={{ marginBottom: '16px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Quality comparison</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B' }}>Percent (%) · Higher is better · Measured from one run of {overview.questionsCount} annotated questions</div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', fontSize: '0.775rem' }}>
            {chartRows.map((row) => (
              <div key={row.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontWeight: 600 }}>
                  <span>{row.label}</span>
                  <span style={{ color: '#64748B' }}>N/A vs {fmtPct(row.current)}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ width: '0%', height: '8px', background: '#CBD5E1', borderRadius: '4px' }}></div>
                  <div style={{ width: `${barWidth(row.current)}%`, height: '8px', background: '#2563EB', borderRadius: '4px' }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Card: Latency, Satisfaction & Protocol */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: '4px' }}>Latency and satisfaction</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '14px' }}>Same legend as quality chart</div>

            <div style={{ marginBottom: '16px', fontSize: '0.775rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, marginBottom: '4px' }}>
                <span>Response Time · mean seconds</span>
                <span>{fmtSeconds(metrics.latencySeconds)} / N/A</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '4px' }}>
                <div style={{ width: '0%', height: '8px', background: '#CBD5E1', borderRadius: '4px' }}></div>
                <div style={{ width: `${barWidth(metrics.latencySeconds, 6)}%`, height: '8px', background: '#2563EB', borderRadius: '4px' }}></div>
              </div>
              <div style={{ fontSize: '0.7rem', color: '#64748B' }}>Scale: 0-6 seconds · measured mean per question.</div>
            </div>

            <div style={{ marginBottom: '16px', fontSize: '0.775rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, marginBottom: '4px' }}>
                <span>User Satisfaction · rating out of 5</span>
                <span style={{ color: '#94A3B8' }}>{NA}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '4px' }}>
                <div style={{ width: '0%', height: '8px', background: '#CBD5E1', borderRadius: '4px' }}></div>
                <div style={{ width: '0%', height: '8px', background: '#2563EB', borderRadius: '4px' }}></div>
              </div>
              <div style={{ fontSize: '0.7rem', color: '#64748B' }}>N/A — not measured: no user study in this environment.</div>
            </div>
          </div>

          <div style={{ borderTop: '1px solid #F1F5F9', paddingTop: '12px' }}>
            <h4 style={{ fontSize: '0.825rem', fontWeight: 700, color: '#0F172A', marginBottom: '6px' }}>Benchmark protocol</h4>
            <p style={{ fontSize: '0.725rem', color: '#475569', lineHeight: 1.5 }}>
              KnowledgeOps AI: hybrid retrieval, specialist agents, and claim-level citations, measured live via POST /api/evaluation/run. F1 is computed from measured precision and recall. Baseline RAG is not configured in this environment, so baseline values show N/A.
            </p>
          </div>
        </div>
      </div>

      {/* Test Questions and Expected Answers Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Test questions and expected answers</h3>
            <div style={{ fontSize: '0.725rem', color: '#64748B' }}>Annotated cases from the eval set · Expected answers are tied to source records</div>
          </div>
          <span style={{ fontSize: '0.75rem', color: '#2563EB', fontWeight: 600 }}>View {overview.questionsCount} questions →</span>
        </div>

        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Test question</th>
                <th>Expected answer</th>
                <th>Evidence</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {questions.map((q) => (
                <tr key={q.id}>
                  <td><strong>{q.question}</strong></td>
                  <td>{q.expected_answer}</td>
                  <td>{q.evidence_citations.join(' · ')}</td>
                  <td>
                    {q.result ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-start' }}>
                        <span className={`badge ${q.result.correct ? 'badge-green' : 'badge-red'}`}>
                          {q.result.status === 'error' ? 'Run error' : (q.result.correct ? 'Measured: correct' : 'Measured: incorrect')}
                        </span>
                        <span style={{ fontSize: '0.675rem', color: '#64748B' }}>
                          Annotated: {q.result_label} · P {fmtPct(q.result.precision * 100)} · R {fmtPct(q.result.recall * 100)}
                        </span>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-start' }}>
                        <span className="badge badge-gray">Not run</span>
                        <span style={{ fontSize: '0.675rem', color: '#64748B' }}>Annotated: {q.result_label}</span>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ padding: '12px 20px', background: '#F8FAFC', borderTop: '1px solid #E2E8F0', fontSize: '0.725rem', color: '#64748B' }}>
          Annotated labels come from data/evaluation/questions.json ({overview.questionsCount} questions).
          Measured results are produced by running the agent pipeline in this environment and update when you select “Run evaluation”.
          Baseline RAG is not configured, so no baseline comparison is reported.
        </div>
      </div>
    </div>
  );
}
