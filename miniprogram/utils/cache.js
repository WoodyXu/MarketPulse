const CACHE_PREFIX = 'marketpulse';

function buildCacheKey(type, section) {
  return `${CACHE_PREFIX}:${type}:${section}`;
}

module.exports = {
  CACHE_PREFIX,
  buildCacheKey
};
