"""验证已打包应用里的标签引擎。

在隔离的 PATH 下运行，确认引擎使用内置 FFmpeg，
并且转码、标签写入与封面处理都符合预期。
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

resources = Path(sys.argv[1]).resolve() / "Contents/Resources"
engine = resources / "audiotag"
ffmpeg = resources / "tools/ffmpeg"
environment = {**os.environ, "PATH": "/usr/bin:/bin"}


def call(request):
    """向引擎发送一条请求并返回结果字段。"""
    process = subprocess.run([str(engine), "request"], input=json.dumps(request),
                             text=True, capture_output=True, env=environment)
    response = json.loads(process.stdout)
    if process.returncode or not response.get("ok"):
        raise RuntimeError(response)
    return response["result"]


def pcm(path):
    """返回解码后的音频摘要，用于确认转码没有改变声音。"""
    raw = subprocess.check_output([str(ffmpeg), "-v", "error", "-i", str(path),
                                   "-map", "0:a:0", "-f", "s16le", "-"], env=environment)
    return hashlib.sha256(raw).hexdigest()


def make_source(path):
    """生成一段带标题的测试视频。"""
    subprocess.run([
        str(ffmpeg), "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=320x240:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-c:v", "mpeg4", "-c:a", "aac", "-metadata", "title=Before", "-shortest", str(path)
    ], check=True, env=environment)


def main():
    with tempfile.TemporaryDirectory(prefix="audiotag-release-smoke-") as temporary:
        work = Path(temporary)
        source = work / "fixture.mp4"
        converted = work / "converted.mp3"
        patched = work / "patched.mp3"
        make_source(source)
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        capabilities = call({"operation": "capabilities"})
        if capabilities["dependencies"]["ffmpeg"] != str(ffmpeg):
            raise SystemExit("发行包没有使用内置 FFmpeg")
        result = call({
            "operation": "extract", "input": str(source), "output": str(converted),
            "metadata": {"title": "Release smoke", "artist": "AudioTag"},
            "first_frame": True, "bitrate": 320
        })
        if result["metadata"]["title"] != "Release smoke" or not result["has_cover"]:
            raise SystemExit("MP4 转 MP3 的标签或首帧封面不正确")
        edited = call({"operation": "patch", "input": str(converted), "output": str(patched),
                       "metadata": {"title": "After"}})
        if edited["metadata"]["title"] != "After" or edited["metadata"]["artist"] != "AudioTag":
            raise SystemExit("标签修改或未选字段的保留行为不正确")
        if pcm(converted) != pcm(patched):
            raise SystemExit("仅标签修改改变了音频内容")
        if hashlib.sha256(source.read_bytes()).hexdigest() != before:
            raise SystemExit("源视频被修改")
    print("发行包引擎验证通过：隔离 PATH、内置 FFmpeg、首帧、转 MP3、标签保留、原文件与 PCM 不变")


if __name__ == "__main__":
    main()
