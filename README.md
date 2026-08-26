# RuFaS Agentic Tooling 🐄🌱

A specialized agentic engineering and diagnostic toolkit for **RuFaS (Ruminant Farm Systems)** whole-farm dairy simulation modeling.

---

## 🎯 Overview

RuFaS is a modular, biophysical, whole-farm simulation environment designed to simulate dairy farm production, soil-crop-animal dynamics, environmental footprint, economics, energy, and greenhouse gas (GHG) emissions.

This repository provides:
1. **RuFaS Specialist Skills Suite (`skills/`)**:
   - `rufas-specialist`: Whole-system architecture, simulation engine lifecycle, metadata graph, runner and diagnostics.
   - `rufas-animal-specialist`: Herd demographics, lactation curves (Wood/Dijkstra), NASEM/NRC LP ration formulation, enteric methane ($\text{CH}_4$), and excretion.
   - `rufas-field-soil-specialist`: Multi-layer soil water balance, N/P/C biogeochemistry, crop growth (GDD/RUE), management schedules, and harvests.
   - `rufas-feed-storage-specialist`: Storage structures (silos, bunkers, bags), degradation/spoilage, inventory forecasting, and feed fulfillment.
   - `rufas-manure-specialist`: Barn collection, solid-liquid separation, storage lagoons, anaerobic digestion, gaseous emissions ($\text{CH}_4, \text{NH}_3, \text{N}_2\text{O}$), and field application.
   - `rufas-eee-specialist`: Economics (IOFC, COP), ASABE tractor machinery fuel, electricity, and Scope 1-3 GHG lifecycle accounting.
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
│   ├── rufas-specialist/              # System-level specialist
│   │   ├── SKILL.md
│   │   └── references/                # In-depth architectural references
│   ├── rufas-animal-specialist/       # Animal & herd specialist
│   │   └── SKILL.md
│   ├── rufas-field-soil-specialist/   # Field, soil & crop specialist
│   │   └── SKILL.md
│   ├── rufas-feed-storage-specialist/ # Feed storage & inventory specialist
│   │   └── SKILL.md
│   ├── rufas-manure-specialist/       # Manure management & treatment specialist
│   │   └── SKILL.md
│   └── rufas-eee-specialist/          # Economics, energy & emissions specialist
│       └── SKILL.md
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

---

## 🧠 Installing Skills in AI Assistants & CLI Tools

The skills in this suite adhere to the open [Agent Skills Specification](https://agentskills.io/specification) (`SKILL.md` format) and can be loaded automatically into major AI coding assistants and CLI tools.

### ⚡ Automated One-Step Installation

Use the built-in installer to deploy all 6 specialist skills into all detected CLI environments:

```bash
# Install to all supported AI CLIs at once (Universal, Claude, Antigravity)
python -m tools.install_skills --runtime all

# Or install into a specific target project repository (e.g. RuFaS)
python -m tools.install_skills --project-repo ../RuFaS
```

---

### 🔧 Manual Installation by AI Assistant / CLI Runtime

#### 1. Google Antigravity (`agy` / Antigravity CLI)
Antigravity discovers skills in user-level and project-level directories:
- **User-Level (Global across all projects)**:
  ```bash
  mkdir -p ~/.gemini/antigravity-cli/skills ~/.agents/skills
  cp -r skills/* ~/.agents/skills/
  cp -r skills/* ~/.gemini/antigravity-cli/skills/
  ```
- **Project-Level (Workspace specific)**:
  ```bash
  mkdir -p /path/to/RuFaS/.agents/skills
  cp -r skills/* /path/to/RuFaS/.agents/skills/
  ```

#### 2. Anthropic Claude Code (`claude`)
Claude Code automatically indexes skills from `~/.claude/skills/` or the project root:
- **User-Level (Global across all sessions)**:
  ```bash
  mkdir -p ~/.claude/skills
  cp -r skills/* ~/.claude/skills/
  ```
- **Project-Level**:
  ```bash
  mkdir -p /path/to/project/.claude/skills
  cp -r skills/* /path/to/project/.claude/skills/
  ```

#### 3. GitHub Copilot CLI (`gh copilot` / Copilot Workspace)
Copilot CLI recognizes standard agent skill folders at user and repo roots:
- **User-Level**:
  ```bash
  mkdir -p ~/.agents/skills
  cp -r skills/* ~/.agents/skills/
  ```
- **Repository-Level**:
  ```bash
  mkdir -p /path/to/RuFaS/.agents/skills
  cp -r skills/* /path/to/RuFaS/.agents/skills/
  ```

#### 4. OpenAI Codex, Gemini CLI, Cursor, Windsurf & Generic Agent Frameworks
Modern agentic runtimes adopting the `agentskills.io` standard load from the universal alias directory:
- **Global**:
  ```bash
  mkdir -p ~/.agents/skills
  cp -r skills/* ~/.agents/skills/
  ```
- **Project Root**:
  ```bash
  mkdir -p .agents/skills
  cp -r skills/* .agents/skills/
  ```

---

### 🎯 Verifying Installed Skills

Once installed, AI assistants will automatically discover and invoke the appropriate specialist when asked domain-specific questions, or you can invoke them directly using slash commands or mentions (e.g. `/rufas-specialist`, `/rufas-animal-specialist`, `/rufas-field-soil-specialist`, `/rufas-feed-storage-specialist`, `/rufas-manure-specialist`, `/rufas-eee-specialist`).

