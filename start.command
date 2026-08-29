#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h}"
cd "$project_dir"

if [[ -x ".venv/bin/python" ]]; then
  python_bin=".venv/bin/python"
else
  python_bin="python"
fi

if ! "$python_bin" -c "import flask, requests, whisper, yt_dlp, youtube_transcript_api" 2>/dev/null; then
  echo "[拾页] 缺少运行依赖。请先双击 setup.command 完成一次安装。"
  read "reply?按回车键关闭窗口。"
  exit 1
fi

echo "[拾页] 本地服务启动中…"
echo "[拾页] 地址：http://127.0.0.1:43127"
echo "[拾页] 保持本窗口开启；按 Control+C 可停止。"
echo
exec "$python_bin" -m server.app
