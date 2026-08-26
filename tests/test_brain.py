import sys
from pathlib import Path
import pytest
import kuzu

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.rufas_brain import (
    init_brain_database,
    populate_structural_ontology,
    ingest_simulation_run,
    compute_statistical_correlations,
)


def test_init_brain_database(tmp_path):
    db_dir = str(tmp_path / "test_brain.kuzu")
    conn = init_brain_database(db_dir)
    assert conn is not None

    # Verify all 6 Node tables exist
    res_m = conn.execute("MATCH (m:Module) RETURN count(m)").get_next()
    assert res_m[0] == 0

    res_cb = conn.execute("MATCH (b:ConfigBlob) RETURN count(b)").get_next()
    assert res_cb[0] == 0

    res_p = conn.execute("MATCH (p:InputParameter) RETURN count(p)").get_next()
    assert res_p[0] == 0

    res_v = conn.execute("MATCH (v:OutputVariable) RETURN count(v)").get_next()
    assert res_v[0] == 0

    res_r = conn.execute("MATCH (r:SimulationRun) RETURN count(r)").get_next()
    assert res_r[0] == 0

    res_rm = conn.execute("MATCH (rm:RunMetric) RETURN count(rm)").get_next()
    assert res_rm[0] == 0

    # Insert sample nodes and relationship to verify relationship tables work
    conn.execute("CREATE (m:Module {name: 'animal', description: 'Animal module', manager_class: 'HerdManager'})")
    conn.execute("CREATE (b:ConfigBlob {name: 'animal', title: 'Animal Config', file_path: 'animal.json', description: 'Animal config', format_type: 'json'})")
    conn.execute("MATCH (b:ConfigBlob {name: 'animal'}), (m:Module {name: 'animal'}) CREATE (b)-[:CONFIG_OF]->(m)")
    rel_res = conn.execute("MATCH (b:ConfigBlob)-[:CONFIG_OF]->(m:Module) RETURN b.name, m.name").get_next()
    assert rel_res[0] == "animal"
    assert rel_res[1] == "animal"


def test_init_brain_database_in_memory():
    conn = init_brain_database(":memory:")
    assert conn is not None
    res = conn.execute("MATCH (m:Module) RETURN count(m)").get_next()
    assert res[0] == 0


def test_init_brain_database_idempotent(tmp_path):
    db_dir = str(tmp_path / "idempotent_brain.kuzu")
    conn1 = init_brain_database(db_dir)
    conn1.execute("CREATE (m:Module {name: 'manure', description: 'Manure module', manager_class: 'ManureManager'})")
    
    # Re-initialize on same path should succeed without throwing error
    conn2 = init_brain_database(db_dir)
    res = conn2.execute("MATCH (m:Module) RETURN count(m)").get_next()
    assert res[0] == 1


def test_populate_structural_ontology(tmp_path):
    db_dir = str(tmp_path / "test_brain.kuzu")
    conn = init_brain_database(db_dir)
    rufas_root = Path(__file__).resolve().parent.parent.parent / "RuFaS"
    
    summary = populate_structural_ontology(conn, rufas_root)
    assert isinstance(summary, dict)
    
    # 1. Verify 5 canonical modules
    modules_res = conn.execute("MATCH (m:Module) RETURN m.name ORDER BY m.name").get_as_df()
    module_names = modules_res["m.name"].tolist()
    assert sorted(module_names) == ["animal", "eee", "feed_storage", "field_soil", "manure"]
    
    # 2. Verify ConfigBlobs (at least 22 canonical blobs)
    blobs_count = conn.execute("MATCH (b:ConfigBlob) RETURN count(b)").get_next()[0]
    assert blobs_count >= 22
    
    # 3. Verify CONFIG_OF edges linking blobs to modules
    config_of_count = conn.execute("MATCH (b:ConfigBlob)-[:CONFIG_OF]->(m:Module) RETURN count(*)").get_next()[0]
    assert config_of_count >= 22
    
    # 4. Verify InputParameter nodes and CONTAINS_PARAM edges
    params_count = conn.execute("MATCH (p:InputParameter) RETURN count(p)").get_next()[0]
    assert params_count > 500
    
    contains_param_count = conn.execute("MATCH (b:ConfigBlob)-[:CONTAINS_PARAM]->(p:InputParameter) RETURN count(*)").get_next()[0]
    assert contains_param_count > 500
    
    # 5. Verify OutputVariables (2,038 variables)
    vars_count = conn.execute("MATCH (v:OutputVariable) RETURN count(v)").get_next()[0]
    assert vars_count > 1000
    
    # Check specific output variable properties
    var_res = conn.execute("MATCH (v:OutputVariable {name: 'AnimalModuleReporter.report_herd_statistics_data.daily_milk_production (kg/day)'}) RETURN v.module, v.unit, v.category").get_next()
    assert var_res is not None
    assert var_res[0] == "animal"
    assert var_res[1] == "kg/day"
    assert var_res[2] == "production"
    
    # 6. Verify biophysical CAUSALLY_INFLUENCES edges
    causal_count = conn.execute("MATCH (p:InputParameter)-[c:CAUSALLY_INFLUENCES]->(v:OutputVariable) RETURN count(c)").get_next()[0]
    assert causal_count > 50
    
    # Verify cow_num causal edge
    cow_causal = conn.execute("MATCH (p:InputParameter)-[c:CAUSALLY_INFLUENCES]->(v:OutputVariable) WHERE p.id CONTAINS 'cow_num' RETURN count(c)").get_next()[0]
    assert cow_causal > 0


def test_populate_structural_ontology_idempotent(tmp_path):
    db_dir = str(tmp_path / "test_brain_idempotent.kuzu")
    conn = init_brain_database(db_dir)
    rufas_root = Path(__file__).resolve().parent.parent.parent / "RuFaS"
    
    # Run once
    summary1 = populate_structural_ontology(conn, rufas_root)
    # Run twice
    summary2 = populate_structural_ontology(conn, rufas_root)
    
    modules_count = conn.execute("MATCH (m:Module) RETURN count(m)").get_next()[0]
    assert modules_count == 5
    
    blobs_count = conn.execute("MATCH (b:ConfigBlob) RETURN count(b)").get_next()[0]
    assert blobs_count >= 22


def test_ingest_simulation_run(tmp_path):
    db_dir = str(tmp_path / "test_brain.kuzu")
    conn = init_brain_database(db_dir)
    rufas_root = Path(__file__).resolve().parent.parent.parent / "RuFaS"
    populate_structural_ontology(conn, rufas_root)

    output_dir = rufas_root / "output"
    summary = ingest_simulation_run(conn, output_dir, run_id="test_run_01", scenario_name="freestall")
    assert summary["run_id"] == "test_run_01"
    assert summary["metrics_ingested"] > 500
    assert summary["status"] == "completed"

    # Query SimulationRun in KuzuDB
    run_res = conn.execute("MATCH (r:SimulationRun {run_id: 'test_run_01'}) RETURN r.run_id, r.scenario_name, r.duration_days, r.status").get_next()
    assert run_res[0] == "test_run_01"
    assert run_res[1] == "freestall"
    assert run_res[2] == 60
    assert run_res[3] == "completed"

    # Verify RunMetric nodes
    metrics_count = conn.execute("MATCH (rm:RunMetric {run_id: 'test_run_01'}) RETURN count(rm)").get_next()[0]
    assert metrics_count > 500

    # Verify GENERATED_METRIC edges
    gen_count = conn.execute("MATCH (r:SimulationRun {run_id: 'test_run_01'})-[:GENERATED_METRIC]->(rm:RunMetric) RETURN count(rm)").get_next()[0]
    assert gen_count == metrics_count

    # Verify OF_VARIABLE edges
    of_var_count = conn.execute("MATCH (rm:RunMetric {run_id: 'test_run_01'})-[:OF_VARIABLE]->(v:OutputVariable) RETURN count(v)").get_next()[0]
    assert of_var_count == metrics_count

    # Verify SIMULATED_WITH edges
    sim_with_count = conn.execute("MATCH (r:SimulationRun {run_id: 'test_run_01'})-[:SIMULATED_WITH]->(p:InputParameter) RETURN count(p)").get_next()[0]
    assert sim_with_count > 0


def test_ingest_simulation_run_custom_config(tmp_path):
    db_dir = str(tmp_path / "test_brain_custom.kuzu")
    conn = init_brain_database(db_dir)
    rufas_root = Path(__file__).resolve().parent.parent.parent / "RuFaS"
    populate_structural_ontology(conn, rufas_root)

    output_dir = rufas_root / "output"
    custom_config = {
        "animal.herd_information.cow_num": 150,
        "mature_body_weight": 700.0,
    }
    summary = ingest_simulation_run(
        conn,
        output_dir,
        run_id="test_run_custom",
        scenario_name="freestall_custom",
        config_data=custom_config,
    )
    assert summary["run_id"] == "test_run_custom"

    # Verify overridden parameter value in SIMULATED_WITH edge
    res = conn.execute("MATCH (r:SimulationRun {run_id: 'test_run_custom'})-[s:SIMULATED_WITH]->(p:InputParameter) WHERE p.id CONTAINS 'cow_num' RETURN s.value").get_next()
    assert res is not None
    assert res[0] == "150"


def test_ingest_simulation_run_idempotent(tmp_path):
    db_dir = str(tmp_path / "test_brain_ingest_idem.kuzu")
    conn = init_brain_database(db_dir)
    rufas_root = Path(__file__).resolve().parent.parent.parent / "RuFaS"
    populate_structural_ontology(conn, rufas_root)

    output_dir = rufas_root / "output"
    summary1 = ingest_simulation_run(conn, output_dir, run_id="run_idem", scenario_name="freestall")
    summary2 = ingest_simulation_run(conn, output_dir, run_id="run_idem", scenario_name="freestall")

    runs_count = conn.execute("MATCH (r:SimulationRun {run_id: 'run_idem'}) RETURN count(r)").get_next()[0]
    assert runs_count == 1
    metrics_count = conn.execute("MATCH (rm:RunMetric {run_id: 'run_idem'}) RETURN count(rm)").get_next()[0]
    assert metrics_count == summary1["metrics_ingested"]


def test_ingest_cli(tmp_path, monkeypatch, capsys):
    from tools.rufas_brain import main
    db_dir = str(tmp_path / "cli_brain.kuzu")
    rufas_root = Path(__file__).resolve().parent.parent.parent / "RuFaS"

    # 1. Run init CLI
    monkeypatch.setattr(sys, "argv", ["rufas-brain", "init", "--db-path", db_dir, "--rufas-root", str(rufas_root)])
    main()
    captured = capsys.readouterr()
    assert "initialized at" in captured.out

    # 2. Run ingest CLI
    output_dir = str(rufas_root / "output")
    monkeypatch.setattr(sys, "argv", ["rufas-brain", "ingest", "--db-path", db_dir, "--output-dir", output_dir, "--run-id", "cli_run_01", "--scenario", "freestall"])
    main()
    captured = capsys.readouterr()
    assert "ingested successfully" in captured.out


def test_compute_statistical_correlations_synthetic(tmp_path):
    db_dir = str(tmp_path / "test_corr.kuzu")
    conn = init_brain_database(db_dir)

    # Create synthetic input parameters and output variables
    conn.execute("CREATE (p:InputParameter {id: 'animal.herd_information.cow_num', blob_name: 'animal', param_name: 'cow_num', data_type: 'int', unit: 'animals', default_value: '100', description: 'Herd size'})")
    conn.execute("CREATE (p:InputParameter {id: 'animal.mature_body_weight', blob_name: 'animal', param_name: 'mature_body_weight', data_type: 'float', unit: 'kg', default_value: '650.0', description: 'Body weight'})")
    conn.execute("CREATE (p:InputParameter {id: 'animal.constant_param', blob_name: 'animal', param_name: 'constant_param', data_type: 'float', unit: '%', default_value: '5.0', description: 'Constant parameter'})")

    conn.execute("CREATE (v:OutputVariable {name: 'AnimalModuleReporter.daily_milk_production (kg/day)', module: 'animal', unit: 'kg/day', category: 'production', reporter_class: 'AnimalReporter', description: 'Milk output'})")
    conn.execute("CREATE (v:OutputVariable {name: 'AnimalModuleReporter.feed_efficiency (kg/kg)', module: 'animal', unit: 'kg/kg', category: 'production', reporter_class: 'AnimalReporter', description: 'Efficiency'})")
    conn.execute("CREATE (v:OutputVariable {name: 'GeneralReporter.constant_metric', module: 'general', unit: '', category: 'general', reporter_class: 'GeneralReporter', description: 'Constant metric'})")

    # Create 5 synthetic simulation runs
    cow_vals = [50, 100, 150, 200, 250]
    mbw_vals = [500.0, 550.0, 600.0, 650.0, 700.0]
    const_val = 5.0

    for i in range(5):
        run_id = f"run_{i+1}"
        conn.execute(
            "CREATE (r:SimulationRun {run_id: $rid, scenario_name: 'freestall', execution_date: '2026-08-26', start_date: '2013:1', end_date: '2013:60', duration_days: 60, random_seed: 42, status: 'completed'})",
            {"rid": run_id},
        )
        # Link parameters
        conn.execute(
            "MATCH (r:SimulationRun {run_id: $rid}), (p:InputParameter {id: 'animal.herd_information.cow_num'}) CREATE (r)-[:SIMULATED_WITH {value: $val}]->(p)",
            {"rid": run_id, "val": str(cow_vals[i])},
        )
        conn.execute(
            "MATCH (r:SimulationRun {run_id: $rid}), (p:InputParameter {id: 'animal.mature_body_weight'}) CREATE (r)-[:SIMULATED_WITH {value: $val}]->(p)",
            {"rid": run_id, "val": str(mbw_vals[i])},
        )
        conn.execute(
            "MATCH (r:SimulationRun {run_id: $rid}), (p:InputParameter {id: 'animal.constant_param'}) CREATE (r)-[:SIMULATED_WITH {value: $val}]->(p)",
            {"rid": run_id, "val": str(const_val)},
        )

        # Output metrics:
        # daily_milk: perfectly positively correlated with cow_num (30.0 * cow_num)
        # feed_efficiency: negatively correlated with cow_num (2.5 - 0.005 * cow_num)
        # constant_metric: constant 100.0 across all runs
        milk_val = 30.0 * cow_vals[i]
        fe_val = 2.5 - 0.005 * cow_vals[i]
        const_metric_val = 100.0

        # Create RunMetric nodes & edges
        conn.execute(
            """
            MATCH (r:SimulationRun {run_id: $rid}), (v:OutputVariable {name: 'AnimalModuleReporter.daily_milk_production (kg/day)'})
            CREATE (rm:RunMetric {id: $mid, run_id: $rid, var_name: 'AnimalModuleReporter.daily_milk_production (kg/day)', mean_val: $mean, min_val: $mean, max_val: $mean, sum_val: $mean, non_null_count: 60})
            CREATE (r)-[:GENERATED_METRIC]->(rm)
            CREATE (rm)-[:OF_VARIABLE]->(v)
            """,
            {"rid": run_id, "mid": f"{run_id}::milk", "mean": milk_val},
        )
        conn.execute(
            """
            MATCH (r:SimulationRun {run_id: $rid}), (v:OutputVariable {name: 'AnimalModuleReporter.feed_efficiency (kg/kg)'})
            CREATE (rm:RunMetric {id: $mid, run_id: $rid, var_name: 'AnimalModuleReporter.feed_efficiency (kg/kg)', mean_val: $mean, min_val: $mean, max_val: $mean, sum_val: $mean, non_null_count: 60})
            CREATE (r)-[:GENERATED_METRIC]->(rm)
            CREATE (rm)-[:OF_VARIABLE]->(v)
            """,
            {"rid": run_id, "mid": f"{run_id}::fe", "mean": fe_val},
        )
        conn.execute(
            """
            MATCH (r:SimulationRun {run_id: $rid}), (v:OutputVariable {name: 'GeneralReporter.constant_metric'})
            CREATE (rm:RunMetric {id: $mid, run_id: $rid, var_name: 'GeneralReporter.constant_metric', mean_val: $mean, min_val: $mean, max_val: $mean, sum_val: $mean, non_null_count: 60})
            CREATE (r)-[:GENERATED_METRIC]->(rm)
            CREATE (rm)-[:OF_VARIABLE]->(v)
            """,
            {"rid": run_id, "mid": f"{run_id}::const", "mean": const_metric_val},
        )

    correlations = compute_statistical_correlations(conn, min_r=0.5, max_p=0.05, min_samples=3)
    assert isinstance(correlations, list)
    assert len(correlations) >= 2

    # Check positive correlation: cow_num -> daily_milk_production
    pos_corr = next((c for c in correlations if c["param_id"] == "animal.herd_information.cow_num" and "daily_milk_production" in c["var_name"]), None)
    assert pos_corr is not None
    assert pos_corr["pearson_r"] > 0.99
    assert pos_corr["spearman_r"] > 0.99
    assert pos_corr["p_value"] < 0.01
    assert pos_corr["sample_size"] == 5

    # Check negative correlation: cow_num -> feed_efficiency
    neg_corr = next((c for c in correlations if c["param_id"] == "animal.herd_information.cow_num" and "feed_efficiency" in c["var_name"]), None)
    assert neg_corr is not None
    assert neg_corr["pearson_r"] < -0.99
    assert neg_corr["spearman_r"] < -0.99
    assert neg_corr["p_value"] < 0.01

    # Verify constant parameter and constant metric produced no correlations
    const_p_corr = [c for c in correlations if c["param_id"] == "animal.constant_param"]
    assert len(const_p_corr) == 0
    const_m_corr = [c for c in correlations if "constant_metric" in c["var_name"]]
    assert len(const_m_corr) == 0

    # Verify CORRELATES_WITH edges in KuzuDB
    edge_res = conn.execute("MATCH (p:InputParameter)-[c:CORRELATES_WITH]->(v:OutputVariable) RETURN p.id, v.name, c.pearson_r, c.spearman_r, c.p_value, c.sample_size").get_as_df()
    assert len(edge_res) >= 2
    assert "animal.herd_information.cow_num" in edge_res["p.id"].values


def test_compute_correlations_cli(tmp_path, monkeypatch, capsys):
    from tools.rufas_brain import main
    db_dir = str(tmp_path / "cli_corr.kuzu")
    conn = init_brain_database(db_dir)

    # Insert synthetic nodes and runs
    conn.execute("CREATE (p:InputParameter {id: 'cow_num', blob_name: 'animal', param_name: 'cow_num', data_type: 'int', unit: '', default_value: '100', description: ''})")
    conn.execute("CREATE (v:OutputVariable {name: 'milk_yield', module: 'animal', unit: 'kg', category: 'production', reporter_class: 'AnimalReporter', description: ''})")

    for i in range(4):
        rid = f"run_{i}"
        conn.execute("CREATE (r:SimulationRun {run_id: $rid, scenario_name: 's', execution_date: '', start_date: '', end_date: '', duration_days: 10, random_seed: 0, status: 'completed'})", {"rid": rid})
        conn.execute("MATCH (r:SimulationRun {run_id: $rid}), (p:InputParameter {id: 'cow_num'}) CREATE (r)-[:SIMULATED_WITH {value: $val}]->(p)", {"rid": rid, "val": str(50 * (i + 1))})
        conn.execute("MATCH (r:SimulationRun {run_id: $rid}), (v:OutputVariable {name: 'milk_yield'}) CREATE (rm:RunMetric {id: $mid, run_id: $rid, var_name: 'milk_yield', mean_val: $val, min_val: 0.0, max_val: 0.0, sum_val: 0.0, non_null_count: 10}) CREATE (r)-[:GENERATED_METRIC]->(rm) CREATE (rm)-[:OF_VARIABLE]->(v)", {"rid": rid, "mid": f"{rid}::m", "val": float(1000 * (i + 1))})

    monkeypatch.setattr(sys, "argv", ["rufas-brain", "compute-correlations", "--db-path", db_dir, "--min-r", "0.5", "--max-p", "0.05", "--min-samples", "3"])
    main()
    captured = capsys.readouterr()
    assert "Correlations computed" in captured.out or "Found" in captured.out or "cow_num" in captured.out


def test_compute_correlations_nonlinear_monotonic(tmp_path):
    import math
    db_dir = str(tmp_path / "nonlin_corr.kuzu")
    conn = init_brain_database(db_dir)

    conn.execute("CREATE (p:InputParameter {id: 'param_x', blob_name: 'test', param_name: 'param_x', data_type: 'float', unit: '', default_value: '1.0', description: ''})")
    conn.execute("CREATE (v:OutputVariable {name: 'var_exp', module: 'test', unit: '', category: '', reporter_class: '', description: ''})")

    # 5 runs with exponential relationship y = exp(x)
    for x in [1.0, 2.0, 3.0, 4.0, 5.0]:
        rid = f"run_{int(x)}"
        y = math.exp(x)
        conn.execute("CREATE (r:SimulationRun {run_id: $rid, scenario_name: 'exp_test', execution_date: '', start_date: '', end_date: '', duration_days: 10, random_seed: 0, status: 'completed'})", {"rid": rid})
        conn.execute("MATCH (r:SimulationRun {run_id: $rid}), (p:InputParameter {id: 'param_x'}) CREATE (r)-[:SIMULATED_WITH {value: $val}]->(p)", {"rid": rid, "val": str(x)})
        conn.execute("MATCH (r:SimulationRun {run_id: $rid}), (v:OutputVariable {name: 'var_exp'}) CREATE (rm:RunMetric {id: $mid, run_id: $rid, var_name: 'var_exp', mean_val: $val, min_val: $val, max_val: $val, sum_val: $val, non_null_count: 10}) CREATE (r)-[:GENERATED_METRIC]->(rm) CREATE (rm)-[:OF_VARIABLE]->(v)", {"rid": rid, "mid": f"{rid}::exp", "val": y})

    corrs = compute_statistical_correlations(conn, min_r=0.5, max_p=0.05, min_samples=3)
    assert len(corrs) == 1
    assert corrs[0]["param_id"] == "param_x"
    assert corrs[0]["var_name"] == "var_exp"
    assert corrs[0]["spearman_r"] == pytest.approx(1.0)
    assert corrs[0]["pearson_r"] > 0.8
    assert corrs[0]["p_value"] < 0.05


def test_compute_correlations_empty_and_insufficient_samples(tmp_path):
    db_dir = str(tmp_path / "empty_corr.kuzu")
    conn = init_brain_database(db_dir)

    # Empty DB
    assert compute_statistical_correlations(conn) == []

    # 2 runs with min_samples=3
    conn.execute("CREATE (p:InputParameter {id: 'p1', blob_name: '', param_name: 'p1', data_type: 'int', unit: '', default_value: '1', description: ''})")
    conn.execute("CREATE (v:OutputVariable {name: 'v1', module: '', unit: '', category: '', reporter_class: '', description: ''})")
    for i in range(2):
        rid = f"run_{i}"
        conn.execute("CREATE (r:SimulationRun {run_id: $rid, scenario_name: 's', execution_date: '', start_date: '', end_date: '', duration_days: 10, random_seed: 0, status: 'completed'})", {"rid": rid})
        conn.execute("MATCH (r:SimulationRun {run_id: $rid}), (p:InputParameter {id: 'p1'}) CREATE (r)-[:SIMULATED_WITH {value: $val}]->(p)", {"rid": rid, "val": str(i + 1)})
        conn.execute("MATCH (r:SimulationRun {run_id: $rid}), (v:OutputVariable {name: 'v1'}) CREATE (rm:RunMetric {id: $mid, run_id: $rid, var_name: 'v1', mean_val: $val, min_val: 0.0, max_val: 0.0, sum_val: 0.0, non_null_count: 10}) CREATE (r)-[:GENERATED_METRIC]->(rm) CREATE (rm)-[:OF_VARIABLE]->(v)", {"rid": rid, "mid": f"{rid}::m", "val": float(i + 1)})

    assert compute_statistical_correlations(conn, min_samples=3) == []


def test_compute_correlations_idempotent(tmp_path):
    db_dir = str(tmp_path / "idem_corr.kuzu")
    conn = init_brain_database(db_dir)

    conn.execute("CREATE (p:InputParameter {id: 'p1', blob_name: '', param_name: 'p1', data_type: 'int', unit: '', default_value: '1', description: ''})")
    conn.execute("CREATE (v:OutputVariable {name: 'v1', module: '', unit: '', category: '', reporter_class: '', description: ''})")
    for i in range(4):
        rid = f"run_{i}"
        conn.execute("CREATE (r:SimulationRun {run_id: $rid, scenario_name: 's', execution_date: '', start_date: '', end_date: '', duration_days: 10, random_seed: 0, status: 'completed'})", {"rid": rid})
        conn.execute("MATCH (r:SimulationRun {run_id: $rid}), (p:InputParameter {id: 'p1'}) CREATE (r)-[:SIMULATED_WITH {value: $val}]->(p)", {"rid": rid, "val": str(i + 1)})
        conn.execute("MATCH (r:SimulationRun {run_id: $rid}), (v:OutputVariable {name: 'v1'}) CREATE (rm:RunMetric {id: $mid, run_id: $rid, var_name: 'v1', mean_val: $val, min_val: 0.0, max_val: 0.0, sum_val: 0.0, non_null_count: 10}) CREATE (r)-[:GENERATED_METRIC]->(rm) CREATE (rm)-[:OF_VARIABLE]->(v)", {"rid": rid, "mid": f"{rid}::m", "val": float(i + 1)})

    # Compute twice
    corrs1 = compute_statistical_correlations(conn, min_samples=3)
    corrs2 = compute_statistical_correlations(conn, min_samples=3)
    assert len(corrs1) == len(corrs2) == 1

    # Verify only 1 edge exists
    edge_count = conn.execute("MATCH (p:InputParameter)-[c:CORRELATES_WITH]->(v:OutputVariable) RETURN count(c)").get_next()[0]
    assert edge_count == 1


def test_brain_query_and_impact_tracing_ontology(tmp_path):
    from tools.rufas_brain import execute_cypher_query, trace_parameter_impact, lookup_variable_info
    db_dir = str(tmp_path / "test_brain.kuzu")
    conn = init_brain_database(db_dir)
    rufas_root = Path(__file__).resolve().parent.parent.parent / "RuFaS"
    populate_structural_ontology(conn, rufas_root)

    # 1. Execute OpenCypher Query
    res = execute_cypher_query(conn, "MATCH (m:Module) RETURN m.name ORDER BY m.name")
    assert isinstance(res, list)
    assert len(res) == 5
    assert res[0]["m.name"] == "animal"

    # 2. Trace Parameter Impact
    impacts = trace_parameter_impact(conn, "cow_num")
    assert isinstance(impacts, dict)
    assert impacts["param_query"] == "cow_num"
    assert impacts["matched_parameters_count"] > 0
    assert len(impacts["parameters"]) > 0
    # Check causal pathways found for cow_num
    found_causal = any(len(p["causal_pathways"]) > 0 for p in impacts["parameters"])
    assert found_causal

    # 3. Lookup Variable Info
    info = lookup_variable_info(conn, "daily_milk_production")
    assert isinstance(info, list)
    assert len(info) > 0
    matched_var = info[0]
    assert "daily_milk_production" in matched_var["name"]
    assert matched_var["module"] == "animal"
    assert matched_var["unit"] == "kg/day"
    assert matched_var["category"] == "production"
    assert len(matched_var["causal_inputs"]) > 0


def test_execute_cypher_query_unit(tmp_path):
    from tools.rufas_brain import execute_cypher_query
    db_dir = str(tmp_path / "test_query.kuzu")
    conn = init_brain_database(db_dir)

    conn.execute("CREATE (m:Module {name: 'animal', description: 'Animal subsystem', manager_class: 'HerdManager'})")
    conn.execute("CREATE (m:Module {name: 'manure', description: 'Manure subsystem', manager_class: 'ManureManager'})")

    # Basic query
    res = execute_cypher_query(conn, "MATCH (m:Module) RETURN m.name AS name, m.manager_class AS manager ORDER BY m.name")
    assert len(res) == 2
    assert res[0] == {"name": "animal", "manager": "HerdManager"}
    assert res[1] == {"name": "manure", "manager": "ManureManager"}

    # Filtered query with 0 results
    empty_res = execute_cypher_query(conn, "MATCH (m:Module) WHERE m.name = 'nonexistent' RETURN m.name")
    assert empty_res == []

    # Aggregation query
    count_res = execute_cypher_query(conn, "MATCH (m:Module) RETURN count(m) AS cnt")
    assert count_res == [{"cnt": 2}]


def test_trace_parameter_impact_synthetic(tmp_path):
    from tools.rufas_brain import trace_parameter_impact
    db_dir = str(tmp_path / "test_trace.kuzu")
    conn = init_brain_database(db_dir)

    conn.execute("CREATE (p:InputParameter {id: 'animal.herd_information.cow_num', blob_name: 'animal', param_name: 'cow_num', data_type: 'int', unit: 'animals', default_value: '100', description: 'Cow count'})")
    conn.execute("CREATE (v1:OutputVariable {name: 'AnimalReporter.daily_milk (kg/day)', module: 'animal', unit: 'kg/day', category: 'production', reporter_class: 'AnimalReporter', description: 'Milk output'})")
    conn.execute("CREATE (v2:OutputVariable {name: 'ManureReporter.ch4_emissions (kg)', module: 'manure', unit: 'kg', category: 'emissions', reporter_class: 'ManureReporter', description: 'Methane output'})")

    # Add causal edge
    conn.execute(
        "MATCH (p:InputParameter {id: 'animal.herd_information.cow_num'}), (v:OutputVariable {name: 'AnimalReporter.daily_milk (kg/day)'}) CREATE (p)-[:CAUSALLY_INFLUENCES {pathway: 'Production Scaling', mechanism: 'More cows produce more milk'}]->(v)"
    )

    # Add correlation edge
    conn.execute(
        "MATCH (p:InputParameter {id: 'animal.herd_information.cow_num'}), (v:OutputVariable {name: 'ManureReporter.ch4_emissions (kg)'}) CREATE (p)-[:CORRELATES_WITH {pearson_r: 0.95, spearman_r: 0.93, p_value: 0.001, sample_size: 10}]->(v)"
    )

    # Case-insensitive search by param_name
    impact = trace_parameter_impact(conn, "COW_NUM")
    assert impact["param_query"] == "COW_NUM"
    assert impact["matched_parameters_count"] == 1
    p_info = impact["parameters"][0]
    assert p_info["id"] == "animal.herd_information.cow_num"
    assert len(p_info["causal_pathways"]) == 1
    assert p_info["causal_pathways"][0]["output_variable"] == "AnimalReporter.daily_milk (kg/day)"
    assert p_info["causal_pathways"][0]["pathway"] == "Production Scaling"

    assert len(p_info["correlations"]) == 1
    assert p_info["correlations"][0]["output_variable"] == "ManureReporter.ch4_emissions (kg)"
    assert p_info["correlations"][0]["pearson_r"] == 0.95

    # Nonexistent parameter
    none_impact = trace_parameter_impact(conn, "nonexistent_parameter_xyz")
    assert none_impact["matched_parameters_count"] == 0
    assert none_impact["parameters"] == []


def test_lookup_variable_info_synthetic(tmp_path):
    from tools.rufas_brain import lookup_variable_info
    db_dir = str(tmp_path / "test_lookup.kuzu")
    conn = init_brain_database(db_dir)

    conn.execute("CREATE (p:InputParameter {id: 'animal.cow_num', blob_name: 'animal', param_name: 'cow_num', data_type: 'int', unit: 'animals', default_value: '100', description: 'Herd size'})")
    conn.execute("CREATE (v:OutputVariable {name: 'AnimalReporter.daily_milk (kg/day)', module: 'animal', unit: 'kg/day', category: 'production', reporter_class: 'AnimalReporter', description: 'Milk output'})")
    conn.execute("CREATE (r:SimulationRun {run_id: 'run_alpha', scenario_name: 'freestall', execution_date: '2026-08-26', start_date: '2013:1', end_date: '2013:60', duration_days: 60, random_seed: 42, status: 'completed'})")
    conn.execute("CREATE (rm:RunMetric {id: 'run_alpha::milk', run_id: 'run_alpha', var_name: 'AnimalReporter.daily_milk (kg/day)', mean_val: 3000.0, min_val: 2800.0, max_val: 3200.0, sum_val: 180000.0, non_null_count: 60})")

    # Connect edges
    conn.execute("MATCH (p:InputParameter {id: 'animal.cow_num'}), (v:OutputVariable {name: 'AnimalReporter.daily_milk (kg/day)'}) CREATE (p)-[:CAUSALLY_INFLUENCES {pathway: 'Scaling', mechanism: 'Herd size'}]->(v)")
    conn.execute("MATCH (p:InputParameter {id: 'animal.cow_num'}), (v:OutputVariable {name: 'AnimalReporter.daily_milk (kg/day)'}) CREATE (p)-[:CORRELATES_WITH {pearson_r: 0.98, spearman_r: 0.97, p_value: 0.0001, sample_size: 5}]->(v)")
    conn.execute("MATCH (r:SimulationRun {run_id: 'run_alpha'}), (rm:RunMetric {id: 'run_alpha::milk'}) CREATE (r)-[:GENERATED_METRIC]->(rm)")
    conn.execute("MATCH (rm:RunMetric {id: 'run_alpha::milk'}), (v:OutputVariable {name: 'AnimalReporter.daily_milk (kg/day)'}) CREATE (rm)-[:OF_VARIABLE]->(v)")

    # Lookup variable by partial case-insensitive query
    vars_info = lookup_variable_info(conn, "DAILY_MILK")
    assert len(vars_info) == 1
    var_meta = vars_info[0]
    assert var_meta["name"] == "AnimalReporter.daily_milk (kg/day)"
    assert var_meta["module"] == "animal"
    assert var_meta["unit"] == "kg/day"
    assert var_meta["category"] == "production"

    # Incoming causal inputs
    assert len(var_meta["causal_inputs"]) == 1
    assert var_meta["causal_inputs"][0]["param_id"] == "animal.cow_num"
    assert var_meta["causal_inputs"][0]["pathway"] == "Scaling"

    # Correlated inputs
    assert len(var_meta["correlated_inputs"]) == 1
    assert var_meta["correlated_inputs"][0]["param_id"] == "animal.cow_num"
    assert var_meta["correlated_inputs"][0]["pearson_r"] == 0.98

    # Run metrics
    assert len(var_meta["run_metrics"]) == 1
    assert var_meta["run_metrics"][0]["run_id"] == "run_alpha"
    assert var_meta["run_metrics"][0]["mean_val"] == 3000.0

    # Nonexistent lookup
    empty_lookup = lookup_variable_info(conn, "nonexistent_metric_123")
    assert empty_lookup == []


def test_cli_query_impact_and_lookup(tmp_path, monkeypatch, capsys):
    import json
    from tools.rufas_brain import main
    db_dir = str(tmp_path / "cli_test_brain.kuzu")
    conn = init_brain_database(db_dir)

    conn.execute("CREATE (p:InputParameter {id: 'cow_num', blob_name: 'animal', param_name: 'cow_num', data_type: 'int', unit: 'cows', default_value: '100', description: 'Herd size'})")
    conn.execute("CREATE (v:OutputVariable {name: 'milk_production', module: 'animal', unit: 'kg', category: 'production', reporter_class: 'AnimalReporter', description: 'Milk yield'})")
    conn.execute("MATCH (p:InputParameter {id: 'cow_num'}), (v:OutputVariable {name: 'milk_production'}) CREATE (p)-[:CAUSALLY_INFLUENCES {pathway: 'Scaling', mechanism: 'Herd count'}]->(v)")
    conn.execute("MATCH (p:InputParameter {id: 'cow_num'}), (v:OutputVariable {name: 'milk_production'}) CREATE (p)-[:CORRELATES_WITH {pearson_r: 0.99, spearman_r: 0.99, p_value: 0.001, sample_size: 5}]->(v)")

    # 1. Test CLI query (tabular and JSON)
    monkeypatch.setattr(sys, "argv", ["rufas-brain", "query", "MATCH (p:InputParameter) RETURN p.id, p.unit", "--db-path", db_dir])
    main()
    captured = capsys.readouterr()
    assert "cow_num" in captured.out

    monkeypatch.setattr(sys, "argv", ["rufas-brain", "query", "MATCH (p:InputParameter) RETURN p.id, p.unit", "--json", "--db-path", db_dir])
    main()
    captured_json = capsys.readouterr()
    data = json.loads(captured_json.out)
    assert isinstance(data, list)
    assert data[0]["p.id"] == "cow_num"

    # 2. Test CLI trace-impact (text and JSON)
    monkeypatch.setattr(sys, "argv", ["rufas-brain", "trace-impact", "--param", "cow_num", "--db-path", db_dir])
    main()
    captured_trace = capsys.readouterr()
    assert "Parameter Impact Trace" in captured_trace.out
    assert "milk_production" in captured_trace.out

    monkeypatch.setattr(sys, "argv", ["rufas-brain", "trace-impact", "--param", "cow_num", "--json", "--db-path", db_dir])
    main()
    captured_trace_json = capsys.readouterr()
    trace_data = json.loads(captured_trace_json.out)
    assert trace_data["matched_parameters_count"] == 1
    assert trace_data["parameters"][0]["id"] == "cow_num"

    # 3. Test CLI lookup-var (text and JSON)
    monkeypatch.setattr(sys, "argv", ["rufas-brain", "lookup-var", "--name", "milk_production", "--db-path", db_dir])
    main()
    captured_lookup = capsys.readouterr()
    assert "milk_production" in captured_lookup.out
    assert "AnimalReporter" in captured_lookup.out

    monkeypatch.setattr(sys, "argv", ["rufas-brain", "lookup-var", "--name", "milk_production", "--json", "--db-path", db_dir])
    main()
    captured_lookup_json = capsys.readouterr()
    lookup_data = json.loads(captured_lookup_json.out)
    assert len(lookup_data) == 1
    assert lookup_data[0]["name"] == "milk_production"





