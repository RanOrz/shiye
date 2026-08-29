const IS_EXTENSION = typeof chrome !== "undefined" && Boolean(chrome.runtime?.id);
const ACTIVE_JOB_KEY = "localClipperActiveMediaJob";

const elements = {
  serviceDot: document.getElementById("service-dot"),
  serviceLabel: document.getElementById("service-label"),
  saveLocation: document.getElementById("save-location"),
  message: document.getElementById("message"),
  pageLoading: document.getElementById("page-loading"),
  pageForm: document.getElementById("page-form"),
  pageTitle: document.getElementById("page-title"),
  pageAuthor: document.getElementById("page-author"),
  pagePublished: document.getElementById("page-published"),
  pageTags: document.getElementById("page-tags"),
  pageContent: document.getElementById("page-content"),
  pageWordCount: document.getElementById("page-word-count"),
  pageAi: document.getElementById("page-ai"),
  savePage: document.getElementById("save-page"),
  mediaForm: document.getElementById("media-form"),
  mediaUrl: document.getElementById("media-url"),
  mediaAi: document.getElementById("media-ai"),
  startMedia: document.getElementById("start-media"),
  jobCard: document.getElementById("job-card"),
  jobStageNumber: document.getElementById("job-stage-number"),
  jobStage: document.getElementById("job-stage"),
  jobDetail: document.getElementById("job-detail"),
  jobProgress: document.getElementById("job-progress"),
  jobResult: document.getElementById("job-result"),
};

const stageMap = {
  queued: ["01", "排队中", 8],
  starting: ["02", "准备处理", 15],
  metadata: ["03", "读取媒体信息", 28],
  captions: ["04", "查找字幕", 42],
  downloading: ["05", "提取音频", 58],
  transcribing: ["06", "本地转写", 74],
  organizing: ["07", "整理 Markdown", 88],
  done: ["08", "已经保存", 100],
  error: ["!", "处理失败", 100],
};

let pageData = null;
let settings = null;
let pollTimer = null;

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("is-active", item === tab));
    document.querySelectorAll(".panel").forEach((panel) => panel.classList.toggle("is-active", panel.id === tab.dataset.panel));
  });
});

document.getElementById("open-settings").addEventListener("click", () => {
  if (IS_EXTENSION) chrome.runtime.openOptionsPage();
});

elements.pageContent.addEventListener("input", updateWordCount);
elements.pageForm.addEventListener("submit", saveCurrentPage);
elements.mediaForm.addEventListener("submit", startMediaJob);

function showMessage(text, type = "success") {
  elements.message.textContent = text;
  elements.message.classList.remove("is-hidden", "is-error");
  elements.message.classList.toggle("is-error", type === "error");
}

function hideMessage() {
  elements.message.classList.add("is-hidden");
}

function setServiceState(online, detail = "") {
  elements.serviceDot.classList.toggle("is-online", online);
  elements.serviceDot.classList.toggle("is-offline", !online);
  elements.serviceLabel.textContent = online ? "本地服务已连接" : "本地服务未运行";
  elements.saveLocation.textContent = detail || (online ? "尚未选择保存文件夹" : "请先运行 start.command");
}

function updateWordCount() {
  const count = elements.pageContent.value.replace(/\s+/g, "").length;
  elements.pageWordCount.textContent = `${count.toLocaleString()} 字`;
}

async function connect() {
  try {
    await ClipperAPI.health();
    const response = await ClipperAPI.getSettings();
    settings = response.settings;
    setServiceState(true, settings.save_root || "尚未选择保存文件夹");
    if (!settings.save_root) showMessage("请先在设置中选择 Markdown 保存文件夹。", "error");
    return true;
  } catch (error) {
    setServiceState(false);
    showMessage(`无法连接本地服务：${error.message}`, "error");
    return false;
  }
}

async function extractCurrentPage() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !/^https?:/i.test(tab.url || "")) {
      throw new Error("该页面不允许扩展读取，请打开普通网页后重试");
    }
    const result = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["page-extractor.js"],
    });
    pageData = result?.[0]?.result;
    if (!pageData?.content) throw new Error("没有提取到网页正文");
    elements.pageTitle.value = pageData.title;
    elements.pageAuthor.value = pageData.author;
    elements.pagePublished.value = pageData.published;
    const defaultTags = ["inbox", "网页剪藏", ...(pageData.tags || [])];
    elements.pageTags.value = [...new Set(defaultTags)].slice(0, 8).join(", ");
    elements.pageContent.value = pageData.content;
    updateWordCount();
    elements.pageLoading.classList.add("is-hidden");
    elements.pageForm.classList.remove("is-hidden");
  } catch (error) {
    elements.pageLoading.classList.add("is-hidden");
    showMessage(`网页提取失败：${error.message}`, "error");
  }
}

async function saveCurrentPage(event) {
  event.preventDefault();
  hideMessage();
  if (!pageData) return showMessage("请重新打开扩展读取当前页面。", "error");
  elements.savePage.disabled = true;
  elements.savePage.querySelector("span").textContent = "正在保存…";
  try {
    const response = await ClipperAPI.savePage({
      metadata: {
        ...pageData,
        title: elements.pageTitle.value.trim(),
        author: elements.pageAuthor.value.trim(),
        published: elements.pagePublished.value.trim(),
        created: new Date().toISOString(),
        tags: elements.pageTags.value.split(/[,，\n]/).map((tag) => tag.trim()).filter(Boolean),
      },
      content: elements.pageContent.value.trim(),
      ai_organize: elements.pageAi.checked,
    });
    showMessage(`已保存：${response.filename}${response.warning ? `；${response.warning}` : ""}`);
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    elements.savePage.disabled = false;
    elements.savePage.querySelector("span").textContent = "保存到本地";
  }
}

async function startMediaJob(event) {
  event.preventDefault();
  hideMessage();
  elements.startMedia.disabled = true;
  elements.startMedia.querySelector("span").textContent = "正在提交…";
  try {
    const response = await ClipperAPI.createMediaJob({
      url: elements.mediaUrl.value.trim(),
      ai_organize: elements.mediaAi.checked,
    });
    await ClipperAPI.storageSet({ [ACTIVE_JOB_KEY]: response.job_id });
    elements.jobCard.classList.remove("is-hidden");
    renderJob({ stage: "queued", detail: "任务已提交到本地服务", status: "queued" });
    pollJob(response.job_id);
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    elements.startMedia.disabled = false;
    elements.startMedia.querySelector("span").textContent = "开始转写";
  }
}

function renderJob(job) {
  const [number, label, progress] = stageMap[job.stage] || stageMap.starting;
  elements.jobStageNumber.textContent = number;
  elements.jobStage.textContent = label;
  elements.jobDetail.textContent = job.detail || "正在处理";
  elements.jobProgress.style.width = `${progress}%`;
  elements.jobProgress.style.background = job.status === "error" ? "var(--signal)" : "var(--signal)";
  if (job.status === "done") {
    const warning = job.result?.warning ? ` · ${job.result.warning}` : "";
    elements.jobResult.textContent = `已保存到 ${job.result?.path || "本地文件夹"}${warning}`;
  } else if (job.status === "error") {
    elements.jobResult.textContent = job.error || "处理失败";
  } else {
    elements.jobResult.textContent = "可以关闭弹窗，任务会在本地继续运行。";
  }
}

function pollJob(jobId) {
  clearTimeout(pollTimer);
  const tick = async () => {
    try {
      const job = await ClipperAPI.getMediaJob(jobId);
      elements.jobCard.classList.remove("is-hidden");
      renderJob(job);
      if (["done", "error"].includes(job.status)) {
        await ClipperAPI.storageRemove([ACTIVE_JOB_KEY]);
        if (job.status === "done") showMessage(`转写完成：${job.result.filename}`);
        return;
      }
      pollTimer = setTimeout(tick, 1400);
    } catch (error) {
      showMessage(`无法读取任务状态：${error.message}`, "error");
    }
  };
  tick();
}

async function restoreMediaJob() {
  const stored = await ClipperAPI.storageGet([ACTIVE_JOB_KEY]);
  if (stored[ACTIVE_JOB_KEY]) pollJob(stored[ACTIVE_JOB_KEY]);
}

function loadPreviewMode() {
  setServiceState(true, "~/Documents/Knowledge/Inbox");
  elements.pageLoading.classList.add("is-hidden");
  elements.pageForm.classList.remove("is-hidden");
  elements.pageTitle.value = "浏览器里的知识，应该回到你的文件夹";
  elements.pageAuthor.value = "示例作者";
  elements.pagePublished.value = "2026-08-30";
  elements.pageContent.value = "## 示例正文\n\n这是扩展的视觉预览。真实使用时，这里会显示当前网页转换后的 Markdown。";
  updateWordCount();
}

async function init() {
  if (!IS_EXTENSION) return loadPreviewMode();
  const online = await connect();
  await extractCurrentPage();
  if (online) await restoreMediaJob();
}

init();
