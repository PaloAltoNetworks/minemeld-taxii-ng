import re

STIX2_SIMPLE_PATTERN = re.compile(
    "\[\s*([a-zA-Z_][a-zA-Z0-9_-]*):([a-zA-Z_][a-zA-Z0-9_]*)(\.[a-zA-Z_][a-zA-Z0-9_]*)+\s*=\s*'([^']*)'\]"
)

def convert_pattern(pattern):
    match = STIX2_SIMPLE_PATTERN.match(pattern)
    if match is None:
        return []

    