from dataclasses import dataclass


class DownloadError(Exception):
    pass


@dataclass(frozen=True)
class Song:
    platform: str
    song_id: str
    title: str
    artist: str
    album: str
    cover_url: str
    duration: float
    restriction: str = ""


@dataclass(frozen=True)
class AudioSource:
    url: str
    label: str
