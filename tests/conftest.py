"""Тест бүрт тоглогчийн жинхэнэ ахиц, тохиргооны файлыг хөндөхгүй байх хамгаалалт.

App-ийг `settings=` / `campaign=`-гүй үүсгэвэл %APPDATA%/OutworldDevourer-оос уншиж, бичдэг.
Тест ажиллуулж буй хүний тохиргоо (жишээ нь бүтэн дэлгэц) тестэд нөлөөлөхгүй, тест түүний
файлыг дарж бичихгүй байхын тулд хоёр замыг түр хавтас руу чиглүүлнэ.
"""

import pytest


@pytest.fixture(autouse=True)
def isolated_user_files(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTWORLD_SAVE", str(tmp_path / "user" / "save.json"))
    monkeypatch.setenv("OUTWORLD_SETTINGS", str(tmp_path / "user" / "settings.json"))
