# 参与贡献

感谢你帮助改进 AudioTag。提交 Issue 或 Pull Request 前，请先确认问题能在当前版本复现，并尽量附上操作系统版本、输入格式、最小复现步骤和相关日志。请勿上传包含个人音频、封面、歌词或密钥的文件。

## 本地开发

项目包含 Python 标签引擎、一个本地网页入口和 macOS SwiftUI 应用。Python 开发环境需要 Python 3.11+ 与 `uv`：

```sh
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
```

运行网页入口：

```sh
.venv/bin/audiotag serve
```

构建 macOS 应用需要 Xcode Command Line Tools；完整构建还需要本机 FFmpeg：

```sh
./script/build_and_run.sh --build-only
```

## 提交前检查

```sh
.venv/bin/python -m pytest -q
node --test tests/site.test.cjs tests/local_editor.test.cjs
swift test
```

涉及界面时，请同步更新 `DESIGN.md` 中受影响的设计约定；涉及发布脚本时，请确认没有写入本机路径、签名身份、钥匙串名称或其他凭据。发行包、`dist/`、`.build/` 和虚拟环境不应提交。

## Pull Request 约定

- 一个 Pull Request 聚焦一个问题，标题使用动词开头并说明用户可见结果。
- 新增行为要补充有意义的测试或说明为什么不适合自动化验证。
- 不要在提交中加入真实音频、封面、发行包、钥匙串数据或第三方私有凭据。
- 维护者会在合并前检查测试、许可证和第三方组件归属信息。
