# Outwold devourer

AI босстой, 2D ээлжит тактик тоглоом. Knight, Mage, Healer гурав Demon Lord + 2 Imp-тэй 8×8 талбар дээр тулалдана.
Босс тоглогчийн зуршлыг сурч, хэн рүү, ямар ур чадвар хэрэглэхээ өөрөө шийднэ.

Төслийн менежментийн хичээлийн багийн төсөл, 2026.11.09 – 12.10.

## Бүтэц

| Хавтас | Агуулга | Хариуцагч |
|---|---|---|
| `engine/` | Тоглоомын дүрэм: төлөв, нүүдэл, ур чадвар, ээлж. **pygame-гүй.** Тоглоом болон AI хоёулаа үүнийг ашиглана | AI |
| `ai/` | Боссын AI: нөхцөл үнэлэх функц, MCTS, уур хилэн, «Боссын бодол»-ын өгөгдөл | AI |
| `game/` | Pygame: дүрслэл, UI, sprite, дуу, «Боссын бодол» самбар, .exe build | GD |
| `learning/` | Тоглолтын log, зуршлын профайл, дараагийн нүүдэл таамаглагч | DQ |
| `bots/`, `experiments/` | Скриптэй bot тоглогчид, 100 тулааны туршилт, A/B | DQ |
| `docs/` | GDD, тэнцвэрийн хүснэгт, төслийн баримт | PM |
| `tests/` | Автомат тест (`pytest`) | Бүгд |

**Дүрэм зөвхөн `engine/`-д байна.** `game/` болон `ai/` дүрмийг дахин бичихгүй. Ингэснээр
босс тооцоолж буй тоглоом, тоглогчийн харж буй тоглоом хоёр үргэлж ижил байна.
Тоон утгыг (HP, хохирол, cooldown) зөвхөн `engine/constants.py`-д өөрчилнө.

## Эхлүүлэх

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

## `engine` API (GD, DQ-д зориулав)

```python
from engine import GameState, legal_actions, apply, END_TURN

s = GameState.new_game()          # эхлэх байрлал
acts = legal_actions(s)           # одоогийн талын боломжит бүх нүүдэл (+ END_TURN)
events = apply(s, acts[0], validate=True)   # s-ийг өөрчилнө, үйл явдлын жагсаалт буцаана
s.is_over, s.winner               # winner: "heroes" | "demons" | "draw" | None
```

### Ээлж
- Эхлээд `heroes`, дараа нь `demons`. Хоёул нүүвэл нэг round (`s.round`). 40 round-оос хэтэрвэл тэнцээ.
- Өөрийн ээлжинд **амьд дүр бүр нэг `Action`** хийнэ. Дарааллыг тоглогч сонгоно.
- Бүх дүр нүүсний дараа ээлж автоматаар солигдоно. `END_TURN` нь үлдсэнийг алгасна.

### `Action` = хөдлөх + нэг ур чадвар
| Талбар | Утга |
|---|---|
| `unit` | `"knight"`, `"mage"`, `"healer"`, `"demon_lord"`, `"imp1"`, `"imp2"` |
| `dest` | Хөдөлсний дараах нүд `(x, y)`. Хөдлөхгүй бол одоогийн нүд. `y=0` дээд эгнээ |
| `skill` | Ур чадварын id эсвэл `None` (зөвхөн хөдлөх / хүлээх) |
| `target` | Бай нүд. Taunt, Imp дуудахад `None` |
| `target_uid` | Нэг байтай ур чадварын бай дүр |
| `variant` | Мөсөн хана: `0` хэвтээ `(x,y),(x+1,y)`, `1` босоо `(x,y),(x,y+1)` |
| `leap` | `True` бол `dest` руу Сүүдрийн үсрэлтээр очно (Demon Lord) |

**UI-д зөвлөмж:** тоглогч дүр сонгоход `unit_actions(s, unit)`-аас тухайн дүрийн нүүдлүүдийг ав.
Хөдөлж болох нүд = `{a.dest for a in ...}`, тухайн нүднээс хэрэглэж болох ур чадвар = `a.dest == сонгосон нүд`
байх нүүдлүүд. Ингэвэл UI өөрөө дүрэм шалгах шаардлагагүй.

### Үйл явдал (events) — анимаци, log-д
`apply()` dict-үүдийн жагсаалт буцаана. `type`:
`move` (`unit, from, to, leap`), `skill` (`unit, skill, target, target_uid`),
`damage` (`src, dst, amount, absorbed, hp`), `death` (`unit`), `heal` (`src, dst, amount`),
`shield`, `curse` (`src, dst, turns`), `taunt` (`src, targets, turns`), `wall` (`src, cells, turns`),
`summon` (`src, spawned`), `turn_end`, `turn_start` (`side, round`), `game_over` (`winner, round`).

### Хадгалах, хуулах
- `s.clone()` — хурдан гүн хуулбар (AI simulation).
- `s.to_dict()` / `GameState.from_dict(d)`, `a.to_dict()` / `Action.from_dict(d)` — JSON log, save.
- `s.render()` — debug-д зориулсан текст зураг.

### Дүрмийн нарийн хэсэг
- Зай = Manhattan. Хөдөлгөөн 4 чиглэлд, дүр болон мөсөн хана хаана.
- Cooldown: `1` = ээлж бүр, `2` = хоёр ээлж тутам. Тал бүрийн ээлж эхлэхэд буурна.
- Хараал: бай өөрийн 2 ээлжийн турш эдгэрэл авахгүй. Taunt: дайснууд дараагийн 2 ээлжид
  нэг байтай ур чадвараа Knight хүрэх зайд байвал зөвхөн Knight руу чиглүүлнэ.
- Мөсөн хана боссын 2 ээлжийг хаана. Бамбай дараагийн 20 хохирлыг шингээнэ.
- Imp дуудах: үхсэн Imp-үүдийг боссын хажууд бүтэн HP-тэй сэргээнэ (хамгийн ихдээ 2). Тэр ээлжид нүүхгүй.
- `s.boss_enraged` — HP < 30%. Уур хилэнгийн зан төлөвийг AI шийднэ.

PDF-д тодорхойгүй байсан утгыг (`constants.py`-д `TBD (GDD)` гэж тэмдэглэсэн) GDD батлагдахад засна.

## `ai` API (GD-д: тоглоомд нэгтгэх)

```python
from ai import BossAI

boss = BossAI(profile=None)              # profile: DQ-ийн зуршлын профайл (dict), None = суралцдаггүй
                                         # mode="lookahead" (default, ~20 мс), "mcts" (~1 сек), "eval" (~7 мс)
# боссын ээлж ирэхэд:
decision, events = boss.play_turn(state) # state-ийг шууд өөрчилнө, events-ээр анимаци хийнэ
panel = decision.to_panel()              # «Боссын бодол» самбар
```

`panel` жишээ:
```python
{"habits": ["Healer-т их найддаг (эдгээлт 8/тулаан)"],
 "options": [{"label": "Сүүдрийн үсрэлт → Хар дөл Mage-т", "score": 0.57, "chosen": True},
             {"label": "Сүүдрийн үсрэлт → Тамын гал (Mage)", "score": 0.54, "chosen": False},
             {"label": "Хар дөл Mage-т", "score": 0.53, "chosen": False}],
 "enraged": False, "random_pick": False, "ms": 1003, "mode": "mcts", "iterations": 4800}
```
Хурдан хэмжих: `python -m ai.bench --games 20 --heroes greedy -v`.

### Профайлын формат (DQ → AI)
```json
{"target_priority": {"knight": 1.0, "mage": 1.2, "healer": 1.8},
 "habits": ["Healer-т их найддаг (эдгээлт 8/тулаан)", "Healer Knight-ийн ард нуугддаг"]}
```
`target_priority` — баатар бүрийн аюулын түвшин (default 1.0 / 1.3 / 1.4). Өндөр бол босс түүнийг түрүүлж онилно.
`habits` — самбарт харуулах мөрүүд.

### Таамаглагч (DQ → AI)
MCTS тоглогчийн хариу нүүдлийг таамаглахдаа DQ-ийн таамаглагчийг ашиглана:
```python
def predictor(state, unit_uid, actions) -> list[float]:   # len == len(actions), магадлал/жин
    ...
boss = BossAI(profile=profile, predictor=predictor)
```
Өгөхгүй бол `GreedyHeroModel` ашиглана: баатрууд шунахай тоглоно гэж таамаглана.
`lookahead` горимд таамаглагчийг `PredictorHeroModel`-оор, `mcts` горимд rollout-д ашиглана.
Горимуудын харьцуулалт, туршилтын дүн: [`docs/ai.md`](docs/ai.md).

**Анхаар:** `mcts` горимд шийдвэр ~1 секунд үргэлжилнэ. UI царцахгүйн тулд `boss.decide()`-г
тусдаа thread-д ажиллуулж, хооронд нь «Босс бодож байна...» харуулна. Дараа нь
`decision.actions`-ийг нэг нэгээр нь `apply()` хийж анимацлана.
