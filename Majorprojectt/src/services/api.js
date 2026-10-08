const API_BASE = '/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function postQuery(question, sourceFilter = null, projectFilter = null) {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      source_filter: sourceFilter,
      project_filter: projectFilter
    })
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to analyze project query');
  }
  return res.json();
}

export async function ingestDemoData() {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force_reindex: true })
  });
  if (!res.ok) throw new Error('Failed to ingest enterprise demo data');
  return res.json();
}

export async function fetchConnectors() {
  const res = await fetch(`${API_BASE}/connectors`);
  if (!res.ok) throw new Error('Failed to fetch connectors status');
  return res.json();
}

export async function fetchMcpStatus() {
  const res = await fetch(`${API_BASE}/mcp/status`);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to fetch MCP status');
  }
  return res.json();
}

export async function fetchRagStatus() {
  const res = await fetch(`${API_BASE}/rag/status`);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to fetch RAG status');
  }
  return res.json();
}

export async function fetchLlmStatus() {
  const res = await fetch(`${API_BASE}/llm/status`);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to fetch LLM status');
  }
  return res.json();
}

export async function indexRag(forceReindex = false) {
  const res = await fetch(`${API_BASE}/rag/index`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force_reindex: forceReindex })
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to index documents');
  }
  return res.json();
}

export async function searchRag(query, projectId = '', topK = null) {
  const res = await fetch(`${API_BASE}/rag/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, project_id: projectId, top_k: topK })
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to search the knowledge index');
  }
  return res.json();
}

export async function executeWorkflowAction(actionData) {
  const res = await fetch(`${API_BASE}/workflow/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(actionData)
  });
  if (!res.ok) throw new Error('Failed to execute workflow action');
  return res.json();
}

export async function fetchAuditLogs() {
  const res = await fetch(`${API_BASE}/audit-logs`);
  if (!res.ok) throw new Error('Failed to fetch audit logs');
  return res.json();
}
