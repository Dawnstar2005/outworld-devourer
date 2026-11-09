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

## Тоглоом ажиллуулах (`game/`)

```bash
python -m game                      # эхлэлийн дүр зураг → үндсэн цэс, 60 FPS
python -m game --skip-intro         # эхлэлийн дүр зураггүй
python -m game --skip-menu          # шууд тоглоом
python -m game --boss-mode mcts     # боссын AI-г MCTS горимоор (ai/ суусан үед; цэснээс ч сольж болно)
python -m game --placeholder-boss   # ai/ байсан ч түр боссоор тоглох
```

Дэлгэц: үндсэн цэс (Тоглох · Босс: хурдан/ухаалаг · Удирдлага · Гарах) → тоглоом → үр дүн
(дүр бүрийн хохирол, эдгээлт, алсан тоо, шилдэг баатар). Тоглоомын үеэр Esc (сонголтгүй үед) — түр зогсолт.

| Үйлдэл | Удирдлага |
|---|---|
| Баатар сонгох | Баатар дээр зүүн товч |
| Очих нүд сонгох | Тодорсон (цэнхэр) нүдэн дээр зүүн товч — дүрийн сүүдэр тэнд харагдана |
| Зөвхөн хөдлөх / хүлээх | Очих нүдэн дээр дахин дарах, эсвэл `W` / Space / «Хөдлөх · Хүлээх» товч |
| Ур чадвар | `1`–`4` эсвэл самбарын товч → бай дээр дарна. Хохирол, «унана» гэдэг нь урьдчилан харагдана |
| Taunt, Imp дуудах | Товчийг дахин дарах эсвэл дүрийн нүдэн дээр дарах |
| Мөсөн ханын чиглэл | `V` / хулганы дугуй |
| Буцах | Баруун товч / Esc — ур чадвар → очих нүд → сонголт гэсэн дарааллаар; сонголтгүй бол Esc түр зогсооно |
| Ээлж дуусгах | `E` / Enter / «Ээлж дуусгах» товч |
| «Боссын бодол» самбар | `Tab` — нээх / хаах (цонх баруун тийш өргөсөж, агшина) |
| Дуу | `M` — асаах / унтраах |
| Дахин эхлэх (тоглолт дууссаны дараа) | `R` эсвэл үр дүнгийн дэлгэцийн «Дахин тоглох» |

Дүр дээрх тэмдэг: цэнхэр тоо — бамбай, `Х2` — хараал (2 ээлж), `T2` — taunt (2 ээлж).
Хулганаа дүр дээр аваачихад түүний ур чадвар, cooldown самбарт харагдана.

Босс `ai/` main-д ороогүй үед түр `PlaceholderBoss`-оор нүүнэ. `ai` байвал автоматаар
`BossAI(mode="eval")`-ийг ашиглана. Боссын шийдвэрийг тусдаа thread-д тооцоолдог (`game/boss_driver.py`),
энэ хугацаанд «Босс бодож байна...» гэж харагдана.

«Боссын бодол» самбар (`game/boss_panel.py`) нь `decision.to_panel()`-ийг харуулна: танисан зуршил,
эхний 3 сонголт (оноо, сонгосон нь, санамсаргүй эсэх), уур хилэн, горим/хугацаа/симуляцийн тоо.
Түр босс ажиллаж байхад «AI холбогдоогүй» гэсэн тайлбар гарна.

Sprite, дуу: [Kenney](https://www.kenney.nl)-ийн CC0 багц (Tiny Dungeon, RPG Audio, Interface Sounds,
Music Jingles). Хөгжим: OpenGameArt-ийн CC0 — эхлэл (Vampire's Piano, TAD), цэс (Dark Forest Theme,
cynicmusic), тулаан (Battle Theme A, cynicmusic), үр дүн (Cold Silence, Eponasoft).
Бүгд `game/assets/`-д, эх файл бүрийн жагсаалт `game/assets/CREDITS.md`-д. Файл олдохгүй
эсвэл audio төхөөрөмж байхгүй бол тоглоом өнгөт дөрвөлжин, дуугүйгээр үргэлжилнэ.

Сонголтын логик (`game/input.py`), session (`game/session.py`), боссын thread зэрэг нь pygame-гүй,
`tests/test_game_input.py`-д тестлэгдсэн. `tests/test_game_app.py` нь App-ийг дэлгэцгүй (SDL dummy) ажиллуулна.

### `on_action` hook
Хүний болон боссын нүүдэл бүр `GameSession.play()`-ээр дамждаг, нүүдэл бүрийн дараа hook дуудагдана:
```python
from game.app import App
from game.session import GameSession

def on_action(state_before, action, events):
    # state_before.to_dict(), action.to_dict(), events — JSON-д бичихэд бэлэн
    ...

App(GameSession(on_action=on_action)).run()   # эсвэл session.add_hook(fn)
```

## Тоглолтын log (`learning/`)

`python -m game` тоглолт бүрийг `logs/`-д (git-д орохгүй) нэг файл болгон бичнэ. `--log-dir DIR` — өөр хавтас,
`--no-log` — бичихгүй. Формат нь JSON Lines, мөр бүр нэг объект:

```json
{"type": "start", "version": 1, "time": "2026-11-09T15:30:12", "human_side": "heroes", "meta": {"boss": "eval"}, "state": {...}}
{"type": "action", "i": 0, "round": 1, "side": "heroes", "actor": "human", "state": {...нүүдлээс өмнөх...}, "action": {...}, "events": [...]}
{"type": "end", "winner": "heroes", "rounds": 7, "actions": 58, "reason": "game_over"}
```

`reason`: `game_over` (дууссан), `restart` (шинээр эхэлсэн), `menu`, `quit` (дуусаагүй). Мөр бүрийг бичмэгц
flush хийдэг тул тоглоом гэнэт хаагдсан ч бичсэн хэсэг үлдэнэ.

```python
from learning import iter_logs, read_log, replay_check
for path, records in iter_logs("logs", finished_only=True):
    assert replay_check(records)      # log-ийг engine-ээр дахин тоглуулж яг таарч байгааг шалгана
```

### Зуршлын профайл (`learning/profile.py`)

Сүүлийн 20 тулааны log-оос `BossAI(profile=...)`-д өгөх профайл гаргана:

```bash
python -m learning.profile logs          # → logs/profile.json, дэлгэцэнд target_priority, habits
```

- `target_priority` — тоглогч аль баатраас хамгийн их хамаардгийг (өгсөн хохирол + эдгээлт + бамбайгаар
  **бодитоор шингээсэн** хохирол + taunt) хувиар тооцож, default аюулын түвшинг (Knight 1.0, Mage 1.3,
  Healer 1.4) хамгийн ихдээ 0.7–1.6 дахин өөрчилнө. Өгөгдөл бага (≈60 нүүдлээс цөөн) үед default-оос бага холдоно.
- `habits` (самбарт, хамгийн ихдээ 4): «Healer-т их найддаг», «Healer Knight-ийн ард нуугддаг»,
  «Knight урд талд түрж тоглодог», «Mage алсаас довтолдог», «Боссыг шууд онилдог», «Imp-үүдийг түрүүлж
  устгадаг», «Taunt-ийг байнга ашигладаг», «Мөсөн ханаар хамгаалдаг», «Ихэнхдээ байрандаа хүлээдэг»,
  «Ээлжээ эрт дуусгадаг».

Тоглоом шинэ тоглолт бүрийн өмнө профайлыг log-оос шинээр гаргаж боссод өгнө (`--profile auto`, default).
`--profile none` — суралцдаггүй босс (A/B туршилтын B бүлэг), `--profile path.json` — тогтмол профайл.
Log-ийн `meta.learned` нь тухайн тулаанд босс профайлтай байсан эсэхийг тэмдэглэнэ.

## Bot тоглогчид (`bots/`)

Өөр өөр зуршилтай тоглогчийг дуурайдаг скриптэй bot-ууд (профайл, 100 тулааны туршилтад):
`random`, `greedy`, `healer_reliant`, `mage_reliant`, `aggressive`, `cautious`.

```python
from bots import HERO_BOTS, play_match
from game.boss_driver import PlaceholderBoss      # эсвэл ai.BossAI(...)
r = play_match(HERO_BOTS["cautious"](seed=1), PlaceholderBoss(seed=1), logger=None)
r.winner, r.rounds, r.boss_hp
```

## Туршилт (`experiments/`)

```bash
python -m experiments --games 100 --boss eval     # ai/ шаардлагатай; --boss placeholder — түр босс
```

1. **Үндсэн:** суралцаагүй босс vs 6 bot, 100 тулаан — ялалтын хувь, тулааны урт, боссын үлдсэн HP.
2. **A/B:** bot бүрийн 5 тулааны log-оос профайл сургаад, суралцсан (A) ба суралцаагүй (B) боссыг
   **ижил seed**-ээр 100 + 100 тулаанд харьцуулна. Ялгааны 95% интервал — paired bootstrap.
3. **Тэнцвэр:** `engine/constants.py`-г өөрчлөхгүйгээр утгыг зөвхөн туршилтын процесст түр сольж
   (боссын HP ×0.8, ×0.7, баатруудын HP ×1.25, Хар дөл ×0.75, Тамын галын cooldown +1, ...) тус бүрт 100 тулаан.

Гаралт: `experiments/results/REPORT.md` (монгол тайлан, PM-ийн дүгнэлттэй), `games.csv` (тулаан бүр),
`profiles.json`. Seed тогтмол тул дахин ажиллуулахад ижил дүн гарна.

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
