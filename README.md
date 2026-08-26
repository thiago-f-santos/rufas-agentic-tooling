# RuFaS Agentic Tooling 🐄🌱

A specialized agentic engineering and diagnostic toolkit for **RuFaS (Ruminant Farm Systems)** whole-farm dairy simulation modeling.

---

## 🎯 Overview

RuFaS is a modular, biophysical, whole-farm simulation environment designed to simulate dairy farm production, soil-crop-animal dynamics, environmental footprint, economics, energy, and greenhouse gas (GHG) emissions.

This repository provides:
1. **RuFaS Specialist Skill (`skills/rufas-specialist/`)**: Comprehensive agent instruction guide and reference manuals for deep-domain reasoning on RuFaS daily lifecycle, biophysical subsystems, metadata hierarchy, and diagnostics.
2. **Operational Tooling (`tools/`)**:
   - `rufas_inspector.py`: Validates input metadata, schema conformity, and cross-validation rules.
   - `rufas_runner.py`: Executes RuFaS simulations with managed output filters and structured log/error capture.
   - `rufas_analyzer.py`: Parses and synthesizes output pools, mass balances, greenhouse gas emissions, and herd productivity.
3. **Skill Verification Suite (`tests/`)**: Automated TDD scenarios to test and verify agent comprehension under pressure.

---

## 📁 Repository Structure

```text
rufas-agentic-tooling/
├── AGENTS.md                          # Behavioral guidelines for AI agents
├── README.md                          # Project documentation
├── pyproject.toml                     # Python project configuration and entrypoints
├── skills/
│   └── rufas-specialist/
│       ├── SKILL.md                   # Main skill entrypoint (SDO optimized)
│       └── references/
│           ├── simulation-flow.md     # Daily orchestration sequence & cross-module data structures
│           ├── biophysical-modules.md # Animal, Field/Soil, Feed Storage, and Manure subsystems
│           ├── eee-and-lifecycle.md   # Economics, Energy, and Emissions (GHG) calculations
│           ├── input-metadata-schema.md # Metadata graph, 22 required blobs & cross-validation syntax
│           └── output-and-diagnostics.md# Output pools, prefix filtering, and error diagnosis
├── tools/
│   ├── __init__.py
│   ├── rufas_inspector.py             # CLI metadata & input validator
│   ├── rufas_runner.py                # Simulation runner & log extractor
│   └── rufas_analyzer.py              # Output CSV and metrics analyzer
└── tests/
    ├── test_scenarios.md              # TDD validation scenarios
    └── test_tooling.py                # Unit and integration tests for tools
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.12 or 3.13
- RuFaS repository cloned adjacent to this project (e.g. `../RuFaS`)

### Installation
```bash
pip install -e .
```

### CLI Tool Usage

#### 1. Inspecionar Metadados e Validação Cruzada
```bash
python -m tools.rufas_inspector --scenario ../RuFaS/input/metadata/example_freestall_dairy_metadata.json
```

#### 2. Executar Simulação RuFaS
```bash
python -m tools.rufas_runner --task-metadata ../RuFaS/input/task_manager_metadata.json --rufas-root ../RuFaS
```

#### 3. Analisar Resultados e Emissões
```bash
python -m tools.rufas_analyzer --output-dir ../RuFaS/output/
```
