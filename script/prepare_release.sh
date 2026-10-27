#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
IDENTITY="${SIGNING_IDENTITY:-Developer ID Application: zhixin xie (77TN4427T5)}"
PROFILE="${NOTARY_PROFILE:-samantha-notary}"
WORK="$ROOT/.build/releases/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$WORK"
swift test
.venv/bin/python -m pytest -q
node --test tests/site.test.cjs
bash script/build_release_tools.sh
swift build -c release
.venv/bin/pyinstaller --noconfirm --clean --onefile --codesign-identity "$IDENTITY" \
  --name mp3tag --distpath "$WORK/engine" --workpath "$WORK/python" \
  --specpath "$WORK" --paths "$ROOT" script/engine_entry.py
ENGINE_BINARY="$WORK/engine/mp3tag" TOOLS_BUNDLE="$ROOT/.build/release-tools/bundle-encoder-only" \
  python3 script/stage_app.py .build/release/AudioTag "$WORK/AudioTag.app" "$IDENTITY"
python3 script/verify_engine_bundle.py "$WORK/AudioTag.app"
ditto -c -k --sequesterRsrc --keepParent "$WORK/AudioTag.app" "$WORK/notary-submission.zip"
xcrun notarytool submit "$WORK/notary-submission.zip" --keychain-profile "$PROFILE" \
  --wait --output-format json > "$WORK/notary-result.json"
python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["status"] == "Accepted", "Apple 未接受公证"' "$WORK/notary-result.json"
xcrun stapler staple "$WORK/AudioTag.app"
python3 script/finalize_release.py "$WORK/AudioTag.app"
echo "发行制品已在 site 中准备好，尚未上传；发布前还需检查源码授权、平台登录和实际域名。"
