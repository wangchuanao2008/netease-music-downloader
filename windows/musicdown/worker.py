import json
import queue
import threading
from pathlib import Path

import httpx
from PySide6.QtCore import QObject, Signal, QStandardPaths

from .audio import cover_bytes, download_audio, inspect_audio
from .links import resolve_link
from .models import DownloadError
from .providers import PROVIDERS
from .providers.alternate import AlternateProvider


class Events(QObject):
    info = Signal(int, object, object)
    progress = Signal(int, int)
    state = Signal(int, str)
    complete = Signal(int, str, object, object)


class DownloadManager:
    def __init__(self):
        self.events = Events()
        self.pending = queue.Queue()
        self.cancellations = {}
        self.active_keys = set()
        self.lock = threading.Lock()
        app_data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        app_data.mkdir(parents=True, exist_ok=True)
        self.manifest_path = app_data / "downloads.json"
        try:
            self.manifest = json.loads(self.manifest_path.read_text())
        except (OSError, ValueError):
            self.manifest = {}
        threading.Thread(target=self._loop, daemon=True, name="download-worker").start()

    def add(self, task_id: int, url: str, folder: str, mp3: bool, alternate: bool = True) -> None:
        event = threading.Event()
        self.cancellations[task_id] = event
        self.pending.put((task_id, url, Path(folder), mp3, alternate, event))

    def cancel(self, task_id: int) -> None:
        if task_id in self.cancellations:
            self.cancellations[task_id].set()

    def _save_manifest(self) -> None:
        temp = self.manifest_path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2))
        temp.replace(self.manifest_path)

    def _loop(self) -> None:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
                   "Referer": "https://music.163.com/"}
        with httpx.Client(headers=headers, follow_redirects=True, timeout=20) as client:
            while True:
                task_id, url, folder, mp3, alternate, cancelled = self.pending.get()
                try:
                    if cancelled.is_set():
                        raise DownloadError("已取消")
                    self.events.state.emit(task_id, "解析链接")
                    platform, song_id, final_url = resolve_link(url, client)
                    key = f"{platform}:{song_id}:{'mp3' if mp3 else 'source'}:{'alternate' if alternate else 'direct'}"
                    with self.lock:
                        if key in self.active_keys:
                            raise DownloadError("同一歌曲已在下载队列中")
                        self.active_keys.add(key)
                    try:
                        provider = PROVIDERS[platform]
                        self.events.state.emit(task_id, "获取歌曲信息")
                        song = provider.song(song_id, client)
                        cover = cover_bytes(song, client)
                        self.events.info.emit(task_id, song, cover)
                        old_entry = self.manifest.get(key)
                        old = old_entry.get("path") if isinstance(old_entry, dict) else old_entry
                        if old and Path(old).is_file() and Path(old).parent == folder:
                            try:
                                details = inspect_audio(Path(old))
                                if isinstance(old_entry, dict):
                                    details["source"] = old_entry.get("source", "")
                                self.events.complete.emit(task_id, "已存在", str(old), details)
                                continue
                            except DownloadError:
                                pass
                        if cancelled.is_set():
                            raise DownloadError("已取消")
                        self.events.state.emit(task_id, "获取音频地址")
                        primary_error = ""
                        try:
                            sources = provider.sources(song, client)
                            self.events.state.emit(task_id, "下载中")
                            path, details = download_audio(song, sources, folder, mp3, client, cancelled,
                                                           lambda percent: self.events.progress.emit(task_id, percent),
                                                           lambda state: self.events.state.emit(task_id, state), cover)
                        except DownloadError as exc:
                            if cancelled.is_set() or not alternate:
                                raise
                            primary_error = str(exc)
                            self.events.state.emit(task_id, "查找备用音源")
                            try:
                                sources = AlternateProvider().sources(song, client)
                                self.events.state.emit(task_id, "下载备用音源")
                                path, details = download_audio(song, sources, folder, mp3, client, cancelled,
                                                               lambda percent: self.events.progress.emit(task_id, percent),
                                                               lambda state: self.events.state.emit(task_id, state), cover)
                            except DownloadError as alt_exc:
                                raise DownloadError(f"原音源：{primary_error}；备用音源：{alt_exc}") from alt_exc
                        self.manifest[key] = {"path": str(path), "source": details.get("source", "")}
                        self._save_manifest()
                        self.events.complete.emit(task_id, "已完成", str(path), details)
                    finally:
                        with self.lock:
                            self.active_keys.discard(key)
                except DownloadError as exc:
                    self.events.complete.emit(task_id, "已取消" if cancelled.is_set() else "失败", str(exc), None)
                except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
                    self.events.complete.emit(task_id, "失败", f"网络或文件错误：{exc}", None)
                finally:
                    self.cancellations.pop(task_id, None)
                    self.pending.task_done()
