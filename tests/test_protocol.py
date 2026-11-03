"""AI JSON 接口与命令行的行为约定。

这些用例锁定对外协议：字段名、错误信息和退出码都属于接口的一部分，
重构时不能随意更改。
"""

import base64
import io
import json
import shutil
import subprocess
import sys

from PIL import Image
import pytest

from audiotag.engine import perform
from audiotag.fsutil import publish_atomically
from audiotag.tags import inspect_audio


@pytest.fixture
def audio(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("需要 ffmpeg")
    path = tmp_path / "song.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=duration=0.1", str(path)], check=True)
    return path


@pytest.fixture
def video(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("需要 ffmpeg")
    path = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=10:d=0.5",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
         "-c:v", "libx264", "-c:a", "aac", "-metadata", "title=片段标题", "-shortest", str(path)],
        check=True,
    )
    return path


def test_capabilities_lists_operations_and_dependencies():
    result = perform({"operation": "capabilities"})
    assert result["operations"] == ["capabilities", "parse", "inspect", "probe", "frame", "patch", "extract"]
    assert result["formats"] == ["mp3", "flac", "m4a", "mp4", "ogg", "opus", "wav"]
    assert result["version"]
    assert set(result["dependencies"]) == {"ffmpeg", "ffprobe"}


def test_parse_operation_returns_metadata_and_warnings():
    result = perform({"operation": "parse", "text": "Title: 协议标题\nArtist: 协议歌手"})
    assert result["metadata"] == {"title": "协议标题", "artist": "协议歌手"}
    assert result["warnings"] == []


def test_inspect_and_probe_operations(audio, video):
    inspected = perform({"operation": "inspect", "input": str(audio)})
    assert inspected["format"] == "MP3"
    assert inspected["has_cover"] is False
    probed = perform({"operation": "probe", "input": str(video)})
    assert probed["audio_streams"][0]["codec"] == "aac"
    assert probed["video_streams"][0]["width"] == 64
    assert probed["metadata"]["title"] == "片段标题"


def test_frame_operation_returns_data_uri_and_exports_jpeg(video, tmp_path):
    inline = perform({"operation": "frame", "input": str(video)})
    assert inline["cover"].startswith("data:image/jpeg;base64,")
    assert len(base64.b64decode(inline["cover"].split(",", 1)[1])) > 0

    target = tmp_path / "cover.jpg"
    exported = perform({"operation": "frame", "input": str(video), "output": str(target)})
    assert exported["output"] == str(target)
    assert target.exists()
    with Image.open(target) as image:
        assert image.size == (64, 64)


def test_frame_operation_refuses_existing_or_wrong_extension(video, tmp_path):
    existing = tmp_path / "cover.jpg"
    existing.write_bytes(b"")
    with pytest.raises(ValueError, match="已存在"):
        perform({"operation": "frame", "input": str(video), "output": str(existing)})
    with pytest.raises(ValueError, match=".jpg"):
        perform({"operation": "frame", "input": str(video), "output": str(tmp_path / "cover.png")})


def test_patch_operation_writes_tags_and_reports_the_written_path(audio, tmp_path):
    target = tmp_path / "written.mp3"
    result = perform({
        "operation": "patch",
        "input": str(audio),
        "output": str(target),
        "metadata": {"title": "协议写入"},
    })
    assert result["output"] == str(target)
    assert result["metadata"]["title"] == "协议写入"
    assert result["warnings"] == []
    assert inspect_audio(target)["metadata"]["title"] == "协议写入"


def test_extract_operation_converts_to_mp3(video, tmp_path):
    target = tmp_path / "converted.mp3"
    result = perform({
        "operation": "extract",
        "input": str(video),
        "output": str(target),
        "metadata": {"artist": "协议歌手"},
        "first_frame": True,
        "bitrate": 192,
    })
    assert result["output"] == str(target)
    assert result["cover_source"] == "first_frame"
    assert result["has_cover"] is True
    assert target.exists()


def test_unknown_operation_and_missing_input_report_clearly():
    with pytest.raises(ValueError, match="请提供 input 文件路径"):
        perform({"operation": "unknown"})
    with pytest.raises(ValueError, match="不支持的 operation"):
        perform({"operation": "unknown", "input": "/tmp/x.mp3"})


def test_output_path_expands_home_directory(audio, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "home.mp3"
    result = perform({
        "operation": "patch",
        "input": str(audio),
        "output": "~/home.mp3",
        "metadata": {"title": "家目录"},
    })
    assert target.exists()
    assert result["output"] == str(target)


def test_publish_atomically_refuses_to_overwrite(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("新内容")
    destination = tmp_path / "destination.txt"
    destination.write_text("旧内容")
    with pytest.raises(FileExistsError):
        publish_atomically(source, destination)
    assert destination.read_text() == "旧内容"


def test_cli_patch_with_json_and_output_directory(audio, tmp_path):
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"title": "命令行写入"}), encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "audiotag.cli", "patch", str(audio),
         "--json", str(metadata), "--output-dir", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    written = output / "song.tagged.mp3"
    assert written.exists()
    assert inspect_audio(written)["metadata"]["title"] == "命令行写入"


def test_cli_reports_missing_source_with_exit_code_one(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "audiotag.cli", "inspect", str(tmp_path / "missing.mp3")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "错误：" in result.stderr


def test_engine_binary_emits_json_only():
    result = subprocess.run(
        [sys.executable, "-m", "audiotag.engine", "capabilities"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["operations"]


def test_engine_binary_reports_invalid_arguments_with_exit_code_two():
    result = subprocess.run(
        [sys.executable, "-m", "audiotag.engine", "nonsense"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_arguments"


def test_cover_rejects_oversized_and_unsupported_images():
    from audiotag.cover import read_cover

    with pytest.raises(ValueError, match="无法读取封面图片"):
        read_cover(b"not an image")
    gif = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(gif, format="GIF")
    with pytest.raises(ValueError, match="仅支持 JPEG 或 PNG"):
        read_cover(gif.getvalue())
