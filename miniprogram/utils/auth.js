function getLoginState() {
  return {
    loggedIn: false,
    userInfo: null
  };
}

module.exports = {
  getLoginState
};
