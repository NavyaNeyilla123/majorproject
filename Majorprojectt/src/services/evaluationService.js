import { apiClient } from '../api/client';
import { notifyCacheUpdate } from './cacheStore';

// Single source of truth: FastAPI /api/evaluation. The backend derives the
// question list, counts and metrics; no dataset JSON is read in the frontend.
const NO_RUN_STATE = {
  status: 'no_run',
  dataset: 'KnowledgeOps release-readiness eval set',
  questionsCount: 0,
  snapshotDate: '—',
  executedAt: null,
  message: 'No evaluation run completed',
  metrics: {
    precision: null,
    recall: null,
    f1Score: null,
    answerAccuracy: null,
    evidenceAccuracy: null,
    latencySeconds: null,
    failureRate: null,
    satisfaction: null
  },
  metricNotes: {},
  questions: []
};

let cache = NO_RUN_STATE;

export const syncEvaluationFromBackend = async () => {
  const data = await apiClient.get('/evaluation');
  if (data) {
    cache = { ...NO_RUN_STATE, ...data };
    notifyCacheUpdate();
  }
};

syncEvaluationFromBackend();

export const evaluationService = {
  fetchEvaluation: () => apiClient.get('/evaluation'),
  sync: syncEvaluationFromBackend,

  refresh: async () => {
    const data = await apiClient.get('/evaluation');
    if (data) {
      cache = { ...NO_RUN_STATE, ...data };
      notifyCacheUpdate();
    }
    return cache;
  },

  runEvaluation: async () => {
    const data = await apiClient.post('/evaluation/run');
    if (data) {
      cache = { ...NO_RUN_STATE, ...data };
      notifyCacheUpdate();
      return { ok: true, overview: cache };
    }
    return { ok: false, overview: cache };
  },

  getOverview: () => cache,

  getTestQuestions: () => cache.questions || []
};
