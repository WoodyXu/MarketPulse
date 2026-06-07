import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MINIPROGRAM_ROOT = REPO_ROOT / "miniprogram"


class MiniProgramRequestCacheTest(unittest.TestCase):
    def run_node_script(self, script):
        subprocess.run(["node", "-e", script], check=True, cwd=REPO_ROOT)

    def test_cache_key_and_ttl_contract(self):
        script = textwrap.dedent(
            f"""
            const cache = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "cache.js"))});

            if (cache.buildCacheKey("ashare", "turnover") !== "marketpulse:ashare:turnover") {{
              throw new Error("cache key mismatch");
            }}
            if (cache.CACHE_TTL_MS !== 24 * 60 * 60 * 1000) {{
              throw new Error("cache ttl mismatch");
            }}
            if (!cache.isCacheEntryValid({{
              cachedAt: 1000,
              type: "ashare",
              section: "turnover",
              data: {{}}
            }}, 1000 + cache.CACHE_TTL_MS)) {{
              throw new Error("entry should be valid at ttl boundary");
            }}
            if (cache.isCacheEntryValid({{
              cachedAt: 1000,
              type: "ashare",
              section: "turnover",
              data: {{}}
            }}, 1001 + cache.CACHE_TTL_MS)) {{
              throw new Error("entry should expire after ttl");
            }}
            """
        )

        self.run_node_script(script)

    def test_request_hits_cloud_function_and_writes_cache(self):
        script = textwrap.dedent(
            f"""
            const cache = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "cache.js"))});
            const request = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "request.js"))});
            cache.clearMemoryCache();

            const storage = {{}};
            let callCount = 0;
            const wxApi = {{
              getStorageSync(key) {{ return storage[key]; }},
              setStorageSync(key, value) {{ storage[key] = value; }},
              removeStorageSync(key) {{ delete storage[key]; }},
              cloud: {{
                callFunction(options) {{
                  callCount += 1;
                  if (options.name !== "getDashboardSection") {{
                    throw new Error("unexpected cloud function name");
                  }}
                  if (options.data.type !== "ashare" || options.data.section !== "turnover") {{
                    throw new Error("unexpected request data");
                  }}
                  return Promise.resolve({{
                    result: {{
                      type: "ashare",
                      section: "turnover",
                      data: {{ points: [1, 2, 3] }}
                    }}
                  }});
                }}
              }}
            }};

            request.requestDashboardSection("ashare", "turnover", {{ wxApi, now: 2000 }})
              .then((response) => {{
                if (callCount !== 1 || response.data.points.length !== 3) {{
                  throw new Error("first request did not use cloud response");
                }}
                const cached = storage["marketpulse:ashare:turnover"];
                if (!cached || cached.cachedAt !== 2000 || cached.data.points.length !== 3) {{
                  throw new Error("cache was not written");
                }}
                return request.requestDashboardSection("ashare", "turnover", {{ wxApi, now: 3000 }});
              }})
              .then((response) => {{
                if (callCount !== 1 || response.data.points.length !== 3) {{
                  throw new Error("second request should use cache without cloud call");
                }}
              }})
              .catch((error) => {{
                console.error(error.message);
                process.exit(1);
              }});
            """
        )

        self.run_node_script(script)

    def test_request_uses_valid_storage_cache_after_memory_clear(self):
        script = textwrap.dedent(
            f"""
            const cache = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "cache.js"))});
            const request = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "request.js"))});
            cache.clearMemoryCache();

            const storage = {{
              "marketpulse:beijing:credit": {{
                cachedAt: 5000,
                type: "beijing",
                section: "credit",
                data: {{ creditYoy: [{{ month: "2026-05" }}] }}
              }}
            }};
            let callCount = 0;
            const wxApi = {{
              getStorageSync(key) {{ return storage[key]; }},
              setStorageSync(key, value) {{ storage[key] = value; }},
              removeStorageSync(key) {{ delete storage[key]; }},
              cloud: {{
                callFunction() {{
                  callCount += 1;
                  return Promise.reject(new Error("cloud should not be called"));
                }}
              }}
            }};

            request.requestDashboardSection("beijing", "credit", {{ wxApi, now: 6000 }})
              .then((response) => {{
                if (callCount !== 0 || response.data.creditYoy[0].month !== "2026-05") {{
                  throw new Error("valid storage cache was not used");
                }}
              }})
              .catch((error) => {{
                console.error(error.message);
                process.exit(1);
              }});
            """
        )

        self.run_node_script(script)

    def test_request_failure_falls_back_to_valid_cache(self):
        script = textwrap.dedent(
            f"""
            const cache = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "cache.js"))});
            const request = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "request.js"))});
            cache.clearMemoryCache();

            const storage = {{
              "marketpulse:ashare:margin": {{
                cachedAt: 10000,
                type: "ashare",
                section: "margin",
                data: {{ marginBalance: [42] }}
              }}
            }};
            const wxApi = {{
              getStorageSync(key) {{ return storage[key]; }},
              setStorageSync(key, value) {{ storage[key] = value; }},
              removeStorageSync(key) {{ delete storage[key]; }},
              cloud: {{
                callFunction() {{
                  return Promise.reject(new Error("network failed"));
                }}
              }}
            }};

            request.requestDashboardSection("ashare", "margin", {{
              wxApi,
              now: 11000,
              forceRefresh: true
            }})
              .then((response) => {{
                if (response.data.marginBalance[0] !== 42) {{
                  throw new Error("valid cache fallback mismatch");
                }}
              }})
              .catch((error) => {{
                console.error(error.message);
                process.exit(1);
              }});
            """
        )

        self.run_node_script(script)

    def test_request_failure_with_expired_cache_rejects(self):
        script = textwrap.dedent(
            f"""
            const cache = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "cache.js"))});
            const request = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "request.js"))});
            cache.clearMemoryCache();

            const storage = {{
              "marketpulse:ashare:indexDeviation": {{
                cachedAt: 1000,
                type: "ashare",
                section: "indexDeviation",
                data: {{ stale: true }}
              }}
            }};
            const wxApi = {{
              getStorageSync(key) {{ return storage[key]; }},
              setStorageSync(key, value) {{ storage[key] = value; }},
              removeStorageSync(key) {{ delete storage[key]; }},
              cloud: {{
                callFunction() {{
                  return Promise.reject(new Error("network failed"));
                }}
              }}
            }};

            request.requestDashboardSection("ashare", "indexDeviation", {{
              wxApi,
              now: 1001 + cache.CACHE_TTL_MS,
              forceRefresh: true
            }})
              .then(() => {{
                console.error("expected expired cache request to reject");
                process.exit(1);
              }})
              .catch((error) => {{
                if (!error.message.includes("云函数请求失败，请稍后重试")) {{
                  console.error(error.message);
                  process.exit(1);
                }}
              }});
            """
        )

        self.run_node_script(script)

    def test_request_rejects_invalid_cloud_response_shape(self):
        script = textwrap.dedent(
            f"""
            const cache = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "cache.js"))});
            const request = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "request.js"))});
            cache.clearMemoryCache();

            const wxApi = {{
              getStorageSync() {{ return null; }},
              setStorageSync() {{}},
              removeStorageSync() {{}},
              cloud: {{
                callFunction() {{
                  return Promise.resolve({{ result: {{ type: "ashare", section: "turnover" }} }});
                }}
              }}
            }};

            request.requestDashboardSection("ashare", "turnover", {{ wxApi, now: 2000 }})
              .then(() => {{
                console.error("expected invalid response to reject");
                process.exit(1);
              }})
              .catch((error) => {{
                if (!error.message.includes("数据结构异常，请稍后重试")) {{
                  console.error(error.message);
                  process.exit(1);
                }}
              }});
            """
        )

        self.run_node_script(script)

    def test_request_maps_cloud_error_codes_to_stable_page_messages(self):
        script = textwrap.dedent(
            f"""
            const cache = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "cache.js"))});
            const request = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "request.js"))});
            cache.clearMemoryCache();

            const codes = [
              ["PAYLOAD_NOT_FOUND", "暂无可用数据，请稍后重试"],
              ["PAYLOAD_READ_FAILED", "暂无可用数据，请稍后重试"],
              ["SECTION_DATA_MISSING", "数据结构异常，请稍后重试"]
            ];

            function buildWxApi(code) {{
              return {{
                getStorageSync() {{ return null; }},
                setStorageSync() {{}},
                removeStorageSync() {{}},
                cloud: {{
                  callFunction() {{
                    return Promise.resolve({{
                      result: {{
                        type: "ashare",
                        section: "turnover",
                        error: {{ code, message: "raw cloud message" }}
                      }}
                    }});
                  }}
                }}
              }};
            }}

            (async () => {{
              for (const [code, message] of codes) {{
                try {{
                  await request.requestDashboardSection("ashare", "turnover", {{
                    wxApi: buildWxApi(code),
                    now: 2000,
                    forceRefresh: true
                  }});
                  throw new Error(`expected ${{code}} to reject`);
                }} catch (error) {{
                  if (error.message !== message || error.code !== code) {{
                    throw new Error(`unexpected mapping for ${{code}}: ${{error.code}} ${{error.message}}`);
                  }}
                }}
              }}
            }})().catch((error) => {{
              console.error(error.message);
              process.exit(1);
            }});
            """
        )

        self.run_node_script(script)


if __name__ == "__main__":
    unittest.main()
