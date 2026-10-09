import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from mutagen import File
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, ID3NoHeaderError, TALB, TIT2, TPE1
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover

from .models import DownloadError, Song


def safe_name(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value).strip(" .")[:180] or "未命名"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_ffmpeg() -> str | None:
    candidates = (Path(sys.executable).resolve().parent / "ffmpeg.exe",
                  Path(__file__).resolve().parents[1] / "ffmpeg.exe")
    return shutil.which("ffmpeg") or next((str(p) for p in candidates if p.is_file()), None)


def inspect_audio(path: Path) -> dict:
    try:
        obj = File(path)
        if isinstance(obj, MP3):
            ext, codec, lossless = "mp3", "MP3", False
        elif isinstance(obj, MP4):
            is_alac = "alac" in str(getattr(obj.info, "codec", "")).lower()
            ext, codec, lossless = "m4a", "ALAC" if is_alac else "AAC", is_alac
        elif isinstance(obj, FLAC):
            ext, codec, lossless = "flac", "FLAC", True
        else:
            raise DownloadError("服务器返回的内容不是支持的 MP3、M4A 或 FLAC 音频")
        info = obj.info
        duration = float(info.length)
        bitrate = round(info.bitrate / 1000) if getattr(info, "bitrate", 0) else 0
        if duration <= 0:
            raise DownloadError("音频文件没有有效时长")
        return {"extension": ext, "codec": codec, "lossless": lossless,
                "bitrate_kbps": bitrate, "duration_seconds": duration}
    except DownloadError:
        raise
    except Exception as exc:
        raise DownloadError(f"音频文件无法解析：{exc}") from exc


def tag_audio(path: Path, song: Song, cover: bytes | None, suffix: str) -> None:
    if suffix == "mp3":
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()
        tags.delall("TIT2"); tags.add(TIT2(encoding=3, text=song.title))
        tags.delall("TPE1"); tags.add(TPE1(encoding=3, text=song.artist))
        tags.delall("TALB"); tags.add(TALB(encoding=3, text=song.album))
        if cover:
            tags.delall("APIC")
            tags.add(APIC(encoding=3, mime="image/png" if cover.startswith(b"\x89PNG") else "image/jpeg",
                          type=3, desc="Cover", data=cover))
        tags.save(path)
    elif suffix == "m4a":
        audio = MP4(path)
        audio["\xa9nam"] = [song.title]; audio["\xa9ART"] = [song.artist]; audio["\xa9alb"] = [song.album]
        if cover:
            fmt = MP4Cover.FORMAT_PNG if cover.startswith(b"\x89PNG") else MP4Cover.FORMAT_JPEG
            audio["covr"] = [MP4Cover(cover, imageformat=fmt)]
        audio.save()
    elif suffix == "flac":
        audio = FLAC(path)
        audio["title"] = song.title; audio["artist"] = song.artist; audio["album"] = song.album
        if cover:
            pic = Picture(); pic.type = 3
            pic.mime = "image/png" if cover.startswith(b"\x89PNG") else "image/jpeg"
            pic.data = cover; audio.clear_pictures(); audio.add_picture(pic)
        audio.save()


def cover_bytes(song: Song, client: httpx.Client) -> bytes | None:
    if not song.cover_url:
        return None
    try:
        response = client.get(song.cover_url, timeout=12)
        response.raise_for_status()
        data = response.content
        if len(data) <= 2_000_000 and (data.startswith(b"\xff\xd8") or data.startswith(b"\x89PNG")):
            return data
    except httpx.HTTPError:
        pass
    return None


def download_audio(song: Song, sources, target_dir: Path, mp3: bool, client: httpx.Client,
                   cancelled, progress, status, cover: bytes | None) -> tuple[Path, dict]:
    target_dir.mkdir(parents=True, exist_ok=True)
    temp_path = None
    errors = []
    try:
        for source in sources:
            if cancelled.is_set():
                raise DownloadError("已取消")
            fd, name = tempfile.mkstemp(prefix=".musicdown-", suffix=".part", dir=target_dir)
            os.close(fd); temp_path = Path(name)
            try:
                with client.stream("GET", source.url, follow_redirects=True, timeout=45) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if "html" in content_type or "json" in content_type:
                        raise DownloadError("服务器返回网页而非音频，可能需要权限或链接已失效")
                    total = int(response.headers.get("content-length") or 0)
                    received = 0
                    with temp_path.open("wb") as out:
                        for chunk in response.iter_bytes(131072):
                            if cancelled.is_set():
                                raise DownloadError("已取消")
                            out.write(chunk); received += len(chunk)
                            progress(round(received * 100 / total) if total else -1)
                details = inspect_audio(temp_path)
                if song.duration > 0 and details["duration_seconds"] + 3 < song.duration * 0.9:
                    raise DownloadError(f"仅取得试听片段（{details['duration_seconds']:.0f}/{song.duration:.0f} 秒），未保存为完整歌曲")
                break
            except (httpx.HTTPError, DownloadError) as exc:
                errors.append(f"{source.label}：{exc}")
                temp_path.unlink(missing_ok=True); temp_path = None
                if cancelled.is_set():
                    raise DownloadError(str(exc)) from exc
        else:
            reason = "；".join(errors) if errors else "没有可下载的音频"
            if song.restriction:
                reason = f"{song.restriction}；{reason}"
            raise DownloadError(reason)

        suffix = details["extension"]
        if mp3 and suffix != "mp3":
            ffmpeg = find_ffmpeg()
            if not ffmpeg:
                raise DownloadError("转换 MP3 需要 ffmpeg.exe；请将其加入 PATH，或放在程序同目录")
            status("转换 MP3 中")
            converted = temp_path.with_suffix(".mp3.part")
            proc = subprocess.Popen([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(temp_path),
                                     "-vn", "-codec:a", "libmp3lame", "-q:a", "2", "-f", "mp3", str(converted)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            while proc.poll() is None:
                if cancelled.wait(0.2):
                    proc.terminate(); proc.wait(timeout=5); converted.unlink(missing_ok=True)
                    raise DownloadError("已取消")
            err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            if proc.returncode:
                converted.unlink(missing_ok=True)
                raise DownloadError(f"MP3 转换失败：{err[-300:]}")
            temp_path.unlink(); temp_path = converted
            details = inspect_audio(temp_path); suffix = "mp3"

        stem = safe_name(f"{song.artist} - {song.title}")
        final = target_dir / f"{stem}.{suffix}"
        if final.exists():
            existing = inspect_audio(final)
            if _sha256(final) == _sha256(temp_path):
                existing["source"] = source.label
                temp_path.unlink(); return final, existing
            final = target_dir / f"{stem} [{song.platform}-{song.song_id}].{suffix}"
            index = 2
            while final.exists():
                if _sha256(final) == _sha256(temp_path):
                    existing = inspect_audio(final)
                    existing["source"] = source.label
                    temp_path.unlink(); return final, existing
                final = target_dir / f"{stem} [{song.platform}-{song.song_id}-{index}].{suffix}"
                index += 1
        status("写入歌曲信息")
        try:
            tag_audio(temp_path, song, cover, suffix)
        except Exception:
            # A playable file is preferable to treating optional tagging as a download failure.
            pass
        os.replace(temp_path, final); temp_path = None
        details = inspect_audio(final)
        details["source"] = source.label
        return final, details
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
