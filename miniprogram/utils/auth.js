const AUTH_STORAGE_KEY = 'marketpulse:auth';

function getWxApi() {
  if (typeof wx === 'undefined') {
    return null;
  }
  return wx;
}

function normalizeUserInfo(userInfo) {
  const source = userInfo || {};
  return {
    avatarUrl: source.avatarUrl || '',
    nickName: source.nickName || ''
  };
}

function hasCompleteUserInfo(userInfo) {
  return Boolean(userInfo && userInfo.avatarUrl && userInfo.nickName);
}

function getStoredAuth(wxApi) {
  if (!wxApi || !wxApi.getStorageSync) {
    return null;
  }

  try {
    return wxApi.getStorageSync(AUTH_STORAGE_KEY) || null;
  } catch (error) {
    return null;
  }
}

function setStoredAuth(authState, wxApi) {
  if (!wxApi || !wxApi.setStorageSync) {
    return;
  }

  wxApi.setStorageSync(AUTH_STORAGE_KEY, authState);
}

function clearLoginState(wxApi = getWxApi()) {
  if (!wxApi || !wxApi.removeStorageSync) {
    return;
  }

  wxApi.removeStorageSync(AUTH_STORAGE_KEY);
}

function getLoginState(wxApi = getWxApi()) {
  const storedAuth = getStoredAuth(wxApi);
  const userInfo = normalizeUserInfo(storedAuth && storedAuth.userInfo);
  const loggedIn = Boolean(storedAuth && storedAuth.loginAt && hasCompleteUserInfo(userInfo));

  return {
    loggedIn,
    userInfo: loggedIn ? userInfo : null
  };
}

function runWxLogin(wxApi) {
  return new Promise((resolve, reject) => {
    if (!wxApi || !wxApi.login) {
      reject(new Error('微信登录能力不可用'));
      return;
    }

    wxApi.login({
      success(result) {
        if (result && result.code) {
          resolve(result.code);
          return;
        }
        reject(new Error('微信登录失败'));
      },
      fail(error) {
        reject(error || new Error('微信登录失败'));
      }
    });
  });
}

function loginWithUserInfo(userInfo, wxApi = getWxApi()) {
  const normalizedUserInfo = normalizeUserInfo(userInfo);
  if (!hasCompleteUserInfo(normalizedUserInfo)) {
    return Promise.reject(new Error('请先选择头像并填写昵称'));
  }

  return runWxLogin(wxApi).then((loginCode) => {
    const authState = {
      loginAt: Date.now(),
      userInfo: normalizedUserInfo
    };
    setStoredAuth(authState, wxApi);

    return {
      loggedIn: true,
      loginCode,
      userInfo: normalizedUserInfo
    };
  });
}

module.exports = {
  AUTH_STORAGE_KEY,
  clearLoginState,
  getLoginState,
  loginWithUserInfo,
  normalizeUserInfo
};
