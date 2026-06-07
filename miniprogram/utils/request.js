const cache = require('./cache');

const CLOUD_FUNCTION_NAME = 'getDashboardSection';

function getWxApi() {
  if (typeof wx === 'undefined') {
    return null;
  }
  return wx;
}

function normalizeResponse(result, type, section) {
  const response = result && result.result ? result.result : result;

  if (response && response.error) {
    throw buildRequestError(response.error, 'cloud');
  }

  if (!response || response.type !== type || response.section !== section || !Object.prototype.hasOwnProperty.call(response, 'data')) {
    throw buildRequestError({
      code: 'INVALID_RESPONSE',
      message: '云函数返回的数据结构不符合预期'
    }, 'cloud');
  }

  return {
    type: response.type,
    section: response.section,
    data: response.data
  };
}

function buildRequestError(error, source) {
  const code = error && error.code ? error.code : '';
  const messageByCode = {
    PAYLOAD_NOT_FOUND: '暂无可用数据，请稍后重试',
    PAYLOAD_READ_FAILED: '暂无可用数据，请稍后重试',
    SECTION_DATA_MISSING: '数据结构异常，请稍后重试',
    INVALID_RESPONSE: '数据结构异常，请稍后重试',
    INVALID_SECTION: '数据结构异常，请稍后重试',
    UNAUTHENTICATED: '登录状态失效，请重新登录',
    CLOUD_NOT_CONFIGURED: '云函数暂不可用，请稍后重试'
  };
  const requestError = new Error(messageByCode[code] || (source === 'cache' ? '暂无可用缓存，请重试' : '云函数请求失败，请稍后重试'));
  requestError.code = code || (source === 'cache' ? 'CACHE_UNAVAILABLE' : 'REQUEST_FAILED');
  requestError.cause = error || null;
  return requestError;
}

function callDashboardSection(type, section, options = {}) {
  const wxApi = options.wxApi || getWxApi();

  if (!wxApi || !wxApi.cloud || !wxApi.cloud.callFunction) {
    return Promise.reject(new Error('微信云函数能力不可用'));
  }

  return wxApi.cloud.callFunction({
    name: CLOUD_FUNCTION_NAME,
    data: {
      type,
      section
    }
  }).then((result) => normalizeResponse(result, type, section));
}

function buildResponseFromCache(entry) {
  return {
    type: entry.type,
    section: entry.section,
    data: entry.data
  };
}

function requestDashboardSection(type, section, options = {}) {
  if (!type || !section) {
    return Promise.reject(new Error('请求参数缺少 type 或 section'));
  }

  const cacheOptions = {
    now: options.now,
    wxApi: options.wxApi
  };

  if (!options.forceRefresh) {
    const cachedEntry = cache.getCachedSection(type, section, cacheOptions);
    if (cachedEntry) {
      return Promise.resolve(buildResponseFromCache(cachedEntry));
    }
  }

  return callDashboardSection(type, section, options)
    .then((response) => {
      cache.setCachedSection(type, section, response.data, cacheOptions);
      return response;
    })
    .catch((error) => {
      const cachedEntry = cache.getCachedSection(type, section, cacheOptions);
      if (cachedEntry) {
        return buildResponseFromCache(cachedEntry);
      }

      if (error && error.code) {
        throw error;
      }
      throw buildRequestError(error, 'cloud');
    });
}

module.exports = {
  CLOUD_FUNCTION_NAME,
  buildRequestError,
  callDashboardSection,
  normalizeResponse,
  requestDashboardSection
};
