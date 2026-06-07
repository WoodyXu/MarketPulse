const auth = require('../../utils/auth');

Page({
  data: {
    loginState: auth.getLoginState(),
    authForm: {
      avatarUrl: '',
      nickName: ''
    },
    authError: '',
    authLoading: false,
    boards: [
      {
        title: '资本市场',
        desc: '指数偏离、融资余额、成交金额和成交集中度',
        path: '/pages/ashare/index'
      },
      {
        title: '北京楼市',
        desc: '看房、成交、网签和居民贷款',
        path: '/pages/beijing/index'
      }
    ]
  },

  onLoad() {
    this.refreshLoginState();
  },

  onShow() {
    this.refreshLoginState();
  },

  refreshLoginState() {
    this.setData({
      loginState: auth.getLoginState()
    });
  },

  onChooseAvatar(event) {
    const avatarUrl = event.detail && event.detail.avatarUrl ? event.detail.avatarUrl : '';
    this.setData({
      'authForm.avatarUrl': avatarUrl,
      authError: ''
    });
  },

  onNicknameInput(event) {
    const nickName = event.detail && event.detail.value ? event.detail.value : '';
    this.setData({
      'authForm.nickName': nickName,
      authError: ''
    });
  },

  submitLogin() {
    if (this.data.authLoading) {
      return;
    }

    this.setData({
      authLoading: true,
      authError: ''
    });

    auth.loginWithUserInfo(this.data.authForm)
      .then((loginState) => {
        this.setData({
          loginState,
          authLoading: false,
          authError: ''
        });
      })
      .catch(() => {
        this.setData({
          authLoading: false,
          authError: '登录失败，请重试'
        });
      });
  },

  openBoard(event) {
    if (!this.data.loginState.loggedIn) {
      this.setData({
        authError: '请先登录后查看看板'
      });
      return;
    }

    const { path } = event.currentTarget.dataset;
    if (!path) {
      return;
    }
    wx.navigateTo({ url: path });
  },

  onShareAppMessage() {
    return {
      title: 'MarketPulse 市场脉搏',
      path: '/pages/home/index'
    };
  },

  onShareTimeline() {
    return {
      title: 'MarketPulse 市场脉搏'
    };
  }
});
