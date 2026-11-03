import io
import json
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image
import pytest

from audiotag.engine import perform
from audiotag.media import extract_mp3
from audiotag.tags import get_cover, load_audio


@pytest.fixture
def video(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("需要 ffmpeg")
    path = tmp_path / "中文 video.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=96x64:r=10:d=0.6", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.6", "-c:v", "libx264", "-c:a", "aac", "-metadata", "title=原视频标题", "-shortest", str(path)], check=True)
    return path


def test_extract_first_frame_and_source_metadata(video):
    before = video.read_bytes()
    result = extract_mp3(video, video.with_suffix(".mp3"), {"artist": "Silent Horizon", "lyrics": "第一段\n\n第二段"}, bitrate=192)
    assert result["metadata"]["title"] == "原视频标题"
    assert result["metadata"]["artist"] == "Silent Horizon"
    assert result["metadata"]["lyrics"] == "第一段\n\n第二段"
    assert abs(result["duration"] - 0.6) < 0.1
    assert result["cover_source"] == "first_frame"
    audio = load_audio(result["output"])
    assert abs(audio.info.bitrate - 192000) < 1000
    with Image.open(io.BytesIO(get_cover(audio))) as image:
        assert image.size == (96, 64)
        red, green, blue = image.convert("RGB").getpixel((48, 32))
        assert red > 240 and green < 10 and blue < 10
    assert video.read_bytes() == before
    with pytest.raises(ValueError, match="已存在"):
        extract_mp3(video, video.with_suffix(".mp3"))


def test_custom_cover_overrides_frame_and_audio_only(video):
    cover = io.BytesIO()
    Image.new("RGB", (40, 40), "blue").save(cover, format="PNG")
    result = extract_mp3(video, video.parent / "custom.mp3", cover_bytes=cover.getvalue())
    assert result["cover_source"] == "custom"
    assert get_cover(load_audio(result["output"])) == cover.getvalue()
    audio_only = video.parent / "audio.m4a"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-c:a", "copy", str(audio_only)], check=True)
    destination = video.parent / "audio.mp3"
    with pytest.raises(ValueError, match="没有视频"):
        extract_mp3(audio_only, destination)
    assert not destination.exists()
    result = extract_mp3(audio_only, destination, use_first_frame=False)
    assert not result["has_cover"]


def test_json_protocol_and_missing_audio(video):
    request = {"operation": "extract", "input": str(video), "output": str(video.with_suffix(".mp3")), "metadata": {"title": "协议标题"}}
    response = subprocess.run([sys.executable, "-m", "audiotag.engine", "request"], input=json.dumps(request), text=True, capture_output=True)
    assert response.returncode == 0, response.stdout
    result = json.loads(response.stdout)
    assert result["ok"] and result["result"]["metadata"]["title"] == "协议标题"
    response = subprocess.run([sys.executable, "-m", "audiotag.engine", "extract", str(video), "--output", request["output"]], capture_output=True, text=True)
    assert response.returncode == 1
    assert json.loads(response.stdout)["ok"] is False
    silent = video.parent / "silent.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-an", "-c:v", "copy", str(silent)], check=True)
    with pytest.raises(ValueError, match="没有音轨"):
        perform({"operation": "extract", "input": str(silent), "output": str(video.parent / "silent.mp3")})
