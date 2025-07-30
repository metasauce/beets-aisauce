from beets.test.helper import PluginTestCase

from beetsplug import aisauce


class AISauceTestCase(PluginTestCase):
    plugin = "aisauce"

    def __init__(self):
        super().__init__()
        self.config.add(
            {
                # make this nested - to generate one candidate per settings group
                "api_base_url": "https://api.deepseek.com",
                "api_key": "your_api_key_here",
                "system_prompt": _default_system_prompt,
                "user_prompt": __default_user_prompt,
                "clean_all_fields": True,
                # should all incoming data be removed before write back?
                # this likely only keeps: title, artist, album, genre, year
                "title_as_album": True,
                "album_overwrite": False,  # set to string to always set the album
                "album_artist_overwrite": False,  # set to string to always set the album artist
                "compilation": False,  # set to True to always set compilation to True
                "ensure_this_str_in_title": "Bootleg",
                # if ensured_string.lower() not in meta.title.lower():
                # meta.title = f"{meta.title} [{ensured_string}]"
            }
        )
        self.config["client_secret"].redact = True

    def setUp(self):
        super().setUp()
        self.ai = aisauce.AISauce()

    def test_album_for_id(self):
        # Lookup by album ID is not supported in AISauce
        result = self.ai.album_for_id("some_album_id")
        assert result is None

    def test_track_for_id(self):
        # Lookup by track ID is not supported in AISauce
        result = self.ai.track_for_id("some_track_id")
        assert result is None


_default_system_prompt = """
You are a helpful programming assistant, and an expert in musical metadata.
The user will provide messy metadata, and your task is to clean up the metadata with
consistent formatting. Often the metadata is for bootlegs.

Please parse the following quantities and output them in JSON format:
- title
- artist
- album
- genre
- date, but only keep the year (YYYY)

Do not invent values for fields that you cannot infer from the input.

EXAMPLE INPUT:
Clean up the following metadata:
{
    "FILE:": ["  Busta Rhymes - Gimme Some More (winslow.edit).mp3 "],
    "TITLE": [" Busta Rhymes - Gimme Some More [Free DL via Soundcloud] "],
    "ARTIST": ["  winslow "],
    "ALBUM": [""],
    "GENRE": ["  DnB, neurofunk  "],
    "DATE": ["  14.11.2021  "]
    "COMPOSER": ["  Jablonksy, Steve  "],
    "COMMENT": ["  got this from a friend  "]
    "OTHER FIELD:": ["  some other value  "]
}

EXAMPLE JSON OUTPUT:
{
    "title": "Gimme Some More [Busta Rhymes] (winslow.edit)",
    "artist": "winslow",
    "album": "",
    "genre": "Drum And Bass; Neurofunk",
    "date": "2014"
}
"""

__default_user_prompt = """
Clean up the following metadata for a bootleg I downloaded.

Often, Artist, Title and Album are empty or malformatted, but the file name might provide
a clue.

Note, for my bootlegs, a song with an input title like
"Ed Sheeran - Shape Of You (IZUK Bootleg)"
should have in the output
"IZUK" as the artist
and "Shape Of You [Ed Sheeran] (IZUK Bootleg)" for both the title and album.

If genres are contained, Title-case them and dont use abbreviations like "DnB" or "D&B",
use "Drum And Bass" instead. If multiple genres are returned, separate them in your reply
with a semicolon. In most cases, the genre is likely "Drum And Bass".

Make sure the casing is sensible - OFTEN THE INPUT HAS SHOUTCASE (capslock),
But I Prefer Title Case.

Remove strings like "Free DL via Soundcloud", "[Free Download]" and "FREE DOWNLOAD" from the title and other fields.

Make sure that the word "Bootleg" is contained in the title, and if not, add it as "[Bootleg]" at the end.
Usually you will find something like "(Danny Bird Remix)" towards the end of the title, in this case, add "Bootleg" there: "(Danny Bird Remix, Bootleg)".

INPUT:
{}
"""
