import json
import re

STYLE_GUIDE = """Writing style rules — apply to every output:
- Use clear, simple language.
- Write in a spartan, informative style.
- Keep sentences short and direct.
- Use active voice.
- Focus on practical, actionable insights.
- Support claims with data and concrete examples.
- Avoid em dashes. Use commas or periods only.
- Avoid metaphors, cliches, generalization, rhetorical questions, setup language, warnings, notes, hashtags, markdown, asterisks, and unnecessary adjectives or adverbs.
- Avoid choppy sentence flow.
- Avoid restricted words: can, may, just, very, really, literally, actually, probably, basically, could, maybe, utilize, leverage, groundbreaking, pivotal, moreover, however, in conclusion, in summary.
- Review your response before sending. Ensure zero em dashes appear.
"""


def parse_json(raw: str, fallback: dict) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return fallback
