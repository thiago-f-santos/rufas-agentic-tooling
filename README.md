# RuFaS Agentic Tooling 🐄🌱

A specialized agentic engineering, knowledge graph, and diagnostic toolkit for **RuFaS (Ruminant Farm Systems)** whole-farm dairy simulation modeling.

---

## 🎯 Overview

RuFaS is a modular, biophysical, whole-farm simulation environment designed to simulate dairy farm production, soil-crop-animal dynamics, environmental footprint, economics, energy, and greenhouse gas (GHG) emissions.

This repository provides:
1. **RuFaS Specialist Skills Suite (`skills/`)** — 7 domain specialist skills adhering to the open [Agent Skills Specification](https://agentskills.io/specification):
   - `rufas`: Whole-system architecture, simulation engine lifecycle, metadata graph, runner, and system diagnostics.
   - `rufas-animal`: Herd demographics, lactation curves (Wood/Dijkstra), NASEM/NRC LP ration formulation, enteric methane ($\text{CH}_4$), and excretion.
   - `rufas-field`: Multi-layer soil water balance, N/P/C biogeochemistry, crop growth (GDD/RUE), management schedules, and harvests.
   - `rufas-feed`: Storage structures (silos, bunkers, bags), degradation/spoilage, inventory forecasting, and feed fulfillment.
   - `rufas-manure`: Barn collection, solid-liquid separation, storage lagoons, anaerobic digestion, gaseous emissions ($\text{CH}_4, \text{NH}_3, \text{N}_2\text{O}$), and field application.
   - `rufas-eee`: Economics (IOFC, COP), ASABE tractor machinery fuel, electricity, and Scope 1-3 GHG lifecycle accounting.
   - `rufas-brain`: Embedded Graph Memory Brain on KùzuDB (`kuzu`), structural biophysical ontology, cross-run statistical correlation engine (Pearson $r$, Spearman $\rho$, $p$-values), causal impact tracing, 2,038 output variable catalog, OpenCypher queries, and Obsidian knowledge vault generation.
2. **Operational & Intelligence Tooling (`tools/`)**:
   - `rufas_inspector.py` (`rufas-inspect`): Validates input metadata, JSON schema conformity, and cross-validation rules across 22 configuration blobs.
   - `rufas_runner.py` (`rufas-run`): Executes RuFaS simulations with managed output filters and structured log/error capture.
   - `rufas_analyzer.py` (`rufas-analyze`): Parses and synthesizes output pools, mass balances, greenhouse gas emissions, and herd productivity.
   - `rufas_brain.py` (`rufas-brain`): Embedded property graph database (KùzuDB) for biophysical ontology, simulation history, cross-run statistical correlations, causal impact tracing, variable lookups, and Obsidian knowledge vault export.
   - `install_skills.py` (`rufas-install-skills`): Multi-runtime CLI installer to automatically deploy specialist skills into Universal (`~/.agents/skills`), Claude Code (`~/.claude/skills`), Google Antigravity (`~/.gemini/antigravity-cli/skills`), GitHub Copilot CLI, or target project repositories.
3. **Obsidian Knowledge Graph (`vault/`)**:
   - Interactive Markdown knowledge graph with 2,038 output variables, input parameter dictionaries, biophysical causal paths, and dynamic Dataview DQL dashboards.
4. **Skill Verification Suite (`tests/`)**:
   - Automated TDD scenarios and unit tests verifying tool robustness, graph schema integrity, and agent comprehension under pressure.

---

## 📁 Repository Structure

```text
rufas-agentic-tooling/
├── AGENTS.md                          # Behavioral guidelines for AI agents
├── README.md                          # Project documentation
├── pyproject.toml                     # Python packaging & CLI console script entrypoints
├── data/                              # Embedded database storage (e.g. rufas_brain.kuzu)
├── docs/                              # Architectural guides and documentation
├── skills/                            # Specialist Skills Suite (agentskills.io standard)
│   ├── rufas/                         # System-level specialist & simulation lifecycle
│   │   ├── SKILL.md
│   │   └── references/                # In-depth architectural references
│   ├── rufas-animal/                  # Animal & herd specialist
│   │   └── SKILL.md
│   ├── rufas-field/                   # Field, soil & crop specialist
│   │   └── SKILL.md
│   ├── rufas-feed/                    # Feed storage & inventory specialist
│   │   └── SKILL.md
│   ├── rufas-manure/                  # Manure management & treatment specialist
│   │   └── SKILL.md
│   ├── rufas-eee/                     # Economics, energy & emissions specialist
│   │   └── SKILL.md
│   └── rufas-brain/                   # Graph Memory Brain & Correlation Engine specialist
│       ├── SKILL.md
│       └── references/                # Graph schema & Cypher query references
├── tools/                             # Core CLI & Python operational tools
│   ├── __init__.py
│   ├── rufas_inspector.py             # CLI metadata & input validator (`rufas-inspect`)
│   ├── rufas_runner.py                # Simulation runner & log extractor (`rufas-run`)
│   ├── rufas_analyzer.py              # Output CSV and metrics analyzer (`rufas-analyze`)
│   ├── rufas_brain.py                 # Graph Memory Brain & OpenCypher engine (`rufas-brain`)
│   └── install_skills.py              # Multi-runtime skill installer (`rufas-install-skills`)
├── vault/                             # Generated Obsidian Knowledge Graph Vault
│   ├── 00_Dashboard.md                # Interactive Dataview dashboard
│   ├── 01_Simulations/                # Simulation run notes & metric summaries
│   ├── 02_Parameters/                 # Parameter dictionary & causal relationships
│   ├── 03_Outputs/                    # 2,038 output variable notes with metadata & units
│   ├── 04_Correlations/               # Cross-run statistical correlation notes
│   └── 05_Modules/                    # 5 canonical module overview notes
└── tests/
    ├── test_scenarios.md              # TDD validation scenarios
    ├── test_tooling.py                # Unit and integration tests for tools
    └── test_brain.py                  # Unit and integration tests for Graph Memory Brain
```

---

## 🚀 Getting Started

### Prerequisites
- Python >= 3.11 (tested on 3.11, 3.12, 3.13)
- RuFaS repository cloned adjacent to this project (e.g. `../RuFaS`)

### Installation
```bash
# Clone the repository
git clone git@github.com:thiago-f-santos/rufas-agentic-tooling.git
cd rufas-agentic-tooling

# Install in editable mode with all dependencies
pip install -e .
```

---

## 🛠️ CLI Tool Usage

Each tool can be run directly using its CLI console script or as a Python module (`python -m tools.<tool_name>`).

### 1. Inspecionar Metadados e Validação Cruzada (`rufas-inspect`)
Valida a integridade dos metadados de cenário ou gerenciador de tarefas em relação aos esquemas e aos 22 arquivos de configuração obrigatórios:
```bash
# Via console script
rufas-inspect --scenario ../RuFaS/input/metadata/example_freestall_dairy_metadata.json

# Via módulo Python
python -m tools.rufas_inspector --scenario ../RuFaS/input/metadata/example_freestall_dairy_metadata.json
```

### 2. Executar Simulação RuFaS (`rufas-run`)
Executa simulações completas do RuFaS com controle de saída, filtros de log e captura estruturada de erros:
```bash
# Executar simulação apontando para os metadados do gerenciador de tarefas
rufas-run --task-metadata ../RuFaS/input/task_manager_metadata.json --rufas-root ../RuFaS
```

### 3. Analisar Resultados e Emissões (`rufas-analyze`)
Sintetiza saídas CSV geradas por simulações, calculando balanço de massa, emissões e métricas por subsistema:
```bash
# Analisar diretório de saída
rufas-analyze --output-dir ../RuFaS/output/

# Exportar sumário estruturado em JSON
rufas-analyze --output-dir ../RuFaS/output/ --json
```

### 4. Graph Memory Brain & Motor de Correlação (`rufas-brain`)
Gerencia o grafo de propriedades KùzuDB unificando ontologia biofísica, histórico de simulações, correlações estatísticas e exportação para Obsidian:

```bash
# 1. Inicializar o banco de dados KùzuDB e popular ontologia biofísica
rufas-brain init --db-path data/rufas_brain.kuzu --rufas-root ../RuFaS

# 2. Ingerir uma simulação executada a partir do diretório de saída CSV
rufas-brain ingest --output-dir ../RuFaS/output --run-id freestall_baseline --scenario example_freestall

# 3. Computar correlações estatísticas cruzadas entre todas as simulações ingeridas
rufas-brain compute-correlations --min-r 0.5 --max-p 0.05 --min-samples 3

# 4. Executar consultas OpenCypher (tabela formatada ou JSON)
rufas-brain query "MATCH (m:Module) RETURN m.name, m.manager_class"
rufas-brain query "MATCH (p:InputParameter)-[r:CORRELATES_WITH]->(v:OutputVariable) RETURN p.id, v.name, r.pearson_r LIMIT 10" --json

# 5. Rastrear caminhos causais e impactos de parâmetros
rufas-brain trace-impact --param cow_num
rufas-brain trace-impact --param mature_body_weight --json

# 6. Consultar catálogo de variáveis de saída (2.038 variáveis)
rufas-brain lookup-var --name daily_milk_production
rufas-brain lookup-var --name enteric_methane --json

# 7. Exportar cofre de conhecimento interativo para o Obsidian
rufas-brain export-obsidian --output-dir vault/
```

### 5. Instalador Automatizado de Skills (`rufas-install-skills`)
Instala e valida as 7 specialist skills em todos os ambientes de assistentes de IA detectados:
```bash
# Instalar em todos os runtimes suportados (Universal, Claude Code, Antigravity)
rufas-install-skills --runtime all

# Instalar na pasta .agents/skills/ de um repositório alvo (ex: ../RuFaS)
rufas-install-skills --project-repo ../RuFaS

# Executar validação prévia sem copiar arquivos
rufas-install-skills --dry-run
```

---

## 🧠 Installing Skills in AI Assistants & CLI Tools

The skills in this suite adhere to the open [Agent Skills Specification](https://agentskills.io/specification) (`SKILL.md` format) and can be loaded automatically into major AI coding assistants and CLI tools.

### ⚡ Automated One-Step Installation

Use the built-in installer to deploy all **7 specialist skills** into all detected CLI environments:

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

Once installed, AI assistants will automatically discover and invoke the appropriate specialist when asked domain-specific questions, or you can invoke them directly using slash commands or mentions:
- `/rufas`: System architecture & simulation engine lifecycle
- `/rufas-animal`: Herd biology, rations, lactation & animal emissions
- `/rufas-field`: Soil water, biogeochemistry, crops & harvests
- `/rufas-feed`: Feed storage degradation, spoilage & inventories
- `/rufas-manure`: Barn collection, lagoons, digesters & field application
- `/rufas-eee`: Economics, energy, fuel, electricity & Scope 1-3 GHG
- `/rufas-brain`: Graph Memory Brain, causal discovery, correlation engine & variable catalog queries

---

## 🧪 Testing & Verification

Run the test suite to verify tool functionality and skill compliance:
```bash
# Run unit & integration tests
pytest tests/ -v
```

---

## 📄 License

This project is licensed under the Apache 2.0 License.

