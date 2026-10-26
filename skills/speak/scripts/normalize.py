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


def _spell(word: str) -> str:
    return "-".join(word.upper())


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
    if t and t[-1] not in ".!?":
        t += "."
    return t


if __name__ == "__main__":
    import sys
    print(normalize(sys.stdin.read()))
