"""Text normalisation for spoken agent output.

Every rule here fixes a failure measured on Pocket TTS (voice alba) on
2026-09-19. Nothing is speculative. See the comment on each rule for the
observed failure it prevents.
"""

import re

# Acronyms that must be spelled out rather than read as a word.
# Observed: a service named "aiml-...-api" was read as "AMO ... AP".
ACRONYMS = {
    "aiml": "A-I-M-L",
    "api": "A-P-I",
    "cli": "C-L-I",
    "sdk": "S-D-K",
    "url": "U-R-L",
    "ui": "U-I",
    "ci": "C-I",
    "pr": "P-R",
    "qa": "Q-A",
    "db": "D-B",
    "sql": "sequel",
    "yaml": "yammle",
    "json": "jason",
    "http": "H-T-T-P",
    "https": "H-T-T-P-S",
    "aws": "A-W-S",
    "mcp": "M-C-P",
    "llm": "L-L-M",
    "tts": "T-T-S",
    "sast": "sast",
    "sca": "S-C-A",
}

# File extensions spoken letter by letter.
# Observed: "retry.py" was read as "Retrie. PI".
EXTENSIONS = {
    "py": "dot P-Y", "js": "dot J-S", "ts": "dot T-S", "tsx": "dot T-S-X",
    "jsx": "dot J-S-X", "md": "dot M-D", "json": "dot jason", "yaml": "dot yammle",
    "yml": "dot yammle", "sh": "dot S-H", "go": "dot go", "rs": "dot R-S",
    "java": "dot java", "rb": "dot R-B", "toml": "dot tommle", "cfg": "dot config",
    "txt": "dot text", "csv": "dot C-S-V", "html": "dot H-T-M-L", "css": "dot C-S-S",
    "sql": "dot sequel", "env": "dot env", "lock": "dot lock", "xml": "dot X-M-L",
}

UNITS = {"s": "seconds", "ms": "milliseconds", "m": "minutes",
         "h": "hours", "d": "days", "kb": "kilobytes", "mb": "megabytes",
         "gb": "gigabytes", "tb": "terabytes"}


ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety"]
SCALES = [(10**12, "trillion"), (10**9, "billion"), (10**6, "million"),
          (1000, "thousand"), (100, "hundred")]
ORDINAL_SUFFIX = {"one": "first", "two": "second", "three": "third", "five": "fifth",
                  "eight": "eighth", "nine": "ninth", "twelve": "twelfth"}


def _spell(word: str) -> str:
    return "-".join(word.upper())


def _words(n: int) -> str:
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    for size, name in SCALES:
        if n >= size:
            rest = n % size
            return f"{_words(n // size)} {name}" + ("" if rest == 0 else " " + _words(rest))
    return str(n)


def _year(n: int) -> str:
    if 2000 <= n <= 2009:
        return _words(n)
    hi, lo = divmod(n, 100)
    if lo == 0:
        return f"{_words(hi)} hundred"
    return f"{_words(hi)} {'oh ' if lo < 10 else ''}{_words(lo)}"


def _ordinal(n: int) -> str:
    words = _words(n).split()
    last = words[-1]
    if last in ORDINAL_SUFFIX:
        words[-1] = ORDINAL_SUFFIX[last]
    elif last.endswith("y"):
        words[-1] = last[:-1] + "ieth"
    else:
        words[-1] = last + "th"
    return " ".join(words)


def _digits(s: str) -> str:
    return " ".join(ONES[int(d)] for d in s)


def _numbers(t: str) -> str:
    """Spell digits as words. Observed 2026-10-29: Pocket TTS garbled raw
    digits ("2026", "3.7", "1,250", "2:30"); the same sentences with the
    numbers written as words were read correctly."""
    # Version strings: 0.6.2 -> "zero point six point two".
    t = re.sub(r"(?<![\w.])\d+(?:\.\d+){2,}(?![\w.])",
               lambda m: " point ".join(_words(int(p)) for p in m.group(0).split(".")), t)
    # Clock times: 2:30 -> "two thirty", 9:05 -> "nine oh five", 4:00 -> "four o'clock".
    def _time(m):
        h, mins = int(m.group(1)), int(m.group(2))
        if mins == 0:
            return f"{_words(h)} o'clock"
        return f"{_words(h)} {'oh ' if mins < 10 else ''}{_words(mins)}"
    t = re.sub(r"\b(\d{1,2}):([0-5]\d)\b", _time, t)
    # Ordinals: 29th -> "twenty ninth".
    t = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", lambda m: _ordinal(int(m.group(1))), t)
    # Sizes with a space before the unit: "3.7 GB" -> "3.7 gigabytes".
    t = re.sub(r"(\d)\s+(ms|kb|mb|gb|tb)\b", lambda m: f"{m.group(1)} {UNITS[m.group(2).lower()]}",
               t, flags=re.IGNORECASE)

    def _num(m):
        whole, frac, pct = m.group(1), m.group(2), m.group(3)
        n = int(whole.replace(",", ""))
        if frac is None and "," not in whole and len(whole) == 4 and 1900 <= n <= 2099:
            spoken = _year(n)
        elif len(whole) > 1 and whole.startswith("0"):
            spoken = _digits(whole)
        else:
            spoken = _words(n)
        if frac is not None:
            spoken += " point " + _digits(frac)
        return spoken + (" percent" if pct else "")
    # Letters glued to digits ("Q3", "v2") still get the digits spoken.
    return re.sub(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(%)?(?![\d])", lambda m: " " + _num(m) + " ", t)


def normalize(text: str) -> str:
    t = text

    # Strip fenced code blocks and inline code. Spoken output should never
    # contain raw code; the caller is expected to summarise, this is a backstop.
    t = re.sub(r"```.*?```", " ", t, flags=re.DOTALL)
    t = re.sub(r"`([^`]*)`", r" \1 ", t)

    # Strip markdown emphasis, headers, list bullets and link syntax.
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"(\*\*|__|\*|_)", "", t)

    # URLs become a neutral phrase rather than a spelled-out mess.
    t = re.sub(r"https?://\S+", " a link ", t)

    # CRITICAL: a double dash truncates everything after it.
    # Measured: the same line ran 4.88s with "--" and 8.56s without.
    t = re.sub(r"\s--+\s*", " ", t)
    t = re.sub(r"(?<=\s)--(?=\w)", "", t)

    # File paths. Keep the last two components so the sentence stays useful
    # but does not become a long spelled-out path.
    def _path(m):
        parts = [p for p in m.group(0).split("/") if p]
        return " ".join(parts[-2:])
    t = re.sub(r"(?:[\w.\-]+/){1,}[\w.\-]+", _path, t)

    # File extensions, after path shortening so "retry.py" is still intact.
    def _ext(m):
        return m.group(1) + " " + EXTENSIONS[m.group(2).lower()]
    t = re.sub(r"\b([\w\-]+)\.(" + "|".join(EXTENSIONS) + r")\b", _ext,
               t, flags=re.IGNORECASE)

    # Ticket keys: PROJ-1436 -> "P-R-O-J dash 1436".
    # Observed on another engine: read as "PROJ 14.36".
    t = re.sub(r"\b([A-Z]{2,6})-(\d+)\b", lambda m: f"{_spell(m.group(1))} dash {m.group(2)}", t)

    # Issue and PR numbers.
    t = re.sub(r"(?<![\w])#(\d+)", r"number \1", t)

    # Bare durations and sizes: 5s -> 5 seconds, 200ms -> 200 milliseconds.
    def _unit(m):
        return f"{m.group(1)} {UNITS[m.group(2).lower()]}"
    t = re.sub(r"\b(\d+)(ms|kb|mb|gb|tb|[smhd])\b", _unit, t)

    # "todo" was read as "toe-doe", and "to dos" as "toe-does". Observed 2026-10-29.
    t = re.sub(r"\bto-?dos\b", "to dues", t, flags=re.IGNORECASE)
    t = re.sub(r"\bto-?do\b", "to do", t, flags=re.IGNORECASE)

    t = _numbers(t)

    # Hyphenated lowercase identifiers become separate words so the engine
    # does not try to pronounce them as one invented word.
    t = re.sub(r"\b([a-z]+(?:-[a-z]+){1,})\b", lambda m: m.group(1).replace("-", " "), t)

    # Known acronyms, whole-word only, case insensitive.
    for word, spoken in ACRONYMS.items():
        t = re.sub(rf"\b{word}\b", spoken, t, flags=re.IGNORECASE)

    # Unknown short all-caps tokens get spelled out.
    t = re.sub(r"\b([A-Z]{2,5})\b",
               lambda m: _spell(m.group(1)) if "-" not in m.group(1) else m.group(1), t)

    # Leftover symbols that have no good spoken form.
    t = t.replace("->", " becomes ").replace("=>", " becomes ")
    t = re.sub(r"[|>~^{}\[\]\\]", " ", t)

    # Collapse whitespace and make sure it ends on a full stop so the engine
    # does not clip the final word.
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r" ([.,!?;:])", r"\1", t)
    if t and t[-1] not in ".!?":
        t += "."
    return t


if __name__ == "__main__":
    import sys
    print(normalize(sys.stdin.read()))
