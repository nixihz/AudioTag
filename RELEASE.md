# 官网与 macOS 发行

## AudioTag 更名

产品对外名称统一为 AudioTag，原生构建输出 `dist/AudioTag.app`，新发行 ZIP 使用 `audiotag-<版本>-<构建号>.zip`。Bundle ID `com.brian.mp3tag`、Keychain account `mp3tag`、更新公钥、站点标识和域名暂时保留，避免改名改变更新身份或指向未配置的服务。内部 Python 包及 AI 引擎仍名为 `mp3tag`；源码安装新增 `audiotag` 命令，并保留旧命令。

此次更名只更新项目源码与本地构建，不代表已完成公证或部署。已签名或公开的历史制品不得直接改写；下一次发行需重新构建、签名、公证并生成校验数据。

## 当前状态

已参考 `/opt/case/brian/music` 接入静态官网与 Sparkle 2.10.0，并构建 Developer ID 签名的 Apple Silicon 应用。**尚未部署，尚未公证，不能作为已完成的公开发行。**

发行前还有三项前置条件：

1. `app-platform --server https://apps.xiezhixin.com whoami` 必须返回已登录。浏览器授权由用户完成，令牌只保存在本机。
2. 本机 `notarytool` 必须能读取有效公证配置。当前 `samantha-notary` 返回 `No Keychain password item found`；不要把 Apple ID 密码、App 专用密码或 API 私钥写入仓库或聊天。
3. 作者确认 Python 标签引擎源码的公开方式与 GPL 许可。该引擎使用 Mutagen；仅公开 Mutagen 上游源码不足以完成对应引擎的发行准备。未确认前，不上传二进制或项目引擎源码。

`generate_appcast` 首次读取 `mp3tag` 的钥匙串密钥时可能需要用户处理系统授权弹窗。不要导出私钥到网站或日志。

## 版本与身份

- 唯一发行配置：`Config/Release.json`，首版 `1.0.0`，构建号 `1`。
- Bundle ID：`com.brian.mp3tag`。保持既有身份，不因产品更名而更换。
- 签名：`Developer ID Application: zhixin xie (77TN4427T5)`，启用 Hardened Runtime。
- 架构：Apple Silicon，最低 macOS 26.0。Swift 主程序支持更低版本，但随包媒体工具要求 macOS 26。
- 官网展示名：AudioTag；平台应用标识仍为 `mp3tag`。目标平台为 `https://apps.xiezhixin.com`。
- 当前配置的官网：`https://mp3tag.xiezhixin.com/`。这是沿用 music 的命名规则，**还没有平台发布结果确认**。首次取得平台地址后必须核对，若不同则在公证构建前同步更新配置、设置页链接与官网 canonical。
- Sparkle feed：官网下 `/updates/appcast.xml`；版本 ZIP、说明和校验值：`/downloads/`；组件许可证及对应源码：`/sources/`。
- Ed25519 私钥使用独立 Keychain account `mp3tag`，不能复用 `keli-music`，也不能重新生成密钥替代已发行公钥。

## 构建工具与源码

发布版不复制 Homebrew FFmpeg 全套 GPL 扩展。`script/build_release_tools.sh` 从校验过的 FFmpeg 9.0.2 与 LAME 4.0 源码构建，FFmpeg 禁用自动发现、GPL/nonfree 扩展与网络，LAME 禁用可选 mpg123 解码器。FFmpeg / FFprobe 仅依赖可替换的 LAME 动态库及系统库。

源码包需预先放入 `.build/release-tools/`：

| 文件 | SHA-256 |
| --- | --- |
| `ffmpeg-9.0.2.tar.xz` | `8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e` |
| `lame-4.0.tar.gz` | `3df5124d5ad3a98312ffd7ba6a9b36230e4f8a3e66d3ce0f425e336c32d216eb` |

对应上游来源为 FFmpeg 官方 releases 和 LAME SourceForge。构建工具依赖 Xcode Command Line Tools、make、pkg-config、nasm、Python 与现有 `.venv`。

## 制作发行

在源码许可、域名及公证配置确认后执行：

```sh
NOTARY_PROFILE=samantha-notary bash script/prepare_release.sh
```

流程依次执行测试、编译媒体工具、构建 Swift release、为 PyInstaller 内嵌库签名、按由内向外顺序签名应用、隔离 PATH 验证引擎、提交 Apple 公证、装订票据、生成最终 ZIP 与 Sparkle appcast。

`script/finalize_release.py` 只接受配置一致、签名有效、已装订公证票据且通过 Gatekeeper 的应用。最终 ZIP 使用 `ditto --keepParent --sequesterRsrc`，以保留 Sparkle 需要的符号链接与应用属性。它生成 `site/release.json`、发行说明、SHA-256 清单和官网 appcast；同版本制品已存在时拒绝覆盖。

发布前必须把获准公开的**对应版本引擎源码与构建说明**加入 `site/sources/`，并在该目录页面增加下载链接与许可说明。SwiftUI 客户端不包含在此项源码准备中。未完成此项不得发布。

## 预览、发布与复核

```sh
app-platform run ./site --bind 127.0.0.1:0
node --test tests/site.test.cjs
python3 script/check_site.py
app-platform --server https://apps.xiezhixin.com publish ./site
```

后续更新才使用 `publish ./site --update`。只发布 `site/`，不要上传 `.build/`、`dist/`、`.venv/`、`data/` 或钥匙串内容。保留全部已公开历史 ZIP；安装包签名、校验值或 appcast 生成后不得再修改制品。

发布后核对平台返回的真实官网地址，检查 HTTPS、首页、版本数据、XML、源码与安装包直链均无登录跳转；重新下载 ZIP 比较 SHA-256 与字节数。对同一 ZIP 验证 Ed25519 签名，并确认篡改副本被拒绝。

首次发行只能验证配置与发行包，不能据此宣称完成了旧版在线替换。完整的 Sparkle 下载、验签、替换与重启验收，需要保留同公钥、同 Bundle ID 的真实旧构建。
