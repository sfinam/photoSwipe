from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from photoswipe.config import ConfigStore
from photoswipe.i18n import (
    current_language,
    format_date,
    set_language,
    system_language,
    tr,
)
from tests.helpers import TempWorkspace


class I18nTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = TempWorkspace()
        self.original = current_language()
        set_language("en")

    def tearDown(self) -> None:
        set_language(self.original)
        self.ws.cleanup()

    def test_english_russian_and_portuguese_strings(self) -> None:
        set_language("en")
        self.assertEqual(tr("Library"), "Library")
        set_language("ru")
        self.assertEqual(tr("Library"), "Библиотека")
        self.assertEqual(tr("Photos sorted: {count}", count=3), "Фото разобрано: 3")
        set_language("pt")
        self.assertEqual(tr("Library"), "Biblioteca")
        self.assertEqual(
            tr("Photos sorted: {count}", count=3), "Fotos classificadas: 3"
        )

    def test_formatting_dates_in_each_language(self) -> None:
        value = "2024-10-05T19:46:57"
        set_language("en")
        self.assertEqual(format_date(value), "October 5, 2024, 19:46")
        set_language("ru")
        self.assertEqual(format_date(value), "5 октября 2024, 19:46")
        set_language("pt")
        self.assertEqual(format_date(value), "5 de outubro de 2024, 19:46")

    def test_system_language_detection(self) -> None:
        with patch.dict(
            os.environ,
            {"LANG": "pt_BR.UTF-8", "LC_ALL": "", "LC_MESSAGES": ""},
            clear=False,
        ):
            self.assertEqual(system_language(), "pt")
        with patch.dict(
            os.environ,
            {"LANG": "ru_RU.UTF-8", "LC_ALL": "", "LC_MESSAGES": ""},
            clear=False,
        ):
            self.assertEqual(system_language(), "ru")

    def test_new_config_uses_language_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {"LANG": "pt_BR.UTF-8", "LC_ALL": "", "LC_MESSAGES": ""},
            clear=False,
        ):
            config = ConfigStore(self.ws.base / "pt-config.json").load()
        self.assertEqual(config.language, "pt")
        self.assertEqual(config.destinations.favorite, "Favoritos")
        self.assertEqual(config.destinations.trash, "Lixeira")
        self.assertEqual(config.destinations.maybe, "Talvez")

    def test_language_persists_in_config(self) -> None:
        path = self.ws.base / "config.json"
        store = ConfigStore(path)
        config = store.load()
        config.language = "ru"
        store.save(config)
        reloaded = ConfigStore(path).load()
        self.assertEqual(reloaded.language, "ru")


if __name__ == "__main__":
    unittest.main()
