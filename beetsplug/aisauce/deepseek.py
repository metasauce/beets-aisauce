from dataclasses import dataclass
import taglib
from pathlib import Path
from pprint import pformat
import requests
import json
import os
from openai import OpenAI


def cleanup_metadata(tags: dict[str, list[str]], file_path: Path) -> dict[str, str]:
    """
    Use Deepseeker via openAI api to clean up metadata.
    """

    client = OpenAI(
        api_key=os.getenv("DS_API_KEY"),
        base_url="https://api.deepseek.com",
    )

    sys_prompt = os.getenv("DS_SYSTEM_PROMPT", DS_SYSTEM_PROMPT)
    user_prompt = os.getenv("DS_USER_PROMPT", DS_USER_PROMPT)

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": sys_prompt,
            },
            {
                "role": "user",
                "content": user_prompt.format(
                    pformat(tags | {"FILE": [file_path.name]}, sort_dicts=True)
                ),
            },
        ],
        stream=False,
        response_format={"type": "json_object"},
        # we want this to be reproducible, otherwise you might get hard-to -find
        # not-quite duplicates
        temperature=0.0,
    )

    return json.loads(response.choices[0].message.content)


# https://platform.openai.com/docs/guides/structured-outputs?api-mode=responses

DS_SYSTEM_PROMPT = """
You are a helpful programming assistant, and an expert in musical metadata.
The user will provide messy metadata, and your task is to clean up the metadata with
consistent formatting. Often the metadata is for bootlegs.

Please parse the following quantities and output them in JSON format:
- title
- artist
- album
- album_artist
- genre
- date

Do not invent values for fields that you cannot infer from the input.

EXAMPLE INPUT:
Clean up the following metadata:
{
    "FILE:": ["  Busta Rhymes - Gimme Some More (winslow.edit).mp3 "],
    "TITLE": [" Busta Rhymes - Gimme Some More [Free DL via Soundcloud] "],
    "ARTIST": ["  Busta Rhymes "],
    "ALBUM": [""],
    "GENRE": ["  DnB, neurofunk  "],
    "DATE": ["  14.11.2021  "]
    "COMPOSER": ["  Jablonksy, Steve  "],
    "COMMENT": ["  got this from a friend  "]
    "OTHER FIELD:": ["  some other value  "]
}

EXAMPLE JSON OUTPUT:
{
    "title": "Gimme Some More (winslow.edit)",
    "artist": "Busta Rhymes",
    "album_artist": "",
    "album": "",
    "genre": "Drum And Bass; Neurofunk",
    "date": "2014"
}
"""

DS_USER_PROMPT = """
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

Also make sure the casing is sensible - OFTEN THE INPUT HAS SHOUTCASE (capslock),
But I Prefer Title Case.

INPUT:
{}
"""

DS_USER_PROMPT_WITH_GENRES = """
Clean up the following metadata for a bootleg I downloaded.
I also have a list of genres that I use. Please match genres from the input to the
conventions I use. If multiple genres are returned, separate them in your reply with
a semicolon. In most cases, the genre is likely "Drum And Bass".

INPUT:
{}

GENRES:
Acid Jazz
Electronica
Downtempo
Jazz
Acid Rock
Psychedelic Rock
Rock
Alternative Metal
Hard Rock
Alternative Rock
Reggae
Comedy
Pop
Electronic
Ambient
Classical
Bebop
Blues
Big Beat
Breakbeat
Drum And Bass
Techno
Electro
Trance
Bluegrass
Country
Breakbeat Hardcore
Breakcore
Britpop
Power Pop
Soul
Pop Rock
Celtic Punk
Folk Punk
Punk Rock
Contemporary Classical
Crunk
Gangsta Rap
Hip Hop
Crust Punk
Thrash Metal
Techstep
Speed Metal
Dance-Punk
Glam Rock
Disco
Dancehall
Dark Ambient
Darkstep
Death Metal
Black Metal
Reggaeton
Deathcore
Deep House
House
Dub
Roots Reggae
Ska
Dubstep
Uk Garage
Easy Listening
Electro House
Electro-Industrial
Electropop
Djent
Post-Hardcore
Progressive Metal
Indie Rock
No Wave
Post-Punk
Slowcore
Post-Rock
Christian Rock
Rapcore
Nu Metal
Eurobeat
Folk Metal
Folk Rock
Free Jazz
Funk
Funk Metal
Rap Rock
Grunge
Hardstyle
Hard Trance
Comedy Rock
Swing
Hip House
Diva House
Horror Punk
Humor
Idm
Lo-Fi
Indie Folk
Indie Pop
Anti-Folk
Art Rock
Garage Rock
Punk Blues
Power Pop
Punk Rock
Blues
Industrial Metal
Industrial Rock
Jazz Fusion
Chamber Jazz
Kizomba
Krautrock
Liquid Funk
Bossa Nova
Happy Hardcore
Ghettotech
Ghetto House
K-Pop
Medieval Metal
Melodic Death Metal
Groove Metal
Metalcore
Christian Metal
Modern Classical
Neo Soul
Neue Deutsche Härte
New Beat
New Rave
New Wave
Nu Jazz
Opera
Contemporary Classical
Classical Music
Orchestral
Orchestra
Alternative Hip Hop
Christian Punk
East Coast Hip Hop
Pop Rap
Soft Rock
Stoner Metal
Doom Metal
Desert Rock
Stoner Rock
Symphonic
Symphonic Metal
Synthpop
Dream Pop
Sadcore
Turntablism
Speedcore
Power Metal
Powerviolence
Sludge Metal
Progressive House
Progressive Metal
Progressive Rock
Art Rock
Ragga
Ragga Jungle
Gabber
Roots Reggae
Salsa
Samba
Screamo
Nintendocore
Shoegaze
Skate Punk
Space Rock
Heavy Metal
Viking Metal
Vocal House
Vocal Jazz
Witch House
World Fusion
Worldbeat
"""
