# Энэ repo дээр ажиллах AI туслахуудад

Баг: PM (Үүрцолмон, хүн), AI Engineer (Claude, claude.ai), Game Developer + Data/ML + QA
(Claude Code). Хүн бүр өөрийн хавтас дээр ажиллана — README-ийн «Бүтэц» хүснэгтийг үз.

2026-11-09: Codex (Data/ML + QA) төслөөс гарсан. Түүний ажлыг (`learning/`, `bots/`,
`experiments/`, QA) PM-ийн шийдвэрээр GD (Claude Code) хариуцна.

## Заавал
- **Тоглоомын дүрмийг зөвхөн `engine/`-д бичнэ.** `game/`, `ai/`, `bots/`-д дүрэм давтаж бичихгүй.
  Дүрэм өөрчлөх шаардлагатай бол `engine/` дээр PR нээж, AI Engineer-ээр review хийлгэнэ.
- Тоон утга зөвхөн `engine/constants.py`-д.
- `engine/` pygame болон гадны сан импортлохгүй (AI simulation хурдан, тест дэлгэцгүй ажиллана).
- Ажил бүр өөрийн branch → PR → өөр нэг гишүүний review → merge (Definition of Done).
  Review солилцоо: GD-ийн PR-ийг AI Engineer, AI Engineer-ийн PR-ийг GD review хийнэ. Merge — PM.
- PR-ээс өмнө `python -m pytest -q` давсан байна.
- Код дахь тайлбар, баримт монгол хэлээр; хувьсагч, функцийн нэр англиар.

## Хуваарийн гол огноо
- 11/15 GD: grid, ээлж, баатрууд хөдөлдөг (Pygame, `engine` дээр)
- 11/18 AI: simulator бэлэн (`engine` — хийгдсэн)
- 11/20 GD (DQ-ийн оронд): тоглолтын log (`apply()`-ийн events + `Action.to_dict()` ашигла)
- 11/22 AI: нөхцөл үнэлэх функцтэй анхны босс
- 11/25 AI: MCTS ≤ 2 сек (шийдвэрийн цэг)
- 12/2 нэгтгэл, 12/6 эцсийн .exe
