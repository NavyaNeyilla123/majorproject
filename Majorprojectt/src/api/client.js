const API_BASE_URL = 'http://localhost:8000/api';

// Reachability state shared with the UI so a dead backend produces a visible,
// actionable banner instead of silently rendered empty screens.
let apiStatus = {
  reachable: true,
  error: null,
  endpoint: null,
  checkedAt: null
};
const statusListeners = new Set();

function emitStatus() {
  statusListeners.forEach((listener) => {
    try {
      listener();
    } catch (err) {
      // never let one subscriber break the rest
    }
  });
}

function markSuccess() {
  const changed = !apiStatus.reachable || apiStatus.error !== null;
  apiStatus = { reachable: true, error: null, endpoint: null, checkedAt: Date.now() };
  if (changed) emitStatus();
}

function markFailure(endpoint, message) {
  apiStatus = {
    reachable: false,
    error: message,
    endpoint,
    checkedAt: Date.now()
  };
  emitStatus();
}

export function subscribeApiStatus(listener) {
  statusListeners.add(listener);
  return () => statusListeners.delete(listener);
}

export function getApiStatus() {
  return apiStatus;
}

export async function checkApiHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (!res.ok) throw new Error(`API error ${res.status}`);
    await res.json();
    markSuccess();
    return true;
  } catch (err) {
    markFailure('/health', err.message || 'connection refused');
    return false;
  }
}

export const apiClient = {
  get: async (endpoint) => {
    try {
      const res = await fetch(`${API_BASE_URL}${endpoint}`);
      if (!res.ok) {
        throw new Error(`API error ${res.status}`);
      }
      const data = await res.json();
      markSuccess();
      return data;
    } catch (err) {
      const message = err.message || 'connection failed';
      console.warn(`[FastAPI Client] Fetch failed for ${endpoint}:`, err);
      markFailure(endpoint, message);
      return null;
    }
  },

  post: async (endpoint, data) => {
    try {
      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!res.ok) {
        throw new Error(`API error ${res.status}`);
      }
      const body = await res.json();
      markSuccess();
      return body;
    } catch (err) {
      const message = err.message || 'connection failed';
      console.warn(`[FastAPI Client] POST failed for ${endpoint}:`, err);
      markFailure(endpoint, message);
      return null;
    }
  }
};
