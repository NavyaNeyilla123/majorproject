import { apiClient } from '../api/client';
import { notifyCacheUpdate } from './cacheStore';

// Single source of truth: FastAPI POST /api/reports/generate derives every
// section (summary, risks, actions, citations, provenance) from repositories.
// No dataset JSON is read in the frontend.

let cache = {
  loaded: false,
  generating: false,
  report: null,
  recent: []
};

export const reportService = {
  sync: async (projectId = 'proj-platform-api') => {
    const data = await apiClient.get(
      `/reports/latest?project_id=${encodeURIComponent(projectId)}`
    );
    if (!data) return null;
    cache.report = data.report || null;
    cache.recent = data.recent || [];
    cache.loaded = true;
    notifyCacheUpdate();
    return cache.report;
  },

  generate: async (projectId = 'proj-platform-api') => {
    if (cache.generating) return cache.report;
    cache.generating = true;
    notifyCacheUpdate();
    try {
      const data = await apiClient.post('/reports/generate', {
        project_id: projectId
      });
      if (data && data.report) {
        cache.report = data.report;
        cache.recent = data.recent || [];
      }
      return cache.report;
    } finally {
      cache.generating = false;
      notifyCacheUpdate();
    }
  },

  getReport: () => cache.report,

  getRecent: () => cache.recent.slice(),

  isGenerating: () => cache.generating,

  isLoaded: () => cache.loaded
};
