"""Shared text-analytics helpers: sentiment (VADER), hashtag extraction, review-signal regexes."""
from __future__ import annotations
import re
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_an = SentimentIntensityAnalyzer()

HASHTAG_RX = re.compile(r"#(\w{2,40})")

# Review-derived signals used as TRANSPARENT sustainability proxies (see README: limitations).
SIGNALS = {
    "dur_neg": r"fell apart|falling apart|came apart|ripped|tore\b|torn|broke\b|broken|snapped|unravel|fell off|faded|fading|shrunk|shrank|pilling|pilled|flimsy|cheaply made|cheap quality|poor quality|poorly made|stitching (?:came|is coming|came undone)|seam(?:s)? (?:split|ripped|came)|rusted|tarnish|turned (?:green|black)|discolor",
    "dur_pos": r"durable|well[- ]made|sturdy|holds? up|held up|long[- ]lasting|lasts? (?:for )?(?:years|long)|great quality|high quality|good quality|excellent quality|solid construction|built to last|worn (?:it )?for years",
    "fit_neg": r"too small|too big|too large|too tight|too loose|runs small|runs large|runs big|run small|doesn'?t fit|did not fit|didn'?t fit|wrong size|sizing (?:is|was) off|size chart|had to return|returned|sent (?:it )?back|return(?:ing)? it",
    "versatile": r"versatile|goes with everything|go with everything|dress(?:ed)? (?:it )?(?:up|down)|many occasions|any occasion|every ?day|wear (?:it )?with (?:anything|everything)|multiple ways|so many (?:outfits|ways)|all[- ]season",
}
_SIG_RX = {k: re.compile(v, re.I) for k, v in SIGNALS.items()}


def vader_compound(texts: pd.Series) -> pd.Series:
    return texts.map(lambda t: _an.polarity_scores(t)["compound"])


def label(compound: float) -> str:
    return "positive" if compound >= 0.05 else "negative" if compound <= -0.05 else "neutral"


def signal_flags(texts: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({k: texts.str.contains(rx, regex=True).astype("int8") for k, rx in _SIG_RX.items()})


def extract_hashtags(text: str) -> list[str]:
    return [h.lower() for h in HASHTAG_RX.findall(text or "")]
