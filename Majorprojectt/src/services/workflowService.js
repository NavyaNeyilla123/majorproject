const API_BASE = '/api';

const STAGE_META = {
  'Planner Agent': { icon: 'brain', task: 'Scope release query', input: 'Question + project catalog' },
  'Retrieval Agent': { icon: 'search', task: 'Retrieve records', input: 'Plan + objectives' },
  'Analysis Agent': { icon: 'workflow', task: 'Cross-check signals', input: 'Retrieved records' },
  'LLM Agent': { icon: 'sparkles', task: 'Ground answer with claims', input: 'Analysis + evidence' },
  'Workflow Agent': { icon: 'workflow', task: 'Draft next steps', input: 'Findings + owners' },
  'Evidence Agent': { icon: 'shield', task: 'Attach citations', input: 'Claims + sources' }
};

const STATUS_LABELS = {
  completed: 'Completed',
  failed: 'Failed',
  skipped: 'Not executed'
};

const RESULT_TYPES = {
  completed: 'green',
  failed: 'red',
  skipped: 'gray'
};

function formatDuration(ms) {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.round(ms)} ms`;
}

function formatTimestamp(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  // Valid Intl options only: second accepts 'numeric' | '2-digit' (never '3-digit',
  // which throws "Value out of range for Date.prototype.toLocaleString options").
  return date.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit'
  });
}

function mapStage(stage, index, elapsedMs) {
  const meta = STAGE_META[stage.agent] || { icon: 'workflow', task: stage.agent, input: 'Context' };
  return {
    id: index + 1,
    agent: stage.agent,
    icon: meta.icon,
    status: STATUS_LABELS[stage.status] || stage.status,
    statusType: stage.status,
    task: meta.task,
    input: meta.input,
    output: stage.detail || (stage.error ? stage.error : '—'),
    error: stage.error || null,
    duration: stage.status === 'skipped' ? 'Not executed' : formatDuration(stage.duration_ms || 0),
    durationMs: stage.duration_ms || 0,
    startedAt: stage.started_at ? formatTimestamp(stage.started_at) : '—',
    endedAt: stage.ended_at ? formatTimestamp(stage.ended_at) : '—',
    elapsed: formatDuration(elapsedMs)
  };
}

// Honest model-usage label: never claim a real model ran when the provider is
// mock/deterministic, and never claim an external call happened without one.
function modelUsageLabel(snapshot, llmStatus) {
  if (llmStatus) {
    if (!llmStatus.configured) return 'No model configured — deterministic fallback (no model call)';
    const provider = llmStatus.provider || 'unknown';
    const model = llmStatus.model || 'unknown model';
    if (provider === 'mock') return `${model} · mock provider (deterministic; no external calls)`;
    return `${model} · ${provider} provider`;
  }
  if (snapshot.llm_used) return 'Configured provider used (LLM status unavailable for provider detail)';
  return 'Deterministic fallback (no model call)';
}

function mapRun(snapshot, llmStatus) {
  if (!snapshot) return null;
  let running = 0;
  const stages = (snapshot.stages || []).map((stage, index) => {
    running += stage.duration_ms || 0;
    return mapStage(stage, index, running);
  });
  const executionLogs = stages.map((stage) => ({
    elapsed: stage.elapsed,
    agent: stage.agent.replace(' Agent', ''),
    event: stage.output,
    result: stage.error || stage.status,
    resultType: RESULT_TYPES[stage.statusType] || 'gray'
  }));
  const totalMs = snapshot.total_duration_ms || 0;
  const modelUsage = modelUsageLabel(snapshot, llmStatus);
  return {
    runId: snapshot.run_id,
    question: snapshot.question,
    project: snapshot.project,
    status: snapshot.status === 'completed' ? 'Run complete' : 'Run failed',
    statusType: snapshot.status === 'completed' ? 'green' : 'red',
    actionsAwaitingCount: snapshot.actions_awaiting_count || 0,
    timestamp: formatTimestamp(snapshot.started_at),
    totalTime: formatDuration(totalMs),
    stagesCount: stages.length,
    stages,
    executionLogs,
    answer: snapshot.answer || '',
    risks: snapshot.risks || [],
    blockers: snapshot.blockers || [],
    decisions: snapshot.decisions || [],
    recommendedActions: snapshot.recommended_actions || [],
    evidence: snapshot.evidence || [],
    failedStage: snapshot.failed_stage || null,
    error: snapshot.error || null,
    provenance: {
      triggeredBy: 'Ask KnowledgeOps · API',
      timeSpan: `${formatTimestamp(snapshot.started_at)} → ${formatTimestamp(snapshot.ended_at)}`,
      projectSnapshot: snapshot.project || '—',
      retrievalConfig: 'Synthetic GitHub + Gmail records',
      modelPrompt: modelUsage,
      modelUsage,
      evidenceCount: (snapshot.evidence || []).length,
      tokenUsage: `${(snapshot.evidence || []).length} evidence links · ${stages.length} stages`
    },
    asQueryResult: {
      run_id: snapshot.run_id,
      question: snapshot.question,
      project: snapshot.project,
      answer: snapshot.answer || '',
      risks: snapshot.risks || [],
      blockers: snapshot.blockers || [],
      decisions: snapshot.decisions || [],
      recommended_actions: snapshot.recommended_actions || [],
      action_details: snapshot.action_details || [],
      evidence: snapshot.evidence || [],
      sources: (snapshot.evidence || []).map((item) => item.label),
      trace: snapshot.stages || [],
      target_release: snapshot.target_release || '',
      target_date: snapshot.target_date || '',
      status: snapshot.release_status || '',
      confidence: snapshot.confidence || ''
    }
  };
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function fetchLlmStatusSafe() {
  try {
    return await fetchJson(`${API_BASE}/llm/status`);
  } catch (err) {
    return null;
  }
}

export const workflowService = {
  listRuns: async () => {
    const data = await fetchJson(`${API_BASE}/workflows`);
    return (data.runs || []).map((run) => ({
      runId: run.run_id,
      question: run.question,
      project: run.project,
      status: run.status === 'completed' ? 'Run complete' : 'Run failed',
      statusType: run.status === 'completed' ? 'green' : 'red',
      actionsAwaitingCount: run.actions_awaiting_count || 0,
      timestamp: formatTimestamp(run.started_at),
      totalTime: formatDuration(run.total_duration_ms || 0),
      stagesCount: (run.stages || []).length
    }));
  },

  getWorkflowRun: async (runId) => {
    const [snapshot, llmStatus] = await Promise.all([
      fetchJson(`${API_BASE}/workflows/${encodeURIComponent(runId)}`),
      fetchLlmStatusSafe()
    ]);
    return mapRun(snapshot, llmStatus);
  }
};
