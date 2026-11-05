"""Rule-based product taxonomy derived from product titles.

The Amazon Reviews 2023 'Fashion' metadata has an empty `categories` field, so the
product type / department / colour / material are *derived* from title text and
the `details` dictionary with transparent keyword rules (documented in README).
"""
from __future__ import annotations
import re

# (article_type, group, keywords) - first match wins, order matters (specific -> generic)
ARTICLE_RULES: list[tuple[str, str, list[str]]] = [
    ("Sneakers", "Footwear", ["sneaker", "running shoe", "athletic shoe", "trainer", "walking shoe", "tennis shoe"]),
    ("Boots", "Footwear", ["boot", "booties", "bootie"]),
    ("Sandals", "Footwear", ["sandal", "flip flop", "flip-flop", "slide", "slipper", "clog"]),
    ("Heels & Flats", "Footwear", ["pump", "high heel", "stiletto", "ballet flat", "flats", "loafer", "oxford", "wedge"]),
    ("Shoes", "Footwear", ["shoe", "footwear", "moccasin"]),
    ("Socks", "Clothing", ["sock", "stocking", "hosiery"]),
    ("Underwear & Intimates", "Clothing", ["underwear", "brief", "boxer", "panties", "panty", "bra ", "bralette", "lingerie", "thong", "shapewear", "undershirt"]),
    ("Swimwear", "Clothing", ["swimsuit", "bikini", "swim trunk", "swimwear", "board short", "one piece swim", "rash guard", "tankini"]),
    ("Dresses", "Clothing", ["dress", "gown", "sundress", "maxi", "romper", "jumpsuit"]),
    ("Jeans", "Clothing", ["jean", "denim"]),
    ("Pants & Leggings", "Clothing", ["pant", "legging", "trouser", "jogger", "chino", "sweatpant", "cargo", "capri", "yoga pant", "tights"]),
    ("Shorts & Skirts", "Clothing", ["short", "skirt", "skort"]),
    ("Jackets & Coats", "Clothing", ["jacket", "coat", "parka", "blazer", "vest", "windbreaker", "cardigan", "puffer", "anorak"]),
    ("Hoodies & Sweaters", "Clothing", ["hoodie", "sweatshirt", "sweater", "pullover", "jumper", "fleece"]),
    ("Tops & T-Shirts", "Clothing", ["t-shirt", "tee", "shirt", "blouse", "tank top", "top", "tunic", "polo", "henley", "camisole"]),
    ("Pajamas & Loungewear", "Clothing", ["pajama", "pyjama", "nightgown", "robe", "sleepwear", "loungewear", "onesie"]),
    ("Watches", "Accessories", ["watch"]),
    ("Jewellery", "Accessories", ["necklace", "bracelet", "earring", "ring ", "pendant", "jewelry", "jewellery", "anklet", "charm", "brooch", "choker", "sterling silver", "gold plated"]),
    ("Bags & Wallets", "Accessories", ["handbag", "backpack", "purse", "wallet", "tote", "clutch", "satchel", "crossbody", "duffel", "bag"]),
    ("Sunglasses & Eyewear", "Accessories", ["sunglass", "glasses", "eyewear"]),
    ("Hats & Caps", "Accessories", ["hat", "cap ", "beanie", "bucket hat", "visor", "beret"]),
    ("Scarves & Gloves", "Accessories", ["scarf", "scarves", "glove", "mitten", "shawl", "wrap", "bandana"]),
    ("Belts & Ties", "Accessories", ["belt", "suspender", "necktie", "bow tie", "tie "]),
    ("Hair Accessories", "Accessories", ["headband", "hair clip", "scrunchie", "hair tie", "barrette"]),
]

COLOURS = [
    "black", "white", "grey", "gray", "navy", "blue", "red", "pink", "green", "brown", "beige", "khaki",
    "yellow", "orange", "purple", "burgundy", "gold", "silver", "cream", "tan", "olive", "teal", "multicolor",
]
# Materials explicitly named in product text (labelled attribute only - NOT an eco claim)
MATERIALS = ["cotton", "wool", "linen", "silk", "leather", "polyester", "denim", "nylon", "cashmere",
             "spandex", "viscose", "rayon", "bamboo", "hemp", "suede", "canvas", "fleece"]
NATURAL_FIBRES = {"cotton", "wool", "linen", "silk", "leather", "cashmere", "bamboo", "hemp", "suede", "canvas"}
SYNTHETIC_FIBRES = {"polyester", "nylon", "spandex", "viscose", "rayon", "fleece"}

GENDER_RULES = [
    ("Girls", ["girls", "girl's", "toddler girl", "little girl"]),
    ("Boys", ["boys", "boy's", "toddler boy", "little boy"]),
    ("Women", ["women", "woman", "ladies", "lady", "womens", "female"]),
    ("Men", ["men's", "mens", "men ", "man ", "male", "gentlemen"]),
    ("Kids", ["kids", "baby", "infant", "toddler", "children", "youth"]),
]
DEPT_MAP = {"womens": "Women", "mens": "Men", "girls": "Girls", "boys": "Boys", "unisex-adult": "Unisex",
            "baby-girls": "Kids", "baby-boys": "Kids", "unisex-baby": "Kids", "unisex": "Unisex", "unisex-child": "Kids"}


def _find(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


_COMPILED = [(a, g, re.compile("|".join(rf"\b{re.escape(k.strip())}(?:s|es)?\b" for k in kws))) for a, g, kws in ARTICLE_RULES]


def classify(title: str) -> tuple[str, str]:
    t = title.lower()
    for art, group, rx in _COMPILED:
        if rx.search(t):
            return art, group
    return "Other", "Other"


def gender(title: str, dept: str | None) -> str:
    if isinstance(dept, str) and dept.lower() in DEPT_MAP:
        return DEPT_MAP[dept.lower()]
    t = f" {title.lower()} "
    for g, kws in GENDER_RULES:
        if any(k in t for k in kws):
            return g
    return "Unisex"


def colour(title: str) -> str | None:
    t = title.lower()
    for c in COLOURS:
        if re.search(rf"\b{c}\b", t):
            return "grey" if c == "gray" else c
    return None


def materials(text: str) -> list[str]:
    t = text.lower()
    return [m for m in MATERIALS if re.search(rf"\b{m}\b", t)]
