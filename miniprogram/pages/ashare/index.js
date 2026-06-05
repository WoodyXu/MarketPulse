Page({
  data: {
    tabs: [
      { key: 'indexDeviation', title: '指数MA60偏离' },
      { key: 'margin', title: 'A股融资余额' },
      { key: 'turnover', title: 'A股成交金额' },
      { key: 'topConcentration', title: 'A股成交集中度' }
    ],
    activeTab: 'indexDeviation'
  },

  onShareAppMessage() {
    return {
      title: 'MarketPulse 资本市场看板',
      path: '/pages/ashare/index'
    };
  }
});
