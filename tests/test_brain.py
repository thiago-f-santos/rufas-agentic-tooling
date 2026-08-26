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


