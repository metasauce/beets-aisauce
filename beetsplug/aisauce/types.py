from __future__ import annotations


from typing import TypedDict
from beets.library import Item
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
    filename: str | None
    title: str
    artist: str
    album: str
    album_artist: str | None
    genres: str | None
    year: int | None
    comment: str | None
    length: int | None
    index: int | None

    def to_track_info(self, **kwargs) -> TrackInfo:
        """
        Convert the AI response to a structured Beets TrackInfo object.
        """
        return TrackInfo(
            title=self.title,
            artist=self.artist,
            album=self.album,
            album_artist=self.album_artist,
            genres=self.genres,
            year=self.year,
            comment=self.comment,
            length=self.length,
            index=self.index,
        )


class AlbumInfoAIResponse(BaseModel):
    tracks: list[TrackInfoAIResponse]
    album_title: str  # mapped to `title`
    album_artist: str  # mapped to `artist`
    genre: str | None
    year: int | None
    label: str | None
    is_compilation: bool | None  # mapped to `va`

    def to_album_info(self, **kwargs) -> AlbumInfo:
        """
        Convert the AI response to a structured Beets AlbumInfo object.
        """

        # Apply datasource to track and album fields
        data_source = kwargs.pop("data_source", None)

        return AlbumInfo(
            tracks=[ti.to_track_info(data_source=data_source) for ti in self.tracks],
            album=self.album_title,
            artist=self.album_artist,
            genre=self.genre,
            year=self.year,
            label=self.label,
            va=self.is_compilation or False,  # Default to False if not provided
            data_source=data_source,
            **kwargs,
        )

    def apply_to_items(self, items: list[Item]) -> list[dict[str, dict[str, str]]]:
        """
        Apply the AI response data to a list of Beets Item objects
        and return a diff of changes made.

        Returns:
            dict: A dictionary containing:
                - 'applied_changes': list of dicts showing changes per item
                - 'summary': dict with counts of total changes by field
        """
        applied_changes = []

        for i, (ai_track, item) in enumerate(zip(self.tracks, items)):
            # Track changes for each field
            changes = {}

            if item.title != ai_track.title:
                changes["title"] = {"old": item.title, "new": ai_track.title}
                item.title = ai_track.title

            if item.artist != ai_track.artist:
                changes["artist"] = {"old": item.artist, "new": ai_track.artist}
                item.artist = ai_track.artist

            if item.album != ai_track.album:
                changes["album"] = {"old": item.album, "new": ai_track.album}
                item.album = ai_track.album

            if (
                ai_track.album_artist is not None
                and item.albumartist != ai_track.album_artist
            ):
                changes["albumartist"] = {
                    "old": item.albumartist,
                    "new": ai_track.album_artist,
                }
                item.albumartist = ai_track.album_artist

            if ai_track.genres is not None and item.genre != ai_track.genres:
                changes["genre"] = {"old": item.genre, "new": ai_track.genres}
                item.genre = ai_track.genres

            if ai_track.year is not None and item.year != ai_track.year:
                changes["year"] = {"old": item.year, "new": ai_track.year}
                item.year = ai_track.year

            if ai_track.comment is not None and item.comment != ai_track.comment:
                changes["comment"] = {"old": item.comment, "new": ai_track.comment}
                item.comment = ai_track.comment

            if ai_track.length is not None and item.length != ai_track.length:
                changes["length"] = {"old": item.length, "new": ai_track.length}
                item.length = ai_track.length

            if ai_track.index is not None and item.track != ai_track.index:
                changes["track"] = {"old": item.track, "new": ai_track.index}
                item.track = ai_track.index

            applied_changes.append(changes)

        return applied_changes
