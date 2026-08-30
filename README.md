# 拾页 · Local Web Clipper

一个本地优先的 Chrome 扩展，将当前网页或公开音视频链接转换成带 metadata 的 Markdown，并保存到你选择的本地文件夹。

快速上手请看：[如何使用](./docs/如何使用.md)；完整的成本、隐私和技术选型说明见：[使用说明与成本评估](./docs/使用说明与成本评估.md)。

## 已实现

- 当前网页：提取标题、作者、发布日期、网址、站点、描述、标签和正文。
- 音视频链接：YouTube 字幕优先；没有字幕时使用 `yt-dlp + Whisper` 本地转写。
- Markdown：YAML frontmatter、完整正文/转写、可选 AI 摘要、核心要点和标签。
- 本地保存：首次选择根目录，网页和转写分别进入可配置子目录。
- 后台任务：关闭扩展弹窗后转写继续运行，重新打开可恢复进度。
- AI 服务：支持 OpenAI-compatible 接口和本地 Ollama；未配置时核心功能照常使用。
- 本地安全：服务只监听 `127.0.0.1`，写操作需要扩展配对令牌，API Key 不进入扩展代码。
- 请求保护：网页剪藏请求最大 8MB，异常超大页面会提示缩短正文后重试。

## 一次性安装

### 1. 安装本地服务

首次使用双击 [setup.command](./setup.command)。它会在项目内创建 `.venv` 并安装依赖。

本机还需要 FFmpeg：

```bash
brew install ffmpeg
```

如果当前 Python 已经包含 Flask、Whisper、yt-dlp 和 YouTube 字幕库，可以跳过 `setup.command`。

### 2. 启动本地服务

双击 [start.command](./start.command)，并保持打开的终端窗口运行。看到下面的信息即表示成功：

```text
[拾页] 地址：http://127.0.0.1:43127
```

### 3. 加载 Chrome 扩展

1. 在 Chrome 地址栏打开 `chrome://extensions`。
2. 打开右上角“开发者模式”。
3. 点击“加载已解压的扩展程序”。
4. 选择本项目的 `extension` 文件夹：

```text
~/local-web-clipper/extension
```

5. 将“拾页”固定到浏览器工具栏。

### 4. 选择 Markdown 文件夹

打开扩展设置，点击“选择文件夹”。macOS 会弹出目录选择窗口。选择一次后，网页和转写结果会自动写入该目录。

## 使用方式

### 剪藏网页

打开普通网页，点击“拾页”，切换到“网页正文”，点击【本页】提取并清理正文，然后点击底部“保存正文”。如果网页中已有选中文本，扩展优先剪藏选区。

### 转写音视频

打开扩展的“音视频转写”，粘贴公开链接或“标题 + 链接”的分享文本，然后点击“开始转写”。任务会依次读取媒体信息、查找字幕、必要时提取音频并用 Whisper 转写，最后保存带时间戳的 Markdown。

仅处理你有权访问、下载和转写的内容。需要登录、付费、DRM 或受到平台限制的链接可能无法处理。

## AI 设置

AI 整理是可选项，不负责基础转写：

- `OpenAI 兼容接口`：填写 Base URL、模型和 API Key。
- `本地 Ollama`：默认地址为 `http://127.0.0.1:11434`，只需填写本地模型名称。

第三方 AI 开启时，待整理文字会发送给你配置的服务。未开启时，网页与转写内容留在电脑中。

## 开发与测试

```bash
python -m unittest discover -s server/tests -v
for js_file in extension/*.js; do node --check "$js_file"; done
python -m server.app
```

默认配置保存在：

```text
~/.local-web-clipper/config.json
```

配置文件权限为 `0600`，只允许当前用户读写。
