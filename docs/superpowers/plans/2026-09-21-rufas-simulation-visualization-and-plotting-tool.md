# Ferramenta de Visualização e Plotagem RuFaS (`rufas-plot`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o comando CLI `rufas-plot` e a biblioteca de visualização `tools/rufas_plotter.py` no `rufas-agentic-tooling` para gerar painéis gráficos executivos (Whole-Farm 360°) e modulares em formatos estático (PNG/PDF a 300 DPI) e interativo (HTML via Plotly), com suporte a dados *ragged* e comparação de cenários.

**Architecture:** Módulo Python autônomo com leitor seletivo baseado em escaneamento de cabeçalho (`nrows=0`) e `usecols` para CSVs de 140+ MB, normalizador temporal para dados heterogêneos (*ragged* por vaca vs diário de fazenda), motor duplo de renderização (Matplotlib + Plotly), motor comparativo de cenários ($\Delta\%$) e integração direta via CLI e flag `--plot` no `rufas-analyze`.

**Tech Stack:** Python 3.11+, Pandas, Matplotlib, Plotly, NumPy, Pytest, Pillow (para validação de imagem).

**Spec:** [`docs/superpowers/specs/2026-09-21-rufas-simulation-visualization-and-plotting-tool-design.md`](../specs/2026-09-21-rufas-simulation-visualization-and-plotting-tool-design.md)

## Global Constraints

- **Python Floor:** `>=3.11`
- **Dependência Nova:** `plotly>=5.0.0` adicionada a `pyproject.toml` e instalada no `venv`.
- **Restrição de Limite RuFaS:** Validação obrigatória de caminhos via `assert_within_rufas_scope` de `tools.config`.
- **Desempenho de Leitura:** Proibido carregar CSVs inteiros com `pd.read_csv(filepath)`. Usar sempre inspeção prévia de colunas e `usecols`.
- **Normalização Temporal:** Séries de saída devem ser indexadas uniformemente por `simulation_day` ($0 \dots T-1$).
- **Exportação HTML:** Arquivos HTML devem ser 100% autossuficientes (`include_plotlyjs=True`).

---

### Task 1: Configuração do Projeto e Instalação de Dependências

**Files:**
- Modify: `pyproject.toml:13-36`
- Test: Virtual environment verification via pip

**Interfaces:**
- Produces: Ambiente com `plotly>=5.0.0` instalado e entrypoint CLI `rufas-plot = "tools.rufas_plotter:main"` registrado.

- [ ] **Step 1: Atualizar `pyproject.toml` com dependência Plotly e script `rufas-plot`**

```toml
# Em dependencies:
dependencies = [
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "deepdiff>=6.0.0",
    "jsonschema>=4.17.0",
    "kuzu>=0.11.3",
    "scipy>=1.10.0",
    "plotly>=5.0.0",
    "pillow>=10.0.0"
]

# Em [project.scripts]:
rufas-setup = "tools.rufas_setup:main"
rufas-inspect = "tools.rufas_inspector:main"
rufas-run = "tools.rufas_runner:main"
rufas-analyze = "tools.rufas_analyzer:main"
rufas-install-skills = "tools.install_skills:main"
rufas-brain = "tools.rufas_brain:main"
rufas-plot = "tools.rufas_plotter:main"
```

- [ ] **Step 2: Instalar dependências no ambiente virtual**

Run: `./venv/bin/pip install "plotly>=5.0.0" "pillow>=10.0.0" -e .`
Expected: Instalação com sucesso e `plotly` disponível no `venv`.

- [ ] **Step 3: Verificar disponibilidade do módulo Plotly**

Run: `./venv/bin/python -c "import plotly; print(plotly.__version__)"`
Expected: Versão do Plotly impressa sem erros.

- [ ] **Step 4: Commit das alterações de configuração**

```bash
git add pyproject.toml
git commit -m "build: add plotly and pillow dependencies and register rufas-plot entrypoint"
```

---

### Task 2: PresetRegistry e Scanner de Cabeçalho Seletivo

**Files:**
- Create: `tools/rufas_plotter.py`
- Create: `tests/test_rufas_plotter.py`

**Interfaces:**
- Produces:
  - `PresetRegistry`: Dicionário canônico mapeando `executive`, `animal`, `eee`, `field-crops`, `manure` para regras de resolução de variáveis.
  - `resolve_columns_for_preset(header_columns: List[str], preset: str, custom_vars: Optional[List[str]]) -> Dict[str, Any]`

- [ ] **Step 1: Escrever teste unitário com falha para o `PresetRegistry` e resolução de colunas**

Criar `tests/test_rufas_plotter.py`:
```python
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
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py::test_resolve_columns_executive_preset -v`
Expected: FAIL com `ModuleNotFoundError` ou `ImportError`.

- [ ] **Step 3: Implementar `PresetRegistry` e `resolve_columns_for_preset` em `tools/rufas_plotter.py`**

Criar `tools/rufas_plotter.py` com:
- Dicionário `PRESET_DEFINITIONS` cobrindo `executive`, `animal`, `eee`, `field-crops`, `manure`.
- Função `resolve_columns_for_preset` que mapeia padrões, resolve colunas dependentes de tempo e extrai variáveis solicitadas.

- [ ] **Step 4: Executar testes para verificar aprovação**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py -v`
Expected: PASS para ambos os testes.

- [ ] **Step 5: Commit**

```bash
git add tools/rufas_plotter.py tests/test_rufas_plotter.py
git commit -m "feat(plotter): implement PresetRegistry and selective column resolution"
```

---

### Task 3: Normalizador Temporal e Leitor de Séries Ragged (`TemporalAligner`)

**Files:**
- Modify: `tools/rufas_plotter.py`
- Modify: `tests/test_rufas_plotter.py`

**Interfaces:**
- Produces:
  - `RaggedTimeSeriesLoader.load_aligned_dataframe(csv_path: Path, preset: str, custom_vars: Optional[List[str]] = None, rolling_window: int = 30) -> AlignedSimulationData`
  - Classe de dados `AlignedSimulationData` contendo `df: pd.DataFrame` uniforme indexado por `simulation_day` e metadados das séries (unidades, títulos, agregações).

- [ ] **Step 1: Escrever teste unitário com falha para agregação de dados *ragged***

Adicionar em `tests/test_rufas_plotter.py`:
```python
import pandas as pd
import numpy as np
from tools.rufas_plotter import TemporalAligner

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

    aligner = TemporalAligner(csv_file, preset="executive")
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
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py::test_temporal_aligner_ragged_data -v`
Expected: FAIL com `NameError: TemporalAligner is not defined`.

- [ ] **Step 3: Implementar `TemporalAligner` e `RaggedTimeSeriesLoader` em `tools/rufas_plotter.py`**

Implementar:
- `TemporalAligner`: lê apenas colunas resolvidas com `usecols`, identifica colunas com `_time_col` específico ou usa `RufasTime.simulation_day`, aplica funções de agregação (`sum`, `mean`) e reindexa com `pd.RangeIndex(0, max_day + 1)`.
- Cálculo de colunas rolling: `df[f"{col}_rolling"] = df[col].rolling(window, min_periods=1).mean()`.

- [ ] **Step 4: Executar testes para verificar aprovação**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py -v`
Expected: PASS para todos os testes.

- [ ] **Step 5: Commit**

```bash
git add tools/rufas_plotter.py tests/test_rufas_plotter.py
git commit -m "feat(plotter): implement TemporalAligner for ragged RuFaS time-series"
```

---

### Task 4: Comparador de Cenários (`ScenarioComparator`)

**Files:**
- Modify: `tools/rufas_plotter.py`
- Modify: `tests/test_rufas_plotter.py`

**Interfaces:**
- Produces:
  - `ScenarioComparator.compare(baseline_data: AlignedSimulationData, scenario_data: AlignedSimulationData) -> ScenarioComparisonResult`
  - Métodos para extração de séries sobrepostas, deltas diários ($\Delta\%$) e sumário consolidado de KPIs.

- [ ] **Step 1: Escrever teste unitário com falha para o cálculo de deltas entre cenários**

Adicionar em `tests/test_rufas_plotter.py`:
```python
from tools.rufas_plotter import ScenarioComparator, AlignedSimulationData

def test_scenario_comparator_delta_calculation():
    df_base = pd.DataFrame({
        "milk_produced_total": [100.0, 100.0, 100.0],
        "methane_emission": [50.0, 50.0, 50.0]
    }, index=[0, 1, 2])
    
    df_scen = pd.DataFrame({
        "milk_produced_total": [105.0, 110.0, 100.0],
        "methane_emission": [45.0, 40.0, 45.0]
    }, index=[0, 1, 2])

    base = AlignedSimulationData(df=df_base, name="Baseline", units={"milk_produced_total": "kg/day", "methane_emission": "g/day"})
    scen = AlignedSimulationData(df=df_scen, name="Treatment", units={"milk_produced_total": "kg/day", "methane_emission": "g/day"})

    comp = ScenarioComparator(base, [scen])
    result = comp.compute_deltas()

    # Leite no dia 1 aumentou 10%
    assert result.scenarios[0].pct_deltas["milk_produced_total"][1] == 10.0
    # Metano no dia 1 reduziu 20%
    assert result.scenarios[0].pct_deltas["methane_emission"][1] == -20.0
    # Resumo anual acumulado
    summary = comp.get_kpi_summary()
    assert summary["Treatment"]["methane_emission"]["total_delta_pct"] == pytest.approx(-13.33, rel=1e-2)
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py::test_scenario_comparator_delta_calculation -v`
Expected: FAIL com `NameError: ScenarioComparator is not defined`.

- [ ] **Step 3: Implementar `ScenarioComparator` em `tools/rufas_plotter.py`**

Implementar classes e métodos de alinhamento temporal mútuo, cálculo seguro de deltas com tratamento de divisão por zero (`np.where(base == 0, 0, (scen - base) / base * 100)`), e resumo estatístico de métricas-chave.

- [ ] **Step 4: Executar testes para verificar aprovação**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py -v`
Expected: PASS para todos os testes.

- [ ] **Step 5: Commit**

```bash
git add tools/rufas_plotter.py tests/test_rufas_plotter.py
git commit -m "feat(plotter): implement ScenarioComparator for A/B delta analytics"
```

---

### Task 5: Motor de Renderização Estática (`MatplotlibRenderer`)

**Files:**
- Modify: `tools/rufas_plotter.py`
- Modify: `tests/test_rufas_plotter.py`

**Interfaces:**
- Produces:
  - `MatplotlibRenderer.render(data: AlignedSimulationData, output_path: Path, comparison: Optional[ScenarioComparisonResult] = None, dpi: int = 300) -> Path`

- [ ] **Step 1: Escrever teste unitário com falha para renderização de imagem PNG válida**

Adicionar em `tests/test_rufas_plotter.py`:
```python
from PIL import Image
from tools.rufas_plotter import MatplotlibRenderer

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
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py::test_matplotlib_renderer_creates_valid_png -v`
Expected: FAIL com `NameError: MatplotlibRenderer is not defined`.

- [ ] **Step 3: Implementar `MatplotlibRenderer` em `tools/rufas_plotter.py`**

Implementar geração de figuras:
- Configuração de estilo: grid discreto, paletas de cores (`#1f77b4`, `#2ca02c`, `#d62728`, `#9467bd`, etc.).
- Subplots para preset `executive` (grid 3x2) e modulares (grid 2x2).
- Plotagem de série diária suavizada + linha sólida de média móvel.
- Se houver `ScenarioComparisonResult`, sobrepor curvas com estilos de linha (`-`, `--`, `:`) e adicionar subpainel de delta percentual.
- Exportação segura fechando figuras com `plt.close(fig)` para evitar vazamento de memória.

- [ ] **Step 4: Executar testes para verificar aprovação**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py -v`
Expected: PASS para todos os testes.

- [ ] **Step 5: Commit**

```bash
git add tools/rufas_plotter.py tests/test_rufas_plotter.py
git commit -m "feat(plotter): implement MatplotlibRenderer for publication-quality PNG/PDF"
```

---

### Task 6: Motor de Renderização Interativa (`PlotlyRenderer`)

**Files:**
- Modify: `tools/rufas_plotter.py`
- Modify: `tests/test_rufas_plotter.py`

**Interfaces:**
- Produces:
  - `PlotlyRenderer.render(data: AlignedSimulationData, output_path: Path, comparison: Optional[ScenarioComparisonResult] = None) -> Path`

- [ ] **Step 1: Escrever teste unitário com falha para exportação de HTML interativo autônomo**

Adicionar em `tests/test_rufas_plotter.py`:
```python
from tools.rufas_plotter import PlotlyRenderer

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
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py::test_plotly_renderer_creates_standalone_html -v`
Expected: FAIL com `NameError: PlotlyRenderer is not defined`.

- [ ] **Step 3: Implementar `PlotlyRenderer` em `tools/rufas_plotter.py`**

Implementar geração de dashboard interativo:
- `make_subplots` com `shared_xaxes=True`.
- Hovertemplate com dia de simulação e valor com unidade formatada.
- Adição de range slider no eixo inferior.
- Exportação com `fig.write_html(str(output_path), include_plotlyjs=True, full_html=True)`.

- [ ] **Step 4: Executar testes para verificar aprovação**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py -v`
Expected: PASS para todos os testes.

- [ ] **Step 5: Commit**

```bash
git add tools/rufas_plotter.py tests/test_rufas_plotter.py
git commit -m "feat(plotter): implement PlotlyRenderer for standalone interactive HTML dashboards"
```

---

### Task 7: Orquestrador da API (`generate_plots`) e CLI `rufas-plot`

**Files:**
- Modify: `tools/rufas_plotter.py`
- Modify: `tests/test_rufas_plotter.py`

**Interfaces:**
- Produces:
  - `generate_plots(...) -> Dict[str, Any]`
  - `main()` com parser `argparse` e validação de escopo via `assert_within_rufas_scope`.

- [ ] **Step 1: Escrever teste de integração para `generate_plots` e CLI**

Adicionar em `tests/test_rufas_plotter.py`:
```python
from tools.rufas_plotter import generate_plots

def test_generate_plots_end_to_end_on_real_csv(tmp_path):
    real_csv = Path("/home/thiago/Projects/RuFaS/output/CSVs/Minas_Gerais_Pilot_saved_variables_csv_all_variables.txt_21-Sep-2026_Mon_11-14-15.csv")
    if not real_csv.exists():
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
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py::test_generate_plots_end_to_end_on_real_csv -v`
Expected: FAIL com `ImportError` ou `NameError: generate_plots is not defined`.

- [ ] **Step 3: Implementar `generate_plots` e `main()` CLI em `tools/rufas_plotter.py`**

Implementar:
- Validação de escopo com `assert_within_rufas_scope`.
- Detecção automática do último CSV se `input_path` for omitido ou apontar para um diretório.
- Orquestração dos passos de carregamento seletivo, alinhamento temporal, comparação e renderização dupla.
- CLI com `argparse` e código de saída 0 para sucesso, 1 para falha com mensagem explicativa.

- [ ] **Step 4: Executar testes para verificar aprovação**

Run: `./venv/bin/pytest tests/test_rufas_plotter.py -v`
Expected: PASS para toda a suíte de testes do plotter.

- [ ] **Step 5: Testar o comando CLI diretamente no terminal**

Run: `./venv/bin/python tools/rufas_plotter.py --help`
Expected: Exibição completa da mensagem de ajuda da CLI.

- [ ] **Step 6: Commit**

```bash
git add tools/rufas_plotter.py tests/test_rufas_plotter.py
git commit -m "feat(plotter): implement generate_plots API orchestrator and rufas-plot CLI"
```

---

### Task 8: Integração no `rufas_analyzer.py` e Atualização de Skills

**Files:**
- Modify: `tools/rufas_analyzer.py:270-300`
- Modify: `skills/rufas/SKILL.md`
- Test: `tests/test_rufas_analyzer.py`

**Interfaces:**
- Produces:
  - Flag `--plot` disponível em `rufas-analyze`.
  - Skill `rufas` documentando o uso do visualizador e da geração de gráficos para os agentes.

- [ ] **Step 1: Adicionar teste para flag `--plot` no `rufas_analyzer`**

Em `tests/test_rufas_analyzer.py`:
```python
from tools.rufas_analyzer import parse_arguments

def test_analyzer_cli_supports_plot_flag():
    args = parse_arguments(["output/", "--plot"])
    assert args.plot is True
```

- [ ] **Step 2: Implementar flag `--plot` no `tools/rufas_analyzer.py`**

Adicionar:
```python
parser.add_argument("--plot", action="store_true", help="Gera automaticamente painéis gráficos da simulação.")
```
E na execução principal, se `args.plot`:
```python
from tools.rufas_plotter import generate_plots
generate_plots(output_dir=target_dir, preset="executive", output_format="both")
```

- [ ] **Step 3: Documentar o `rufas-plot` em `skills/rufas/SKILL.md`**

Adicionar seção com instruções de uso do `rufas-plot`, presets e opções para que o agente Antigravity saiba quando e como gerar gráficos ao analisar simulações.

- [ ] **Step 4: Executar suíte completa de testes de regressão**

Run: `./venv/bin/pytest tests/ -v`
Expected: Todos os testes passando sem erros.

- [ ] **Step 5: Commit**

```bash
git add tools/rufas_analyzer.py skills/rufas/SKILL.md tests/test_rufas_analyzer.py
git commit -m "feat(analyzer): add --plot flag and document rufas-plot in rufas skill"
```
