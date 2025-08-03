from __future__ import annotations


from typing import TypedDict
from pydantic import BaseModel

from beets.autotag import TrackInfo, AlbumInfo


class Provider(TypedDict):
    """A provider for open ai api."""

    id: str
    api_key: str
    api_base_url: str
    model: str


class AISauceSource(TypedDict):
    """Configuration for AISauce plugin."""

    provider: Provider
    user_prompt: str
    system_prompt: str


class TrackInfoAIResponse(BaseModel):
    title: str
    artist: str
    album: str
    album_artist: str | None
    genres: str | None
    date: str | None
    comment: str | None

    def to_track_info(self) -> TrackInfo:
        """
        Convert the AI response to a structured Beets TrackInfo object.
        """
        return TrackInfo(
            title=self.title,
            artist=self.artist,
            album=self.album,
            album_artist=self.album_artist,
            genres=self.genres,
            date=self.date,
            comment=self.comment,
        )


class AlbumInfoAIResponse(BaseModel):
    tracks: list[TrackInfoAIResponse]
    album_title: str  # mapped to `title`
    album_artist: str  # mapped to `artist`
    genre: str | None
    year: int | None
    label: str | None
    is_compilation: bool | None  # mapped to `va`

    def to_album_info(self) -> AlbumInfo:
        """
        Convert the AI response to a structured Beets AlbumInfo object.
        """
        return AlbumInfo(
            tracks=[ti.to_track_info() for ti in self.tracks],
            album=self.album_title,
            artist=self.album_artist,
            genre=self.genre,
            year=self.year,
            label=self.label,
            va=self.is_compilation or False,  # Default to False if not provided
        )
