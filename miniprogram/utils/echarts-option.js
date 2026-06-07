const COLORS = {
  primary: '#00754A',
  primaryDark: '#006241',
  gold: '#cba258',
  purple: '#8b5cf6',
  axis: '#6b7280',
  grid: '#e5e7eb',
  text: '#1f2937'
};

const WEEKDAY_ORDER = ['周一', '周二', '周三', '周四', '周五', '周末'];

function isFiniteNumber(value) {
  return Number.isFinite(Number(value));
}

function toNumber(value) {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
}

function formatNumber(value, digits) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return '';
  }
  return numberValue.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
}

function formatSignedNumber(value, digits) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return '';
  }
  const sign = numberValue > 0 ? '+' : '';
  return `${sign}${formatNumber(numberValue, digits)}`;
}

function formatPercent(value, digits) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return '';
  }
  return `${formatNumber(numberValue * 100, digits)}%`;
}

function formatPctChg(value) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return '';
  }
  return `${formatSignedNumber(numberValue, 2)}%`;
}

function formatRatio(value) {
  return formatNumber(value, 2);
}

function buildEmptyOption(title) {
  return {
    title: {
      text: title || ''
    },
    series: []
  };
}

function sortByField(rows, fieldName) {
  return [...(rows || [])].sort((left, right) => String(left[fieldName]).localeCompare(String(right[fieldName])));
}

function sortByNumberField(rows, fieldName) {
  return [...(rows || [])].sort((left, right) => Number(left[fieldName]) - Number(right[fieldName]));
}

function groupBy(rows, fieldName) {
  const grouped = {};
  (rows || []).forEach((row) => {
    const key = row[fieldName];
    if (!grouped[key]) {
      grouped[key] = [];
    }
    grouped[key].push(row);
  });
  return grouped;
}

function toDateValuePoints(rows, dateField, valueField) {
  return sortByField(rows || [], dateField)
    .map((row) => [row[dateField], toNumber(row[valueField])])
    .filter((point) => point[0] && point[1] !== null);
}

function toLabeledValuePoints(rows) {
  return sortByField(rows || [], 'x')
    .map((row) => [row.label || row.x, toNumber(row.value)])
    .filter((point) => point[0] && point[1] !== null);
}

function tooltipRows(params) {
  if (!Array.isArray(params)) {
    return params ? [params] : [];
  }
  return params;
}

function makeBaseLineOption(title, xName, yName, yFormatter) {
  return {
    color: [COLORS.primary, COLORS.gold, COLORS.purple, COLORS.primaryDark],
    title: {
      text: title,
      left: 0,
      textStyle: {
        color: COLORS.text,
        fontSize: 15,
        fontWeight: 600
      }
    },
    tooltip: {
      trigger: 'axis',
      confine: true
    },
    legend: {
      top: 28,
      textStyle: {
        color: COLORS.axis,
        fontSize: 11
      }
    },
    grid: {
      top: 66,
      right: 18,
      bottom: 32,
      left: 48,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      name: xName || '',
      boundaryGap: false,
      axisLabel: {
        color: COLORS.axis,
        hideOverlap: true
      },
      axisLine: {
        lineStyle: {
          color: COLORS.grid
        }
      }
    },
    yAxis: {
      type: 'value',
      name: yName || '',
      axisLabel: {
        color: COLORS.axis,
        formatter: yFormatter || ((value) => formatNumber(value, 0))
      },
      splitLine: {
        lineStyle: {
          color: COLORS.grid,
          type: 'dashed'
        }
      }
    },
    series: []
  };
}

function makeLineSeries(name, data, color, extra) {
  return {
    name,
    type: 'line',
    data,
    showSymbol: false,
    smooth: false,
    lineStyle: {
      width: 2.5,
      color: color || COLORS.primary
    },
    itemStyle: {
      color: color || COLORS.primary
    },
    ...(extra || {})
  };
}

function withReferenceLine(series, value, label) {
  return {
    ...series,
    markLine: {
      symbol: 'none',
      label: {
        formatter: label || ''
      },
      lineStyle: {
        color: COLORS.gold,
        type: 'dashed'
      },
      data: [{ yAxis: value, name: label || '' }]
    }
  };
}

function withLatestPoint(series) {
  const data = series.data || [];
  if (!data.length) {
    return series;
  }
  return {
    ...series,
    markPoint: {
      symbol: 'circle',
      symbolSize: 8,
      label: {
        show: false
      },
      data: [{ coord: data[data.length - 1] }]
    }
  };
}

function buildIndexDeviationOptions(rows) {
  const grouped = groupBy(rows || [], 'series');
  return Object.keys(grouped).map((seriesName) => {
    const sortedRows = sortByField(grouped[seriesName], 'date');
    const points = sortedRows
      .map((row) => [row.date, toNumber(row.deviation), row])
      .filter((point) => point[0] && point[1] !== null);
    const option = makeBaseLineOption(`${seriesName} MA60 偏离度`, '日期', '偏离度', (value) => formatPercent(value, 2));
    option.tooltip.formatter = (params) => {
      const row = points[tooltipRows(params)[0]?.dataIndex]?.[2] || {};
      return `${row.date || ''}<br/>偏离度：${formatPercent(row.deviation, 2)}<br/>收盘：${formatNumber(row.close, 2)}<br/>MA60：${formatNumber(row.ma60, 2)}`;
    };
    option.series = [
      withLatestPoint(makeLineSeries('MA60 偏离度', points.map((point) => [point[0], point[1]]), COLORS.primary))
    ];
    option.series[0].markLine = {
      symbol: 'none',
      lineStyle: {
        color: COLORS.grid,
        type: 'dashed'
      },
      data: [{ yAxis: 0, name: '零轴' }]
    };
    return option;
  });
}

function buildMarginBalanceOption(rows) {
  const option = makeBaseLineOption('沪深市场融资余额', '日期', '亿元', (value) => formatNumber(value, 0));
  option.tooltip.formatter = (params) => {
    const item = tooltipRows(params)[0];
    return `${item?.axisValue || ''}<br/>融资余额：${formatNumber(item?.data?.[1], 2)} 亿元`;
  };
  option.series = [
    makeLineSeries(
      '沪深合计融资余额（亿元）',
      toDateValuePoints(rows, 'date', 'marginBalance100m'),
      COLORS.primary,
      { areaStyle: { opacity: 0.12 } }
    )
  ];
  return option;
}

function buildMarginRatioOption(rows) {
  const option = makeBaseLineOption('融资余额 / 流通市值', '日期', '占比', (value) => formatPercent(value, 2));
  option.tooltip.formatter = (params) => {
    const item = tooltipRows(params)[0];
    return `${item?.axisValue || ''}<br/>占流通市值：${formatPercent(item?.data?.[1], 2)}`;
  };
  option.series = [
    withLatestPoint(makeLineSeries('融资余额/流通市值', toDateValuePoints(rows, 'date', 'marginToMarketCap'), COLORS.gold))
  ];
  return option;
}

function buildTurnoverOption(rows) {
  const sortedRows = sortByField(rows || [], 'date');
  const option = makeBaseLineOption('沪深成交金额与沪深300点位', '日期', '成交金额（亿元）', (value) => formatNumber(value, 0));
  option.yAxis = [
    option.yAxis,
    {
      type: 'value',
      name: '沪深300点位',
      axisLabel: {
        color: COLORS.axis,
        formatter: (value) => formatNumber(value, 0)
      },
      splitLine: {
        show: false
      }
    }
  ];
  option.grid.right = 48;
  option.tooltip.formatter = (params) => {
    const rowsForTooltip = tooltipRows(params);
    return `${rowsForTooltip[0]?.axisValue || ''}<br/>成交金额：${formatNumber(rowsForTooltip[0]?.data?.[1], 2)} 亿元<br/>沪深300：${formatNumber(rowsForTooltip[1]?.data?.[1], 2)}`;
  };
  option.series = [
    makeLineSeries(
      '沪深合计成交金额（亿元）',
      sortedRows.map((row) => [row.date, toNumber(row.totalAmount100m)]).filter((point) => point[1] !== null),
      COLORS.primary,
      { areaStyle: { opacity: 0.12 } }
    ),
    makeLineSeries(
      '沪深300点位',
      sortedRows.map((row) => [row.date, toNumber(row.hs300Close)]).filter((point) => point[1] !== null),
      COLORS.purple,
      { yAxisIndex: 1 }
    )
  ];
  return option;
}

function buildTopConcentrationOption(topConcentration) {
  const rows = topConcentration?.chart || [];
  const option = makeBaseLineOption('Top5%成交集中度', '日期', '集中度', (value) => formatPercent(value, 2));
  option.tooltip.formatter = (params) => {
    const item = tooltipRows(params)[0];
    return `${item?.axisValue || ''}<br/>集中度：${formatPercent(item?.data?.[1], 2)}`;
  };
  option.series = [
    withLatestPoint(makeLineSeries(
      'Top5%成交集中度',
      toDateValuePoints(rows, 'date', 'value'),
      COLORS.primary,
      { areaStyle: { opacity: 0.12 } }
    ))
  ];
  return option;
}

function buildWeekdayOptions(rows, weekdayOrder, titleSuffix, valueName, unit) {
  const grouped = groupBy(rows || [], 'weekday');
  const order = weekdayOrder && weekdayOrder.length ? weekdayOrder : WEEKDAY_ORDER;
  return order.map((weekday) => {
    const option = makeBaseLineOption(`${weekday}${titleSuffix}`, '日期', unit || '', (value) => formatNumber(value, 0));
    option.tooltip.formatter = (params) => {
      const item = tooltipRows(params)[0];
      return `${item?.axisValue || ''}<br/>${valueName}：${formatNumber(item?.data?.[1], 0)}${unit || ''}`;
    };
    option.series = [
      makeLineSeries(valueName, toLabeledValuePoints(grouped[weekday] || []), COLORS.primary, { areaStyle: { opacity: 0.12 } })
    ];
    return option;
  });
}

function buildHouseViewPeopleOptions(rows, weekdayOrder) {
  return buildWeekdayOptions(rows, weekdayOrder, '看房人数', '看房人数', '人');
}

function buildLianjiaDealsOptions(rows, weekdayOrder) {
  return buildWeekdayOptions(rows, weekdayOrder, '大中介成交量', '大中介成交量', '套')
    .map((option) => {
      if (option.title.text === '周末大中介成交量') {
        option.series[0] = withReferenceLine(option.series[0], 1200, '周末荣枯线');
      }
      return option;
    });
}

function buildDecreaseRatioOption(rows) {
  const option = makeBaseLineOption('房东调价跌涨比', '日期', '跌涨比', (value) => formatRatio(value));
  option.tooltip.formatter = (params) => {
    const item = tooltipRows(params)[0];
    return `${item?.axisValue || ''}<br/>跌涨比：${formatRatio(item?.data?.[1])}`;
  };
  option.series = [
    withReferenceLine(makeLineSeries('跌涨比', toLabeledValuePoints(rows || []), COLORS.primary), 10, '参考线')
  ];
  return option;
}

function buildOnlineSigningOptions(data) {
  const dailyOption = makeBaseLineOption('每日二手房网签量', '日期', '套', (value) => formatNumber(value, 0));
  dailyOption.tooltip.formatter = (params) => {
    const item = tooltipRows(params)[0];
    return `${item?.axisValue || ''}<br/>网签量：${formatNumber(item?.data?.[1], 0)}套`;
  };
  dailyOption.series = [
    makeLineSeries('每日二手房网签量', toLabeledValuePoints(data?.dailyOnlineSignings || []), COLORS.primary, { areaStyle: { opacity: 0.12 } })
  ];

  const monthlyOption = makeBaseLineOption('每月二手房网签量', '月份', '套', (value) => formatNumber(value, 0));
  monthlyOption.tooltip.formatter = (params) => {
    const item = tooltipRows(params)[0];
    return `${item?.axisValue || ''}<br/>月度网签量：${formatNumber(item?.data?.[1], 0)}套`;
  };
  monthlyOption.series = [
    withReferenceLine(
      makeLineSeries('每月二手房网签量', toLabeledValuePoints(data?.monthlyOnlineSignings || []), COLORS.primary, { areaStyle: { opacity: 0.12 } }),
      12000,
      '荣枯线'
    )
  ];
  return {
    dailyOnlineSignings: dailyOption,
    monthlyOnlineSignings: monthlyOption
  };
}

function buildCreditYoyOption(rows) {
  const option = makeBaseLineOption('居民贷款余额增速', '月份', '同比增速', (value) => formatPercent(value, 2));
  option.tooltip.formatter = (params) => {
    const item = tooltipRows(params)[0];
    return `${item?.axisValue || ''}<br/>同比增速：${formatPercent(item?.data?.[1], 2)}`;
  };
  option.series = [
    withReferenceLine(makeLineSeries('居民贷款余额同比增速', toLabeledValuePoints(rows || []), COLORS.primary), 0, '荣枯线')
  ];
  return option;
}

function buildCreditMonthGroupOptions(rows, valueName, titleBuilder) {
  const grouped = groupBy(rows || [], 'month');
  const options = {};
  for (let month = 1; month <= 12; month += 1) {
    const option = makeBaseLineOption(titleBuilder(month), '年份', '亿元', (value) => formatSignedNumber(value, 2));
    const points = sortByNumberField(grouped[month] || [], 'x')
      .map((row) => [row.label || String(row.x), toNumber(row.value)])
      .filter((point) => point[0] && point[1] !== null);
    option.tooltip.formatter = (params) => {
      const item = tooltipRows(params)[0];
      return `${item?.axisValue || ''}<br/>${valueName}：${formatSignedNumber(item?.data?.[1], 2)}亿元`;
    };
    option.series = [
      withReferenceLine(makeLineSeries(valueName, points, COLORS.primary), 0, '荣枯线')
    ];
    options[month] = option;
  }
  return options;
}

function buildCreditMonthIncreaseOptions(rows) {
  return buildCreditMonthGroupOptions(rows, '当月居民贷款增量', (month) => `${month}月当月居民贷款增量`);
}

function buildCreditYtdIncreaseOptions(rows) {
  return buildCreditMonthGroupOptions(rows, '当年累计居民贷款增量', (month) => `1-${month}月居民贷款增量`);
}

module.exports = {
  COLORS,
  WEEKDAY_ORDER,
  buildEmptyOption,
  buildIndexDeviationOptions,
  buildMarginBalanceOption,
  buildMarginRatioOption,
  buildTurnoverOption,
  buildTopConcentrationOption,
  buildHouseViewPeopleOptions,
  buildLianjiaDealsOptions,
  buildDecreaseRatioOption,
  buildOnlineSigningOptions,
  buildCreditYoyOption,
  buildCreditMonthIncreaseOptions,
  buildCreditYtdIncreaseOptions,
  formatNumber,
  formatPercent,
  formatPctChg,
  formatRatio,
  formatSignedNumber,
  groupBy,
  isFiniteNumber
};
