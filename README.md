# AudioTag

本地音频标签工具。粘贴中文或英文歌曲信息，写入标题、歌手、专辑、流派、年份、音轨、BPM、歌词和封面。支持 MP3、FLAC、M4A/MP4（音频）、OGG Vorbis、Opus、WAV。

项目原名 Mp3tag，现更名为 AudioTag，避免名称被理解为只支持 MP3。原生应用为 `AudioTag.app`，源码安装后使用 `audiotag` 命令；旧的 `mp3tag` 命令继续可用。内部 Python 包、AI 引擎文件名、Bundle ID、更新签名身份和现有站点地址暂时保留，不影响已有集成。

## SwiftUI macOS 应用与 AI 二进制

当前推荐使用 `dist/AudioTag.app`：双击打开 SwiftUI 原生应用。选择或拖入文件，粘贴歌曲信息并解析，然后检查勾选字段、选择封面与导出目录。MP4 默认转成 MP3，默认使用第一个视频帧作为前封面；自选图片优先于首帧。单文件有多音轨时可指定流编号，批量使用每个文件的第一音轨。码率可选 128/192/256/320 kbps。

应用与 AI 二进制都内置 Python 标签引擎；`dist/tools` 和应用资源内打包 FFmpeg、FFprobe 及其非系统动态库。运行不需要 Python、虚拟环境或 Homebrew。当前构建为 Apple Silicon arm64，本地 ad-hoc 签名，未做 Developer ID 签名与公证；SwiftUI 源码最低 macOS 14，但本次打包的 FFmpeg 要求 macOS 26，因此交付包最低 macOS 26，在本机 macOS 27.0.1 验证。AI 二进制分发时需要同时携带 `dist/mp3tag` 与 `dist/tools` 文件夹；完整 `.app` 已自带同一套工具。

从源码构建需 Xcode Command Line Tools、uv、FFmpeg（`brew install ffmpeg`）：

```sh
./script/build_and_run.sh
./script/build_and_run.sh --build-only
swift test
```

Codex 的 Run 按钮已连接构建脚本。现有网页入口保留，新增视频转换流程以 SwiftUI 和 AI 二进制为入口。

AI 调用 `dist/mp3tag`，标准输出只有 JSON。成功退出码 0，操作失败 1，参数错误 2；`--help` 显示帮助文本。所有输出拒绝覆盖已有文件。

```sh
dist/mp3tag capabilities
dist/mp3tag probe '/path/video.mp4'
dist/mp3tag inspect '/path/song.mp3' --include-cover
dist/mp3tag parse examples/beneath-the-metal-sky.txt
dist/mp3tag extract '/path/video.mp4' --output '/path/song.mp3' --text examples/beneath-the-metal-sky.txt --bitrate 320
dist/mp3tag extract '/path/audio.m4a' --output '/path/song.mp3' --no-first-frame
dist/mp3tag frame '/path/video.mp4' --output '/path/cover.jpg'
dist/mp3tag patch '/path/song.flac' --output '/path/song.tagged.flac' --metadata metadata.json --cover cover.jpg
```

也支持从 stdin 接收单条 JSON 请求（便于 AI 和其他程序集成）：

```sh
dist/mp3tag request <<'JSON'
{"operation":"extract","input":"/path/video.mp4","output":"/path/song.mp3","first_frame":true,"bitrate":320,"metadata":{"title":"Beneath the Metal Sky","artist":"Silent Horizon"}}
JSON
```

成功响应：`{"ok":true,"result":{"output":"…","metadata":{…},"has_cover":true,"cover_source":"first_frame",…}}`。失败响应：`{"ok":false,"error":{"code":"operation_failed","message":"…"}}`。

operation 为 `capabilities/parse/inspect/probe/frame/patch/extract`。`parse` 传 `text`，其余文件操作传 `input`；`patch/extract` 必须指定 `output`，可传 `metadata` 对象、`text` 原始歌曲信息、`cover` 图片路径。`extract` 另支持 `first_frame`（默认 true）、`bitrate`（默认 320）、`audio_stream`（ffprobe 的流 index）；`inspect` 可传 `include_cover`。`frame` 不指定 `output` 时返回 JPEG data URI，指定时导出 .jpg。纯音频转 MP3 应使用 `first_frame:false`；无音轨会拒绝转换，无视频画面但要求首帧时会报错。

转 MP3 属于有损重新编码，无法提升原音质；保留源容器可识别的基础标签，并以用户补丁覆盖。首帧按视频方向解码，等比例缩放至最大 2000×2000 并编码为 JPEG，再写入 ID3 APIC 前封面。默认输出副本，原视频始终不修改。字幕轨不自动当作歌词，歌词需显式提供。

## 启动网页

```sh
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/audiotag serve
```

自动打开 http://127.0.0.1:8765 。若没有 uv，可用 `python3 -m venv .venv` 和 `.venv/bin/pip install -e '.[dev]'`。也可以双击 macOS 的 `启动.command`。

选择文件 → 粘贴信息 → 解析 → 检查勾选字段 → 可选选择封面 → 写入并导出。点击「试试示例」可以载入本次提供的完整歌词。页面读取第一个音频的现有标签供参考，只有勾选且非空的字段才更新；空值和未勾选字段保留原值。

批量导出时，同一份补丁应用到每个音频，下载 ZIP。每批最多 32 个文件，每个最多 512 MB，总计最多 2 GB。封面支持 JPEG/PNG，最多 20 MB、4000 万像素。封面替换使用前封面类型，取消替换则保留原封面。浏览器播放器能否试听取决于浏览器的编解码器支持，不影响标签写入。

## 命令行

```sh
.venv/bin/audiotag inspect '/path/song.mp3'
.venv/bin/audiotag parse examples/beneath-the-metal-sky.txt
.venv/bin/audiotag patch '/path/song.mp3' --text examples/beneath-the-metal-sky.txt
.venv/bin/audiotag patch '/path/song.mp3' '/path/song.flac' --text info.txt --cover cover.png --output-dir ./output
.venv/bin/audiotag patch '/path/song.m4a' --json metadata.json --cover cover.jpg
.venv/bin/audiotag patch '/path/song.mp3' --cover cover.jpg
.venv/bin/audiotag patch '/path/song.mp3' --text info.txt --in-place
```

默认生成 `song.tagged.mp3` 副本，不覆盖已有输出。`--in-place` 先生成并校验新文件，再把原文件备份为 `song.mp3.bak`，最后原子替换；已有备份会阻止修改。批量命令按文件逐一处理，遇到错误会停止，前面已经成功的文件不会回滚。

JSON 字段：`title`、`artist`、`album`、`genre`、`year`、`track`、`bpm`、`lyrics`。例如：

```json
{"title":"Beneath the Metal Sky","artist":"Silent Horizon","track":"1/1","bpm":"95","year":"2024"}
```

文本支持 `歌曲名称 (Title)：…` 或 `Title: …`。歌词应放在最后；`Lyrics:` 后所有行均视为歌词，包括冒号、段落和空行。未识别的行会提示；不访问网络猜测信息。艺术家示例中「或根据你的喜好自定义」是可选说明，会去掉并提示校对。

## 写入行为

- 音频不重新编码，默认保留未更新的标签与封面，写入后重新读取并校验。
- MP3/WAV 使用 ID3 文本帧、USLT 非同步歌词和 APIC 前封面；FLAC/Vorbis/Opus 使用 Vorbis 标签及图片块；M4A 使用标准 iTunes atoms。
- M4A 的 BPM 只支持整数，音轨及总数最多 65535，其他格式支持小数 BPM。部分播放器不显示 WAV/Opus 封面或歌词，取决于播放器实现。
- MP4 原生封面列表会替换为所选前封面。多个值的字段修改后统一为所填单值；歌词修改会替换 ID3 原有 USLT 非同步歌词帧。
- 原文件始终留在电脑上，仅传到本机 Python 服务的临时目录，下载完成后清理。服务仅绑定 127.0.0.1，拒绝其他网页来源的写入请求。
- 本工具不转换音频格式，不支持删除标签或在线搜索封面。

## 验证

```sh
.venv/bin/python -m pytest -q
```

跨格式测试用 ffmpeg 创建短音频，检查标准标签、歌词、封面、保留字段、下载 ZIP、备份保护，并比较解码音频 SHA-256。未安装 ffmpeg 时这些测试跳过；日常编辑不需要 ffmpeg。设计见 [DESIGN.md](DESIGN.md)。

## 官网与 Sparkle 发行

静态官网源码位于 `site/`，参考 music 项目的陶土红唱片视觉与 `app-platform` 托管方式。原生端已接入 Sparkle 2.10.0，提供检查更新与自动检查设置；版本、公钥和更新源统一记录在 `Config/Release.json`。

目前处于发行准备阶段：已有 Developer ID 签名的 Apple Silicon 构建，尚未完成 Apple 公证或公开部署。平台登录、公证凭据及 Python 引擎源码许可确认仍是发布前置条件。构建、公证、签名清单与部署步骤见 [RELEASE.md](RELEASE.md)；不要把本机调试包当作已公证发行包上传。
