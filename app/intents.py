from __future__ import annotations

import re


WEATHER_KEYWORDS = (
    "weather",
    "forecast",
    "temperature",
    "rain",
    "snow",
    "humidity",
    "wind",
    "storm",
    "sunny",
    "cloudy",
)

LOCATION_TRAILING_STOPWORDS = {
    "today",
    "tomorrow",
    "now",
    "currently",
    "tonight",
    "this",
    "week",
    "weekend",
    "please",
}


def is_weather_query(text: str) -> bool:
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in WEATHER_KEYWORDS)


def extract_weather_location(text: str) -> str | None:
    lowered = (text or "").strip()
    if not lowered:
        return None

    patterns = [
        r"\b(?:in|at|for)\s+([a-zA-Z][a-zA-Z\s,\.-]{1,60})",
        r"\bweather\s+([a-zA-Z][a-zA-Z\s,\.-]{1,60})",
        r"\bforecast\s+([a-zA-Z][a-zA-Z\s,\.-]{1,60})",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            location = re.sub(r"\?$", "", match.group(1)).strip(" ,.-")
            parts = location.split()
            while parts and parts[-1].lower() in LOCATION_TRAILING_STOPWORDS:
                parts.pop()
            location = " ".join(parts).strip(" ,.-")
            if location:
                return location
    return None
