const auth = require('../../utils/auth');
const chartOption = require('../../utils/echarts-option');
const request = require('../../utils/request');

const DASHBOARD_TYPE = 'ashare';
const DEFAULT_TAB = 'indexDeviation';
const TABS = [
  { key: 'indexDeviation', title: '指数MA60偏离' },
  { key: 'margin', title: 'A股融资余额' },
  { key: 'turnover', title: 'A股成交金额' },
  { key: 'topConcentration', title: 'A股成交集中度' }
];

function buildInitialSectionStates() {
  return TABS.reduce((states, tab) => {
    states[tab.key] = {
      loading: false,
      loaded: false,
      error: '',
      data: null,
      chartCards: [],
      topStockTables: []
    };
    return states;
  }, {});
}

function findTabTitle(key) {
  const tab = TABS.find((item) => item.key === key);
  return tab ? tab.title : '';
}

function createChartEc(option) {
  return {
    lazyLoad: false,
    option,
    onInit(canvas, width, height, dpr) {
      const echarts = require('../../components/ec-canvas/echarts');
      const chart = echarts.init(canvas, null, {
        width,
        height,
        devicePixelRatio: dpr
      });
      canvas.setChart(chart);
      chart.setOption(option);
      return chart;
    }
  };
}

function buildChartCard(key, option) {
  return {
    key,
    title: option && option.title ? option.title.text : '',
    canvasId: `ashare-${key}`,
    ec: createChartEc(option)
  };
}

function buildSectionChartCards(section, data) {
  if (section === 'indexDeviation') {
    return chartOption.buildIndexDeviationOptions(Array.isArray(data) ? data : [])
      .map((option, index) => buildChartCard(`index-deviation-${index}`, option));
  }

  if (section === 'margin') {
    const rows = Array.isArray(data) ? data : [];
    return [
      buildChartCard('margin-balance', chartOption.buildMarginBalanceOption(rows)),
      buildChartCard('margin-ratio', chartOption.buildMarginRatioOption(rows))
    ];
  }

  if (section === 'turnover') {
    return [
      buildChartCard('turnover', chartOption.buildTurnoverOption(Array.isArray(data) ? data : []))
    ];
  }

  if (section === 'topConcentration') {
    return [
      buildChartCard('top-concentration', chartOption.buildTopConcentrationOption(data && !Array.isArray(data) ? data : {}))
    ];
  }

  return [];
}

function formatAmount100m(amountYuan) {
  const amountValue = Number(amountYuan);
  if (!Number.isFinite(amountValue)) {
    return '';
  }
  return `${chartOption.formatNumber(amountValue / 100000000, 2)}亿`;
}

function buildTopStockTables(topConcentration) {
  return (topConcentration && topConcentration.recentTables ? topConcentration.recentTables : [])
    .map((table) => ({
      date: table.date || '',
      stocks: (table.stocks || []).map((stock) => ({
        code: stock.tsCode || '',
        displayName: stock.name || stock.tsCode || '',
        amountText: formatAmount100m(stock.amountYuan),
        pctChgText: chartOption.formatPctChg(stock.pctChg),
        pctChgClass: Number(stock.pctChg) > 0 ? 'stock-up' : Number(stock.pctChg) < 0 ? 'stock-down' : ''
      }))
    }));
}

function buildSectionRenderData(section, data) {
  return {
    chartCards: buildSectionChartCards(section, data),
    topStockTables: section === 'topConcentration' ? buildTopStockTables(data) : []
  };
}

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}

function isSectionDataValid(section, data) {
  if (section === 'indexDeviation' || section === 'margin' || section === 'turnover') {
    return Array.isArray(data);
  }

  if (section === 'topConcentration') {
    return isPlainObject(data) && Array.isArray(data.chart) && Array.isArray(data.recentTables);
  }

  return false;
}

function buildSectionShapeError() {
  const error = new Error('数据结构异常，请稍后重试');
  error.code = 'SECTION_SHAPE_INVALID';
  return error;
}

Page({
  data: {
    loginState: auth.getLoginState(),
    authForm: {
      avatarUrl: '',
      nickName: ''
    },
    authError: '',
    authLoading: false,
    tabs: TABS,
    activeTab: DEFAULT_TAB,
    activeTabTitle: findTabTitle(DEFAULT_TAB),
    sectionStates: buildInitialSectionStates(),
    activeSectionState: buildInitialSectionStates()[DEFAULT_TAB]
  },

  onLoad() {
    return this.refreshLoginState();
  },

  onShow() {
    return this.refreshLoginState();
  },

  refreshLoginState() {
    const loginState = auth.getLoginState();

    this.setData({
      loginState
    });

    if (loginState.loggedIn) {
      return this.loadActiveTabData();
    }

    return Promise.resolve(null);
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
        this.loadActiveTabData();
      })
      .catch(() => {
        this.setData({
          authLoading: false,
          authError: '登录失败，请重试'
        });
      });
  },

  onTapTab(event) {
    const section = event.currentTarget && event.currentTarget.dataset ? event.currentTarget.dataset.key : '';

    if (!section || !this.data.sectionStates[section]) {
      return;
    }

    if (section === this.data.activeTab) {
      return this.loadSectionData(section);
    }

    this.setActiveTab(section);
    return this.loadSectionData(section);
  },

  loadActiveTabData(options = {}) {
    return this.loadSectionData(this.data.activeTab, options);
  },

  loadSectionData(section, options = {}) {
    const forceRefresh = Boolean(options.forceRefresh);
    const currentState = this.data.sectionStates[section];
    if (!currentState || currentState.loading || (currentState.loaded && !forceRefresh)) {
      return Promise.resolve(currentState || null);
    }

    this.setSectionState(section, {
      loading: true,
      error: ''
    });

    return request.requestDashboardSection(DASHBOARD_TYPE, section, {
      forceRefresh
    })
      .then((response) => {
        if (!isSectionDataValid(section, response.data)) {
          throw buildSectionShapeError();
        }
        const renderData = buildSectionRenderData(section, response.data);
        this.setSectionState(section, {
          loading: false,
          loaded: true,
          error: '',
          data: response.data,
          chartCards: renderData.chartCards,
          topStockTables: renderData.topStockTables
        });
        return response;
      })
      .catch((error) => {
        this.setSectionState(section, {
          loading: false,
          error: error && error.message ? error.message : '数据加载失败，请重试'
        });
        throw error;
      });
  },

  retryActiveSection() {
    return this.loadActiveTabData({ forceRefresh: true }).catch(() => null);
  },

  onPullDownRefresh() {
    return this.loadActiveTabData({ forceRefresh: true })
      .catch(() => null)
      .then(() => {
        if (typeof wx !== 'undefined' && wx.stopPullDownRefresh) {
          wx.stopPullDownRefresh();
        }
      });
  },

  setSectionState(section, partialState) {
    const currentState = this.data.sectionStates[section] || {};
    const nextState = Object.assign({}, currentState, partialState);
    const nextData = {
      [`sectionStates.${section}`]: nextState
    };

    if (section === this.data.activeTab) {
      nextData.activeSectionState = nextState;
    }

    this.setData(nextData);
  },

  setActiveTab(section) {
    this.setData({
      activeTab: section,
      activeTabTitle: findTabTitle(section),
      activeSectionState: this.data.sectionStates[section]
    });
  },

  onShareAppMessage() {
    return {
      title: 'MarketPulse 资本市场看板',
      path: '/pages/ashare/index'
    };
  }
});
