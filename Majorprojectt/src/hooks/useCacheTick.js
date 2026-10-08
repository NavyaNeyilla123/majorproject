import { useSyncExternalStore } from 'react';
import { subscribeCache, getCacheVersion } from '../services/cacheStore';

// Re-renders the component whenever any service cache updates from the backend.
export default function useCacheTick() {
  return useSyncExternalStore(subscribeCache, getCacheVersion, getCacheVersion);
}
