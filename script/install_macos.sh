#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
APP_BUNDLE="${APP_BUNDLE:-$ROOT_DIR/dist/AudioTag.app}"
CLI_BINARY="${CLI_BINARY:-$ROOT_DIR/dist/audiotag}"
TOOLS_BUNDLE="${TOOLS_BUNDLE:-$ROOT_DIR/dist/tools}"
INSTALL_APP="${INSTALL_APP:-/Applications/AudioTag.app}"
INSTALL_BIN="${INSTALL_BIN:-/usr/local/bin/audiotag}"
INSTALL_TOOLS="${INSTALL_TOOLS:-/usr/local/bin/tools}"
HOME_DIR="${HOME:-}"

fail() {
  echo "安装失败：$*" >&2
  exit 1
}

canonical_path() {
  local path="$1"
  local parent
  parent="$(cd -P "$(dirname "$path")" 2>/dev/null && pwd)" || fail "无法访问目标目录：$(dirname "$path")"
  printf '%s/%s\n' "$parent" "$(basename "$path")"
}

validate_target() {
  local path="$1"
  [[ -n "$path" && "$path" = /* ]] || fail "安装目标必须是绝对路径：$path"
  case "$path" in
    /|"$ROOT_DIR"|"$HOME_DIR"|/Applications|/usr|/usr/local)
      fail "拒绝使用过宽或危险的安装目标：$path"
      ;;
  esac
}

for artifact in "$APP_BUNDLE" "$CLI_BINARY" "$TOOLS_BUNDLE/ffmpeg" "$TOOLS_BUNDLE/ffprobe"; do
  [[ -e "$artifact" ]] || fail "缺少构建产物：$artifact，请先运行 task macos:build"
done
[[ -d "$APP_BUNDLE" ]] || fail "应用产物不是目录：$APP_BUNDLE"
[[ -x "$CLI_BINARY" ]] || fail "CLI 产物不可执行：$CLI_BINARY"

for target in "$INSTALL_APP" "$INSTALL_BIN" "$INSTALL_TOOLS"; do
  validate_target "$target"
  mkdir -p "$(dirname "$target")"
done

source_app="$(canonical_path "$APP_BUNDLE")"
source_cli="$(canonical_path "$CLI_BINARY")"
source_tools="$(canonical_path "$TOOLS_BUNDLE")"
for target in "$INSTALL_APP" "$INSTALL_BIN" "$INSTALL_TOOLS"; do
  target_path="$(canonical_path "$target")"
  case "$target_path" in
    "$source_app"|"$source_cli"|"$source_tools")
      fail "源产物与安装目标不能相同：$target"
      ;;
  esac
done

targets=("$INSTALL_APP" "$INSTALL_TOOLS" "$INSTALL_BIN")
for ((index = 0; index < ${#targets[@]}; index++)); do
  first="$(canonical_path "${targets[index]}")"
  for ((other = index + 1; other < ${#targets[@]}; other++)); do
    [[ "$first" != "$(canonical_path "${targets[other]}")" ]] ||
      fail "安装目标重复：${targets[index]}"
  done
done

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/audiotag-install.XXXXXX")"
stage_app="$work_dir/AudioTag.app"
stage_tools="$work_dir/tools"
stage_cli="$work_dir/audiotag"
backup_paths=()
replaced=()
rollback_needed=1

rollback() {
  local index
  for ((index = ${#targets[@]} - 1; index >= 0; index--)); do
    if [[ "${replaced[index]:-0}" = 1 ]]; then
      rm -rf "${targets[index]}"
    fi
    if [[ -n "${backup_paths[index]:-}" && ( -e "${backup_paths[index]}" || -L "${backup_paths[index]}" ) ]]; then
      mv "${backup_paths[index]}" "${targets[index]}"
    fi
  done
}

cleanup() {
  local status=$?
  if [[ "$rollback_needed" = 1 ]]; then
    rollback || echo "警告：安装失败后的回滚也失败，请检查安装目标" >&2
  fi
  rm -rf "$work_dir"
  exit "$status"
}
trap cleanup EXIT

/usr/bin/ditto --rsrc --extattr --acl "$APP_BUNDLE" "$stage_app"
/usr/bin/ditto --rsrc --extattr --acl "$TOOLS_BUNDLE" "$stage_tools"
/usr/bin/ditto --rsrc --extattr --acl "$CLI_BINARY" "$stage_cli"
chmod 755 "$stage_cli" "$stage_tools/ffmpeg" "$stage_tools/ffprobe"

/usr/bin/codesign --verify --deep --strict "$stage_app"
/usr/bin/codesign --verify --deep --strict "$stage_cli"
"$stage_cli" capabilities >/dev/null

for ((index = 0; index < ${#targets[@]}; index++)); do
  target="${targets[index]}"
  backup="${target}.audiotag-backup.$$.$index"
  [[ ! -e "$backup" && ! -L "$backup" ]] || fail "备份目标已存在：$backup"
  if [[ -e "$target" || -L "$target" ]]; then
    mv "$target" "$backup"
    backup_paths[index]="$backup"
  else
    backup_paths[index]=""
  fi
  case "$index" in
    0) mv "$stage_app" "$target" ;;
    1) mv "$stage_tools" "$target" ;;
    2) mv "$stage_cli" "$target" ;;
  esac
  replaced[index]=1
done

/usr/bin/codesign --verify --deep --strict "$INSTALL_APP"
/usr/bin/codesign --verify --deep --strict "$INSTALL_BIN"
"$INSTALL_BIN" capabilities >/dev/null
chmod 755 "$INSTALL_BIN" "$INSTALL_TOOLS/ffmpeg" "$INSTALL_TOOLS/ffprobe"

for backup in "${backup_paths[@]}"; do
  [[ -z "$backup" ]] || rm -rf "$backup"
done
rollback_needed=0

echo "已安装：$INSTALL_APP"
echo "已安装：$INSTALL_BIN"
echo "已安装：$INSTALL_TOOLS"
