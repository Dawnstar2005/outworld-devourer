# Ассетын эх сурвалж

Sprite, дууны эффект [Kenney](https://www.kenney.nl)-ийн, хөгжим [OpenGameArt](https://opengameart.org)-ийн
**CC0 1.0** (Creative Commons Zero) лицензтэй бүтээл.
Хувийн, сургалтын, арилжааны төсөлд чөлөөтэй ашиглаж болно. Нэр дурдах нь заавал биш, гэхдээ бид дурдаж байна.
Лицензийн эх бичвэр: `LICENSE-kenney.txt`. Татсан огноо: 2026-11-09.

## Sprite — [Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon) (16×16)

| Файл | Эх файл | Хэрэглээ |
|---|---|---|
| `sprites/knight.png` | `Tiles/tile_0096.png` | Knight |
| `sprites/mage.png` | `Tiles/tile_0084.png` | Mage |
| `sprites/healer.png` | `Tiles/tile_0112.png` | Healer |
| `sprites/demon_lord.png` | `Tiles/tile_0110.png` | Demon Lord |
| `sprites/imp.png` | `Tiles/tile_0120.png` | Imp |
| `sprites/floor.png` | `Tiles/tile_0000.png` | Талбарын шал |
| `sprites/wall.png` | `Tiles/tile_0040.png` | Мөсөн хана (цэнхэр өнгөөр будна) |

## Дуу

| Файл | Багц | Эх файл |
|---|---|---|
| `sounds/step.ogg` | [RPG Audio](https://kenney.nl/assets/rpg-audio) | `footstep00.ogg` |
| `sounds/leap.ogg` | RPG Audio | `cloth1.ogg` |
| `sounds/slash.ogg` | RPG Audio | `knifeSlice.ogg` |
| `sounds/dark_flame.ogg` | RPG Audio | `knifeSlice2.ogg` |
| `sounds/blast.ogg` | RPG Audio | `chop.ogg` |
| `sounds/death.ogg` | RPG Audio | `dropLeather.ogg` |
| `sounds/summon.ogg` | RPG Audio | `doorOpen_1.ogg` |
| `sounds/ice.ogg` | [Interface Sounds](https://kenney.nl/assets/interface-sounds) | `glass_006.ogg` |
| `sounds/heal.ogg` | Interface Sounds | `confirmation_002.ogg` |
| `sounds/shield.ogg` | Interface Sounds | `glass_004.ogg` |
| `sounds/curse.ogg` | Interface Sounds | `glitch_002.ogg` |
| `sounds/taunt.ogg` | Interface Sounds | `bong_001.ogg` |
| `sounds/select.ogg` | Interface Sounds | `select_001.ogg` |
| `sounds/tick.ogg` | Interface Sounds | `tick_002.ogg` |
| `sounds/click.ogg` | Interface Sounds | `click_002.ogg` |
| `sounds/back.ogg` | Interface Sounds | `back_001.ogg` |
| `sounds/error.ogg` | Interface Sounds | `error_001.ogg` |
| `sounds/win.ogg` | [Music Jingles](https://kenney.nl/assets/music-jingles) | `8-Bit jingles/jingles_NES12.ogg` |
| `sounds/lose.ogg` | Music Jingles | `8-Bit jingles/jingles_NES11.ogg` |
| `sounds/your_turn.ogg` | Music Jingles | `8-Bit jingles/jingles_NES09.ogg` |

## Хөгжим — [OpenGameArt](https://opengameart.org), CC0

| Файл | Хаана | Нэр | Зохиолч | Эх файл |
|---|---|---|---|---|
| `music/intro.mp3` | Эхлэлийн дүр зураг | [Vampire's Piano](https://opengameart.org/content/vampires-piano) | TAD | `vampires_piano_6.mp3` |
| `music/title.mp3` | Үндсэн цэс | [Dark Forest Theme](https://opengameart.org/content/dark-forest-theme) | cynicmusic | `GameMusic_ForestTheme_24_0.mp3` |
| `music/battle.mp3` | Тулаан | [Battle Theme A](https://opengameart.org/content/battle-theme-a) | cynicmusic | `battleThemeA.mp3` |
| `music/result.ogg` | Үр дүнгийн дэлгэц | [Cold Silence](https://opengameart.org/content/cold-silence) | Eponasoft | `cold_silence.ogg` |

Бүгд OpenGameArt дээр CC0 лицензтэй гэж тэмдэглэгдсэн (2026-11-09-нд шалгав). Хөгжим солих бол
`game/music.py`-ийн `MUSIC_TRACKS`-ийг засна.

Ялалт/ялагдлын jingle-ийг аялгууны чиглэлээр (өгсөх / уруудах) сонгосон. Дууг солих бол
`game/sound.py`-ийн `SOUND_FILES`-ийг засна.
