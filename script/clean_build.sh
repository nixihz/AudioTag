#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$ROOT_DIR" != "/" && -d "$ROOT_DIR" ]] || {
  echo "拒绝清理：无法确认仓库根目录" >&2
  exit 1
}

for path in "$ROOT_DIR/dist" "$ROOT_DIR/.build"; do
  [[ "$path" = "$ROOT_DIR/dist" || "$path" = "$ROOT_DIR/.build" ]] || {
    echo "拒绝清理：路径不在项目输出目录白名单内" >&2
    exit 1
  }
  [[ ! -L "$path" ]] || {
    echo "拒绝清理符号链接：$path" >&2
    exit 1
  }
  if [[ -e "$path" ]]; then
    rm -rf "$path"
    echo "已清理：$path"
  else
    echo "未找到：$path"
  fi
done
