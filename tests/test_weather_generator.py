import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd

from tools.rufas_weather_fetcher import (
    generate_patos_de_minas_weather,
    fetch_nasa_power_weather,
    generate_synthetic_patos_de_minas_weather,
)


class TestWeatherGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_csv = Path(self.temp_dir.name) / "test_weather_mg.csv"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_generate_weather_file_synthetic(self):
        """Test generating synthetic weather data for Patos de Minas."""
        generate_patos_de_minas_weather(self.output_csv, use_api=False)
        self.assertTrue(self.output_csv.exists())

        df = pd.read_csv(self.output_csv)
        self.assertEqual(len(df), 730)  # 365 days * 2 years (2021, 2022)

        expected_cols = ["year", "jday", "precip", "high", "low", "avg", "Hday", "irrigation"]
        self.assertListEqual(list(df.columns), expected_cols)

        # Check year and jday sequences
        years = df["year"].unique()
        self.assertListEqual(sorted(list(years)), [2021, 2022])
        self.assertListEqual(list(df[df["year"] == 2021]["jday"]), list(range(1, 366)))
        self.assertListEqual(list(df[df["year"] == 2022]["jday"]), list(range(1, 366)))

        # Check physical constraints
        self.assertTrue((df["high"] >= df["avg"]).all(), "high must be >= avg")
        self.assertTrue((df["avg"] >= df["low"]).all(), "avg must be >= low")
        self.assertTrue((df["precip"] >= 0.0).all(), "precip must be >= 0.0")
        self.assertTrue((df["Hday"] >= 0.0).all(), "Hday must be >= 0.0")
        self.assertTrue((df["irrigation"] == 0.0).all(), "irrigation must be == 0.0")

        # Check annual rainfall is realistic for Cerrado (~1100-1600 mm/year)
        annual_rain = df.groupby("year")["precip"].sum()
        for yr, rain in annual_rain.items():
            self.assertGreater(rain, 900, f"Annual rainfall for {yr} ({rain:.1f} mm) too low for Cerrado")
            self.assertLess(rain, 1800, f"Annual rainfall for {yr} ({rain:.1f} mm) too high for Cerrado")

        # Check seasonality: rainy season (Nov-Mar) vs dry season (May-Aug)
        # Rainy season: days 1..90 and 305..365 (approx 150 days)
        # Dry season: days 121..243 (approx 123 days)
        rainy_season = df[(df["jday"] <= 90) | (df["jday"] >= 305)]
        dry_season = df[(df["jday"] >= 121) & (df["jday"] <= 243)]

        self.assertGreater(
            rainy_season["precip"].mean(),
            dry_season["precip"].mean() * 3,
            "Rainy season daily precip should be much higher than dry season",
        )

    def test_api_fallback_on_network_failure(self):
        """Test that generator gracefully falls back to calibrated synthetic series on network error."""
        with patch("urllib.request.urlopen", side_effect=Exception("Connection timed out")):
            df = generate_patos_de_minas_weather(self.output_csv, use_api=True)
            self.assertTrue(self.output_csv.exists())
            self.assertEqual(len(df), 730)
            self.assertTrue((df["high"] >= df["avg"]).all())
            self.assertTrue((df["avg"] >= df["low"]).all())

    def test_api_fetch_data_structure(self):
        """Test NASA POWER API fetcher output validity when enabled."""
        df = fetch_nasa_power_weather()
        if df is not None:
            self.assertEqual(len(df), 730)
            expected_cols = ["year", "jday", "precip", "high", "low", "avg", "Hday", "irrigation"]
            self.assertListEqual(list(df.columns), expected_cols)
            self.assertTrue((df["high"] >= df["avg"]).all())
            self.assertTrue((df["avg"] >= df["low"]).all())
            self.assertTrue((df["precip"] >= 0.0).all())
            self.assertTrue((df["Hday"] >= 0.0).all())


if __name__ == "__main__":
    unittest.main()
