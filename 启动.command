#!/bin/zsh
cd "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/audiotag ]]; then
  print '请先按 README.md 安装依赖。'
  read '?按回车退出'
  exit 1
fi
exec .venv/bin/audiotag serve
