# 验证记录

2026-10-10，本机验证。

- 26 项 pytest 测试全部通过，无跳过。ffmpeg 实际生成 MP3、FLAC、M4A、OGG Vorbis、Opus、WAV 六种音频，检查标准标签位置、中文、歌词换行、前封面和保留字段，并比较修改前后解码 PCM 的 SHA-256。
- 测试覆盖无效标签、无效封面不产生成品、输出覆盖保护、批量 ZIP 重名、跨来源拒绝，以及原地修改的备份与重复修改保护。
- 使用 Codex 内置浏览器验证「试试示例 → 解析 → 上传用户 MP3 → 写入并导出」，下载成功，8 个字段和 36 行歌词正确。实际文件的解码音频 SHA-256 修改前后均为 `0585d0ed17d0cdc6eee10e6296fce5b6af4d63898d6728859f36af4cab750fa9`。
- 本次原文件 SHA-256：`49f7c796197622e60f54d98d0682ec95377ff07356f25ad1cab5de0640d5be51`。副本保存在 `output/Beneath_the_Metal_Sky.mp3`，封面未指定，因此没有新增封面。
- 实际检查桌面 1280px 与窄屏 390px。窄屏文档宽度等于视口宽度，无横向溢出。通过截图检查中文文案、主次字体、绿/暖白配色、两栏到单栏布局、字段状态、导出按钮与结果提示。截图保存在 `output/interface.jpg` 和 `output/interface-mobile.jpg`。
- 测试环境出现一项 Starlette 对 httpx TestClient 的弃用提醒，测试结果不受影响。

采用 `frontend-design` 技能。改进建议：该技能可补充本地文件编辑工具的批量差异提示、保留字段状态和原文件保护设计要求；本次已在 DESIGN.md 明确这些行为。

## SwiftUI 与 MP4 转 MP3

- 使用 SwiftPM 构建原生 SwiftUI `Mp3tag.app`，通过 `script/build_and_run.sh --verify` 构建并成功启动，Codex Run 入口已配置。标签引擎打包为 arm64 Mach-O 二进制，支持命令式调用与 stdin JSON。
- 本次 29 项 Python 测试通过，另有 2 项 Swift 测试通过。转换测试覆盖首帧颜色/尺寸、码率/时长、保留视频基础标签、歌词换行、图片覆盖首帧、无音轨与无视频的错误、输出覆盖保护和结构化 JSON 错误。Swift 测试实际启动打包后的二进制验证成功与失败响应。
- 用用户 MP4 在 AI 二进制与 SwiftUI 中分别完成完整导出。两个输出的 8 个字段、36 行歌词与 APIC 前封面一致；时长 164.23 秒，320 kbps，封面 1024×1024。封面字节与单独导出的第一帧 JPEG 一致。
- 本次 MP4 输出副本：`output/video/Beneath the Metal Sky.mp3`；UI 输出：`output/native/Beneath the Metal Sky.mp3`；首帧：`output/video/first-frame.jpg`。原文件不修改。
- SwiftUI 手动验证文件选择、MP4 自动开启转换、首帧预览、示例载入、信息解析、字段勾选、目录选择与成功提示。截图：`output/native-interface.png`。
- FFmpeg、FFprobe 和 19 个非系统动态库已随 CLI 与 `.app` 打包，全部非系统链接改为相对路径。以 `PATH=/usr/bin:/bin` 验证首帧导出成功，不依赖 Homebrew 搜索路径。当前 FFmpeg 二进制的最低系统版本为 macOS 26，应用 Info.plist 与 README 已注明。
- 本次使用 SKILL：`build-macos-apps:swiftpm-macos`、`build-macos-apps:build-run-debug`。改进建议：增加 SwiftUI 前端配合机器可调用引擎时的 JSON 协议测试与动态库完整打包检查；本次都已实施。

## SwiftUI 界面优化

- 按 `emil-design-eng` 优化信息层级与交互：紧凑工具栏、独立滚动的文件与编辑区域、固定底部导出区、基本标签与歌词分段、文本解析成功后自动收起导入区。设计要求同步至 DESIGN.md。
- `swift build`、`script/build_and_run.sh --verify`、2 项 Swift 桥接测试和 `codesign --verify --deep --strict dist/Mp3tag.app` 全部通过。
- 原生界面实测空状态、示例解析、Cmd+O 打开用户 MP4、首帧预览、320 kbps 转换选项、歌词分段切换与内部滚动。切回基本标签后，7 个基本字段与勾选状态保留，歌词仍为 36 行，导出按钮始终可见。
- 实际截图：`output/ui-polish.png`、`output/ui-polish-lyrics.png`。本轮未修改标签引擎，未重复执行音频导出验证。
- 本轮使用 SKILL：`emil-design-eng`，构建沿用 `build-macos-apps:build-run-debug` 工作流。改进建议：为设计技能补充 SwiftUI/macOS 示例，说明鼠标按压与键盘触发反馈的区别、固定操作区及 Reduce Motion 的适配。

## 陶土红主题与轻量动效（2026-10-27）

- 以用户提供的 Perch 截图为主题依据，取样主色约为 `#A7462D`。原生端统一使用 `EditorTheme`；保留网页入口同步强调色、暖白背景与辅助色，不改变网页布局或引擎协议。设计约定同步至 `DESIGN.md`。
- 原生界面拆分为根布局、主题与动效、文件与封面、标签工作区、导出状态栏。标题与流派占整行，年份、音轨、BPM 并排；输出设置固定在侧栏底部，导出操作固定在窗口底部。空封面采用静态唱片图形，不持续旋转。
- 动效只用于鼠标按压（120ms、0.98 缩放）、鼠标替换封面（200ms 淡入）和鼠标导出完成后的状态图标（200ms、0.95 缩放加透明度）。统一使用 `(0.23, 1, 0.32, 1)`；减少动态效果时移除缩放，反馈改为 120ms 淡入。未为输入、字段勾选、标签切换或键盘操作添加动画。
- `swift test` 的 2 项真实引擎桥接测试、pytest 的 29 项测试全部通过。构建与启动使用 `script/build_and_run.sh --verify`，应用签名通过 `codesign --verify --deep --strict`。pytest 仍有原有 Starlette/httpx 弃用提醒。
- 原生界面实际验证空状态、示例载入、解析后自动收起、8 项待写入字段、⌘O 文件面板、音频载入、图片封面选择、歌词页与 36 行歌词、目录选择及副本导出成功状态。通过当前窗口截图检查配色、排版与固定操作区；本轮未保存新截图文件，未完成最小窗口尺寸与系统 Reduce Motion 开关的交互实测，也未逐帧测量动效时序。
- 本轮实际导出副本：`output/ui-terracotta/Beneath_the_Metal_Sky.tagged.mp3`。重新读取标题、艺术家与 36 行歌词正常；APIC 图片与 `output/video/first-frame.jpg` 字节一致。源音频文件 SHA-256 仍为 `eb28eac35470180e187f451235d50396b0093928b1efceb34810af787d3d3a94`；导出前后解码 PCM SHA-256 均为 `0585d0ed17d0cdc6eee10e6296fce5b6af4d63898d6728859f36af4cab750fa9`，原文件与音频内容未改动。
- 依据 sRGB 色值计算，主按钮文字对比度约 5.81:1，辅助文字在侧栏底色上约 4.65:1；这不等同于完整辅助功能审计。
- 使用 SKILL：`stc`、`emil-design-eng`、`animate`、`build-macos-apps:swiftui-patterns`、`build-macos-apps:build-run-debug`。改进建议：设计技能应优先核对用户确认的跨项目品牌色，不把项目旧色当作最终依据；动效技能可补充 SwiftUI 的局部事务、异步操作输入来源捕获和 Reduce Motion 示例。

## 官网与 Sparkle 发行准备（2026-10-27）

- 参考 `/opt/case/brian/music` 创建 `site/`，包含陶土红官网、功能与格式限制、版本数据读取、源码与许可页；新增原生图标。工作台图使用 HTML/CSS 流程示意，明确标注非截图，未冒用旧版界面截图。
- 原生端接入固定版本 Sparkle 2.10.0，保留 `com.brian.mp3tag` 身份。生成独立 Keychain account `mp3tag` 的 Ed25519 密钥，源码仅保存公钥；菜单与设置页支持检查更新和自动检查。当前官网/feed 地址沿用 music 的命名约定，仍须以实际平台发布返回值核对。
- `swift test` 的 4 项测试、Python 的 29 项测试、Node 的 3 项网站逻辑测试全部通过。网站测试覆盖同源下载路径、编码越界/查询凭据拒绝、版本入口更新与失败降级。Python 仍有既存 Starlette/httpx 弃用提醒。脚本的 shell 语法和 Python 编译检查通过。
- 从 FFmpeg 9.0.2 和 LAME 4.0 的校验源码构建独立媒体工具，禁用 GPL/nonfree、网络与自动依赖发现，并关闭 LAME 的 mpg123 解码器。实际只随包携带一个 LAME 动态库；没有复制 Homebrew 的其他可选依赖。组件许可证随应用与源码页提供，第三方原始源码保存在本地 `site/sources/`。
- 已构建 `.build/public-release-1/Mp3tag.app`，版本 `1.0.0（1）`，arm64，最低 macOS 26.0。主程序、Python 内嵌库、媒体工具与 Sparkle 辅助进程使用 `Developer ID Application: zhixin xie (77TN4427T5)` 签名，Hardened Runtime 启用；`codesign --verify --deep --strict` 通过。
- 对该发行候选包执行 `script/verify_engine_bundle.py`，将 PATH 限制为 `/usr/bin:/bin`，验证实际调用内置 FFmpeg，生成 MP4、提取首帧、转 MP3、写入标签，再修改标题。未选艺术家保留；原视频 SHA-256 和仅标签修改前后解码 PCM SHA-256 均不变。
- `app-platform run` 能安装本地网站草稿；HTTP 检查首页和图标均返回 200，打包命令生成 `.build/mp3tag-site-draft.zip`。`script/check_site.py --draft` 通过已有资源检查，并明确列出尚缺的正式版本数据、appcast、校验文件与引擎对应源码归档。完整检查目前应失败，不能据草稿检查放行公开发布。
- **未完成公证与部署。** `notarytool` 提交返回 `No Keychain password item found for profile: samantha-notary`；重新授权执行后结果相同。平台 `whoami` 返回未登录，浏览器授权流程尚未完成。官方 `generate_appcast` 尝试停在 Keychain 读取，已终止等待，未生成可交付 appcast。Python 标签引擎公开源码/许可仍待作者确认，未上传项目源码或发行包。
- **未完成视觉与真实更新验收。** CUA 原生 app 接口多次返回 `timeoutReached`，IAB 返回 `Browser is not available: iab`，因此没有宣称桌面/移动端渲染截图验收或在线更新成功。旧版在线发现、下载、验签、替换、重启与篡改拒绝需在公证和部署完成后实测。
- 本轮使用或查阅 SKILL：`stc`、`emil-design-eng`、`animate`、`qimao-apps`、`sites:sites`、`build-web-apps:frontend-app-builder`、`build-web-apps:frontend-testing-debugging`、`build-macos-apps:build-run-debug`、`build-macos-apps:signing-entitlements`、`build-macos-apps:packaging-notarization`。改进建议：发行技能补充自有 `app-platform` 静态域名托管分支、GPL 引擎对应源码授权检查，以及钥匙串读取受阻时的明确停点，避免将签名成功等同于公证或上线。

## AudioTag 更名验证（2026-10-28）

- 对外名称改为 AudioTag，覆盖原生窗口、设置页、本地网页、官网草稿和发行说明；SwiftPM 可执行产品与应用包改为 AudioTag。保留内部模块、Python 分发包、Bundle ID、更新公钥、Keychain account、站点标识及现有域名。
- 新增 `audiotag` 命令，保留 `mp3tag`。重新执行可编辑安装时发现 setuptools 自动发现了多个顶层目录，因此限定只打包 `mp3tag*`，安装随后通过。两个命令均实测解析相同歌曲信息，帮助文本均显示 AudioTag。
- Python 32 项、Swift 4 项、Node 3 项测试通过。新增检查覆盖网页名称、批量下载文件名、命令别名与官网动态版本标题；Python 仍有既存 Starlette/httpx 弃用提醒。
- `script/build_and_run.sh --build-only` 和 `--verify` 通过；实际启动进程为 `dist/AudioTag.app/Contents/MacOS/AudioTag`。应用 plist 中显示名、名称和可执行文件均为 AudioTag，Bundle ID 与 feed 保持原值。新包为本地 ad-hoc 签名调试构建，`codesign --verify --deep --strict` 通过，不代表已完成 Developer ID 发行或公证。
- 对新包执行 `script/verify_engine_bundle.py`，隔离 PATH 后验证内置 FFmpeg、首帧、MP4 转 MP3、标签保留、原文件和 PCM 不变，全部通过。Shell 启动与发行脚本语法检查通过。
- 官网草稿检查通过，但仍缺正式版本数据、appcast、校验清单和对应引擎源码，未公证、未部署。历史验证记录中的 Mp3tag 名称保留，不改写旧制品及旧验证事实。
- CUA 应用清单确认 AudioTag 正在运行，但读取窗口返回 `cgWindowNotFound`；按 Bundle ID 读取又因新旧应用共享既有身份而歧义。未完成窗口截图和视觉验收。
- 使用或查阅 SKILL：`stc`、`emil-design-eng`、`build-macos-apps:build-run-debug`、`sites:sites`。改进建议：更名流程可增加“展示名、命令别名、内部标识、更新身份、托管地址”的迁移清单，避免全局替换破坏兼容。
