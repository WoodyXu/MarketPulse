Page({
  data: {
    tabs: [
      { key: 'houseViewPeople', title: '看房人数' },
      { key: 'decreaseRatio', title: '跌涨比' },
      { key: 'lianjiaDeals', title: '大中介成交' },
      { key: 'onlineSignings', title: '网签量' },
      { key: 'credit', title: '居民贷款' }
    ],
    activeTab: 'houseViewPeople'
  },

  onShareAppMessage() {
    return {
      title: 'MarketPulse 北京楼市看板',
      path: '/pages/beijing/index'
    };
  }
});
