from beets.test.helper import PluginTestCase

from beetsplug import aisauce


class AISauceTestCase(PluginTestCase):
    plugin = "aisauce"

    def setUp(self):
        super().setUp()
        self.ai = aisauce.AISauce()

    def test_album_for_id(self):
        # Lookup by album ID is not supported in AISauce
        result = self.ai.album_for_id("some_album_id")
        assert result is None
