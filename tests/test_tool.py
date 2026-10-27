import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import mutagen
from fastapi.testclient import TestClient
from mutagen.id3 import TCOM
from PIL import Image
import pytest

from mp3tag.parser import parse_text, validate_patch
from mp3tag.server import app
from mp3tag.tags import get_cover, inspect_audio, load_audio, patch_file


@pytest.fixture(params=[("mp3", "libmp3lame"), ("flac", "flac"), ("m4a", "aac"), ("ogg", "vorbis"), ("opus", "libopus"), ("wav", "pcm_s16le")])
def audio(request, tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("跨格式音频验证需要 ffmpeg")
    extension, codec = request.param
    path = tmp_path / f"source.{extension}"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.15", "-ac", "2", "-c:a", codec, "-strict", "experimental", str(path)], check=True)
    return path


@pytest.fixture
def cover():
    data = io.BytesIO()
    Image.new("RGB", (32, 32), "#275c49").save(data, format="PNG")
    return data.getvalue()


def pcm_hash(path):
    return subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "hash", "-hash", "sha256", "-"])


def test_sample_and_lyrics_colons():
    text = Path("examples/beneath-the-metal-sky.txt").read_text()
    parsed = parse_text(text)
    assert parsed["metadata"]["title"] == "Beneath the Metal Sky"
    assert parsed["metadata"]["artist"] == "Silent Horizon"
    assert parsed["metadata"]["track"] == "1/1"
    assert parsed["metadata"]["lyrics"].count("(Chorus)") == 2
    assert parsed["warnings"] == ["已去除艺术家字段中的可选说明，请检查歌手名称"]
    assert parse_text("Title: 曲名\nLyrics:\nArtist: this is a lyric\n\nEnd")["metadata"]["lyrics"] == "Artist: this is a lyric\n\nEnd"


@pytest.mark.parametrize("patch", [{"track": "3/2"}, {"bpm": "NaN"}, {"year": "24"}, {"title": None}, {"title": True}, {"fake": "oops"}])
def test_reject_invalid_metadata(patch):
    with pytest.raises(ValueError):
        validate_patch(patch)


def test_real_format_tags_cover_and_audio_preservation(audio, cover):
    before = hashlib.sha256(audio.read_bytes()).digest()
    output = audio.with_name("tagged" + audio.suffix)
    patch_file(audio, output, {"title": "中文曲名", "artist": "Silent Horizon", "album": "Concrete Horizons", "genre": "Alternative Rock / Nu-Metal", "year": "2024", "track": "1 / 2", "bpm": "95", "lyrics": "(Verse 1)\nShadows bleed\n\n(Chorus)\nHold on"}, cover)
    # 直接读取格式标准中的标签，避免读写工具共同出错却仍然通过测试。
    tagged = mutagen.File(output)
    if audio.suffix in (".mp3", ".wav"):
        assert tagged.tags["TIT2"].text == ["中文曲名"]
        assert tagged.tags["TRCK"].text == ["1/2"]
        assert tagged.tags["TBPM"].text == ["95"]
        assert tagged.tags.getall("USLT")[0].text == "(Verse 1)\nShadows bleed\n\n(Chorus)\nHold on"
        assert tagged.tags.getall("APIC")[0].type == 3
        tagged.tags.add(TCOM(encoding=3, text=["原作曲家"]))
    elif audio.suffix == ".m4a":
        assert tagged.tags["\xa9nam"] == ["中文曲名"]
        assert tagged.tags["trkn"] == [(1, 2)]
        assert tagged.tags["tmpo"] == [95]
        assert tagged.tags["\xa9lyr"] == ["(Verse 1)\nShadows bleed\n\n(Chorus)\nHold on"]
        tagged.tags["\xa9wrt"] = ["原作曲家"]
    else:
        assert tagged.tags["title"] == ["中文曲名"]
        assert tagged.tags["tracknumber"] == ["1"]
        assert tagged.tags["tracktotal"] == ["2"]
        assert tagged.tags["bpm"] == ["95"]
        assert tagged.tags["lyrics"] == ["(Verse 1)\nShadows bleed\n\n(Chorus)\nHold on"]
        tagged.tags["composer"] = ["原作曲家"]
    tagged.save()
    assert get_cover(tagged) == cover
    second = audio.with_name("second" + audio.suffix)
    patch_file(output, second, {"title": "修改后"})
    preserved = mutagen.File(second)
    composer_key = "TCOM" if audio.suffix in (".mp3", ".wav") else "\xa9wrt" if audio.suffix == ".m4a" else "composer"
    assert str(preserved.tags[composer_key][0]) == "原作曲家"
    assert inspect_audio(second)["metadata"]["artist"] == "Silent Horizon"
    assert get_cover(preserved) == cover
    assert pcm_hash(audio) == pcm_hash(second)
    assert hashlib.sha256(audio.read_bytes()).digest() == before
    with pytest.raises(ValueError, match="已存在"):
        patch_file(audio, output, {"title": "不得覆盖"})


def test_failed_cover_does_not_publish(audio):
    destination = audio.with_name("broken" + audio.suffix)
    with pytest.raises(ValueError, match="封面"):
        patch_file(audio, destination, {"title": "不会写入"}, b"not an image")
    assert not destination.exists()


def test_web_download_and_batch_names(audio, cover):
    with TestClient(app) as client:
        response = client.post("/api/patch", files=[("files", (audio.name, audio.read_bytes())), ("files", (audio.name, audio.read_bytes())), ("cover", ("cover.png", cover))], data={"metadata": json.dumps({"title": "网页导出"})})
        assert response.status_code == 200, response.text if response.status_code != 200 else ""
        assert "AudioTag-tagged.zip" in response.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert len(set(archive.namelist())) == 2
            for index, name in enumerate(archive.namelist()):
                path = audio.parent / f"download-{index}{audio.suffix}"
                path.write_bytes(archive.read(name))
                assert inspect_audio(path)["metadata"]["title"] == "网页导出"
                assert get_cover(load_audio(path)) == cover
        blocked = client.post("/api/parse", json={"text": "Title: hi"}, headers={"Origin": "https://example.com"})
        assert blocked.status_code == 403


def test_web_branding():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "<title>AudioTag ·" in response.text
        assert 'aria-label="AudioTag 首页"' in response.text


@pytest.mark.parametrize("command", ["audiotag", "mp3tag"])
def test_cli_names_parse_metadata(command, tmp_path):
    executable = Path(sys.executable).parent / command
    source = tmp_path / "info.txt"
    source.write_text("Title: 跨格式音频\nArtist: AudioTag", encoding="utf-8")
    result = subprocess.run([str(executable), "parse", str(source)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["metadata"] == {"title": "跨格式音频", "artist": "AudioTag"}
    help_result = subprocess.run([str(executable), "--help"], text=True, capture_output=True)
    assert help_result.returncode == 0
    assert "AudioTag 本地音频标签编辑工具" in help_result.stdout


def test_cli_backup_and_refusal(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("需要 ffmpeg")
    path = tmp_path / "song.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=duration=0.1", str(path)], check=True)
    original = path.read_bytes()
    info = tmp_path / "info.txt"
    info.write_text("Title: 原地修改验证", encoding="utf-8")
    command = [sys.executable, "-m", "mp3tag.cli", "patch", str(path), "--text", str(info), "--in-place"]
    result = subprocess.run(command, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    assert path.with_name("song.mp3.bak").read_bytes() == original
    assert inspect_audio(path)["metadata"]["title"] == "原地修改验证"
    saved = path.read_bytes()
    result = subprocess.run(command, capture_output=True)
    assert result.returncode == 1
    assert path.read_bytes() == saved
