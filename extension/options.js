const IS_EXTENSION_OPTIONS = typeof chrome !== "undefined" && Boolean(chrome.runtime?.id);

const ui = {
  form: document.getElementById("settings-form"),
  connectionCard: document.getElementById("connection-card"),
  connectionLabel: document.getElementById("connection-label"),
  connectionDetail: document.getElementById("connection-detail"),
  saveRoot: document.getElementById("save-root"),
  chooseFolder: document.getElementById("choose-folder"),
  pageSubdir: document.getElementById("page-subdir"),
  mediaSubdir: document.getElementById("media-subdir"),
  whisperModel: document.getElementById("whisper-model"),
  aiEnabled: document.getElementById("ai-enabled"),
  aiFields: document.getElementById("ai-fields"),
  aiProvider: document.getElementById("ai-provider"),
  aiModel: document.getElementById("ai-model"),
  aiBaseUrl: document.getElementById("ai-base-url"),
  apiKeyField: document.getElementById("api-key-field"),
  aiApiKey: document.getElementById("ai-api-key"),
  keyStatus: document.getElementById("key-status"),
  clearKey: document.getElementById("clear-key"),
  formMessage: document.getElementById("form-message"),
  saveSettings: document.getElementById("save-settings"),
};

let clearApiKey = false;

ui.aiEnabled.addEventListener("change", updateAiVisibility);
ui.aiProvider.addEventListener("change", () => updateProvider(true));
ui.chooseFolder.addEventListener("click", chooseFolder);
ui.clearKey.addEventListener("click", () => {
  clearApiKey = true;
  ui.aiApiKey.value = "";
  ui.keyStatus.textContent = "保存后清除";
});
ui.form.addEventListener("submit", saveSettings);

function setConnection(online, detail = "") {
  ui.connectionCard.classList.toggle("is-online", online);
  ui.connectionCard.classList.toggle("is-offline", !online);
  ui.connectionLabel.textContent = online ? "本地服务已连接" : "本地服务未运行";
  ui.connectionDetail.textContent = detail || (online ? "127.0.0.1:43127" : "请双击 start.command 后刷新页面");
}

function setMessage(text, error = false) {
  ui.formMessage.textContent = text;
  ui.formMessage.style.color = error ? "var(--coral)" : "var(--green)";
}

function updateAiVisibility() {
  ui.aiFields.classList.toggle("is-disabled", !ui.aiEnabled.checked);
}

function updateProvider(setDefaults = false) {
  const ollama = ui.aiProvider.value === "ollama";
  ui.apiKeyField.classList.toggle("is-hidden", ollama);
  if (setDefaults) {
    ui.aiBaseUrl.value = ollama ? "http://127.0.0.1:11434" : "https://api.openai.com/v1";
    ui.aiModel.placeholder = ollama ? "例如：qwen3:8b" : "例如：gpt-4.1-mini";
  }
}

function populate(settings) {
  ui.saveRoot.value = settings.save_root || "";
  ui.pageSubdir.value = settings.page_subdir || "网页剪藏";
  ui.mediaSubdir.value = settings.media_subdir || "视频转写";
  ui.whisperModel.value = settings.whisper_model || "base";
  ui.aiEnabled.checked = Boolean(settings.ai?.enabled);
  ui.aiProvider.value = settings.ai?.provider || "openai_compatible";
  ui.aiModel.value = settings.ai?.model || "";
  ui.aiBaseUrl.value = settings.ai?.base_url || "https://api.openai.com/v1";
  ui.keyStatus.textContent = settings.ai?.has_api_key ? "已安全保存在本地" : "未保存";
  updateAiVisibility();
  updateProvider(false);
}

async function loadSettings() {
  try {
    const health = await ClipperAPI.health();
    const response = await ClipperAPI.getSettings();
    setConnection(true, `服务版本 ${health.version} · 127.0.0.1:43127`);
    populate(response.settings);
  } catch (error) {
    setConnection(false);
    setMessage(error.message, true);
  }
}

async function chooseFolder() {
  ui.chooseFolder.disabled = true;
  ui.chooseFolder.textContent = "等待选择…";
  setMessage("请在弹出的 macOS 窗口中选择文件夹。", false);
  try {
    const response = await ClipperAPI.chooseFolder();
    populate(response.settings);
    setMessage("文件夹已选择，设置已经保存。", false);
  } catch (error) {
    if (!/取消选择文件夹/.test(error.message)) setMessage(error.message, true);
  } finally {
    ui.chooseFolder.disabled = false;
    ui.chooseFolder.textContent = "选择文件夹";
  }
}

async function saveSettings(event) {
  event.preventDefault();
  ui.saveSettings.disabled = true;
  ui.saveSettings.querySelector("span").textContent = "正在保存…";
  try {
    const ai = {
      enabled: ui.aiEnabled.checked,
      provider: ui.aiProvider.value,
      model: ui.aiModel.value.trim(),
      base_url: ui.aiBaseUrl.value.trim(),
      clear_api_key: clearApiKey,
    };
    if (ui.aiApiKey.value.trim()) ai.api_key = ui.aiApiKey.value.trim();
    const response = await ClipperAPI.saveSettings({
      save_root: ui.saveRoot.value.trim(),
      page_subdir: ui.pageSubdir.value.trim(),
      media_subdir: ui.mediaSubdir.value.trim(),
      whisper_model: ui.whisperModel.value,
      ai,
    });
    clearApiKey = false;
    ui.aiApiKey.value = "";
    populate(response.settings);
    setMessage("设置已保存。", false);
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    ui.saveSettings.disabled = false;
    ui.saveSettings.querySelector("span").textContent = "保存设置";
  }
}

function loadPreview() {
  setConnection(true, "服务版本 0.1.0 · 127.0.0.1:43127");
  populate({
    save_root: "~/Documents/Knowledge/Inbox",
    page_subdir: "网页剪藏",
    media_subdir: "视频转写",
    whisper_model: "base",
    ai: {
      enabled: true,
      provider: "openai_compatible",
      model: "small-model",
      base_url: "https://api.example.com/v1",
      has_api_key: true,
    },
  });
}

if (IS_EXTENSION_OPTIONS) loadSettings();
else loadPreview();
