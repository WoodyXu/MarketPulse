Page({
  data: {
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

  openBoard(event) {
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
  }
});
