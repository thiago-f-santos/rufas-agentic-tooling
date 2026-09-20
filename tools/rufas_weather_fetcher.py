"""
RuFaS Weather Fetcher & Generator for Patos de Minas, MG.

Fetches daily weather data from NASA POWER API (daily point, community=AG)
or provides a climatologically calibrated synthetic fallback time series
for the Cerrado region (lat -18.5789, lon -46.5181, 2021-2022).
"""

import argparse
import datetime
import json
import logging
from pathlib import Path
from typing import Optional, Union
import urllib.request

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PATOS_DE_MINAS_LAT = -18.5789
PATOS_DE_MINAS_LON = -46.5181
START_YEAR = 2021
END_YEAR = 2022
START_DATE = "20210101"
END_DATE = "20221231"

NASA_POWER_URL_TEMPLATE = (
    "https://power.larc.nasa.gov/api/temporal/daily/point?"
    "parameters=T2M_MAX,T2M_MIN,T2M,PRECTOTCORR,ALLSKY_SFC_SW_DWN"
    "&community=AG&longitude={lon}&latitude={lat}&start={start}&end={end}&format=JSON"
)

WEATHER_COLUMNS = ["year", "jday", "precip", "high", "low", "avg", "Hday", "irrigation"]


def fetch_nasa_power_weather(
    lat: float = PATOS_DE_MINAS_LAT,
    lon: float = PATOS_DE_MINAS_LON,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    timeout: int = 15,
) -> Optional[pd.DataFrame]:
    """
    Fetch daily weather data from NASA POWER API for the given coordinates and date range.

    Parameters
    ----------
    lat : float
        Latitude in decimal degrees.
    lon : float
        Longitude in decimal degrees.
    start_date : str
        Start date formatted as YYYYMMDD.
    end_date : str
        End date formatted as YYYYMMDD.
    timeout : int, default 15
        Request timeout in seconds.

    Returns
    -------
    pd.DataFrame or None
        DataFrame containing weather records if successful, None otherwise.
    """
    url = NASA_POWER_URL_TEMPLATE.format(lon=lon, lat=lat, start=start_date, end=end_date)
    req = urllib.request.Request(url, headers={"User-Agent": "RuFaS-Weather-Fetcher/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning(f"Failed to fetch data from NASA POWER API: {exc}")
        return None

    try:
        params = data.get("properties", {}).get("parameter", {})
        t2m_max = params.get("T2M_MAX", {})
        t2m_min = params.get("T2M_MIN", {})
        t2m = params.get("T2M", {})
        prectotcorr = params.get("PRECTOTCORR", {})
        allsky = params.get("ALLSKY_SFC_SW_DWN", {})

        dates = sorted(t2m.keys())
        if len(dates) != 730:
            logger.warning(f"Unexpected date count from NASA POWER API: {len(dates)} (expected 730)")
            return None

        records = []
        for d in dates:
            dt = datetime.datetime.strptime(d, "%Y%m%d")
            year = dt.year
            jday = dt.timetuple().tm_yday

            high = float(t2m_max[d])
            low = float(t2m_min[d])
            avg = float(t2m[d])
            precip = max(0.0, float(prectotcorr[d]))
            hday = max(0.0, float(allsky[d]))

            # Missing value check (NASA POWER uses -999 for missing values)
            if any(v < -50 for v in (high, low, avg, precip, hday)):
                logger.warning(f"Missing/invalid data value detected on {d}")
                return None

            # Enforce physical consistency
            if high < avg:
                high = avg
            if avg < low:
                low = avg
            if high < low:
                high = low

            records.append({
                "year": year,
                "jday": jday,
                "precip": round(precip, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "avg": round(avg, 2),
                "Hday": round(hday, 2),
                "irrigation": 0.0,
            })

        df = pd.DataFrame(records)[WEATHER_COLUMNS]
        return df
    except Exception as exc:
        logger.warning(f"Error processing NASA POWER API response: {exc}")
        return None


def generate_synthetic_patos_de_minas_weather(seed: int = 42) -> pd.DataFrame:
    """
    Generate a climatologically calibrated synthetic weather series for Patos de Minas, MG (2021-2022).

    Patos de Minas characteristics:
    - Elevation ~830m, Köppen Aw/Cwa tropical wet-and-dry climate
    - Rainy summer (Nov-Mar), dry winter (May-Aug)
    - Mean annual precipitation: ~1100 - 1600 mm
    - Temperatures: Highs 25-33°C, Lows 11-20°C, Avg 18-25°C
    - Solar radiation Hday: ~14-25 MJ/m²

    Parameters
    ----------
    seed : int, default 42
        Random number generator seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        730-day weather DataFrame conforming to RuFaS requirements.
    """
    rng = np.random.default_rng(seed)
    records = []
    for year in [2021, 2022]:
        for jday in range(1, 366):
            # Phase: Day 15 = mid Jan (peak summer), Day 197 = mid July (peak winter)
            solar_base = 21.0 - 3.5 * np.cos(2 * np.pi * (jday - 15) / 365.0)
            temp_base = 22.0 + 2.5 * np.cos(2 * np.pi * (jday - 15) / 365.0)
            diurnal_range = 11.0 + 2.5 * np.cos(2 * np.pi * (jday - 197) / 365.0)

            # Rainy season probability (high Nov-Mar, dry May-Aug)
            if 120 <= jday <= 245:  # May through Aug
                rain_prob = 0.03
                rain_scale = 5.0
            else:
                rain_prob = 0.48 * np.maximum(0.0, np.cos(2 * np.pi * (jday - 15) / 365.0)) ** 1.2 + 0.08
                rain_scale = 13.0

            is_rain = rng.random() < rain_prob
            if is_rain:
                precip = float(np.round(rng.exponential(scale=rain_scale) + 0.5, 1))
                solar_attenuation = np.clip(1.0 - (precip / 40.0) * 0.5, 0.45, 0.9)
            else:
                precip = 0.0
                solar_attenuation = 1.0 + rng.uniform(-0.08, 0.08)

            hday = float(np.round(np.clip(solar_base * solar_attenuation + rng.normal(0, 0.8), 5.0, 28.0), 2))

            t_noise = rng.normal(0, 0.9)
            t_drop = 1.8 if precip > 10.0 else (0.8 if precip > 2.0 else 0.0)
            avg_temp = float(np.round(temp_base + t_noise - t_drop, 2))

            d_range = max(4.0, diurnal_range + rng.normal(0, 0.8) - (3.5 if precip > 5.0 else 0.0))
            high_temp = float(np.round(avg_temp + d_range * 0.55, 2))
            low_temp = float(np.round(avg_temp - d_range * 0.45, 2))

            # Enforce physical constraints
            if high_temp < avg_temp:
                high_temp = avg_temp + 0.1
            if low_temp > avg_temp:
                low_temp = avg_temp - 0.1

            records.append({
                "year": year,
                "jday": jday,
                "precip": precip,
                "high": high_temp,
                "low": low_temp,
                "avg": avg_temp,
                "Hday": hday,
                "irrigation": 0.0,
            })

    return pd.DataFrame(records)[WEATHER_COLUMNS]


def generate_patos_de_minas_weather(
    output_path: Optional[Union[str, Path]] = None,
    use_api: bool = True,
    timeout: int = 15,
) -> pd.DataFrame:
    """
    Generate or fetch weather dataset for Patos de Minas, MG for 2021-2022 (730 days).

    Parameters
    ----------
    output_path : Path or str, optional
        Target CSV file path to save the generated weather dataset.
    use_api : bool, default True
        Whether to attempt fetching data from NASA POWER API first.
    timeout : int, default 15
        HTTP request timeout in seconds.

    Returns
    -------
    pd.DataFrame
        DataFrame with 730 rows and columns:
        ['year', 'jday', 'precip', 'high', 'low', 'avg', 'Hday', 'irrigation']
    """
    df = None
    if use_api:
        logger.info("Attempting to fetch weather data from NASA POWER API...")
        df = fetch_nasa_power_weather(timeout=timeout)
        if df is not None:
            logger.info("Successfully fetched weather data from NASA POWER API.")

    if df is None:
        if use_api:
            logger.warning("NASA POWER API unavailable or timed out; falling back to calibrated synthetic series.")
        else:
            logger.info("Using calibrated synthetic weather series for Patos de Minas (use_api=False).")
        df = generate_synthetic_patos_de_minas_weather()

    # Validation
    if len(df) != 730:
        raise ValueError(f"Expected 730 weather rows, got {len(df)}")
    if list(df.columns) != WEATHER_COLUMNS:
        raise ValueError(f"Columns mismatch: expected {WEATHER_COLUMNS}, got {list(df.columns)}")

    # Enforce constraints
    if not (df["high"] >= df["avg"]).all():
        raise ValueError("Constraint violated: high < avg")
    if not (df["avg"] >= df["low"]).all():
        raise ValueError("Constraint violated: avg < low")
    if not (df["precip"] >= 0.0).all():
        raise ValueError("Constraint violated: precip < 0")
    if not (df["Hday"] >= 0.0).all():
        raise ValueError("Constraint violated: Hday < 0")
    if not (df["irrigation"] == 0.0).all():
        raise ValueError("Constraint violated: irrigation != 0.0")

    if output_path is not None:
        target_file = Path(output_path)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(target_file, index=False)
        logger.info(f"Saved weather dataset to {target_file}")

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="RuFaS Weather Fetcher & Generator for Patos de Minas, MG")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Path to output CSV file (e.g. ../RuFaS/input/data/weather/weather_minas_gerais.csv)",
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Disable NASA POWER API and force calibrated synthetic weather generation",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="API request timeout in seconds (default: 15)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    use_api = not args.no_api
    df = generate_patos_de_minas_weather(output_path=args.output, use_api=use_api, timeout=args.timeout)
    print(f"Generated {len(df)} weather records successfully.")
    if args.output:
        print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()
