"use strict";

const CLOUD_NOT_CONFIGURED = {
  code: "CLOUD_NOT_CONFIGURED",
  message: "云函数运行时未配置 wx-server-sdk",
};

const UNAUTHENTICATED = {
  code: "UNAUTHENTICATED",
  message: "请先登录后再查看看板数据",
};

const INVALID_SECTION = {
  code: "INVALID_SECTION",
  message: "请求的看板或数据分区不存在",
};

const SECTION_DATA_MISSING = {
  code: "SECTION_DATA_MISSING",
  message: "payload 中缺少当前数据分区所需字段",
};

const PAYLOAD_NOT_FOUND = {
  code: "PAYLOAD_NOT_FOUND",
  message: "未找到当前看板可用的 payload 文件",
};

const PAYLOAD_READ_FAILED = {
  code: "PAYLOAD_READ_FAILED",
  message: "payload 读取失败",
};

const PAYLOAD_PREFIX = "marketpulse-payload";
const MANIFEST_PATH = `${PAYLOAD_PREFIX}/manifest.json`;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

const SECTION_WHITELIST = Object.freeze({
  ashare: Object.freeze({
    indexDeviation: Object.freeze(["indexDeviation"]),
    margin: Object.freeze(["margin"]),
    turnover: Object.freeze(["turnover"]),
    topConcentration: Object.freeze(["topConcentration"]),
  }),
  beijing: Object.freeze({
    houseViewPeople: Object.freeze(["houseViewPeopleByWeekday"]),
    decreaseRatio: Object.freeze(["decreaseRatio"]),
    lianjiaDeals: Object.freeze(["lianjiaDealsByWeekday"]),
    onlineSignings: Object.freeze(["dailyOnlineSignings", "monthlyOnlineSignings"]),
    credit: Object.freeze([
      "creditYoy",
      "loanNetIncreaseByMonth",
      "totalLoanNetIncreaseByMonth",
    ]),
  }),
});

function loadCloudRuntime() {
  try {
    return require("wx-server-sdk");
  } catch (error) {
    return null;
  }
}

function getLoginContext(cloudRuntime) {
  if (!cloudRuntime || typeof cloudRuntime.getWXContext !== "function") {
    return null;
  }
  return cloudRuntime.getWXContext();
}

function normalizeRequest(event) {
  const request = event && typeof event === "object" ? event : {};
  return {
    type: normalizeString(request.type),
    section: normalizeString(request.section),
    date: normalizeString(request.date),
  };
}

function normalizeString(value) {
  return typeof value === "string" ? value.trim() : undefined;
}

function isValidDateText(value) {
  if (!DATE_PATTERN.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function getSectionFields(type, section) {
  if (!type || !section || !SECTION_WHITELIST[type]) {
    return null;
  }
  return SECTION_WHITELIST[type][section] || null;
}

function selectSectionData(payload, type, section) {
  const fields = getSectionFields(type, section);
  if (!fields || !payload || typeof payload !== "object") {
    return null;
  }

  for (const field of fields) {
    if (!Object.prototype.hasOwnProperty.call(payload, field)) {
      return null;
    }
  }

  if (fields.length === 1) {
    return payload[fields[0]];
  }

  return fields.reduce((data, field) => {
    data[field] = payload[field];
    return data;
  }, {});
}

function buildSuccessResponse(request, data) {
  return {
    type: request.type,
    section: request.section,
    data,
  };
}

function buildErrorResponse(request, error) {
  const response = {
    error,
  };
  if (request && request.type) {
    response.type = request.type;
  }
  if (request && request.section) {
    response.section = request.section;
  }
  return response;
}

function getDashboardManifest(manifest, type) {
  if (!manifest || typeof manifest !== "object") {
    return null;
  }
  const dashboards = manifest.dashboards;
  if (!dashboards || typeof dashboards !== "object") {
    return null;
  }
  const dashboard = dashboards[type];
  if (!dashboard || typeof dashboard !== "object") {
    return null;
  }
  return dashboard;
}

function normalizeAvailableDates(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return [...new Set(value.filter(isValidDateText))].sort();
}

function selectAvailableDate(availableDates, requestedDate) {
  const dates = normalizeAvailableDates(availableDates);
  if (dates.length === 0) {
    return null;
  }
  if (!requestedDate) {
    return dates[dates.length - 1];
  }
  if (!isValidDateText(requestedDate)) {
    return null;
  }
  if (dates.includes(requestedDate)) {
    return requestedDate;
  }

  const previousDates = dates.filter((dateText) => dateText <= requestedDate);
  if (previousDates.length > 0) {
    return previousDates[previousDates.length - 1];
  }
  return dates[0];
}

function selectPayloadFile(manifest, type, requestedDate) {
  const dashboard = getDashboardManifest(manifest, type);
  if (!dashboard) {
    return null;
  }

  const selectedDate = selectAvailableDate(dashboard.availableDates, requestedDate);
  if (!selectedDate) {
    return null;
  }

  const files = dashboard.files;
  if (!files || typeof files !== "object" || typeof files[selectedDate] !== "string") {
    if (!requestedDate && dashboard.latestDate === selectedDate && typeof dashboard.latestFile === "string") {
      return {
        date: selectedDate,
        file: dashboard.latestFile,
      };
    }
    return null;
  }

  return {
    date: selectedDate,
    file: files[selectedDate],
  };
}

async function readJsonFromCloudPath(cloudRuntime, cloudPath, options) {
  const storageReader = options && options.storageReader;
  if (typeof storageReader === "function") {
    return storageReader(cloudPath);
  }

  if (!cloudRuntime || typeof cloudRuntime.downloadFile !== "function") {
    throw new Error("cloud downloadFile is not available");
  }

  const response = await cloudRuntime.downloadFile({ fileID: cloudPath });
  const content = response && response.fileContent;
  if (Buffer.isBuffer(content)) {
    return JSON.parse(content.toString("utf8"));
  }
  if (typeof content === "string") {
    return JSON.parse(content);
  }
  throw new Error(`cloud file content is empty: ${cloudPath}`);
}

async function readPayloadFromManifest(request, cloudRuntime, options) {
  const manifest = await readJsonFromCloudPath(cloudRuntime, MANIFEST_PATH, options);
  const payloadFile = selectPayloadFile(manifest, request.type, request.date);
  if (!payloadFile) {
    const error = new Error("payload file is not listed in manifest");
    error.code = PAYLOAD_NOT_FOUND.code;
    throw error;
  }

  const payload = await readJsonFromCloudPath(cloudRuntime, payloadFile.file, options);
  return {
    payload,
    date: payloadFile.date,
  };
}

async function handleRequest(event, context, cloudRuntime, options) {
  const request = normalizeRequest(event);
  const wxContext = getLoginContext(cloudRuntime);
  if (!wxContext || !wxContext.OPENID) {
    return buildErrorResponse(request, UNAUTHENTICATED);
  }

  if (!getSectionFields(request.type, request.section)) {
    return buildErrorResponse(request, INVALID_SECTION);
  }

  const payloadReader = options && options.payloadReader;
  let payloadResult;
  if (typeof payloadReader === "function") {
    payloadResult = {
      payload: await payloadReader(request, context),
      date: request.date,
    };
  } else {
    try {
      payloadResult = await readPayloadFromManifest(request, cloudRuntime, options);
    } catch (error) {
      return buildErrorResponse(
        request,
        error && error.code === PAYLOAD_NOT_FOUND.code ? PAYLOAD_NOT_FOUND : PAYLOAD_READ_FAILED,
      );
    }
  }

  const data = selectSectionData(payloadResult.payload, request.type, request.section);
  if (data === null) {
    return buildErrorResponse(request, SECTION_DATA_MISSING);
  }

  return buildSuccessResponse(request, data);
}

exports.main = async (event, context) => {
  const cloudRuntime = loadCloudRuntime();
  if (!cloudRuntime) {
    return buildErrorResponse(normalizeRequest(event), CLOUD_NOT_CONFIGURED);
  }
  if (typeof cloudRuntime.init === "function") {
    cloudRuntime.init({
      env: cloudRuntime.DYNAMIC_CURRENT_ENV,
    });
  }
  return handleRequest(event, context, cloudRuntime);
};

exports.handleRequest = handleRequest;
exports.getLoginContext = getLoginContext;
exports.normalizeRequest = normalizeRequest;
exports.getSectionFields = getSectionFields;
exports.selectSectionData = selectSectionData;
exports.selectAvailableDate = selectAvailableDate;
exports.selectPayloadFile = selectPayloadFile;
exports.readPayloadFromManifest = readPayloadFromManifest;
exports.buildSuccessResponse = buildSuccessResponse;
exports.buildErrorResponse = buildErrorResponse;
exports.SECTION_WHITELIST = SECTION_WHITELIST;
exports.MANIFEST_PATH = MANIFEST_PATH;
