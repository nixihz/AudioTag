# AudioTag 发行指南

这份文档面向维护者，说明如何从源码构建 macOS 发行包。仓库中的源码和脚本不包含签名私钥、公证凭据或发布平台令牌；这些信息必须只保存在维护者本机的钥匙串或 CI Secret 中。

## 发行前检查

1. 确认项目源码、内置 Python 引擎和第三方组件的许可证已获准公开。
2. 确认 `Config/Release.json` 中的版本号、构建号、HTTPS 更新源和 Sparkle 公钥属于本次发行。
3. 准备 Apple Developer ID 证书、公证配置和 Sparkle Ed25519 私钥。私钥只放在本机钥匙串，不要导出到仓库、网站或日志。
4. 将对应版本的第三方源码和许可证放入 `site/sources/`；发行包不能替代对应源码归档。
5. 在干净环境中运行测试，并确认待发布的应用不是本地调试包。

## 本地构建

开发构建只需要 Xcode Command Line Tools、`uv` 和本机 FFmpeg：

```sh
./script/build_and_run.sh --build-only
swift test
.venv/bin/python -m pytest -q
node --test tests/site.test.cjs tests/local_editor.test.cjs
```

正式发行还需要 FFmpeg 与 LAME 的校验源码，放入 `.build/release-tools/` 后执行：

```sh
bash script/build_release_tools.sh
```

## 公证发行

为避免误用维护者身份，发行脚本要求显式提供签名身份、公证配置和 Sparkle 钥匙串账户：

```sh
SIGNING_IDENTITY='Developer ID Application: <维护者>' \
NOTARY_PROFILE='<notarytool 配置名>' \
SPARKLE_KEY_ACCOUNT='<Sparkle 私钥账户名>' \
bash script/prepare_release.sh
```

脚本会测试、构建、签名、公证、装订票据并生成 `site/` 下的发行文件。只有确认 Apple 公证通过、签名有效、下载地址正确且对应源码归档齐全后，才能发布网站和更新源。

```sh
python3 script/check_site.py
```

仅检查网站草稿时使用 `--draft`；草稿检查通过不代表可以公开发行。发布时只上传 `site/` 中已审核的静态文件，保留历史版本，不覆盖已经公开的同版本制品。

## 版本更新

增加版本号或构建号后重新构建。不要修改已经公开的 ZIP、校验值、appcast 签名或历史发行说明。更新 Sparkle 公钥、Bundle ID 或更新源会使已有安装无法验证后续更新，必须单独规划迁移。
