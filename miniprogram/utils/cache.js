const CACHE_PREFIX = 'marketpulse';
const CACHE_TTL_MS = 24 * 60 * 60 * 1000;
const memoryCache = {};

function getWxApi() {
  if (typeof wx === 'undefined') {
    return null;
  }
  return wx;
}

function buildCacheKey(type, section) {
  return `${CACHE_PREFIX}:${type}:${section}`;
}

function normalizeCacheEntry(entry) {
  if (!entry || typeof entry !== 'object') {
    return null;
  }

  if (!entry.type || !entry.section || !entry.cachedAt || !Object.prototype.hasOwnProperty.call(entry, 'data')) {
    return null;
  }

  return {
    cachedAt: Number(entry.cachedAt),
    type: entry.type,
    section: entry.section,
    data: entry.data
  };
}

function isCacheEntryValid(entry, now = Date.now()) {
  const normalizedEntry = normalizeCacheEntry(entry);
  if (!normalizedEntry || !Number.isFinite(normalizedEntry.cachedAt)) {
    return false;
  }

  return now - normalizedEntry.cachedAt <= CACHE_TTL_MS;
}

function readStorageCache(key, wxApi) {
  if (!wxApi || !wxApi.getStorageSync) {
    return null;
  }

  try {
    return wxApi.getStorageSync(key) || null;
  } catch (error) {
    return null;
  }
}

function writeStorageCache(key, entry, wxApi) {
  if (!wxApi || !wxApi.setStorageSync) {
    return;
  }

  wxApi.setStorageSync(key, entry);
}

function removeStorageCache(key, wxApi) {
  if (!wxApi || !wxApi.removeStorageSync) {
    return;
  }

  wxApi.removeStorageSync(key);
}

function getCachedSection(type, section, options = {}) {
  const now = options.now || Date.now();
  const wxApi = options.wxApi || getWxApi();
  const key = buildCacheKey(type, section);
  const memoryEntry = memoryCache[key];

  if (isCacheEntryValid(memoryEntry, now)) {
    return normalizeCacheEntry(memoryEntry);
  }

  delete memoryCache[key];

  const storageEntry = readStorageCache(key, wxApi);
  if (isCacheEntryValid(storageEntry, now)) {
    const normalizedEntry = normalizeCacheEntry(storageEntry);
    memoryCache[key] = normalizedEntry;
    return normalizedEntry;
  }

  return null;
}

function setCachedSection(type, section, data, options = {}) {
  const now = options.now || Date.now();
  const wxApi = options.wxApi || getWxApi();
  const key = buildCacheKey(type, section);
  const entry = {
    cachedAt: now,
    type,
    section,
    data
  };

  memoryCache[key] = entry;
  writeStorageCache(key, entry, wxApi);

  return entry;
}

function clearCachedSection(type, section, options = {}) {
  const wxApi = options.wxApi || getWxApi();
  const key = buildCacheKey(type, section);

  delete memoryCache[key];
  removeStorageCache(key, wxApi);
}

function clearMemoryCache() {
  Object.keys(memoryCache).forEach((key) => {
    delete memoryCache[key];
  });
}

module.exports = {
  CACHE_PREFIX,
  CACHE_TTL_MS,
  buildCacheKey,
  clearCachedSection,
  clearMemoryCache,
  getCachedSection,
  isCacheEntryValid,
  setCachedSection
};
