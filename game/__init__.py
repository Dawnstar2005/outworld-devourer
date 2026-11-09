"""Outwold devourer — Pygame тоглоом (GD).

Ажиллуулах:  python -m game

Бүтэц:
    session.py     — тоглолтын төлөв + нүүдэл хийх + on_action hook (pygame-гүй)
    input.py       — хулганы сонголт → Action, engine.unit_actions()-аас (pygame-гүй)
    boss_driver.py — боссын шийдвэрийг тусдаа thread-д тооцоолох (pygame-гүй)
    anim.py        — events → хөдөлгөөн, хөвөх тоо (pygame-гүй)
    labels.py      — дүр, үйл явдлын монгол нэр (pygame-гүй)
    layout.py      — нүд ↔ пиксел, товчны байрлал (pygame-гүй)
    theme.py       — өнгө, фонт (pygame)
    board_view.py  — grid, дүр, тодруулга зурах (pygame)
    hud.py         — ээлжийн мэдээлэл, HP, товч (pygame)
    app.py         — үндсэн давталт (pygame)

Тоглоомын дүрэм энд байхгүй: бүгд engine/-д. Энэ багц pygame-ийг зөвхөн
theme / board_view / hud / app-д импортолно, тиймээс бусад модулийг дэлгэцгүй тестэлж болно.
"""
