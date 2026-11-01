// 后端 API 封装（带超时——防止请求挂起导致前端状态锁死）
const DEFAULT_TIMEOUT = 8000; // 8s：正常接口 <1s，超时视为后端异常

export async function api(path, options = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT, ...rest } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const init = {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    signal: controller.signal,
    ...rest,
  };
  try {
    const res = await fetch(path, init);
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        if (body && body.detail) detail = body.detail;
      } catch (_) { /* ignore */ }
      throw new Error(`${res.status}: ${detail}`);
    }
    return res.status === 204 ? null : res.json();
  } finally {
    clearTimeout(timer);
  }
}

export const apiGet = (p, o) => api(p, o);
export const apiPut = (p, b, o) => api(p, { method: "PUT", body: JSON.stringify(b), ...o });
export const apiPost = (p, b, o) => api(p, { method: "POST", body: JSON.stringify(b), ...o });
export const apiDelete = (p, o) => api(p, { method: "DELETE", ...o });
