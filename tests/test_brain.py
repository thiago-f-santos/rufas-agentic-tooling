import sys
from pathlib import Path
import pytest
import kuzu

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.rufas_brain import init_brain_database, populate_structural_ontology


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

