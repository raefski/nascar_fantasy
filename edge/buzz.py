"""Player buzz: how often public DFS content names each player before lock.

GPP ownership is set by what the field was told to play, and the field is told
by the same few dozen YouTube shows every week. Counting who those shows talk
about is a direct read on that, where edge/dfs_nfl_theory.py's field model
only sees points per dollar. This module is the sport-free matching half;
scripts/buzz_nfl.py collects transcripts and scripts/buzz_fit_nfl.py tests
whether the counts improve the ownership fit.

A mention is counted, not a recommendation. "Everyone's on Gibbs, I'm fading
him" still says Gibbs will be owned, which is the only thing ownership needs.

Matching is tuned to YouTube's automatic captions, which capitalise proper
nouns reliably but garble first names ("Jir Gibbs", "Bjon" for Bijan). So
surnames carry most of the weight, and a bare surname or first name only
counts when it is capitalised and not the first word of a sentence -- "Love
the matchup" must not credit Jordan Love.
"""
from __future__ import annotations

import re
from collections import Counter

from edge.names import norm as bare_name

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*")
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

#: DFS shorthand that no rule derives from a name. Keyed by edge.names.norm of
#: the DK display name; only used when that player is on the board.
NICKNAMES = {
    "christianmccaffrey": ["CMC"],
    "jaxonsmithnjigba": ["JSN"],
    "amonrastbrown": ["ARSB"],
    "ajbrown": ["AJB"],
    "brianthomas": ["BTJ"],
    "marvinharrison": ["MHJ"],
    "travisetienne": ["ETN"],
    "deandrehopkins": ["Nuk"],
    "marquisebrown": ["Hollywood Brown"],
}

DST_WORDS = [("defense",), ("d",), ("dst",), ("def",), ("d", "st")]

#: Never a bare surname or first name: football talk says these as places and
#: teams. On the 2026-09-20 slate "Dallas" was the Cowboys 125 times out of
#: 125, all of which had been credited to DeeJay Dallas.
PLACES = set("""
arizona atlanta baltimore buffalo carolina chicago cincinnati cleveland dallas
denver detroit green bay houston indianapolis indy jacksonville kansas city las
vegas los angeles miami minnesota england orleans york philadelphia philly
pittsburgh francisco seattle tampa tennessee washington london ford mexico
dublin berlin munich madrid paris brazil germany lambeau arrowhead
cardinals falcons ravens bills panthers bears bengals browns cowboys broncos
lions packers texans colts jaguars chiefs raiders chargers rams dolphins vikings
patriots saints giants jets eagles steelers niners seahawks buccaneers bucs
titans commanders
""".split())

FULL, NICK, LAST, FIRST, DST = "full", "nick", "last", "first", "dst"
_NEEDS_PROPER_NOUN = {LAST, FIRST}


def _norm_token(t: str) -> str:
    return "".join(c for c in t.lower() if c.isalnum())


def tokenize(text: str) -> list[tuple[str, bool, bool]]:
    """-> [(token, capitalised, starts_sentence)].

    Runs of single capital letters merge ("A. J." -> "aj") so an initialled
    name reads the same whether the captioner dotted it or not. A caption's
    ">>" speaker change counts as a sentence break.
    """
    out: list[list] = []
    prev_end = 0
    for m in _TOKEN_RE.finditer(text):
        raw = m.group(0)
        gap = text[prev_end:m.start()]
        prev_end = m.end()
        tok = _norm_token(raw)
        single_cap = len(raw) == 1 and raw.isupper()
        if single_cap and out and out[-1][3] and re.fullmatch(r"[.\s]*", gap):
            out[-1][0] += tok
            continue
        sentence = not out or bool(re.search(r"[.!?>]", gap))
        out.append([tok, raw[0].isupper(), sentence, single_cap])
    return [(t, cap, sent) for t, cap, sent, _ in out]


#: Rare among NFL players but common among the people doing the talking --
#: hosts, analysts ("Evan" is usually Evan Silva, not Evan Engram), coaches,
#: owners. Never a bare first name. Distinctive ones (Bijan, Baker, Chuba)
#: still count.
COMMON_FIRST_NAMES = set("""
aaron adam alan albert alex alexander andrew andy anthony austin ben benjamin
bill billy blake bob bobby brad brandon brett brian bruce bryan carl carson chad
charles charlie chris christopher cole colin connor cooper craig dan daniel
darnell dave david dawson dennis derek don donald doug douglas drew dylan ed
edward eric ethan evan frank gabe gary george grant greg gregory harold henry
hunter ian jack jacob jake james jason jeff jeffrey jeremy jerry jesse jim jimmy
joe john johnny jon jonah jonathan jonathon jordan jose joseph josh joshua juan
justin keith kevin kurt kyle larry logan luke mack marcus mark mason matt
matthew max michael mike nate nathan nick nicholas noah omar owen parker pat
patrick paul pete peter phil philip ralph randy ray raymond rich richard rick
rob robert roger ron ronald roy russell ryan sam samuel scott sean seth shane
stephen steve steven ted terry tim timothy todd tom tommy tony travis troy
tyler vincent walter wayne will william zach zachary
""".split())


def _is_place(tokens: tuple[str, ...]) -> bool:
    return len(tokens) == 1 and tokens[0] in PLACES


def _name_parts(name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """("Amon-Ra St. Brown") -> (("amon", "ra"), ("st", "brown"))."""
    words = name.split()
    while len(words) > 1 and _norm_token(words[-1]) in _SUFFIXES:
        words.pop()
    first = tuple(t for t, _, _ in tokenize(words[0])) if words else ()
    last = tuple(t for w in words[1:] for t, _, _ in tokenize(w))
    return first, last


def build_aliases(board: list[dict], first_name_counts: Counter | None = None) -> dict:
    """{token tuple: (board name, kind)} for one slate.

    `board` rows need "name" and "pos" ("DST" marks a defence, whose name is
    the team nickname). Every name on the slate belongs here, not just the
    players the model priced: an off-pool "Mason Taylor" has to exist as a full
    name, or its tokens get read as Jordan Mason plus Jonathan Taylor.

    A bare surname is kept only when no other board player shares it. A bare
    first name additionally has to be rare across past NFL seasons
    (`first_name_counts`, at most one prior player), so "Bijan" and "Saquon"
    count but "Kyle" (Kyle Shanahan is not Kyle Pitts) does not.
    """
    first_name_counts = first_name_counts or Counter()
    aliases: dict = {}
    surnames: Counter = Counter()
    firsts: Counter = Counter()
    parts = {}
    for row in board:
        name = row["name"].strip()
        if row.get("pos") == "DST":
            nick = tuple(t for t, _, _ in tokenize(name))
            for words in DST_WORDS:
                aliases[nick + words] = (name, DST)
            continue
        first, last = _name_parts(name)
        if not last:
            continue
        parts[name] = (first, last)
        surnames[last] += 1
        if len(first) == 1:
            firsts[first[0]] += 1

    surname_set = set(surnames)
    for name, (first, last) in parts.items():
        aliases[first + last] = (name, FULL)
        for nick in NICKNAMES.get(bare_name(name), []):
            aliases[tuple(t for t, _, _ in tokenize(nick))] = (name, NICK)
    for name, (first, last) in parts.items():
        if surnames[last] == 1 and last not in aliases and not _is_place(last):
            aliases[last] = (name, LAST)
    for name, (first, last) in parts.items():
        if (len(first) == 1 and len(first[0]) >= 4 and firsts[first[0]] == 1
                and (first[0],) not in surname_set and first not in aliases
                and first_name_counts[first[0]] <= 1 and not _is_place(first)
                and first[0] not in COMMON_FIRST_NAMES):
            aliases[first] = (name, FIRST)
    return aliases


def is_cased(tokens: list[tuple[str, bool, bool]]) -> bool:
    """False for an all-lowercase caption track, where proper-noun rules can't
    work and only full names, nicknames and defences are matched."""
    mid = [cap for _, cap, sent in tokens if not sent]
    return bool(mid) and sum(mid) / len(mid) > 0.02


def count_mentions(text: str, aliases: dict) -> Counter:
    """{board name: mentions} in one transcript. Longest alias wins at each
    position, so "Chase Brown" is one Chase Brown mention and not also a
    Ja'Marr Chase one."""
    tokens = tokenize(text)
    cased = is_cased(tokens)
    longest = max((len(k) for k in aliases), default=0)
    words = [t for t, _, _ in tokens]
    counts: Counter = Counter()
    i = 0
    while i < len(words):
        for n in range(min(longest, len(words) - i), 0, -1):
            hit = aliases.get(tuple(words[i:i + n]))
            if not hit:
                continue
            name, kind = hit
            if kind in _NEEDS_PROPER_NOUN:
                _, cap, sent = tokens[i]
                if not cased or not cap or sent:
                    continue
            counts[name] += 1
            i += n
            break
        else:
            i += 1
    return counts


def aggregate(videos: list[dict]) -> dict:
    """Per-player slate features from per-video counts.

    Each video is {"channel", "views", "counts": Counter}. `reach` weights a
    video's views by the player's share of that video's mentions -- roughly how
    much of its audience's attention went to him.
    """
    out: dict = {}
    for v in videos:
        total = sum(v["counts"].values())
        for name, c in v["counts"].items():
            row = out.setdefault(name, {"mentions": 0, "videos": 0,
                                        "channels": set(), "reach": 0.0})
            row["mentions"] += c
            row["videos"] += 1
            row["channels"].add(v["channel"])
            row["reach"] += (v.get("views") or 0) * c / total
    for row in out.values():
        row["channels"] = len(row["channels"])
        row["reach"] = round(row["reach"], 1)
    return out
