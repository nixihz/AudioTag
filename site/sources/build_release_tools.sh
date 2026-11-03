#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/.build/release-tools"
PREFIX="$WORK/prefix"
mkdir -p "$WORK"
cd "$WORK"
echo '8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e  ffmpeg-9.0.2.tar.xz' | shasum -a 256 -c -
echo '3df5124d5ad3a98312ffd7ba6a9b36230e4f8a3e66d3ce0f425e336c32d216eb  lame-4.0.tar.gz' | shasum -a 256 -c -
if [[ ! -d lame-4.0 ]]; then tar -xf lame-4.0.tar.gz; fi
if [[ ! -d ffmpeg-9.0.2 ]]; then tar -xf ffmpeg-9.0.2.tar.xz; fi
cd "$WORK/lame-4.0"
if [[ -f Makefile ]]; then make distclean > "$WORK/lame-clean.log" 2>&1; fi
./configure --prefix="$PREFIX" --disable-static --enable-shared --disable-frontend --disable-decoder > "$WORK/lame-configure.log" 2>&1
make -j 8 > "$WORK/lame-make.log" 2>&1
make install > "$WORK/lame-install.log" 2>&1
cd "$WORK/ffmpeg-9.0.2"
# 禁用自动发现和 GPL 扩展，只保留本地解码与 MP3 编码所需的依赖。
./configure --prefix="$PREFIX" --disable-autodetect --disable-doc --disable-debug \
  --disable-ffplay --disable-network --disable-shared --enable-static \
  --enable-libmp3lame --extra-cflags="-I$PREFIX/include" \
  --extra-ldflags="-L$PREFIX/lib" > "$WORK/ffmpeg-configure.log" 2>&1
make -j 8 > "$WORK/ffmpeg-make.log" 2>&1
make install > "$WORK/ffmpeg-install.log" 2>&1
cd "$ROOT"
PATH="$PREFIX/bin:$PATH" AUDIOTAG_TOOLS_PREFIX="$PREFIX" .venv/bin/python script/bundle_tools.py "$WORK/bundle-encoder-only"
mkdir -p Config/Licenses site/sources
cp "$WORK/ffmpeg-9.0.2/COPYING.LGPLv2.1" Config/Licenses/FFmpeg-LGPL-2.1.txt
cp "$WORK/ffmpeg-9.0.2/LICENSE.md" Config/Licenses/FFmpeg-LICENSE.md
cp "$WORK/lame-4.0/COPYING" Config/Licenses/LAME-LGPL.txt
cp "$WORK/ffmpeg-9.0.2.tar.xz" "$WORK/lame-4.0.tar.gz" site/sources/
cp script/build_release_tools.sh script/bundle_tools.py site/sources/
cp -R Config/Licenses/. site/sources/
cp "$WORK/bundle-encoder-only/BUILD-NOTICES.txt" site/sources/
