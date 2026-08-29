(function attachClipperApi(global) {
  const API_BASE = "http://127.0.0.1:43127";
  const TOKEN_KEY = "localClipperToken";

  function storageGet(keys) {
    return new Promise((resolve) => chrome.storage.local.get(keys, resolve));
  }

  function storageSet(values) {
    return new Promise((resolve) => chrome.storage.local.set(values, resolve));
  }

  function storageRemove(keys) {
    return new Promise((resolve) => chrome.storage.local.remove(keys, resolve));
  }

  async function parseResponse(response) {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.error || `本地服务返回错误（${response.status}）`);
    }
    return payload;
  }

  async function health() {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2500);
    try {
      const response = await fetch(`${API_BASE}/api/health`, { signal: controller.signal });
      return await parseResponse(response);
    } finally {
      clearTimeout(timer);
    }
  }

  async function pair() {
    const response = await fetch(`${API_BASE}/api/pair`, { method: "POST" });
    const payload = await parseResponse(response);
    await storageSet({ [TOKEN_KEY]: payload.token });
    return payload;
  }

  async function request(path, options = {}, retry = true) {
    let stored = await storageGet([TOKEN_KEY]);
    let token = stored[TOKEN_KEY];
    if (!token) {
      token = (await pair()).token;
    }

    const headers = new Headers(options.headers || {});
    headers.set("X-Local-Clipper-Key", token);
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (response.status === 401 && retry) {
      await storageRemove([TOKEN_KEY]);
      await pair();
      return request(path, options, false);
    }
    return parseResponse(response);
  }

  global.ClipperAPI = {
    API_BASE,
    health,
    pair,
    request,
    getSettings: () => request("/api/settings"),
    saveSettings: (settings) =>
      request("/api/settings", { method: "PUT", body: JSON.stringify(settings) }),
    chooseFolder: () => request("/api/settings/choose-folder", { method: "POST" }),
    savePage: (payload) =>
      request("/api/pages", { method: "POST", body: JSON.stringify(payload) }),
    createMediaJob: (payload) =>
      request("/api/media/jobs", { method: "POST", body: JSON.stringify(payload) }),
    getMediaJob: (jobId) => request(`/api/media/jobs/${encodeURIComponent(jobId)}`),
    storageGet,
    storageSet,
    storageRemove,
  };
})(globalThis);
