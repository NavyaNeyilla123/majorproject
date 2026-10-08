// Shared pub/sub for service caches. Services notify after any backend sync so
// screens re-render when API-fed data arrives (single source of truth: FastAPI).
let version = 0;
const listeners = new Set();

export function notifyCacheUpdate() {
  version += 1;
  listeners.forEach((listener) => {
    try {
      listener();
    } catch (err) {
      // listener errors must never break other subscribers
    }
  });
}

export function subscribeCache(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getCacheVersion() {
  return version;
}
