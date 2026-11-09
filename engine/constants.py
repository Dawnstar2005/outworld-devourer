"""Тоглоомын тоон утгууд.

Бүх тоо нь төлөвлөгөөний (PDF, 2-р хэсэг) анхны утга. Тэнцвэрийн тохиргоогоор (WBS 3.5)
өөрчлөгдөнө. Тоог зөвхөн энэ файлд өөрчилнө — rules.py дотор тоо бичихгүй.

"TBD (GDD)" гэсэн утгууд PDF-д байхгүй тул AI Engineer түр тавьсан. PM GDD-д
(11/12) батлах хүртэл түр утга гэж үзнэ.
"""

from dataclasses import dataclass

BOARD_W = 8
BOARD_H = 8

HEROES = "heroes"
DEMONS = "demons"

MAX_ROUNDS = 40            # TBD (GDD): үүнээс хэтэрвэл тэнцээ (bot туршилт төгсгөлгүй явахгүй)
ENRAGE_THRESHOLD = 0.30    # PDF: боссын HP 30%-иас доош бол уур хилэн
MAX_IMPS = 2


@dataclass(frozen=True)
class Skill:
    sid: str
    name: str
    kind: str          # damage | area_damage | taunt | wall | heal | shield | curse | summon | leap
    range: int         # Manhattan зай
    power: int = 0     # хохирол / эдгэрэлт / бамбайн хэмжээ
    duration: int = 0  # ээлжийн тоо (taunt, wall, curse)
    cooldown: int = 1  # 1 = ээлж бүр, 2 = хоёр ээлж тутам, ...


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
    "dark_flame": Skill("dark_flame", "Хар дөл", "damage", range=4, power=30, cooldown=1),
    "hellfire":   Skill("hellfire", "Тамын гал", "area_damage", range=4, power=20, cooldown=3),
    "curse":      Skill("curse", "Хараал", "curse", range=4, duration=2, cooldown=3),
    "shadow_leap": Skill("shadow_leap", "Сүүдрийн үсрэлт", "leap", range=6, cooldown=4),
    "summon_imp": Skill("summon_imp", "Imp дуудах", "summon", range=1, cooldown=5),
    # Imp
    "claw":       Skill("claw", "Сарвуу", "damage", range=1, power=10, cooldown=1),
}


@dataclass(frozen=True)
class UnitType:
    kind: str
    name: str
    side: str
    hp: int
    move: int
    skills: tuple          # ээлжинд хэрэглэх ур чадварууд (нэгийг сонгоно)
    leap: str = ""         # хөдөлгөөний оронд хэрэглэх ур чадвар (зөвхөн Demon Lord)


UNIT_TYPES = {
    "knight": UnitType("knight", "Knight", HEROES, hp=120, move=3, skills=("sword", "taunt")),
    "mage": UnitType("mage", "Mage", HEROES, hp=70, move=3, skills=("fireball", "ice_wall")),
    "healer": UnitType("healer", "Healer", HEROES, hp=80, move=3, skills=("heal", "shield")),
    "demon_lord": UnitType("demon_lord", "Demon Lord", DEMONS, hp=400, move=2,
                           skills=("dark_flame", "hellfire", "curse", "summon_imp"),
                           leap="shadow_leap"),
    "imp": UnitType("imp", "Imp", DEMONS, hp=30, move=4, skills=("claw",)),
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
