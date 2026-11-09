"""Outworld Devourer — Pygame тоглоом (GD).

Ажиллуулах:  python -m game

Бүтэц:
    session.py     — тоглолтын төлөв + нүүдэл хийх + on_action hook (pygame-гүй)
    input.py       — хулганы сонголт → Action, engine.unit_actions()-аас (pygame-гүй)
    boss_driver.py — боссын шийдвэрийг тусдаа thread-д тооцоолох (pygame-гүй)
    anim.py        — events → хөдөлгөөн, хөвөх тоо (pygame-гүй)
    labels.py      — дүр, үйл явдлын монгол нэр (pygame-гүй)
    layout.py      — нүд ↔ пиксел, товчны байрлал (pygame-гүй)
    stats.py       — тоглолтын статистик, on_action hook-оор (pygame-гүй)
    menu.py        — цэсийн сонголтын логик (pygame-гүй)
    sound.py       — events → дууны эффект, M товч (mixer-ийг зөвхөн тоглуулахад)
    sprites.py     — Kenney CC0 sprite ачаалах, олдохгүй бол өнгөт дөрвөлжин (pygame)
    assets/        — sprite, дуу (зөвхөн CC0, CREDITS.md)
    theme.py       — өнгө, фонт (pygame)
    board_view.py  — grid, дүр, тодруулга зурах (pygame)
    hud.py         — ээлжийн мэдээлэл, HP, ур чадварын товч (pygame)
    boss_panel.py  — «Боссын бодол» самбар, Tab (pygame)
    screens.py     — цэс, удирдлага, түр зогсолт, үр дүн (pygame)
    app.py         — үндсэн давталт, дэлгэц солих (pygame)

Тоглоомын дүрэм энд байхгүй: бүгд engine/-д. Энэ багц pygame-ийг зөвхөн
theme / board_view / hud / app-д импортолно, тиймээс бусад модулийг дэлгэцгүй тестэлж болно.
"""
