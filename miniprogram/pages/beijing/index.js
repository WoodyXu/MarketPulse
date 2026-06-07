const auth = require('../../utils/auth');
const chartOption = require('../../utils/echarts-option');
const request = require('../../utils/request');

const DASHBOARD_TYPE = 'beijing';
const DEFAULT_TAB = 'houseViewPeople';
const DEFAULT_CREDIT_TAB = 'creditYoy';
const TABS = [
  { key: 'houseViewPeople', title: '看房人数' },
  { key: 'decreaseRatio', title: '跌涨比' },
  { key: 'lianjiaDeals', title: '大中介成交' },
  { key: 'onlineSignings', title: '网签量' },
  { key: 'credit', title: '居民贷款' }
];
const CREDIT_TABS = [
  { key: 'creditYoy', title: '同比' },
  { key: 'loanNetIncreaseByMonth', title: '当月净增' },
  { key: 'totalLoanNetIncreaseByMonth', title: '年内累计净增' }
];

function buildInitialSectionStates() {
  return TABS.reduce((states, tab) => {
    states[tab.key] = {
      loading: false,
      loaded: false,
      error: '',
      data: null,
      chartCards: [],
      creditChartGroups: {}
    };
    return states;
  }, {});
}

function findTitle(items, key) {
  const item = items.find((entry) => entry.key === key);
  return item ? item.title : '';
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
    canvasId: `beijing-${key}`,
    ec: createChartEc(option)
  };
}

function buildChartCardsFromOptions(prefix, options) {
  return (options || []).map((option, index) => buildChartCard(`${prefix}-${index}`, option));
}

function buildCreditMonthCards(prefix, optionMap) {
  return Object.keys(optionMap || {})
    .map((month) => Number(month))
    .filter((month) => Number.isFinite(month))
    .sort((left, right) => left - right)
    .map((month) => buildChartCard(`${prefix}-${month}`, optionMap[month]));
}

function buildCreditChartGroups(data) {
  const creditData = data && !Array.isArray(data) ? data : {};
  return {
    creditYoy: [
      buildChartCard('credit-yoy', chartOption.buildCreditYoyOption(Array.isArray(creditData.creditYoy) ? creditData.creditYoy : []))
    ],
    loanNetIncreaseByMonth: buildCreditMonthCards(
      'credit-month-increase',
      chartOption.buildCreditMonthIncreaseOptions(Array.isArray(creditData.loanNetIncreaseByMonth) ? creditData.loanNetIncreaseByMonth : [])
    ),
    totalLoanNetIncreaseByMonth: buildCreditMonthCards(
      'credit-ytd-increase',
      chartOption.buildCreditYtdIncreaseOptions(Array.isArray(creditData.totalLoanNetIncreaseByMonth) ? creditData.totalLoanNetIncreaseByMonth : [])
    )
  };
}

function buildSectionRenderData(section, data, activeCreditTab) {
  if (section === 'houseViewPeople') {
    return {
      chartCards: buildChartCardsFromOptions(
        'house-view-people',
        chartOption.buildHouseViewPeopleOptions(Array.isArray(data) ? data : [], chartOption.WEEKDAY_ORDER)
      ),
      creditChartGroups: {}
    };
  }

  if (section === 'decreaseRatio') {
    return {
      chartCards: [
        buildChartCard('decrease-ratio', chartOption.buildDecreaseRatioOption(Array.isArray(data) ? data : []))
      ],
      creditChartGroups: {}
    };
  }

  if (section === 'lianjiaDeals') {
    return {
      chartCards: buildChartCardsFromOptions(
        'lianjia-deals',
        chartOption.buildLianjiaDealsOptions(Array.isArray(data) ? data : [], chartOption.WEEKDAY_ORDER)
      ),
      creditChartGroups: {}
    };
  }

  if (section === 'onlineSignings') {
    const options = chartOption.buildOnlineSigningOptions(data && !Array.isArray(data) ? data : {});
    return {
      chartCards: [
        buildChartCard('daily-online-signings', options.dailyOnlineSignings),
        buildChartCard('monthly-online-signings', options.monthlyOnlineSignings)
      ],
      creditChartGroups: {}
    };
  }

  if (section === 'credit') {
    const creditChartGroups = buildCreditChartGroups(data);
    return {
      chartCards: creditChartGroups[activeCreditTab] || [],
      creditChartGroups
    };
  }

  return {
    chartCards: [],
    creditChartGroups: {}
  };
}

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}

function isSectionDataValid(section, data) {
  if (section === 'houseViewPeople' || section === 'decreaseRatio' || section === 'lianjiaDeals') {
    return Array.isArray(data);
  }

  if (section === 'onlineSignings') {
    return isPlainObject(data)
      && Array.isArray(data.dailyOnlineSignings)
      && Array.isArray(data.monthlyOnlineSignings);
  }

  if (section === 'credit') {
    return isPlainObject(data)
      && Array.isArray(data.creditYoy)
      && Array.isArray(data.loanNetIncreaseByMonth)
      && Array.isArray(data.totalLoanNetIncreaseByMonth);
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
    creditTabs: CREDIT_TABS,
    activeTab: DEFAULT_TAB,
    activeTabTitle: findTitle(TABS, DEFAULT_TAB),
    activeCreditTab: DEFAULT_CREDIT_TAB,
    activeCreditTabTitle: findTitle(CREDIT_TABS, DEFAULT_CREDIT_TAB),
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

  onTapCreditTab(event) {
    const creditTab = event.currentTarget && event.currentTarget.dataset ? event.currentTarget.dataset.key : '';

    if (!findTitle(CREDIT_TABS, creditTab)) {
      return;
    }

    this.setData({
      activeCreditTab: creditTab,
      activeCreditTabTitle: findTitle(CREDIT_TABS, creditTab)
    });

    if (this.data.activeTab === 'credit') {
      this.setActiveCreditChartCards(creditTab);
    }
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
        const renderData = buildSectionRenderData(section, response.data, this.data.activeCreditTab);
        this.setSectionState(section, {
          loading: false,
          loaded: true,
          error: '',
          data: response.data,
          chartCards: renderData.chartCards,
          creditChartGroups: renderData.creditChartGroups
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
    const activeSectionState = section === 'credit'
      ? this.buildCreditActiveSectionState(this.data.sectionStates[section], this.data.activeCreditTab)
      : this.data.sectionStates[section];

    this.setData({
      activeTab: section,
      activeTabTitle: findTitle(TABS, section),
      activeSectionState
    });
  },

  buildCreditActiveSectionState(sectionState, creditTab) {
    const state = sectionState || {};
    const groups = state.creditChartGroups || {};
    return Object.assign({}, state, {
      chartCards: groups[creditTab] || state.chartCards || []
    });
  },

  setActiveCreditChartCards(creditTab) {
    const creditState = this.data.sectionStates.credit || {};
    const nextCreditState = this.buildCreditActiveSectionState(creditState, creditTab);
    this.setData({
      'sectionStates.credit': nextCreditState,
      activeSectionState: nextCreditState
    });
  },

  onShareAppMessage() {
    return {
      title: 'MarketPulse 北京楼市看板',
      path: '/pages/beijing/index'
    };
  }
});
