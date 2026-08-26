import sys
from pathlib import Path
import pytest
import kuzu

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.rufas_brain import init_brain_database


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
