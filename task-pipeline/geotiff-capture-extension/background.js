/**
 * background.js — Service Worker
 *
 * Handles tile fetching on behalf of the content script.
 * Service workers have no CORS restrictions when fetching
 * resources, which is why we route all tile requests here.
 *
 * Also caches tiles aggressively so repeated captures of
 * the same AOI are fast.
 */

// In-memory tile cache: tileKey → { data: ArrayBuffer, mime, timestamp }
// Keyed by full URL to maximise cache hits across sessions
const tileCache = new Map();
const CACHE_TTL_MS = 15 * 60 * 1000; // 15 minutes

/**
 * Fetch a single tile and return as base64-encoded string.
 * Uses the cache to avoid redundant network requests.
 */
async function fetchTile(url) {
  const now = Date.now();

  // Check in-memory cache first
  if (tileCache.has(url)) {
    const entry = tileCache.get(url);
    if (now - entry.timestamp < CACHE_TTL_MS) {
      return { ok: true, data: entry.base64, mime: entry.mime, fromCache: true };
    }
    tileCache.delete(url);
  }

  try {
    const response = await fetch(url, {
      credentials: 'omit', // public tiles — no cookies needed
      cache: 'force-cache'  // leverage browser HTTP cache
    });

    if (!response.ok) {
      return { ok: false, error: `HTTP ${response.status}` };
    }

    const mime = response.headers.get('content-type') || 'image/jpeg';
    const buffer = await response.arrayBuffer();
    const base64 = bufferToBase64(buffer);

    // Store in cache
    tileCache.set(url, { base64, mime, timestamp: now });

    return { ok: true, data: base64, mime, fromCache: false };

  } catch (err) {
    return { ok: false, error: err.message };
  }
}

/**
 * Convert ArrayBuffer to base64 string efficiently.
 * Chunks to avoid call-stack overflow on large tiles.
 */
function bufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const CHUNK = 0x8000; // 32KB chunks
  let binary = '';
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

/**
 * Fetch multiple tiles in parallel with a concurrency cap.
 * Returns a map of url → result.
 */
async function fetchTilesBatch(urls, concurrency = 6) {
  const results = {};
  const queue = [...urls];

  async function worker() {
    while (queue.length > 0) {
      const url = queue.shift();
      results[url] = await fetchTile(url);
    }
  }

  const workers = Array.from({ length: Math.min(concurrency, urls.length) }, worker);
  await Promise.all(workers);
  return results;
}

// ─── Message Handler ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {

  if (msg.type === 'FETCH_TILE') {
    fetchTile(msg.url).then(sendResponse);
    return true; // Keep channel open for async
  }

  if (msg.type === 'FETCH_TILES_BATCH') {
    fetchTilesBatch(msg.urls).then(results => sendResponse({ results }));
    return true;
  }

  if (msg.type === 'CLEAR_TILE_CACHE') {
    tileCache.clear();
    sendResponse({ ok: true, message: 'Cache cleared' });
    return true;
  }

  if (msg.type === 'CACHE_STATS') {
    sendResponse({
      ok: true,
      count: tileCache.size,
      urls: [...tileCache.keys()].slice(0, 10) // first 10 for debug
    });
    return true;
  }
});

console.log('[MapGeoCapture] Background service worker ready.');
