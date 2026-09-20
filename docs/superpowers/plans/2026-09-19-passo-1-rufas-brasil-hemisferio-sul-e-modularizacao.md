# Suporte ao Hemisfério Sul e Modularização de País/Região (Passo 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement signed latitude for Southern Hemisphere photoperiod calculations and generalize administrative region identification (`country` and `region_code` with IBGE support and FIPS retrocompatibility) in the RuFaS simulation engine.

**Architecture:** Decouple RuFaS from US/Northern Hemisphere assumptions by passing signed latitude to solar declination daylength routines in `FieldManager`, updating `FieldData` to maintain bidirectional synchronization between `latitude` and `absolute_latitude`, and generalizing regional lookups in `EmissionsEstimator` and `LactationCurve` to support ISO 3166-1 alpha-3 country codes and flexible region codes (IBGE and FIPS).

**Tech Stack:** Python 3.12+, pytest, pytest-mock, JSON Schema.

**Spec:** [`rufas-agentic-tooling/docs/superpowers/specs/2026-09-19-passo-1-rufas-brasil-hemisferio-sul-e-modularizacao-design.md`](file:///home/thiago/Projects/rufas-agentic-tooling/docs/superpowers/specs/2026-09-19-passo-1-rufas-brasil-hemisferio-sul-e-modularizacao-design.md) (mirror: [`research/spec_passo_1_codigo_rufas_brasil.md`](file:///home/thiago/Projects/research/spec_passo_1_codigo_rufas_brasil.md))

## Global Constraints

- Preserve 100% backward compatibility with existing US scenario files (`FIPS_county_code`, `absolute_latitude`).
- Follow the RuFaS Boundary & Source of Truth Protocol: all core changes remain within `RuFaS/RUFAS/` and tests within `RuFaS/tests/`.
- No placeholders (TODO, TBD) anywhere in the implementation or tests.
- Wood lactation curve adjustments are additive (`l_param += sum(...)`), so neutral adjustments must be `{"l": 0.0, "m": 0.0, "n": 0.0}`.
- All code follows PEP 8 and passes existing linters and type checkers.

---

### Task 1: Schema Updates for Latitude and Regional Identification

**Files:**
- Modify: `RuFaS/RUFAS/input/metadata/properties/default.json:28-34,6030-6036`
- Create: `RuFaS/tests/test_metadata_schema_passo_1.py`

**Interfaces:**
- Consumes: JSON Schema in `default.json`
- Produces: Validated `latitude` (-90.0 to 90.0) in `field_properties`, `country` (3 uppercase letters) and `region_code` (positive integer) in `config_properties`.

- [ ] **Step 1: Write the failing test**

```python
# RuFaS/tests/test_metadata_schema_passo_1.py
import json
from pathlib import Path
import pytest


def test_schema_properties_passo_1():
    schema_path = Path(__file__).parent.parent / "RUFAS" / "input" / "metadata" / "properties" / "default.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # 1. Check config_properties: country and region_code
    config_props = schema["config_properties"]
    assert "country" in config_props, "country must be defined in config_properties"
    assert config_props["country"]["type"] == "string"
    assert config_props["country"]["pattern"] == "^[A-Z]{3}$"
    assert config_props["country"]["default"] == "USA"

    assert "region_code" in config_props, "region_code must be defined in config_properties"
    assert config_props["region_code"]["type"] == "number"
    assert config_props["region_code"]["minimum"] == 1

    assert "FIPS_county_code" in config_props, "FIPS_county_code must remain for retrocompatibility"

    # 2. Check field_properties: latitude
    field_props = schema["field_properties"]
    assert "latitude" in field_props, "latitude must be defined in field_properties"
    assert field_props["latitude"]["type"] == "number"
    assert field_props["latitude"]["minimum"] == -90.0
    assert field_props["latitude"]["maximum"] == 90.0
    assert field_props["latitude"]["default"] == 43.5

    assert "absolute_latitude" in field_props, "absolute_latitude must remain for retrocompatibility"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metadata_schema_passo_1.py -v` (from `/home/thiago/Projects/RuFaS`)
Expected: FAIL with `AssertionError: country must be defined in config_properties`

- [ ] **Step 3: Write minimal implementation**

In `RuFaS/RUFAS/input/metadata/properties/default.json`:
1. In `config_properties` (after line 27):
```json
    "country": {
      "type": "string",
      "description": "Three-letter country ISO code for the simulation location (e.g. 'USA', 'BRA').",
      "pattern": "^[A-Z]{3}$",
      "default": "USA"
    },
    "region_code": {
      "type": "number",
      "description": "Administrative region code (e.g. 5-digit FIPS for USA, 2-digit UF or 7-digit municipality IBGE code for Brazil).",
      "minimum": 1
    },
```
2. In `field_properties` (before line 6030 `"absolute_latitude"`):
```json
    "latitude": {
      "type": "number",
      "description": "The geographic latitude of the center of this field (degrees, negative for Southern Hemisphere).\nUnits: degrees.",
      "minimum": -90.0,
      "maximum": 90.0,
      "default": 43.5
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_metadata_schema_passo_1.py -v` (from `/home/thiago/Projects/RuFaS`)
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/thiago/Projects/RuFaS
git add RUFAS/input/metadata/properties/default.json tests/test_metadata_schema_passo_1.py
git commit -m "feat(schema): add latitude, country, and region_code to default metadata schema"
```

---

### Task 2: Field Data Latitude with Sign and Bidirectional Fallback

**Files:**
- Modify: `RuFaS/RUFAS/biophysical/field/field/field_data.py:70-76,100-115`
- Create: `RuFaS/tests/test_biophysical/test_crop_soil_field/field_tests/test_field_data.py`

**Interfaces:**
- Consumes: `latitude: float | None = None`, `absolute_latitude: float = 43.5`
- Produces: `FieldData.latitude: float` (signed), `FieldData.absolute_latitude: float` (non-negative), dormancy calculated using absolute value.

- [ ] **Step 1: Write the failing test**

```python
# RuFaS/tests/test_biophysical/test_crop_soil_field/field_tests/test_field_data.py
import pytest
from RUFAS.biophysical.field.field.field_data import FieldData


def test_field_data_southern_hemisphere_latitude():
    """Tests that negative latitude in Southern Hemisphere sets absolute_latitude and preserves latitude."""
    fd = FieldData(name="brazil_field", latitude=-22.5)
    assert fd.latitude == -22.5
    assert fd.absolute_latitude == 22.5
    assert fd.dormancy_threshold is not None


def test_field_data_legacy_absolute_latitude():
    """Tests that legacy initialization with only absolute_latitude sets latitude equal to absolute_latitude."""
    fd = FieldData(name="legacy_field", absolute_latitude=43.5)
    assert fd.latitude == 43.5
    assert fd.absolute_latitude == 43.5


def test_field_data_default_latitude():
    """Tests default latitude when neither is explicitly provided."""
    fd = FieldData(name="default_field")
    assert fd.latitude == 43.5
    assert fd.absolute_latitude == 43.5


def test_field_data_both_provided():
    """Tests that when both are provided, latitude takes precedence for sign and absolute_latitude is sanitized."""
    fd = FieldData(name="both_field", latitude=-15.78, absolute_latitude=15.78)
    assert fd.latitude == -15.78
    assert fd.absolute_latitude == 15.78
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_biophysical/test_crop_soil_field/field_tests/test_field_data.py -v` (from `/home/thiago/Projects/RuFaS`)
Expected: FAIL with `TypeError: FieldData.__init__() got an unexpected keyword argument 'latitude'`

- [ ] **Step 3: Write minimal implementation**

In `RuFaS/RUFAS/biophysical/field/field/field_data.py`:
1. Add `latitude: float | None = None` to `FieldData` attributes (around line 71):
```python
    name: str | None = None
    latitude: float | None = None
    absolute_latitude: float = 43.5
    longitude: float = -88.6
```
2. In `__post_init__` (around line 100):
```python
    def __post_init__(self) -> None:
        """
        Initialize all attributes in FieldData object that need to be set based on other FieldData attributes.

        Raises
        ------
        ValueError
            If the watering amount is < 0.
            If the watering interval is < 0.
        """
        if self.latitude is None:
            self.latitude = self.absolute_latitude
        else:
            self.absolute_latitude = abs(self.latitude)

        self.dormancy_threshold = Dormancy.find_dormancy_threshold(self.absolute_latitude)
        self.dormancy_threshold_daylength = Dormancy.find_threshold_daylength(
            self.minimum_daylength, self.dormancy_threshold
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_biophysical/test_crop_soil_field/field_tests/test_field_data.py -v` (from `/home/thiago/Projects/RuFaS`)
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/thiago/Projects/RuFaS
git add RUFAS/biophysical/field/field/field_data.py tests/test_biophysical/test_crop_soil_field/field_tests/test_field_data.py
git commit -m "feat(field): add signed latitude support and bidirectional fallback to FieldData"
```

---

### Task 3: Field Manager Latitude Propagation and Setup

**Files:**
- Modify: `RuFaS/RUFAS/biophysical/field/manager/field_manager.py:93-96,206-239`
- Modify: `RuFaS/tests/test_biophysical/test_crop_soil_field/manager_tests/test_field_manager.py:125-195`

**Interfaces:**
- Consumes: `field_configuration_data` dictionary from scenario configuration
- Produces: `weather.get_current_day_conditions(time, field.field_data.latitude)`

- [ ] **Step 1: Write the failing test**

In `RuFaS/tests/test_biophysical/test_crop_soil_field/manager_tests/test_field_manager.py`:
Add test `test_setup_field_data_signed_latitude` and `test_daily_update_routine_passes_signed_latitude`:
```python
def test_setup_field_data_signed_latitude():
    """Tests that _setup_field_data properly parses signed latitude with fallback."""
    config_southern = {
        "field_size": 2.0,
        "latitude": -22.5,
        "longitude": -45.0,
        "minimum_daylength": 10.5,
        "seasonal_high_water_table": False,
        "watering_amount_in_liters": 0.0,
        "watering_interval": 0,
        "simulate_water_stress": True,
        "simulate_temp_stress": True,
        "simulate_nitrogen_stress": True,
        "simulate_phosphorus_stress": True,
    }
    field_data = FieldManager._setup_field_data("south_field", config_southern)
    assert field_data.latitude == -22.5
    assert field_data.absolute_latitude == 22.5

    config_legacy = {
        "field_size": 2.0,
        "absolute_latitude": 43.5,
        "longitude": -89.4,
        "minimum_daylength": 9.0,
        "seasonal_high_water_table": False,
        "watering_amount_in_liters": 0.0,
        "watering_interval": 0,
        "simulate_water_stress": True,
        "simulate_temp_stress": True,
        "simulate_nitrogen_stress": True,
        "simulate_phosphorus_stress": True,
    }
    legacy_data = FieldManager._setup_field_data("legacy_field", config_legacy)
    assert legacy_data.latitude == 43.5
    assert legacy_data.absolute_latitude == 43.5


def test_daily_update_routine_passes_signed_latitude(mocker: MockerFixture):
    """Tests that daily_update_routine passes field_data.latitude (signed) to weather."""
    mock_weather = mocker.MagicMock()
    mock_time = mocker.MagicMock()
    mock_crop_factory = mocker.patch("RUFAS.biophysical.field.manager.field_manager.CropDataFactory")
    mock_crop_factory.setup_crop_configurations.return_value = None
    mock_crop_factory.get_available_crop_configurations.return_value = []

    fm = FieldManager({})
    field = mocker.MagicMock()
    field.field_data = FieldData(name="brazil_field", latitude=-22.5)
    field.manage_field.return_value = []
    fm.fields = [field]

    fm.daily_update_routine(weather=mock_weather, time=mock_time, manure_applications=[])
    mock_weather.get_current_day_conditions.assert_called_once_with(mock_time, -22.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_biophysical/test_crop_soil_field/manager_tests/test_field_manager.py -k "test_setup_field_data_signed_latitude or test_daily_update_routine_passes_signed_latitude" -v` (from `/home/thiago/Projects/RuFaS`)
Expected: FAIL (KeyError: 'absolute_latitude' in `_setup_field_data`, or call mismatch in `mock_weather.get_current_day_conditions`)

- [ ] **Step 3: Write minimal implementation**

In `RuFaS/RUFAS/biophysical/field/manager/field_manager.py`:
1. In `daily_update_routine` (around line 94):
Replace:
```python
            current_conditions = weather.get_current_day_conditions(time, field.field_data.absolute_latitude)
```
With:
```python
            current_conditions = weather.get_current_day_conditions(time, field.field_data.latitude)
```

2. In `_setup_field_data` (around line 225):
Replace:
```python
        return FieldData(
            name=field_name,
            field_size=field_configuration_data["field_size"],
            absolute_latitude=field_configuration_data["absolute_latitude"],
            longitude=field_configuration_data["longitude"],
            minimum_daylength=field_configuration_data["minimum_daylength"],
            seasonal_high_water_table=field_configuration_data["seasonal_high_water_table"],
            watering_amount_in_liters=field_configuration_data["watering_amount_in_liters"],
            watering_interval=field_configuration_data["watering_interval"],
            simulate_water_stress=field_configuration_data["simulate_water_stress"],
            simulate_temp_stress=field_configuration_data["simulate_temp_stress"],
            simulate_nitrogen_stress=field_configuration_data["simulate_nitrogen_stress"],
            simulate_phosphorus_stress=field_configuration_data["simulate_phosphorus_stress"],
        )
```
With:
```python
        latitude = field_configuration_data.get("latitude")
        absolute_latitude = field_configuration_data.get("absolute_latitude")
        if latitude is None and absolute_latitude is None:
            latitude = 43.5
            absolute_latitude = 43.5
        elif latitude is None:
            latitude = absolute_latitude
        elif absolute_latitude is None:
            absolute_latitude = abs(latitude)

        return FieldData(
            name=field_name,
            field_size=field_configuration_data["field_size"],
            latitude=latitude,
            absolute_latitude=absolute_latitude,
            longitude=field_configuration_data["longitude"],
            minimum_daylength=field_configuration_data["minimum_daylength"],
            seasonal_high_water_table=field_configuration_data["seasonal_high_water_table"],
            watering_amount_in_liters=field_configuration_data["watering_amount_in_liters"],
            watering_interval=field_configuration_data["watering_interval"],
            simulate_water_stress=field_configuration_data["simulate_water_stress"],
            simulate_temp_stress=field_configuration_data["simulate_temp_stress"],
            simulate_nitrogen_stress=field_configuration_data["simulate_nitrogen_stress"],
            simulate_phosphorus_stress=field_configuration_data["simulate_phosphorus_stress"],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_biophysical/test_crop_soil_field/manager_tests/test_field_manager.py -v` (from `/home/thiago/Projects/RuFaS`)
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/thiago/Projects/RuFaS
git add RUFAS/biophysical/field/manager/field_manager.py tests/test_biophysical/test_crop_soil_field/manager_tests/test_field_manager.py
git commit -m "feat(field): pass signed latitude to weather and support latitude in _setup_field_data"
```

---

### Task 4: Photoperiod Daylength Southern Hemisphere Verification

**Files:**
- Modify: `RuFaS/tests/test_current_day_conditions.py:70-80`
- Test: `RuFaS/tests/test_current_day_conditions.py`

**Interfaces:**
- Consumes: `CurrentDayConditions.determine_daylength(day_number, geographic_latitude, year)`
- Produces: Correct astronomical day lengths for Southern Hemisphere (Brazil) vs Northern Hemisphere (USA) at solstices.

- [ ] **Step 1: Write the failing test**

In `RuFaS/tests/test_current_day_conditions.py`:
Add parametrized test cases for Brazil (`latitude = -22.5` Coronel Pacheco / MG) and USA (`latitude = 42.4` Madison / WI) to `test_determine_daylength` (or a dedicated test function `test_determine_daylength_hemispheres`):
```python
@pytest.mark.parametrize(
    "day_number,geographic_latitude,expected_min,expected_max,description",
    [
        # Northern Hemisphere (Madison, WI: lat +42.4)
        (172, 42.4, 15.0, 16.0, "Madison Summer Solstice (June) - daylength > 15h"),
        (355, 42.4, 8.5, 9.5, "Madison Winter Solstice (December) - daylength < 9.5h"),
        # Southern Hemisphere (Minas Gerais, Brazil: lat -22.5)
        (172, -22.5, 10.0, 11.0, "Brazil Winter Solstice (June) - daylength < 11.0h"),
        (355, -22.5, 13.0, 14.0, "Brazil Summer Solstice (December) - daylength > 13.0h"),
    ],
)
def test_determine_daylength_hemispheres(
    day_number: int,
    geographic_latitude: float,
    expected_min: float,
    expected_max: float,
    description: str,
) -> None:
    """Verifies that signed latitude correctly flips the seasons between North and South hemispheres."""
    daylength = CurrentDayConditions.determine_daylength(day_number, geographic_latitude, 2024)
    assert expected_min <= daylength <= expected_max, (
        f"Failed for {description}: got {daylength}h, expected between {expected_min}h and {expected_max}h"
    )
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_current_day_conditions.py -k "test_determine_daylength_hemispheres" -v` (from `/home/thiago/Projects/RuFaS`)
Expected: PASS (demonstrates that `CurrentDayConditions.determine_daylength` already handles signed latitude properly when supplied from `field_manager.py`).

- [ ] **Step 3: Commit**

```bash
cd /home/thiago/Projects/RuFaS
git add tests/test_current_day_conditions.py
git commit -m "test(weather): add photoperiod hemisphere solstice verification tests"
```

---

### Task 5: Generalization of Country and Region in Purchased Feed Emissions

**Files:**
- Modify: `RuFaS/RUFAS/EEE/emissions.py:141-151,255-290`
- Modify: `RuFaS/tests/test_EEE/test_emissions.py:385-420`

**Interfaces:**
- Consumes: `config.country` (defaults to "USA"), `config.region_code` or `config.FIPS_county_code`
- Produces: `self.purchased_feed_emissions_by_location` and `self.land_use_change_emissions_by_location` retrieved by `region_code` (or legacy `county_code`).

- [ ] **Step 1: Write the failing test**

In `RuFaS/tests/test_EEE/test_emissions.py`:
Add test cases for:
1. `_get_feed_emissions_data` with `"region_code"` column key instead of `"county_code"`.
2. `EmissionsEstimator.__init__` reading `config.region_code` and fallback to `config.FIPS_county_code`.
```python
def test_get_feed_emissions_data_with_region_code(em: EmissionsEstimator):
    """Tests that _get_feed_emissions_data supports region_code as well as county_code."""
    feed_data_brazil = {
        "region_code": [3106200, 3550308],
        "data1": [1.5, 2.5],
        "data2": [10.0, 20.0],
    }
    result = em._get_feed_emissions_data(3106200, feed_data_brazil)
    assert result == {"data1": 1.5, "data2": 10.0}


def test_emissions_estimator_init_region_code_fallback(mocker: MockerFixture):
    """Tests that EmissionsEstimator resolves region_code from config.region_code or fallback to config.FIPS_county_code."""
    mock_im = mocker.MagicMock()
    mocker.patch("RUFAS.EEE.emissions.InputManager", return_value=mock_im)
    mocker.patch("RUFAS.EEE.emissions.OutputManager")
    mocker.patch.object(EmissionsEstimator, "_get_feed_emissions_data", return_value={})

    # Case A: region_code provided
    mock_im.get_data.side_effect = lambda key, required=True: {
        "config.country": "BRA",
        "config.region_code": 3106200,
        "config.FIPS_county_code": None,
        "purchased_feeds_emissions": {},
        "purchased_feed_land_use_change_emissions": {},
    }.get(key)

    estimator_bra = EmissionsEstimator(False, False, False, False)
    assert estimator_bra._get_feed_emissions_data.call_args_list[0][0][0] == 3106200

    # Case B: legacy FIPS_county_code provided
    mock_im.get_data.side_effect = lambda key, required=True: {
        "config.country": None,
        "config.region_code": None,
        "config.FIPS_county_code": 55025,
        "purchased_feeds_emissions": {},
        "purchased_feed_land_use_change_emissions": {},
    }.get(key)

    estimator_legacy = EmissionsEstimator(False, False, False, False)
    assert estimator_legacy._get_feed_emissions_data.call_args_list[2][0][0] == 55025
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_EEE/test_emissions.py -k "test_get_feed_emissions_data_with_region_code or test_emissions_estimator_init_region_code_fallback" -v` (from `/home/thiago/Projects/RuFaS`)
Expected: FAIL with `KeyError: 'county_code'` in `_get_feed_emissions_data`

- [ ] **Step 3: Write minimal implementation**

In `RuFaS/RUFAS/EEE/emissions.py`:
1. In `EmissionsEstimator.__init__` (around line 141):
Replace:
```python
        county_code = self.im.get_data("config.FIPS_county_code")

        purchased_feed_emissions_data = self.im.get_data("purchased_feeds_emissions")
        self.purchased_feed_emissions_by_location = self._get_feed_emissions_data(
            county_code, purchased_feed_emissions_data
        )

        land_use_change_emissions_data = self.im.get_data("purchased_feed_land_use_change_emissions")
        self.land_use_change_emissions_by_location = self._get_feed_emissions_data(
            county_code, land_use_change_emissions_data
        )
```
With:
```python
        country = self.im.get_data("config.country", required=False) or "USA"
        region_code = self.im.get_data("config.region_code", required=False)
        if region_code is None:
            region_code = self.im.get_data("config.FIPS_county_code", required=False)

        purchased_feed_emissions_data = self.im.get_data("purchased_feeds_emissions")
        self.purchased_feed_emissions_by_location = self._get_feed_emissions_data(
            region_code, purchased_feed_emissions_data
        )

        land_use_change_emissions_data = self.im.get_data("purchased_feed_land_use_change_emissions")
        self.land_use_change_emissions_by_location = self._get_feed_emissions_data(
            region_code, land_use_change_emissions_data
        )
```

2. In `_get_feed_emissions_data` (around lines 255-290):
Replace:
```python
    def _get_feed_emissions_data(
        self, county_code: int, feed_emissions_data: dict[str, list[float]]
    ) -> dict[str, float]:
...
        county_codes = feed_emissions_data["county_code"]
        try:
            emissions_index = county_codes.index(county_code)
        except ValueError:
            info_map = {
                "class": self.__class__.__name__,
                "function": self._get_feed_emissions_data.__name__,
            }
            self.om.add_error(
                "Invalid country code access.",
                f"Emission data have county codes {county_codes}," f"Tried to get data with county code: {county_code}",
                info_map,
            )
            raise
```
With:
```python
    def _get_feed_emissions_data(
        self, region_code: int, feed_emissions_data: dict[str, list[float]]
    ) -> dict[str, float]:
        """
        Grabs the appropriate emissions factors for purchased feeds for the location of the simulation.

        Parameters
        ----------
        region_code : int
            The administrative region code (FIPS county code or IBGE code) of the simulation location.
        feed_emissions_data : dict[str, list[float]]
            A mapping of RuFaS feed IDs to their emissions factors per region, including a ``"region_code"``
            or ``"county_code"`` key listing the codes in the same order as the factors.

        Returns
        -------
        dict[str, float]
            A mapping of RuFaS feed IDs to their emissions factors for the simulation's region.

        Raises
        ------
        ValueError
            If the simulation's region code is not present in ``feed_emissions_data``.
        """
        code_column_key = "region_code" if "region_code" in feed_emissions_data else "county_code"
        region_codes = feed_emissions_data[code_column_key]
        try:
            emissions_index = region_codes.index(region_code)
        except ValueError:
            info_map = {
                "class": self.__class__.__name__,
                "function": self._get_feed_emissions_data.__name__,
            }
            self.om.add_error(
                "Invalid country code access.",
                f"Emission data have {code_column_key}s {region_codes}," f"Tried to get data with {code_column_key}: {region_code}",
                info_map,
            )
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_EEE/test_emissions.py -v` (from `/home/thiago/Projects/RuFaS`)
Expected: PASS (all existing and new tests pass)

- [ ] **Step 5: Commit**

```bash
cd /home/thiago/Projects/RuFaS
git add RUFAS/EEE/emissions.py tests/test_EEE/test_emissions.py
git commit -m "feat(eee): support region_code and country with legacy fallback in emissions"
```

---

### Task 6: Generalization of Country and Region in Lactation Curve

**Files:**
- Modify: `RuFaS/RUFAS/biophysical/animal/milk/lactation_curve.py:90-94,168-177`
- Modify: `RuFaS/tests/test_biophysical/test_animal/test_milk_production/test_lactation_curve.py:243-263`

**Interfaces:**
- Consumes: `lactation_inputs["adjustments"]["region"]`, `lactation_inputs["state_to_region_mapping"]`, `region_code: int | None`, `country: str = "USA"`
- Produces: Additive Wood lactation adjustments `{"l": float, "m": float, "n": float}`, with neutral fallback `{"l": 0.0, "m": 0.0, "n": 0.0}`.

- [ ] **Step 1: Write the failing test**

In `RuFaS/tests/test_biophysical/test_animal/test_milk_production/test_lactation_curve.py`:
Add test cases for `_get_region_adjustments` with `country="BRA"`, unknown region, and `country="USA"`:
```python
def test_get_region_adjustments_brazil(lactation_inputs: dict[str, Any]) -> None:
    """Test region adjustments for Brazilian IBGE codes with neutral fallback and region mapping."""
    all_region_adjustments = {
        "southeast": {"l": 0.5, "m": -0.2, "n": -0.1},
    }
    brazil_mapping = {
        "31": "southeast",  # Minas Gerais
        "35": "southeast",  # São Paulo
    }

    # Case 1: 7-digit municipality code for MG (Coronel Pacheco: 3120508)
    adj_mg = LactationCurve._get_region_adjustments(
        all_region_adjustments, brazil_mapping, 3120508, country="BRA"
    )
    assert adj_mg == {"l": 0.5, "m": -0.2, "n": -0.1}

    # Case 2: 2-digit state code for SP (35)
    adj_sp = LactationCurve._get_region_adjustments(
        all_region_adjustments, brazil_mapping, 35, country="BRA"
    )
    assert adj_sp == {"l": 0.5, "m": -0.2, "n": -0.1}

    # Case 3: Unmapped state code -> neutral adjustments
    adj_unknown = LactationCurve._get_region_adjustments(
        all_region_adjustments, brazil_mapping, 12, country="BRA"
    )
    assert adj_unknown == {"l": 0.0, "m": 0.0, "n": 0.0}

    # Case 4: None region_code -> neutral adjustments
    adj_none = LactationCurve._get_region_adjustments(
        all_region_adjustments, brazil_mapping, None, country="BRA"
    )
    assert adj_none == {"l": 0.0, "m": 0.0, "n": 0.0}


def test_set_lactation_parameters_region_code_fallback(mocker: MockerFixture) -> None:
    """Tests set_lactation_parameters reads country and region_code with fallback to FIPS_county_code."""
    mock_im = mocker.patch("RUFAS.biophysical.animal.milk.lactation_curve.InputManager").return_value
    mock_time = mocker.MagicMock()

    mock_lactation_inputs = {
        "adjustments": {
            "year": {"2024": {"l": 0.0, "m": 0.0, "n": 0.0}},
            "region": {"southeast": {"l": 0.5, "m": -0.2, "n": -0.1}},
            "milking_frequency": {"twice_daily": {"l": 0.0, "m": 0.0, "n": 0.0}},
            "parity": {"1": {"l": 0.0, "m": 0.0, "n": 0.0}},
        },
        "state_to_region_mapping": {"31": "southeast"},
        "parameter_mean_values": {"parameter_l_mean": 10.0, "parameter_m_mean": 0.2, "parameter_n_mean": 0.05},
        "parameter_standard_deviations": {
            "1": {"parameter_l_std_dev": 0.1, "parameter_m_std_dev": 0.01, "parameter_n_std_dev": 0.001},
            "2": {"parameter_l_std_dev": 0.1, "parameter_m_std_dev": 0.01, "parameter_n_std_dev": 0.001},
            "3": {"parameter_l_std_dev": 0.1, "parameter_m_std_dev": 0.01, "parameter_n_std_dev": 0.001},
        },
    }
    mock_animal_inputs = {
        "animal_config": {"management_decisions": {"cow_times_milked_per_day": 2.0}},
        "herd_information": {"annual_milk_yield": None},
    }

    mock_im.get_data.side_effect = lambda key, required=True: {
        "lactation": mock_lactation_inputs,
        "config.country": "BRA",
        "config.region_code": 3120508,
        "config.FIPS_county_code": None,
        "animal": mock_animal_inputs,
    }.get(key)

    mock_get_adj = mocker.patch.object(LactationCurve, "_get_region_adjustments", wraps=LactationCurve._get_region_adjustments)
    LactationCurve.set_lactation_parameters(mock_time)
    mock_get_adj.assert_called_once_with(
        mock_lactation_inputs["adjustments"]["region"],
        mock_lactation_inputs["state_to_region_mapping"],
        3120508,
        "BRA",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_biophysical/test_animal/test_milk_production/test_lactation_curve.py -k "test_get_region_adjustments_brazil or test_set_lactation_parameters_region_code_fallback" -v` (from `/home/thiago/Projects/RuFaS`)
Expected: FAIL (argument count mismatch or missing country handling)

- [ ] **Step 3: Write minimal implementation**

In `RuFaS/RUFAS/biophysical/animal/milk/lactation_curve.py`:
1. In `set_lactation_parameters` (around lines 90-94):
Replace:
```python
        fips_code: int = im.get_data("config.FIPS_county_code")
        all_region_adjustments: dict[str, dict[str, float]] = lactation_inputs["adjustments"]["region"]
        region_mapping: dict[str, str] = lactation_inputs["state_to_region_mapping"]
        region_adjustments = cls._get_region_adjustments(all_region_adjustments, region_mapping, fips_code)
```
With:
```python
        country = im.get_data("config.country", required=False) or "USA"
        region_code = im.get_data("config.region_code", required=False)
        if region_code is None:
            region_code = im.get_data("config.FIPS_county_code", required=False)

        all_region_adjustments: dict[str, dict[str, float]] = lactation_inputs["adjustments"]["region"]
        region_mapping: dict[str, str] = lactation_inputs.get("state_to_region_mapping", {})
        region_adjustments = cls._get_region_adjustments(
            all_region_adjustments, region_mapping, region_code, country
        )
```

2. In `_get_region_adjustments` (around lines 168-177):
Replace:
```python
    @classmethod
    def _get_region_adjustments(
        cls, region_adjustment_values: dict[str, dict[str, float]], region_mapping: dict[str, str], fips_code: int
    ) -> dict[str, float]:
        """Retrieves the appropriate adjustment values for the region being simulated."""
        state_fips_code = int(fips_code / 1000)

        region = region_mapping[str(state_fips_code)]

        return region_adjustment_values[region]
```
With:
```python
    @classmethod
    def _get_region_adjustments(
        cls,
        region_adjustment_values: dict[str, dict[str, float]],
        region_mapping: dict[str, str],
        region_code: int | None,
        country: str = "USA",
    ) -> dict[str, float]:
        """
        Retrieves the appropriate adjustment values for the region being simulated.

        Parameters
        ----------
        region_adjustment_values : dict[str, dict[str, float]]
            Mapping of region names to Wood curve parameter adjustments (l, m, n).
        region_mapping : dict[str, str]
            Mapping of state or UF codes to region names.
        region_code : int | None
            Administrative region code (FIPS county code or IBGE municipality/state code).
        country : str, default="USA"
            Three-letter ISO country code.

        Returns
        -------
        dict[str, float]
            Additive Wood parameter adjustments {"l": float, "m": float, "n": float}.
        """
        neutral_adjustments = {"l": 0.0, "m": 0.0, "n": 0.0}
        if region_code is None:
            return neutral_adjustments

        if country == "USA":
            state_fips_code = int(region_code / 1000)
            region = region_mapping.get(str(state_fips_code))
            if region and region in region_adjustment_values:
                return region_adjustment_values[region]
            return neutral_adjustments
        elif country == "BRA":
            code_str = str(region_code)
            state_ibge_code = int(code_str[:2]) if len(code_str) >= 2 else region_code
            region = region_mapping.get(str(state_ibge_code))
            if region and region in region_adjustment_values:
                return region_adjustment_values[region]
            return neutral_adjustments
        else:
            return neutral_adjustments
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_biophysical/test_animal/test_milk_production/test_lactation_curve.py -v` (from `/home/thiago/Projects/RuFaS`)
Expected: PASS (all existing and new tests pass)

- [ ] **Step 5: Commit**

```bash
cd /home/thiago/Projects/RuFaS
git add RUFAS/biophysical/animal/milk/lactation_curve.py tests/test_biophysical/test_animal/test_milk_production/test_lactation_curve.py
git commit -m "feat(animal): generalize lactation curve region adjustments with IBGE and neutral fallback"
```

---

### Task 7: User Usage Documentation for RuFaS Brasil

**Files:**
- Create: `RuFaS/docs/usage_brasil.md`
- Modify: `RuFaS/README.md:57-60`

**Interfaces:**
- Consumes: Technical specifications from Passo 1 (`latitude`, `country`, `region_code`, IBGE mappings)
- Produces: Comprehensive user guide in Portuguese (PT-BR) for researchers and practitioners, referenced in the main `README.md`.

- [ ] **Step 1: Write the user documentation**

Create `RuFaS/docs/usage_brasil.md` detailing:
- Negative latitude setup in `field_properties` (`latitude: -22.53`).
- Automatic synchronization with `absolute_latitude`.
- Sazonalidade climática e fotoperíodo astronômico no Hemisfério Sul.
- Regional modularization in `config_properties` (`country: "BRA"`, `region_code` with IBGE codes).
- Additive neutral adjustments in Wood lactation curve and purchased feed emissions.
- Step-by-step CLI simulation guide and output checking.

- [ ] **Step 2: Reference the guide in RuFaS README.md**

In `RuFaS/README.md` (Getting Started section):
```markdown
7. **RuFaS Brasil (Hemisfério Sul e Regionalização)** - Consulte o [Guia de Uso do RuFaS Brasil](docs/usage_brasil.md) para detalhes sobre configuração de latitude negativa, códigos IBGE e parametrização nacional.
```

- [ ] **Step 3: Verify markdown formatting and file links**

Verify that `RuFaS/docs/usage_brasil.md` is valid markdown and links resolve.

- [ ] **Step 4: Commit**

```bash
cd /home/thiago/Projects/RuFaS
git add docs/usage_brasil.md README.md
git commit -m "docs: add RuFaS Brasil usage guide in docs/usage_brasil.md and reference in README.md"
```

---

### Task 8: Whole-System Integration and Regression Suite

**Files:**
- Test: All affected test suites across weather, field, EEE, animal lactation, and metadata schema.

- [ ] **Step 1: Run comprehensive regression test suite**

Run:
```bash
cd /home/thiago/Projects/RuFaS
pytest \
  tests/test_metadata_schema_passo_1.py \
  tests/test_current_day_conditions.py \
  tests/test_weather.py \
  tests/test_biophysical/test_crop_soil_field/field_tests/test_field_data.py \
  tests/test_biophysical/test_crop_soil_field/manager_tests/test_field_manager.py \
  tests/test_EEE/test_emissions.py \
  tests/test_biophysical/test_animal/test_milk_production/test_lactation_curve.py \
  -v
```
Expected: 100% PASS across all suites without regressions.

- [ ] **Step 2: Commit any remaining adjustments**

```bash
cd /home/thiago/Projects/RuFaS
git status
# If clean, proceed to completion.
```
