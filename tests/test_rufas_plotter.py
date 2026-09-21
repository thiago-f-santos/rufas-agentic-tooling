import pytest
from tools.rufas_plotter import PresetRegistry, resolve_columns_for_preset


def test_resolve_columns_executive_preset():
    mock_headers = [
        "RufasTime.simulation_day (simulation day)",
        "RufasTime.calendar_year (calendar year)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.cow_id (unitless)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.estimated_daily_milk_produced (kg/day)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.simulation_day (simulation day)",
        "AnimalModuleReporter.report_animal_population_statistics.population_number_of_cows (animals)",
        "AnimalModuleReporter.report_enteric_methane_emission.enteric_methane_emission_for_CALF_PEN_0 (g)",
        "FieldDataReporter.send_field_daily_variables.transpiration.field='field_1' (mm)",
        "FeedManager.purchase_feed.ration_interval_202_cost ($)",
        "AnimalModuleReporter.report_manure_excretions.CALF_PEN_0_manure_mass (kg)",
    ]
    resolved = resolve_columns_for_preset(mock_headers, preset="executive")
    assert "milk_produced" in resolved["panels"]
    assert resolved["panels"]["milk_produced"]["value_col"] == "AnimalModuleReporter.report_milk.milk_data_at_milk_update.estimated_daily_milk_produced (kg/day)"
    assert resolved["panels"]["milk_produced"]["time_col"] == "AnimalModuleReporter.report_milk.milk_data_at_milk_update.simulation_day (simulation day)"
    assert len(resolved["required_columns"]) > 0


def test_resolve_columns_custom_vars():
    mock_headers = ["ColA", "ColB", "RufasTime.simulation_day (simulation day)"]
    resolved = resolve_columns_for_preset(mock_headers, preset="custom", custom_vars=["ColA"])
    assert "ColA" in resolved["required_columns"]


def test_preset_registry_contains_canonical_presets():
    expected_presets = ["executive", "animal", "eee", "field-crops", "manure"]
    for p in expected_presets:
        assert p in PresetRegistry, f"Preset '{p}' not found in PresetRegistry"


def test_resolve_columns_modular_presets():
    mock_headers = [
        "RufasTime.simulation_day (simulation day)",
        "RufasTime.calendar_year (calendar year)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.cow_id (unitless)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.estimated_daily_milk_produced (kg/day)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.simulation_day (simulation day)",
        "AnimalModuleReporter.report_animal_population_statistics.population_number_of_cows (animals)",
        "AnimalModuleReporter.report_enteric_methane_emission.enteric_methane_emission_for_CALF_PEN_0 (g)",
        "FieldDataReporter.send_field_daily_variables.transpiration.field='field_1' (mm)",
        "FeedManager.purchase_feed.ration_interval_202_cost ($)",
        "AnimalModuleReporter.report_manure_excretions.CALF_PEN_0_manure_mass (kg)",
    ]
    # Test animal preset
    animal_res = resolve_columns_for_preset(mock_headers, preset="animal")
    assert "milk_produced" in animal_res["panels"]
    assert "RufasTime.simulation_day (simulation day)" in animal_res["required_columns"]

    # Test eee preset
    eee_res = resolve_columns_for_preset(mock_headers, preset="eee")
    assert "methane_emission" in eee_res["panels"] or "feed_cost" in eee_res["panels"]

    # Test field-crops preset
    field_res = resolve_columns_for_preset(mock_headers, preset="field-crops")
    assert "transpiration" in field_res["panels"]

    # Test manure preset
    manure_res = resolve_columns_for_preset(mock_headers, preset="manure")
    assert "manure_mass" in manure_res["panels"] or "manure_excretion" in manure_res["panels"]


def test_resolve_columns_missing_module_handling():
    # Only animal headers, no field or manure
    partial_headers = [
        "RufasTime.simulation_day (simulation day)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.estimated_daily_milk_produced (kg/day)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.simulation_day (simulation day)",
    ]
    resolved = resolve_columns_for_preset(partial_headers, preset="executive")
    assert "milk_produced" in resolved["panels"]
    assert resolved["panels"]["milk_produced"]["available"] is True
    # Transpiration is not present, should be marked available=False rather than crashing
    assert "transpiration" in resolved["panels"]
    assert resolved["panels"]["transpiration"]["available"] is False
    assert resolved["panels"]["transpiration"]["value_col"] is None


def test_resolve_columns_invalid_preset():
    with pytest.raises(ValueError, match="Unknown preset"):
        resolve_columns_for_preset(["ColA"], preset="non_existent_preset")


def test_custom_vars_extending_standard_preset_and_regex_resilience():
    mock_headers = [
        "RufasTime.simulation_day (simulation day)",
        "RufasTime.calendar_year (calendar year)",
        "RufasTime.day (julian day)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.cow_id (unitless)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.estimated_daily_milk_produced (kg/day)",
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.simulation_day (simulation day)",
        "Special.Module.ragged_var(foo)[bar] (kg)",
        "Special.Module.simulation_day (simulation day)",
    ]
    # Pass a raw string containing unescaped regex special chars: '(' and '['
    custom_var = "Special.Module.ragged_var(foo)[bar] (kg)"
    resolved = resolve_columns_for_preset(
        mock_headers,
        preset="executive",
        custom_vars=[custom_var],
    )
    # Check top-level time cols
    assert resolved["global_time_col"] == "RufasTime.simulation_day (simulation day)"
    assert resolved["calendar_year_col"] == "RufasTime.calendar_year (calendar year)"
    assert resolved["julian_day_col"] == "RufasTime.day (julian day)"

    # Check that custom variable was resolved
    matched_panel = None
    for p_info in resolved["panels"].values():
        if p_info.get("value_col") == custom_var:
            matched_panel = p_info
            break
    assert matched_panel is not None
    # Entity-level time column resolved for the custom variable
    assert matched_panel["time_col"] == "Special.Module.simulation_day (simulation day)"
    assert "Special.Module.simulation_day (simulation day)" in resolved["required_columns"]
    assert custom_var in resolved["required_columns"]

