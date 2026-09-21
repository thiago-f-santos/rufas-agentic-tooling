import numpy as np
import pandas as pd
import pytest
from tools.config import RuFaSBoundaryError
from tools.rufas_plotter import (
    AlignedSimulationData,
    MatplotlibRenderer,
    PlotlyRenderer,
    PresetRegistry,
    RaggedTimeSeriesLoader,
    ScenarioComparator,
    ScenarioComparisonResult,
    ScenarioDelta,
    TemporalAligner,
    generate_plots,
    main,
    resolve_columns_for_preset,
)
from PIL import Image
from pathlib import Path




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


def test_matplotlib_renderer_title_and_none_preset(tmp_path, mocker):
    import matplotlib.figure

    df = pd.DataFrame({"x": [1.0, 2.0], "x_rolling": [1.0, 1.5]}, index=[0, 1])

    # Case 1: data with preset=None (defensive check) and custom title
    data_none_preset = AlignedSimulationData(
        df=df,
        name="SimNonePreset",
        preset=None,
        panels={"x": {"primary": "x", "rolling": "x_rolling", "title": "X", "unit": ""}}
    )

    spy_suptitle = mocker.spy(matplotlib.figure.Figure, "suptitle")
    renderer = MatplotlibRenderer()
    out1 = tmp_path / "custom_title.png"
    renderer.render(data_none_preset, out1, title="Custom Dashboard Title")

    assert out1.exists()
    assert spy_suptitle.call_count >= 1
    call_args = spy_suptitle.call_args[0]
    assert call_args[1] == "Custom Dashboard Title"

    # Case 2: default preset title when title is None and preset is 'animal'
    data_animal = AlignedSimulationData(
        df=df,
        name="DairyFarm",
        preset="animal",
        panels={"x": {"primary": "x", "rolling": "x_rolling", "title": "X", "unit": ""}}
    )
    spy_suptitle.reset_mock()
    out2 = tmp_path / "default_title.png"
    renderer.render(data_animal, out2)

    assert out2.exists()
    assert spy_suptitle.call_count >= 1
    call_args2 = spy_suptitle.call_args[0]
    assert "DairyFarm" in call_args2[1]
    assert "Animal" in call_args2[1]


def test_plotly_renderer_creates_standalone_html(tmp_path):
    df = pd.DataFrame({
        "milk_produced_total": [100.0, 105.0, 110.0, 108.0],
        "milk_produced_total_rolling": [100.0, 102.5, 105.0, 105.75],
    }, index=[0, 1, 2, 3])

    data = AlignedSimulationData(
        df=df,
        name="TestSim",
        preset="executive",
        units={"milk_produced_total": "kg/day"},
        panels={
            "milk": {"primary": "milk_produced_total", "rolling": "milk_produced_total_rolling", "title": "Milk Yield", "unit": "kg/day"}
        }
    )

    out_file = tmp_path / "interactive_dashboard.html"
    renderer = PlotlyRenderer()
    saved_path = renderer.render(data, out_file)

    assert saved_path.exists()
    assert saved_path.stat().st_size > 1000
    content = saved_path.read_text(encoding="utf-8")
    assert "<html" in content.lower()
    assert "plotly" in content.lower()
    assert "Milk Yield" in content


def test_plotly_renderer_with_scenario_comparison(tmp_path):
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

    out_file = tmp_path / "comparison_dashboard.html"
    renderer = PlotlyRenderer()
    saved_path = renderer.render(base, out_file, comparison=comp_result)

    assert saved_path.exists()
    assert saved_path.stat().st_size > 1000
    content = saved_path.read_text(encoding="utf-8")
    assert "<html" in content.lower()
    assert "plotly" in content.lower()
    assert "Baseline" in content
    assert "Additive Diet" in content


def test_plotly_renderer_missing_module_handling(tmp_path):
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

    out_file = tmp_path / "missing_module_dashboard.html"
    renderer = PlotlyRenderer()
    saved_path = renderer.render(data, out_file)

    assert saved_path.exists()
    content = saved_path.read_text(encoding="utf-8")
    assert "<html" in content.lower()
    assert "Module &#39;field&#39; not configured in this simulation" in content or "Module 'field' not configured in this simulation" in content


def test_plotly_renderer_calendar_hover_and_custom_title(tmp_path):
    df = pd.DataFrame({
        "var_a": [10.0, 20.0, 30.0],
    }, index=[0, 1, 2])

    cal_years = pd.Series([2026, 2026, 2026], index=[0, 1, 2])
    jul_days = pd.Series([100, 101, 102], index=[0, 1, 2])

    data = AlignedSimulationData(
        df=df,
        name="CalendarSim",
        preset="custom",
        units={"var_a": "kg"},
        panels={
            "metric_a": {"primary": "var_a", "rolling": None, "title": "Metric A", "unit": "kg", "available": True}
        },
        calendar_years=cal_years,
        julian_days=jul_days,
    )

    out_file = tmp_path / "custom_title_dashboard.html"
    renderer = PlotlyRenderer()
    saved_path = renderer.render(data, out_file, title="Special Custom Dashboard Title")

    assert saved_path.exists()
    content = saved_path.read_text(encoding="utf-8")
    assert "Special Custom Dashboard Title" in content
    # Check calendar hover info is embedded
    assert "2026" in content
    assert "100" in content


def test_plotly_renderer_suffix_handling(tmp_path):
    df = pd.DataFrame({"v": [1.0, 2.0]}, index=[0, 1])
    data = AlignedSimulationData(
        df=df,
        name="NoSuffixSim",
        panels={"p": {"primary": "v", "title": "V", "unit": ""}}
    )
    # Give path without .html extension
    out_file = tmp_path / "dashboard_without_ext"
    renderer = PlotlyRenderer()
    saved_path = renderer.render(data, out_file)

    assert saved_path.name == "dashboard_without_ext.html"
    assert saved_path.exists()


def test_plotly_renderer_legend_displayed_when_panel_zero_missing(tmp_path):
    df = pd.DataFrame({
        "var_b": [10.0, 20.0, 30.0],
        "var_b_rolling": [10.0, 15.0, 20.0],
    }, index=[0, 1, 2])

    data = AlignedSimulationData(
        df=df,
        name="MissingFirstPanelSim",
        preset="executive",
        units={"var_b": "kg"},
        panels={
            "panel_0_missing": {
                "primary": None,
                "rolling": None,
                "title": "Missing First Panel",
                "unit": "kg",
                "available": False,
                "missing_reason": "Module not configured",
            },
            "panel_1_valid": {
                "primary": "var_b",
                "rolling": "var_b_rolling",
                "title": "Valid Second Panel",
                "unit": "kg",
                "available": True,
            },
        },
    )

    out_file = tmp_path / "panel_0_missing.html"
    renderer = PlotlyRenderer()
    saved_path = renderer.render(data, out_file)

    assert saved_path.exists()
    content = saved_path.read_text(encoding="utf-8")
    # Verify that showlegend=true is present for the valid panel's traces
    assert '"showlegend":true' in content or '"showlegend": true' in content
    assert "Rolling Avg" in content
    assert "Daily" in content


def test_plotly_renderer_fewer_panels_grid_rangeslider_and_ticks(tmp_path):
    # Executive preset with only 3 panels instead of 6
    df = pd.DataFrame({
        "p1": [1.0, 2.0],
        "p2": [3.0, 4.0],
        "p3": [5.0, 6.0],
    }, index=[0, 1])

    data = AlignedSimulationData(
        df=df,
        name="FewPanelsSim",
        preset="executive",
        panels={
            "p1": {"primary": "p1", "title": "Panel 1", "available": True},
            "p2": {"primary": "p2", "title": "Panel 2", "available": True},
            "p3": {"primary": "p3", "title": "Panel 3", "available": True},
        },
    )

    renderer = PlotlyRenderer()
    # Check grid determination directly
    nrows, ncols = renderer._determine_grid("executive", 3)
    assert nrows == 2
    assert ncols == 2

    out_file = tmp_path / "few_panels.html"
    saved_path = renderer.render(data, out_file)
    assert saved_path.exists()
    content = saved_path.read_text(encoding="utf-8")

    # Range slider should be present and visible
    assert "rangeslider" in content
    assert '"visible":true' in content or '"visible": true' in content
    # Tick labels should be enabled
    assert '"showticklabels":true' in content or '"showticklabels": true' in content


def test_plotly_renderer_julian_days_without_calendar_years(tmp_path):
    df = pd.DataFrame({"val": [10.0, 20.0]}, index=[0, 1])
    jul_days = pd.Series([150, 151], index=[0, 1])

    data = AlignedSimulationData(
        df=df,
        name="JulianOnlySim",
        units={"val": "kg"},
        panels={
            "metric": {"primary": "val", "title": "Metric", "unit": "kg", "available": True}
        },
        calendar_years=None,
        julian_days=jul_days,
    )

    out_file = tmp_path / "julian_only.html"
    renderer = PlotlyRenderer()
    saved_path = renderer.render(data, out_file)

    assert saved_path.exists()
    content = saved_path.read_text(encoding="utf-8")
    assert "150" in content
    assert "Calendar: Day" in content


def test_generate_plots_end_to_end_on_real_csv(tmp_path):
    real_csv = Path("/home/thiago/Projects/RuFaS/output/CSVs/Minas_Gerais_Pilot_saved_variables_csv_all_variables.txt_21-Sep-2026_Mon_11-14-15.csv")
    if not real_csv.exists():
        candidates = sorted(Path("/home/thiago/Projects/RuFaS/output/CSVs").glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            real_csv = candidates[0]
        else:
            pytest.skip("Piloto Minas Gerais CSV não encontrado no ambiente")

    out_dir = tmp_path / "plots"
    result = generate_plots(
        input_path=real_csv,
        preset="executive",
        output_format="both",
        output_dir=out_dir,
        rolling_window=14
    )

    assert result["status"] == "success"
    assert "png" in result["artifacts"]
    assert "html" in result["artifacts"]
    for path_str in result["artifacts"]["png"] + result["artifacts"]["html"]:
        p = Path(path_str)
        assert p.exists()
        assert p.stat().st_size > 0


def test_generate_plots_all_presets_and_compare(tmp_path):
    base_csv = tmp_path / "base.csv"
    scen_csv = tmp_path / "scen.csv"

    base_data = {
        "RufasTime.simulation_day (simulation day)": [0.0, 1.0, 2.0],
        "RufasTime.calendar_year (calendar year)": [2026.0, 2026.0, 2026.0],
        "RufasTime.day (julian day)": [10.0, 11.0, 12.0],
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.estimated_daily_milk_produced (kg/day)": [30.0, 31.0, 32.0],
        "AnimalModuleReporter.report_animal_population_statistics.population_number_of_cows (animals)": [100.0, 100.0, 100.0],
        "AnimalModuleReporter.report_enteric_methane_emission.enteric_methane_emission_for_CALF_PEN_0 (g)": [400.0, 410.0, 420.0],
        "AnimalModuleReporter.report_manure_excretions.CALF_PEN_0_manure_mass (kg)": [50.0, 52.0, 51.0],
        "FeedManager.purchase_feed.ration_cost ($)": [20.0, 21.0, 22.0],
        "FieldDataReporter.send_field_daily_variables.transpiration.field='field_1' (mm)": [3.0, 3.5, 4.0],
    }
    scen_data = {
        "RufasTime.simulation_day (simulation day)": [0.0, 1.0, 2.0],
        "RufasTime.calendar_year (calendar year)": [2026.0, 2026.0, 2026.0],
        "RufasTime.day (julian day)": [10.0, 11.0, 12.0],
        "AnimalModuleReporter.report_milk.milk_data_at_milk_update.estimated_daily_milk_produced (kg/day)": [32.0, 33.0, 34.0],
        "AnimalModuleReporter.report_animal_population_statistics.population_number_of_cows (animals)": [100.0, 100.0, 100.0],
        "AnimalModuleReporter.report_enteric_methane_emission.enteric_methane_emission_for_CALF_PEN_0 (g)": [380.0, 390.0, 395.0],
        "AnimalModuleReporter.report_manure_excretions.CALF_PEN_0_manure_mass (kg)": [48.0, 49.0, 50.0],
        "FeedManager.purchase_feed.ration_cost ($)": [22.0, 23.0, 24.0],
        "FieldDataReporter.send_field_daily_variables.transpiration.field='field_1' (mm)": [3.1, 3.6, 4.1],
    }
    pd.DataFrame(base_data).to_csv(base_csv, index=False)
    pd.DataFrame(scen_data).to_csv(scen_csv, index=False)

    out_dir = tmp_path / "all_plots"
    result = generate_plots(
        input_path=base_csv,
        compare_paths=[scen_csv],
        preset="all",
        output_format="both",
        output_dir=out_dir,
        rolling_window=2,
        allow_external=True,
    )

    assert result["status"] == "success"
    assert len(result["artifacts"]["png"]) == 5
    assert len(result["artifacts"]["html"]) == 5
    for p_str in result["artifacts"]["png"] + result["artifacts"]["html"]:
        p = Path(p_str)
        assert p.exists()
        assert p.stat().st_size > 0
    assert "metrics_summary" in result


def test_generate_plots_custom_vars_and_formats(tmp_path):
    csv_file = tmp_path / "custom.csv"
    data = {
        "RufasTime.simulation_day (simulation day)": [0.0, 1.0, 2.0],
        "var_a (kg)": [10.0, 20.0, 30.0],
        "var_b ($)": [5.0, 15.0, 25.0],
    }
    pd.DataFrame(data).to_csv(csv_file, index=False)

    # Test format="png" only
    png_dir = tmp_path / "png_only"
    res_png = generate_plots(
        input_path=csv_file,
        preset="custom",
        custom_vars=["var_a (kg)", "var_b ($)"],
        output_format="png",
        output_dir=png_dir,
        allow_external=True,
    )
    assert res_png["status"] == "success"
    assert len(res_png["artifacts"]["png"]) == 1
    assert len(res_png["artifacts"]["html"]) == 0

    # Test format="html" only
    html_dir = tmp_path / "html_only"
    res_html = generate_plots(
        input_path=csv_file,
        preset="custom",
        custom_vars=["var_a (kg)", "var_b ($)"],
        output_format="html",
        output_dir=html_dir,
        allow_external=True,
    )
    assert res_html["status"] == "success"
    assert len(res_html["artifacts"]["html"]) == 1
    assert len(res_html["artifacts"]["png"]) == 0


def test_generate_plots_auto_discovery(tmp_path):
    csv_dir = tmp_path / "RuFaS" / "output" / "CSVs"
    csv_dir.mkdir(parents=True)
    old_csv = csv_dir / "sim_old.csv"
    new_csv = csv_dir / "sim_new.csv"
    old_csv.write_text("RufasTime.simulation_day (simulation day)\n0.0\n", encoding="utf-8")
    import time
    time.sleep(0.01)
    new_csv.write_text("RufasTime.simulation_day (simulation day)\n0.0\n1.0\n", encoding="utf-8")

    res = generate_plots(
        input_path=tmp_path / "RuFaS" / "output",
        preset="executive",
        output_format="png",
        output_dir=tmp_path / "out",
        allow_external=True,
    )
    assert res["status"] == "success"
    assert res["selected_csv"] == str(new_csv.resolve())


def test_generate_plots_boundary_violation(tmp_path):
    csv_file = tmp_path / "external.csv"
    csv_file.write_text("RufasTime.simulation_day (simulation day)\n0.0\n", encoding="utf-8")
    with pytest.raises(RuFaSBoundaryError):
        generate_plots(input_path=csv_file, allow_external=False)


def test_cli_execution_success(tmp_path, capsys, monkeypatch):
    csv_file = tmp_path / "cli_sim.csv"
    data = {
        "RufasTime.simulation_day (simulation day)": [0.0, 1.0],
        "AnimalModuleReporter.report_animal_population_statistics.population_number_of_cows (animals)": [50.0, 50.0],
    }
    pd.DataFrame(data).to_csv(csv_file, index=False)

    out_dir = tmp_path / "cli_out"
    test_args = [
        "rufas-plot",
        str(csv_file),
        "-p", "executive",
        "-f", "both",
        "-o", str(out_dir),
        "--allow-external",
    ]
    monkeypatch.setattr("sys.argv", test_args)
    exit_code = main()
    assert exit_code in (0, None)

    captured = capsys.readouterr()
    assert "success" in captured.out.lower() or "generated" in captured.out.lower()
    assert (out_dir / "executive_dashboard.png").exists()
    assert (out_dir / "executive_dashboard.html").exists()


def test_cli_execution_failure(tmp_path, capsys, monkeypatch):
    test_args = [
        "rufas-plot",
        str(tmp_path / "nonexistent.csv"),
        "--allow-external",
    ]
    monkeypatch.setattr("sys.argv", test_args)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert "error" in captured.err.lower() or "not found" in captured.err.lower()











