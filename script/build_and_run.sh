#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
MODE="${1:-run}"
CONFIGURATION="${CONFIGURATION:-debug}"
SIGNING_IDENTITY="${SIGNING_IDENTITY:--}"
if [[ "$MODE" != "--build-only" ]]; then
  pkill -x AudioTag >/dev/null 2>&1 || true
  pkill -x Mp3tag >/dev/null 2>&1 || true
fi
if [[ ! -x .venv/bin/pyinstaller ]]; then
  uv venv .venv --allow-existing
  uv pip install --python .venv/bin/python -e '.[dev]' pyinstaller
fi
if [[ ! -x dist/audiotag ]] || ! .venv/bin/python - <<'PY'
from pathlib import Path
import sys
binary = Path('dist/audiotag')
sources = [Path('script/engine_entry.py'), *Path('mp3tag').glob('*.py')]
sys.exit(0 if binary.exists() and all(path.stat().st_mtime <= binary.stat().st_mtime for path in sources) else 1)
PY
then
  .venv/bin/pyinstaller --noconfirm --onefile --name audiotag --distpath dist --workpath .build/python --specpath .build --paths . script/engine_entry.py >/dev/null
fi
# Keep the old filename as a local compatibility alias for existing scripts.
rm -rf dist/mp3tag
ln -s audiotag dist/mp3tag
swift build -c "$CONFIGURATION"
APP_BUNDLE="${APP_BUNDLE:-$ROOT_DIR/dist/AudioTag.app}"
if [[ ! -f dist/tools/BUILD-NOTICES.txt || script/bundle_tools.py -nt dist/tools/BUILD-NOTICES.txt || "$(command -v ffmpeg)" -nt dist/tools/BUILD-NOTICES.txt ]]; then
  .venv/bin/python script/bundle_tools.py "$ROOT_DIR/dist/tools"
fi
.venv/bin/python script/stage_app.py "$(swift build -c "$CONFIGURATION" --show-bin-path)/AudioTag" "$APP_BUNDLE" "$SIGNING_IDENTITY"
case "$MODE" in
  --build-only) ;;
  run) /usr/bin/open -n "$APP_BUNDLE" ;;
  --verify) /usr/bin/open -n "$APP_BUNDLE"; sleep 1; pgrep -x AudioTag >/dev/null ;;
  --debug) lldb -- "$APP_BUNDLE/Contents/MacOS/AudioTag" ;;
  --logs|--telemetry) /usr/bin/open -n "$APP_BUNDLE"; /usr/bin/log stream --info --style compact --predicate 'process == "AudioTag"' ;;
  *) echo "用法：$0 [--build-only|--verify|--debug|--logs|--telemetry]" >&2; exit 2 ;;
esac
