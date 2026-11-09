"""Тоглоомын тоон утгууд.

Бүх тоо нь төлөвлөгөөний (PDF, 2-р хэсэг) анхны утга. Тэнцвэрийн тохиргоогоор (WBS 3.5)
өөрчлөгдөнө. Тоог зөвхөн энэ файлд өөрчилнө — rules.py дотор тоо бичихгүй.

"TBD (GDD)" гэсэн утгууд PDF-д байхгүй тул AI Engineer түр тавьсан. PM GDD-д
(11/12) батлах хүртэл түр утга гэж үзнэ.

Тэнцвэр (2026-11-09, PM баталсан): PDF-ийн анхны утгаар баатрууд BossAI-ийн эсрэг 100 тулаанаас
0-ийг ялсан. 100 тулааны туршилтын (experiments/results/REPORT.md) дүнгээр боссын HP ×0.6,
Хар дөл ×0.75, баатруудын HP ×1.25 болгосон — bot-ууд ~51% ялна. «PDF: x» гэж анхны утгыг үлдээв.
"""

from dataclasses import dataclass

BOARD_W = 8
BOARD_H = 8

HEROES = "heroes"
DEMONS = "demons"

MAX_ROUNDS = 40            # TBD (GDD): үүнээс хэтэрвэл тэнцээ (bot туршилт төгсгөлгүй явахгүй)
ENRAGE_THRESHOLD = 0.30    # PDF: боссын HP 30%-иас доош бол уур хилэн
MAX_IMPS = 2               # нэг дуудагчийн амьд дагуулын дээд тоо (Imp, Slime, Goblin)
MAX_SUMMONS = MAX_IMPS


@dataclass(frozen=True)
class Skill:
    sid: str
    name: str
    kind: str          # damage | area_damage | drain | taunt | wall | heal | shield | curse | summon | leap
    range: int         # Manhattan зай
    power: int = 0     # хохирол / эдгэрэлт / бамбайн хэмжээ
    duration: int = 0  # ээлжийн тоо (taunt, wall, curse)
    cooldown: int = 1  # 1 = ээлж бүр, 2 = хоёр ээлж тутам, ...
    summons: str = ""  # summon: аль төрлийн үхсэн дагуулыг сэргээх
    drain: float = 0.0  # drain: учруулсан хохирлын хэдэн хувиар өөрийгөө эдгээх


SKILLS = {
    # Knight
    "sword":      Skill("sword", "Сэлэм", "damage", range=1, power=20, cooldown=1),
    "taunt":      Skill("taunt", "Taunt", "taunt", range=3, duration=2, cooldown=3),          # range, cd: TBD (GDD)
    # Mage
    "fireball":   Skill("fireball", "Галт бөмбөг", "area_damage", range=4, power=25, cooldown=2),  # range, cd: TBD
    "ice_wall":   Skill("ice_wall", "Мөсөн хана", "wall", range=3, duration=2, cooldown=3),   # range, cd: TBD
    # Healer
    "heal":       Skill("heal", "Эдгээх", "heal", range=3, power=35, cooldown=2),            # range, cd: TBD
    "shield":     Skill("shield", "Бамбай", "shield", range=3, power=20, cooldown=3),        # range, cd: TBD
    # Demon Lord
    "dark_flame": Skill("dark_flame", "Хар дөл", "damage", range=4, power=22, cooldown=1),  # PDF: 30
    "hellfire":   Skill("hellfire", "Тамын гал", "area_damage", range=4, power=20, cooldown=3),
    "curse":      Skill("curse", "Хараал", "curse", range=4, duration=2, cooldown=3),
    "shadow_leap": Skill("shadow_leap", "Сүүдрийн үсрэлт", "leap", range=6, cooldown=4),
    "summon_imp": Skill("summon_imp", "Imp дуудах", "summon", range=1, cooldown=5, summons="imp"),
    # Imp
    "claw":       Skill("claw", "Сарвуу", "damage", range=1, power=10, cooldown=1),

    # ---- Dungeon (2026-11-09, PM-ийн дизайн) — анхны утга, тэнцвэрийг туршилтаар тааруулна ----
    # 1-р давхар: Slime
    "acid":        Skill("acid", "Хүчил", "damage", range=1, power=9, cooldown=1),
    "slime_slam":  Skill("slime_slam", "Нялцгай цохилт", "area_damage", range=2, power=14, cooldown=2),
    "acid_spit":   Skill("acid_spit", "Хүчлийн нулимс", "damage", range=3, power=12, cooldown=1),
    "split":       Skill("split", "Хуваагдах", "summon", range=1, cooldown=4, summons="slime"),
    # 2-р давхар: Goblin
    "stab":        Skill("stab", "Хутгалах", "damage", range=1, power=11, cooldown=1),
    "cleave":      Skill("cleave", "Хүнд цавчилт", "damage", range=1, power=22, cooldown=1),
    "spear_throw": Skill("spear_throw", "Жад шидэх", "damage", range=4, power=14, cooldown=2),
    "call_goblins": Skill("call_goblins", "Гоблин дуудах", "summon", range=1, cooldown=4,
                          summons="goblin"),
    # 3-р давхар: Vampire
    "bite":        Skill("bite", "Хазах", "drain", range=1, power=11, cooldown=1, drain=0.5),
    "blood_drain": Skill("blood_drain", "Цус сорох", "drain", range=3, power=18, cooldown=1,
                         drain=0.75),
    "bat_swarm":   Skill("bat_swarm", "Сарьсан багваахайн сүрэг", "area_damage", range=3,
                         power=14, cooldown=3),
    "mist_step":   Skill("mist_step", "Манан алхам", "leap", range=5, cooldown=3),
    # 4-р давхар: Demon legion
    "demon_claw":  Skill("demon_claw", "Чөтгөрийн сарвуу", "damage", range=1, power=13, cooldown=1),
    "hellblade":   Skill("hellblade", "Тамын илд", "damage", range=1, power=24, cooldown=1),
    # 5-р давхар: Made in Hell
    "fire_claw":   Skill("fire_claw", "Галт сарвуу", "damage", range=1, power=13, cooldown=1),
    "ember":       Skill("ember", "Цог", "damage", range=3, power=10, cooldown=2),
}


@dataclass(frozen=True)
class UnitType:
    kind: str
    name: str
    side: str
    hp: int
    move: int
    skills: tuple          # ээлжинд хэрэглэх ур чадварууд (нэгийг сонгоно)
    leap: str = ""         # хөдөлгөөний оронд хэрэглэх ур чадвар (Demon Lord, Vampire Lord)
    boss: bool = False     # давхрын босс — үхвэл баатрууд ялна


UNIT_TYPES = {
    "knight": UnitType("knight", "Knight", HEROES, hp=150, move=3, skills=("sword", "taunt")),  # PDF: 120
    "mage": UnitType("mage", "Mage", HEROES, hp=88, move=3, skills=("fireball", "ice_wall")),    # PDF: 70
    "healer": UnitType("healer", "Healer", HEROES, hp=100, move=3, skills=("heal", "shield")),   # PDF: 80
    "demon_lord": UnitType("demon_lord", "Demon Lord", DEMONS, hp=240, move=2,                  # PDF: 400
                           skills=("dark_flame", "hellfire", "curse", "summon_imp"),
                           leap="shadow_leap", boss=True),
    "imp": UnitType("imp", "Imp", DEMONS, hp=30, move=4, skills=("claw",)),

    # ---- Dungeon-ийн мангас, давхрын боссууд ----
    "slime": UnitType("slime", "Slime", DEMONS, hp=26, move=2, skills=("acid",)),
    "slime_king": UnitType("slime_king", "Slime King", DEMONS, hp=170, move=2,
                           skills=("slime_slam", "acid_spit", "split"), boss=True),
    "goblin": UnitType("goblin", "Goblin", DEMONS, hp=30, move=3, skills=("stab",)),
    "goblin_king": UnitType("goblin_king", "Goblin King", DEMONS, hp=190, move=3,
                            skills=("cleave", "spear_throw", "call_goblins"), boss=True),
    "low_vampire": UnitType("low_vampire", "Low Vampire", DEMONS, hp=34, move=3, skills=("bite",)),
    "vampire_lord": UnitType("vampire_lord", "Vampire Lord", DEMONS, hp=200, move=3,
                             skills=("blood_drain", "curse", "bat_swarm"), leap="mist_step",
                             boss=True),
    "demon": UnitType("demon", "Demon", DEMONS, hp=40, move=2, skills=("demon_claw",)),
    "legion_commander": UnitType("legion_commander", "Legion Commander", DEMONS, hp=220, move=2,
                                 skills=("hellblade", "hellfire", "summon_imp"), boss=True),
    "hell_demon": UnitType("hell_demon", "Hell Demon", DEMONS, hp=42, move=3,
                           skills=("fire_claw", "ember")),
}

# Эхлэх байрлал (x, y). y=0 бол дээд эгнээ. TBD (GDD)
START_POSITIONS = {
    "knight": ("knight", (3, 6)),
    "mage": ("mage", (2, 7)),
    "healer": ("healer", (5, 7)),
    "demon_lord": ("demon_lord", (4, 1)),
    "imp1": ("imp", (2, 1)),
    "imp2": ("imp", (6, 1)),
}


# ---- Ахиц (2026-11-09, PM): level, туршлага, item. Тэнцвэрийг туршилтаар тааруулна ----
MAX_LEVEL = 10
LEVEL_XP = (0, 100, 230, 400, 620, 890, 1210, 1580, 2000, 2470)   # level n-д хүрэх нийт XP (n=1..10)
LEVEL_HP_GROWTH = 0.08       # level тутам max HP +8%
LEVEL_POWER_GROWTH = 0.06    # level тутам хохирол / эдгээлт / бамбай +6%
STAGE_XP = 50                # үе давахад баатар бүрт (× давхрын дугаар)
BOSS_STAGE_XP = 140          # давхрын боссыг ялахад (× давхрын дугаар)
LOSS_XP_FRACTION = 0.3       # ялагдсан ч олсон XP-ийн хувь


@dataclass(frozen=True)
class Item:
    iid: str
    name: str
    hp: int = 0              # max HP-д нэмэх
    power: float = 0.0       # хохирол / эдгээлтийн үржвэрт нэмэх (0.08 = +8%)
    move: int = 0            # хөдөлгөөнд нэмэх
    rarity: str = "common"   # common | rare | boss


ITEMS = {
    "life_heart":   Item("life_heart", "Амьдралын зүрх", hp=12),
    "iron_charm":   Item("iron_charm", "Төмөр сахиус", hp=20, rarity="rare"),
    "sharp_edge":   Item("sharp_edge", "Хурц ир", power=0.06),
    "rune_stone":   Item("rune_stone", "Рун чулуу", power=0.10, rarity="rare"),
    "swift_boots":  Item("swift_boots", "Хурдны гутал", move=1, rarity="rare"),
    # давхрын боссын баталгаатай олз
    "slime_core":   Item("slime_core", "Нялцгайн цөм", hp=25, rarity="boss"),
    "goblin_crown": Item("goblin_crown", "Гоблины титэм", power=0.12, rarity="boss"),
    "vampire_fang": Item("vampire_fang", "Цус соруулын соёо", hp=15, power=0.08, rarity="boss"),
    "legion_sigil": Item("legion_sigil", "Легионы тамга", hp=20, power=0.10, rarity="boss"),
}
MAX_ITEMS_PER_HERO = 4
ITEM_DROP_CHANCE = 0.45      # энгийн үе давахад item унах магадлал
RARE_DROP_CHANCE = 0.25      # унасан item rare байх магадлал
BOSS_DROPS = {1: "slime_core", 2: "goblin_crown", 3: "vampire_fang", 4: "legion_sigil"}

# Давхар бүрийн дайснуудын HP / хохирлын үржвэр (баатрууд level ахих тул)
FLOOR_ENEMY_SCALE = {1: (1.0, 1.0), 2: (1.05, 1.05), 3: (1.1, 1.1), 4: (1.15, 1.15),
                     5: (1.35, 1.2)}
