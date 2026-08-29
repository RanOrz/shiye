#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h}"
cd "$project_dir"

echo "[拾页] 正在创建独立 Python 环境…"
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "[拾页] 安装完成。以后双击 start.command 即可启动本地服务。"
read "reply?按回车键关闭窗口。"
