const IS_EXTENSION = typeof chrome !== "undefined" && Boolean(chrome.runtime?.id);
const ACTIVE_JOB_KEY = "localClipperActiveMediaJob";

const elements = {
  serviceDot: document.getElementById("service-dot"), serviceLabel: document.getElementById("service-label"),
  saveLocation: document.getElementById("save-location"), saveLocationText: document.getElementById("save-location-text"),
  openSettings: document.getElementById("open-settings"), currentPage: document.getElementById("use-current-page"),
  resourceForm: document.getElementById("resource-form"), resourceUrl: document.getElementById("resource-url"),
  resourceSubmit: document.getElementById("resource-submit"), pagePreview: document.getElementById("page-preview"),
  pageContent: document.getElementById("page-content"),
  message: document.getElementById("message"), jobCard: document.getElementById("job-card"), jobStageNumber: document.getElementById("job-stage-number"),
  jobStage: document.getElementById("job-stage"), jobDetail: document.getElementById("job-detail"), jobProgress: document.getElementById("job-progress"), jobResult: document.getElementById("job-result"),
};

const stageMap = { queued:["01","排队中",8], starting:["02","准备处理",15], validating:["03","检查链接",20], metadata:["04","读取媒体信息",28], captions:["05","查找字幕",42], downloading:["06","提取音频",58], transcribing:["07","本地转写",74], organizing:["08","整理 Markdown",88], done:["09","已经保存",100], error:["!","处理失败",100] };
let pageData = null; let settings = null; let pollTimer = null; let activeMode = "page";

function showMessage(text, type = "success") { elements.message.textContent = text; elements.message.classList.remove("is-hidden", "is-error"); elements.message.classList.toggle("is-error", type === "error"); }
function showSavedMessage(filename, path, warning = "") { elements.message.replaceChildren(); elements.message.classList.remove("is-hidden", "is-error"); const link = document.createElement("a"); link.textContent = filename || "打开文档"; link.href = `file://${encodeURI(path || "")}`; link.title = "打开 Markdown 文档"; link.addEventListener("click", (event) => { if (IS_EXTENSION && chrome.tabs?.create) { event.preventDefault(); chrome.tabs.create({ url: link.href }); } }); elements.message.append(document.createTextNode("已保存："), link); if (warning) elements.message.append(document.createTextNode(`；${warning}`)); }
function hideMessage() { elements.message.classList.add("is-hidden"); }
function displayFolderName(path) { if (!path) return "尚未选择保存文件夹"; return path.replace(/[\\/]$/, "").split(/[\\/]/).pop() || path; }
function setServiceState(online, detail = "") { elements.serviceDot.classList.toggle("is-online", online); elements.serviceDot.classList.toggle("is-offline", !online); elements.serviceLabel.textContent = online ? "本地服务已连接" : "本地服务未运行"; elements.saveLocationText.textContent = online ? displayFolderName(detail) : "请先运行 start.command"; }
function isVideoUrl(value) { try { const url = new URL(value); return /(^|\.)((youtube\.com)|(youtu\.be)|(vimeo\.com)|(bilibili\.com)|(soundcloud\.com))$/i.test(url.hostname) || /\.(mp3|mp4|m4a|webm|mov|wav|ogg)(?:$|\?)/i.test(url.pathname); } catch { return false; } }

async function connect() {
  try { await ClipperAPI.health(); const response = await ClipperAPI.getSettings(); settings = response.settings; setServiceState(true, settings.save_root || "尚未选择保存文件夹"); if (!settings.save_root) showMessage("点击左上角保存位置，先选择 Markdown 文件夹。", "error"); return true; }
  catch (error) { setServiceState(false); showMessage(`无法连接本地服务：${error.message}`, "error"); return false; }
}

async function chooseFolder() {
  if (!IS_EXTENSION) return showMessage("预览模式下无法切换文件夹。", "error");
  try { const response = await ClipperAPI.chooseFolder(); settings = response.settings; setServiceState(true, settings.save_root || "尚未选择保存文件夹"); showMessage("保存文件夹已更新。"); }
  catch (error) { if (!/取消选择文件夹/.test(error.message)) showMessage(error.message, "error"); }
}

async function getCurrentTab() { const [tab] = await chrome.tabs.query({ active:true, currentWindow:true }); if (!tab?.id || !/^https?:/i.test(tab.url || "")) throw new Error("该页面不允许扩展读取，请打开普通网页后重试"); return tab; }
async function extractCurrentPage() {
  try { const tab = await getCurrentTab(); const result = await chrome.scripting.executeScript({ target:{ tabId:tab.id }, files:["page-extractor.js"] }); pageData = result?.[0]?.result; if (!pageData?.content) throw new Error("没有提取到网页正文"); elements.resourceUrl.value = tab.url; elements.resourceUrl.placeholder = "粘贴链接"; elements.pageContent.value = pageData.content; elements.pagePreview.classList.remove("is-hidden"); elements.resourceSubmit.querySelector("span").textContent = "保存正文"; }
  catch (error) { showMessage(`网页提取失败：${error.message}`, "error"); }
}
async function fillCurrentUrl() { try { const tab = await getCurrentTab(); if (isVideoUrl(tab.url)) { elements.resourceUrl.value = tab.url; } else { await extractCurrentPage(); } } catch (error) { showMessage(error.message, "error"); } }

async function saveCurrentPage() {
  if (!pageData) return showMessage("请先点击“当前页”读取正文。", "error");
  try { const response = await ClipperAPI.savePage({ metadata:{ ...pageData, created:new Date().toISOString(), tags:["inbox","网页剪藏"] }, content:elements.pageContent.value.trim(), ai_organize:false }); showSavedMessage(response.filename, response.path, response.warning); }
  catch (error) { showMessage(error.message, "error"); }
}

async function startMediaJob() {
  try { const response = await ClipperAPI.createMediaJob({ url:elements.resourceUrl.value.trim(), ai_organize:false }); await ClipperAPI.storageSet({ [ACTIVE_JOB_KEY]:response.job_id }); elements.jobCard.classList.remove("is-hidden"); elements.resourceSubmit.disabled = true; elements.resourceSubmit.querySelector("span").textContent = "正在转写…"; renderJob({ stage:"queued", detail:"任务已提交到本地服务", status:"queued" }); pollJob(response.job_id); }
  catch (error) { elements.resourceSubmit.disabled = false; elements.resourceSubmit.querySelector("span").textContent = "保存到本地"; showMessage(error.message, "error"); }
}

async function submitResource(event) { event.preventDefault(); hideMessage(); const url = elements.resourceUrl.value.trim(); if (activeMode === "media" && !url) return showMessage("请先粘贴音视频链接。", "error"); if (activeMode === "page" && !pageData) return showMessage("请先点击“本页”读取正文。", "error"); elements.resourceSubmit.disabled = true; try { if (activeMode === "media" || isVideoUrl(url)) await startMediaJob(); else await saveCurrentPage(); } finally { if (activeMode !== "media" && !isVideoUrl(url)) elements.resourceSubmit.disabled = false; } }
function renderJob(job) { const [number,label,progress] = stageMap[job.stage] || stageMap.starting; elements.jobStageNumber.textContent = number; elements.jobStage.textContent = label; elements.jobDetail.textContent = job.status === "error" ? `错误代码：${job.error_code || "MEDIA_UNKNOWN"} · 阶段：${job.error_stage || job.stage || "unknown"}` : (job.detail || "正在处理"); elements.jobProgress.style.width = `${progress}%`; if (job.status === "done") { elements.jobResult.replaceChildren(); const link = document.createElement("a"); link.textContent = `已保存：${job.result?.filename || "打开文档"}`; link.href = `file://${encodeURI(job.result?.path || "")}`; link.title = "打开 Markdown 文档"; link.addEventListener("click", (event) => { if (IS_EXTENSION && chrome.tabs?.create) { event.preventDefault(); chrome.tabs.create({ url: link.href }); } }); elements.jobResult.append(link); } else elements.jobResult.textContent = job.status === "error" ? (job.error_detail || job.error || "处理失败") : "可以关闭弹窗，任务会在本地继续运行。"; }
function pollJob(jobId) { clearTimeout(pollTimer); const tick = async () => { try { const job = await ClipperAPI.getMediaJob(jobId); elements.jobCard.classList.remove("is-hidden"); renderJob(job); if (["done","error"].includes(job.status)) { await ClipperAPI.storageRemove([ACTIVE_JOB_KEY]); elements.resourceSubmit.disabled = false; elements.resourceSubmit.querySelector("span").textContent = "保存到本地"; if (job.status === "done") showMessage(`转写完成：${job.result.filename}`); return; } pollTimer = setTimeout(tick, 1400); } catch (error) { showMessage(`无法读取任务状态：${error.message}`, "error"); } }; tick(); }
async function restoreMediaJob() { const stored = await ClipperAPI.storageGet([ACTIVE_JOB_KEY]); if (stored[ACTIVE_JOB_KEY]) pollJob(stored[ACTIVE_JOB_KEY]); }

function loadPreviewMode() { setServiceState(true, "~/Documents/Knowledge/Inbox"); elements.resourceUrl.placeholder = "点击【本页】提取当前页面"; elements.pageContent.value = "## 示例正文\n\n点击“本页”后，这里会显示当前网页转换后的 Markdown 正文。"; elements.pagePreview.classList.remove("is-hidden"); elements.resourceSubmit.querySelector("span").textContent = "保存正文"; }

elements.openSettings.addEventListener("click", () => { if (IS_EXTENSION) chrome.runtime.openOptionsPage(); });
elements.saveLocation.addEventListener("click", chooseFolder); elements.currentPage.addEventListener("click", fillCurrentUrl); elements.resourceForm.addEventListener("submit", submitResource);
document.querySelectorAll(".mode-tab").forEach((tab) => tab.addEventListener("click", () => { activeMode = tab.dataset.mode; document.querySelectorAll(".mode-tab").forEach((item) => item.classList.toggle("is-active", item === tab)); elements.resourceUrl.placeholder = activeMode === "media" ? "粘贴音视频链接" : (pageData ? "本页已读取，可直接保存" : "点击【本页】提取当前页面"); elements.pagePreview.classList.toggle("is-hidden", activeMode !== "page" || !pageData); elements.jobCard.classList.toggle("is-hidden", activeMode !== "media"); elements.resourceSubmit.querySelector("span").textContent = activeMode === "media" ? "开始转写" : (pageData ? "保存正文" : "保存到本地"); }));

async function init() { if (!IS_EXTENSION) return loadPreviewMode(); const online = await connect(); if (online) await restoreMediaJob(); }
init();
