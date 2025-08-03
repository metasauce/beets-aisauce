import asyncio
import os
from beets.test.helper import PluginTestCase
from pydantic import BaseModel
import pytest
from beets.library import Item
from beetsplug import aisauce
from beetsplug.aisauce.ai import (
    get_ai_client,
    get_structured_output,
)


class AISauceConfigTestCase(PluginTestCase):
    plugin = "aisauce"

    def setUp(self):
        super().setUp()
        self.ai = aisauce.AISauce()
        self.ai.config.set(
            {
                "providers": [],
                "sources": [],
            }
        )

    def test_provider_array(self):
        # Test that the config is correctly set up with the nested structure

        # No config is set
        providers = self.ai.providers
        assert len(providers) == 0

        # Set up a dummy provider in the config
        self.ai.config["providers"].set([_dummy_provider])

        # Now check that the provider is correctly returned
        providers = self.ai.providers
        assert len(providers) == 1
        assert isinstance(providers, list)
        assert isinstance(providers[0], dict)
        assert "id" in providers[0]
        assert "api_key" in providers[0]
        assert "api_base_url" in providers[0]

    def test_no_provider(self):
        # Test that the default provider ID raises an error when no providers are set,
        # and, if no provider is set, also sources raise an error.
        with pytest.raises(ValueError):
            self.ai.default_provider_id

        with pytest.raises(ValueError):
            self.ai.sources

    def test_no_source(self):
        # provider is set, check no source is no problem and uses default provider
        self.ai.config["providers"].set([_dummy_provider])

        # Default source is returned
        sources = self.ai.sources
        assert len(sources) == 1
        assert isinstance(sources, list)
        assert "provider" in sources[0]
        assert isinstance(sources[0]["provider"], dict)
        assert "user_prompt" in sources[0]
        assert "system_prompt" in sources[0]
        assert sources[0]["user_prompt"] == aisauce.aisauce._default_user_prompt
        assert sources[0]["system_prompt"] == aisauce.aisauce._default_system_prompt

    def test_source_and_provider_no_prompts(self):
        # provider is set, and a source but without prompts
        self.ai.config["providers"].set([_dummy_provider])
        self.ai.config["sources"].set(
            [
                {
                    "provider_id": "Dummy",
                }
            ]
        )

        sources = self.ai.sources
        assert len(sources) == 1
        assert isinstance(sources, list)
        assert "provider" in sources[0]
        assert isinstance(sources[0]["provider"], dict)
        assert "user_prompt" in sources[0]
        assert "system_prompt" in sources[0]
        assert sources[0]["user_prompt"] == aisauce.aisauce._default_user_prompt
        assert sources[0]["system_prompt"] == aisauce.aisauce._default_system_prompt

    def test_source_and_provider(self):
        # everything specified by the user config
        self.ai.config["providers"].set([_dummy_provider])
        self.ai.config["sources"].set([_dummy_source])

        sources = self.ai.sources
        assert len(sources) == 1
        assert isinstance(sources, list)
        assert "provider" in sources[0]
        assert isinstance(sources[0]["provider"], dict)
        assert sources[0]["provider"]["id"] == "Dummy"
        assert "user_prompt" in sources[0]
        assert "system_prompt" in sources[0]
        assert sources[0]["user_prompt"] == "What is the metadata for this file?"
        assert sources[0]["system_prompt"] == "You are an expert in musical metadata."


@pytest.mark.skipif(
    os.environ.get("AI_API_KEY") is None
    or os.environ.get("AI_API_URL") is None
    or os.environ.get("AI_MODEL") is None,
    reason="AI_API_KEY or AI_API_URL or AI_MODEL not set",
)
class IntegrationTest(PluginTestCase):
    """Mixin for local tests that require AISauce plugin."""

    def setUp(self):
        super().setUp()
        self.ai = aisauce.AISauce()
        self.ai.config.set(
            {
                "providers": [
                    {
                        "id": "test_provider",
                        "api_key": os.environ.get("AI_API_KEY"),
                        "api_base_url": os.environ.get("AI_API_URL"),
                        "model": os.environ.get("AI_MODEL"),
                    }
                ],
            }
        )

    def test_generic_structured_out(self):
        class Foo(BaseModel):
            title: str
            artist: str

        client = get_ai_client(self.ai.providers[0])

        out = asyncio.run(
            get_structured_output(
                client,
                user_prompt="What is the title and artist of this song? `99 Red Balloons - Nena`",
                system_prompt="You are an expert in musical metadata.",
                model=self.ai.providers[0]["model"],
                type=Foo,
            )
        )

        assert isinstance(out, Foo)
        assert out.title is not None
        assert out.artist is not None
        assert out.title == "99 Red Balloons"
        assert out.artist == "Nena"

    def test_candidates(self):
        # Get items from test file
        item = Item.from_path(
            os.path.join(
                os.path.dirname(__file__), "data", "Annix - Antidote [free dl].mp3"
            )
        )
        out = self.ai.candidates(
            items=[item],
            artist=item.artist,
            album=item.album,
            va_likely=False,
        )

        # Check that the output is a list of AlbumInfo objects
        assert isinstance(out, list)
        assert len(out) == 1
        assert isinstance(out[0], aisauce.aisauce.AlbumInfo)


class AISauceTestCase(PluginTestCase):
    plugin = "aisauce"

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


_dummy_provider = {
    "id": "Dummy",
    "api_key": "your_api_key_here",
    "api_base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
}


_dummy_source = {
    "provider_id": "Dummy",
    "user_prompt": "What is the metadata for this file?",
    "system_prompt": "You are an expert in musical metadata.",
}
