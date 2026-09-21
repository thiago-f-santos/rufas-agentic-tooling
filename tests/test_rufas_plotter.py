import numpy as np
import pandas as pd
import pytest
from tools.config import RuFaSBoundaryError
from tools.rufas_plotter import (
    AlignedSimulationData,
    MatplotlibRenderer,
    PresetRegistry,
    RaggedTimeSeriesLoader,
    ScenarioComparator,
    ScenarioComparisonResult,
    ScenarioDelta,
    TemporalAligner,
    resolve_columns_for_preset,
)
from PIL import Image



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


def test_temporal_aligner_ragged_data(tmp_path):
    # Simula tabela heterogenea: 3 dias, 2 vacas por dia
    csv_file = tmp_path / "ragged_sim.csv"
    data = {
        "RufasTime.simulation_day (simulation day)": [0.0, 1.0, 2.0, np.nan, np.nan, np.nan],
        "RufasTime.calendar_year (calendar year)": [2026.0, 2026.0, 2026.0, np.nan, np.nan, np.nan],
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.simulation_day (simulation day)": [0.0, 0.0, 1.0, 1.0, 2.0, 2.0],
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.cow_id (unitless)": [101, 102, 101, 102, 101, 102],
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.estimated_daily_milk_produced (kg/day)": [30.0, 25.0, 32.0, 26.0, 31.0, 24.0],
        "FieldDataReporter.send_field_daily_variables.transpiration.field='field_1' (mm)": [4.5, 5.0, 3.8, np.nan, np.nan, np.nan],
    }
    pd.DataFrame(data).to_csv(csv_file, index=False)

    aligner = TemporalAligner(csv_file, preset="executive", allow_external=True)
    aligned = aligner.align(rolling_window=2)
    df = aligned.df

    # Verifica indice diario contínuo
    assert len(df) == 3
    assert list(df.index) == [0, 1, 2]
    # Verifica agregação: soma de leite das 2 vacas (30+25=55, 32+26=58, 31+24=55)
    assert df["milk_produced_total"].tolist() == [55.0, 58.0, 55.0]
    # Verifica media por vaca
    assert df["milk_produced_mean"].tolist() == [27.5, 29.0, 27.5]
    # Verifica variavel global alinhada
    assert df["transpiration"].tolist() == [4.5, 5.0, 3.8]
    # Verifica media movel calculada
    assert "milk_produced_total_rolling" in df.columns


def test_ragged_time_series_loader(tmp_path):
    csv_file = tmp_path / "loader_sim.csv"
    data = {
        "RufasTime.simulation_day (simulation day)": [0.0, 1.0],
        "RufasTime.calendar_year (calendar year)": [2026.0, 2026.0],
        "RufasTime.day (julian day)": [100.0, 101.0],
        "FieldDataReporter.send_field_daily_variables.transpiration.field='field_1' (mm)": [2.5, 3.0],
    }
    pd.DataFrame(data).to_csv(csv_file, index=False)

    aligned = RaggedTimeSeriesLoader.load_aligned_dataframe(
        csv_path=csv_file,
        preset="field-crops",
        rolling_window=2,
        allow_external=True,
    )
    assert isinstance(aligned, AlignedSimulationData)
    assert len(aligned.df) == 2
    assert "transpiration" in aligned.df.columns
    assert "transpiration_rolling" in aligned.df.columns
    assert aligned.calendar_years is not None
    assert aligned.calendar_years.iloc[0] == 2026.0
    assert aligned.julian_days is not None
    assert aligned.julian_days.iloc[1] == 101.0


def test_temporal_aligner_boundary_violation(tmp_path):
    csv_file = tmp_path / "outside.csv"
    csv_file.write_text("RufasTime.simulation_day (simulation day)\n0.0\n", encoding="utf-8")
    with pytest.raises(RuFaSBoundaryError):
        TemporalAligner(csv_file, allow_external=False)


def test_temporal_aligner_empty_csv(tmp_path):
    csv_file = tmp_path / "empty_sim.csv"
    pd.DataFrame(
        columns=[
            "RufasTime.simulation_day (simulation day)",
            "FieldDataReporter.send_field_daily_variables.transpiration.field='field_1' (mm)",
        ]
    ).to_csv(csv_file, index=False)

    aligner = TemporalAligner(csv_file, preset="executive", allow_external=True)
    aligned = aligner.align()
    assert len(aligned.df) == 0
    assert list(aligned.df.index) == []
    assert isinstance(aligned.df.index, pd.RangeIndex)


def test_scenario_comparator_delta_calculation():
    df_base = pd.DataFrame(
        {
            "milk_produced_total": [100.0, 100.0, 100.0],
            "methane_emission": [50.0, 50.0, 50.0],
        },
        index=[0, 1, 2],
    )

    df_scen = pd.DataFrame(
        {
            "milk_produced_total": [105.0, 110.0, 100.0],
            "methane_emission": [45.0, 40.0, 45.0],
        },
        index=[0, 1, 2],
    )

    base = AlignedSimulationData(
        df=df_base,
        name="Baseline",
        units={"milk_produced_total": "kg/day", "methane_emission": "g/day"},
    )
    scen = AlignedSimulationData(
        df=df_scen,
        name="Treatment",
        units={"milk_produced_total": "kg/day", "methane_emission": "g/day"},
    )

    comp = ScenarioComparator(base, [scen])
    result = comp.compute_deltas()

    # Leite no dia 1 aumentou 10%
    assert result.scenarios[0].pct_deltas["milk_produced_total"][1] == 10.0
    # Metano no dia 1 reduziu 20%
    assert result.scenarios[0].pct_deltas["methane_emission"][1] == -20.0
    # Resumo anual acumulado
    summary = comp.get_kpi_summary()
    assert summary["Treatment"]["methane_emission"]["total_delta_pct"] == pytest.approx(-13.33, rel=1e-2)


def test_scenario_comparator_zero_division_safe_handling():
    df_base = pd.DataFrame(
        {
            "var_zero": [0.0, 0.0, 10.0],
            "var_normal": [10.0, 20.0, 30.0],
        },
        index=[0, 1, 2],
    )
    df_scen = pd.DataFrame(
        {
            "var_zero": [0.0, 5.0, 10.0],
            "var_normal": [10.0, 25.0, 15.0],
        },
        index=[0, 1, 2],
    )
    base = AlignedSimulationData(df=df_base, name="BaseZero")
    scen = AlignedSimulationData(df=df_scen, name="ScenZero")

    comp = ScenarioComparator(base, scen)
    result = comp.compute_deltas()

    # When base is 0, pct delta must safely be 0.0 without division by zero warning/error
    assert result.scenarios[0].pct_deltas["var_zero"][0] == 0.0
    assert result.scenarios[0].pct_deltas["var_zero"][1] == 0.0
    assert result.scenarios[0].abs_deltas["var_zero"][1] == 5.0

    summary = comp.get_kpi_summary()
    assert "ScenZero" in summary
    assert summary["ScenZero"]["var_normal"]["mean_delta_pct"] == pytest.approx(-16.666, rel=1e-2)


def test_scenario_comparator_mismatched_timelines():
    # Base has 4 days, scenario has 2 days
    df_base = pd.DataFrame({"metric": [10.0, 20.0, 30.0, 40.0]}, index=[0, 1, 2, 3])
    df_scen = pd.DataFrame({"metric": [12.0, 24.0]}, index=[0, 1])

    base = AlignedSimulationData(df=df_base, name="Base4D")
    scen = AlignedSimulationData(df=df_scen, name="Scen2D")

    comp = ScenarioComparator(base, [scen])
    result = comp.compute_deltas()

    assert len(result.common_index) == 2
    assert list(result.common_index) == [0, 1]
    assert len(result.scenarios[0].abs_deltas) == 2
    assert result.scenarios[0].abs_deltas["metric"].tolist() == [2.0, 4.0]
    assert result.scenarios[0].pct_deltas["metric"].tolist() == [20.0, 20.0]


def test_scenario_comparator_multiple_scenarios_and_classmethod_compare():
    df_base = pd.DataFrame({"val": [100.0, 200.0]}, index=[0, 1])
    df_s1 = pd.DataFrame({"val": [110.0, 220.0]}, index=[0, 1])
    df_s2 = pd.DataFrame({"val": [90.0, 180.0]}, index=[0, 1])

    base = AlignedSimulationData(df=df_base, name="Base")
    s1 = AlignedSimulationData(df=df_s1, name="Plus10")
    s2 = AlignedSimulationData(df=df_s2, name="Minus10")

    result = ScenarioComparator.compare(base, [s1, s2])
    assert len(result.scenarios) == 2
    assert result.scenarios[0].name == "Plus10"
    assert result.scenarios[1].name == "Minus10"
    assert result.scenarios[0].pct_deltas["val"].tolist() == [10.0, 10.0]
    assert result.scenarios[1].pct_deltas["val"].tolist() == [-10.0, -10.0]

    comp = ScenarioComparator(base, [s1, s2])
    comp.compute_deltas()
    overlay = comp.get_overlay_series("val")
    assert "Base" in overlay
    assert "Plus10" in overlay
    assert "Minus10" in overlay
    assert overlay["Base"].tolist() == [100.0, 200.0]
    assert overlay["Plus10"].tolist() == [110.0, 220.0]


def test_matplotlib_renderer_creates_valid_png(tmp_path):
    df = pd.DataFrame({
        "milk_produced_total": [100.0, 105.0, 110.0, 108.0],
        "milk_produced_total_rolling": [100.0, 102.5, 105.0, 105.75],
        "transpiration": [4.0, 5.0, 3.5, 4.2],
        "transpiration_rolling": [4.0, 4.5, 4.16, 4.17],
    }, index=[0, 1, 2, 3])

    data = AlignedSimulationData(
        df=df,
        name="TestSim",
        preset="executive",
        units={"milk_produced_total": "kg/day", "transpiration": "mm"},
        panels={
            "milk": {"primary": "milk_produced_total", "rolling": "milk_produced_total_rolling", "title": "Milk Yield", "unit": "kg/day"},
            "transp": {"primary": "transpiration", "rolling": "transpiration_rolling", "title": "Transpiration", "unit": "mm"}
        }
    )

    out_file = tmp_path / "test_dashboard.png"
    renderer = MatplotlibRenderer()
    saved_path = renderer.render(data, out_file, dpi=100)

    assert saved_path.exists()
    assert saved_path.stat().st_size > 0
    # Validação com PIL
    with Image.open(saved_path) as img:
        assert img.format == "PNG"
        assert img.size[0] > 500 and img.size[1] > 300


def test_matplotlib_renderer_creates_valid_pdf(tmp_path):
    df = pd.DataFrame({
        "var_a": [10.0, 20.0, 30.0],
        "var_a_rolling": [10.0, 15.0, 20.0],
    }, index=[0, 1, 2])

    data = AlignedSimulationData(
        df=df,
        name="PDFSim",
        preset="custom",
        units={"var_a": "units"},
        panels={
            "panel_a": {"primary": "var_a", "rolling": "var_a_rolling", "title": "Metric A", "unit": "units"}
        }
    )

    out_file = tmp_path / "test_report.pdf"
    renderer = MatplotlibRenderer()
    saved_path = renderer.render(data, out_file)

    assert saved_path.exists()
    assert saved_path.stat().st_size > 0
    with open(saved_path, "rb") as f:
        header = f.read(5)
        assert header.startswith(b"%PDF")


def test_matplotlib_renderer_with_scenario_comparison(tmp_path):
    df_base = pd.DataFrame({
        "milk_produced_total": [100.0, 105.0, 110.0],
        "milk_produced_total_rolling": [100.0, 102.5, 105.0],
        "methane": [50.0, 48.0, 49.0],
        "methane_rolling": [50.0, 49.0, 49.0],
    }, index=[0, 1, 2])

    df_scen = pd.DataFrame({
        "milk_produced_total": [102.0, 108.0, 115.0],
        "milk_produced_total_rolling": [102.0, 105.0, 108.3],
        "methane": [45.0, 42.0, 40.0],
        "methane_rolling": [45.0, 43.5, 42.3],
    }, index=[0, 1, 2])

    base = AlignedSimulationData(
        df=df_base,
        name="Baseline",
        preset="executive",
        units={"milk_produced_total": "kg/day", "methane": "g"},
        panels={
            "milk": {"primary": "milk_produced_total", "rolling": "milk_produced_total_rolling", "title": "Milk Yield", "unit": "kg/day"},
            "methane": {"primary": "methane", "rolling": "methane_rolling", "title": "Methane", "unit": "g"}
        }
    )

    scen = AlignedSimulationData(
        df=df_scen,
        name="Additive Diet",
        preset="executive",
        units={"milk_produced_total": "kg/day", "methane": "g"},
        panels={
            "milk": {"primary": "milk_produced_total", "rolling": "milk_produced_total_rolling", "title": "Milk Yield", "unit": "kg/day"},
            "methane": {"primary": "methane", "rolling": "methane_rolling", "title": "Methane", "unit": "g"}
        }
    )

    comparator = ScenarioComparator(base, scen)
    comp_result = comparator.compute_deltas()

    out_file = tmp_path / "comparison_plot.png"
    renderer = MatplotlibRenderer()
    saved_path = renderer.render(base, out_file, comparison=comp_result, dpi=100)

    assert saved_path.exists()
    assert saved_path.stat().st_size > 0
    with Image.open(saved_path) as img:
        assert img.format == "PNG"
        assert img.size[0] > 500 and img.size[1] > 300


def test_matplotlib_renderer_missing_module_handling(tmp_path):
    df = pd.DataFrame({
        "milk_produced_total": [100.0, 105.0],
        "milk_produced_total_rolling": [100.0, 102.5],
    }, index=[0, 1])

    data = AlignedSimulationData(
        df=df,
        name="SimWithMissing",
        preset="executive",
        units={"milk_produced_total": "kg/day"},
        panels={
            "milk": {"primary": "milk_produced_total", "rolling": "milk_produced_total_rolling", "title": "Milk Yield", "unit": "kg/day", "available": True},
            "field": {"primary": None, "rolling": None, "title": "Field Crops", "available": False, "missing_reason": "Module 'field' not configured in this simulation"}
        }
    )

    out_file = tmp_path / "missing_module.png"
    renderer = MatplotlibRenderer()
    saved_path = renderer.render(data, out_file, dpi=100)

    assert saved_path.exists()
    assert saved_path.stat().st_size > 0
    with Image.open(saved_path) as img:
        assert img.format == "PNG"


def test_matplotlib_renderer_memory_safety(tmp_path):
    import matplotlib.pyplot as plt

    df = pd.DataFrame({"x": [1, 2, 3], "x_rolling": [1, 1.5, 2]}, index=[0, 1, 2])
    data = AlignedSimulationData(
        df=df,
        name="MemTest",
        panels={"x": {"primary": "x", "rolling": "x_rolling", "title": "X", "unit": ""}}
    )

    out_file = tmp_path / "mem_test.png"
    renderer = MatplotlibRenderer()

    # Pre-check figure count
    plt.close("all")
    initial_figs = len(plt.get_fignums())
    assert initial_figs == 0

    renderer.render(data, out_file, dpi=50)

    # Figure count should be 0 because plt.close(fig) is guaranteed
    assert len(plt.get_fignums()) == 0






