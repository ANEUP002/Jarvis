# =========================
# WEATHER TOOLS
# =========================

from __future__ import annotations

import os
from typing import Any, Dict

from app.event_streaming import event_stream
from app.intents import extract_weather_location
from tools.base_tool import BaseTool


WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class GetWeatherTool(BaseTool):
    name = "get_weather"
    description = "Get current weather and short forecast for a location"

    def execute(
        self,
        query: str = "",
        location: str | None = None,
        forecast_days: int = 3,
        units: str = "metric",
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            import requests

            disable_env_proxies = os.getenv("WEB_TOOLS_DISABLE_ENV_PROXIES", "true").lower() in ("1", "true", "yes")
            session = requests.Session()
            if disable_env_proxies:
                session.trust_env = False

            resolved_location = (
                (location or "").strip()
                or extract_weather_location(query)
                or os.getenv("WEATHER_DEFAULT_LOCATION", "New York")
            )
            forecast_days = max(1, min(int(forecast_days), 7))
            temperature_unit = "fahrenheit" if units.lower() in {"imperial", "f"} else "celsius"
            wind_speed_unit = "mph" if units.lower() in {"imperial", "f"} else "kmh"

            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "geocode_started",
                    "location": resolved_location,
                },
            )

            geocode_response = session.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": resolved_location, "count": 1, "language": "en", "format": "json"},
                timeout=10,
            )
            geocode_response.raise_for_status()
            geocode_data = geocode_response.json()
            results = geocode_data.get("results") or []
            if not results:
                return {
                    "success": False,
                    "result": None,
                    "error": f"Could not resolve location: {resolved_location}",
                }

            place = results[0]
            latitude = place["latitude"]
            longitude = place["longitude"]
            place_label = ", ".join(
                part for part in [place.get("name"), place.get("admin1"), place.get("country")] if part
            )

            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "forecast_started",
                    "location": place_label,
                    "latitude": latitude,
                    "longitude": longitude,
                },
            )

            weather_response = session.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": forecast_days,
                    "temperature_unit": temperature_unit,
                    "wind_speed_unit": wind_speed_unit,
                },
                timeout=10,
            )
            weather_response.raise_for_status()
            weather_data = weather_response.json()

            current = weather_data.get("current", {})
            current_units = weather_data.get("current_units", {})
            daily = weather_data.get("daily", {})

            current_code = int(current.get("weather_code", -1))
            current_desc = WEATHER_CODE_MAP.get(current_code, "Unknown conditions")
            temp_unit_label = current_units.get("temperature_2m", "C")
            wind_unit_label = current_units.get("wind_speed_10m", "km/h")

            daily_rows = []
            dates = daily.get("time", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            daily_codes = daily.get("weather_code", [])
            daily_precip = daily.get("precipitation_probability_max", [])

            for i, day in enumerate(dates):
                max_temp = max_temps[i] if i < len(max_temps) else None
                min_temp = min_temps[i] if i < len(min_temps) else None
                code = int(daily_codes[i]) if i < len(daily_codes) else -1
                precip = daily_precip[i] if i < len(daily_precip) else None
                daily_rows.append(
                    {
                        "date": day,
                        "condition": WEATHER_CODE_MAP.get(code, "Unknown"),
                        "temp_max": max_temp,
                        "temp_min": min_temp,
                        "precipitation_probability_max": precip,
                    }
                )

            # Natural-language summary suitable for speaking aloud
            _city = place.get("name") or resolved_location
            _temp = current.get("temperature_2m")
            _feels = current.get("apparent_temperature")
            _hum = current.get("relative_humidity_2m")
            _wind = current.get("wind_speed_10m")
            _unit_sym = "°C" if temperature_unit == "celsius" else "°F"

            _temp_str = f"{round(_temp)}{_unit_sym}" if _temp is not None else "unknown temperature"
            _feels_str = f"{round(_feels)}{_unit_sym}" if _feels is not None else None
            _feels_clause = f", feels like {_feels_str}" if _feels_str and abs(_temp - _feels) >= 2 else ""
            _hum_clause = f", humidity {_hum}%" if _hum is not None else ""
            _wind_clause = f", wind {round(_wind)} {wind_unit_label}" if _wind else ""

            summary = (
                f"It's {current_desc.lower()} in {_city}, "
                f"{_temp_str}{_feels_clause}{_hum_clause}{_wind_clause}."
            )

            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "forecast_completed",
                    "location": place_label,
                    "forecast_days": forecast_days,
                },
            )

            return {
                "success": True,
                "result": {
                    "location": place_label,
                    "resolved_location": resolved_location,
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": {
                        "condition": current_desc,
                        "temperature": current.get("temperature_2m"),
                        "apparent_temperature": current.get("apparent_temperature"),
                        "humidity": current.get("relative_humidity_2m"),
                        "wind_speed": current.get("wind_speed_10m"),
                    },
                    "daily": daily_rows,
                    "summary": summary,
                },
                "error": None,
            }
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}
