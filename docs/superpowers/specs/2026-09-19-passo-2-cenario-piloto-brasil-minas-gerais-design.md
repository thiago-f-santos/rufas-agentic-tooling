# Especificação Técnica: Passo 2 - Preparação do Cenário Piloto Brasileiro (Minas Gerais)

**Data:** 19 de Setembro de 2026  
**Status:** Aprovado  
**Tipo:** Arquitetural (Design Spec)  
**Alvo:** `RuFaS/input/` (Cenário Piloto)  

---

## 1. Visão Geral e Objetivos

Esta especificação define os requisitos, a estrutura de arquivos e o mapeamento de fontes de dados para criar o primeiro cenário piloto funcional do RuFaS no Brasil, focado em **Minas Gerais** (`*_minas_gerais.*`).

O objetivo é estabelecer um padrão regional reutilizável: condições climáticas e perfis de solo são ativos regionais compartilhados por fazendas da mesma bacia leiteira, variando entre fazendas apenas o tamanho de área, o número de vacas, o nível de produção de leite e decisões de manejo.

A especificação define:
1. **Dados Climáticos e de Localização:** Definição do município de referência (Patos de Minas - MG), coordenadas geográficas no Hemisfério Sul e estrutura da série temporal diária de 8 colunas.
2. **Esqueleto de Solo e Guia de Mapeamento Científico:** Modelagem do Latossolo Vermelho em 4 camadas (com camada de topo de 20 mm), fornecendo o esqueleto JSON completo e o mapeamento campo a campo para bases da Embrapa Solos, ISRIC SoilGrids e funções de pedotransferência tropicais.
3. **Esqueleto do Talhão e Metadados do Cenário:** Estruturação do `field_minas_gerais.json`, amarração dos 22 blobs obrigatórios em `cenario_minas_gerais_metadata.json` e protocolo de execução/validação.

---

## 2. Seção 1: Definição da Fazenda Piloto (Localização e Clima)

### 2.1 Identificação Geográfica e Administrativa
* **Município de Referência:** Patos de Minas – MG (Cerrado Mineiro / Alto Paranaíba).
* **Código IBGE do Município:** `3148004`
* **Código IBGE do Estado (UF):** `31` (Minas Gerais)
* **Coordenadas Centrais:**
  - **Latitude:** `-18.5789` (Hemisfério Sul, graus decimais negativos)
  - **Longitude:** `-46.5181` (graus decimais)
  - **Altitude:** $\approx 830\text{ metros}$

### 2.2 Período Temporal da Simulação
* **Intervalo:** 2 anos civis completos (`01/01/2021` a `31/12/2022`, dias `2021:1` a `2022:365`).
* **Justificativa:** Avalia duas safras de verão completas (outubro a março) e dois períodos secos de inverno (maio a agosto), confirmando a sazonalidade do Hemisfério Sul.

### 2.3 Série Temporal Diária de Clima: `weather_minas_gerais.csv`
Localizado em `input/data/weather/weather_minas_gerais.csv`. Deve conter as 8 colunas obrigatórias:

| Coluna | Unidade | Descrição e Comportamento Típico em Minas Gerais | Fonte Recomendada |
|---|---|---|---|
| `year` | Ano | `2021` e `2022` | INMET / NASA POWER |
| `jday` | Dia do ano | $1 - 365$ | INMET / NASA POWER |
| `high` | $^\circ\text{C}$ | Temperatura máxima diária ($25^\circ\text{C}$ a $33^\circ\text{C}$) | Estação INMET Patos de Minas (A534) ou NASA POWER |
| `low` | $^\circ\text{C}$ | Temperatura mínima diária ($11^\circ\text{C}$ a $19^\circ\text{C}$) | Estação INMET Patos de Minas (A534) ou NASA POWER |
| `avg` | $^\circ\text{C}$ | Temperatura média diária ($19^\circ\text{C}$ a $25^\circ\text{C}$) | Média calculada ou observada |
| `precip` | $\text{mm}$ | Precipitação pluviométrica diária (pluviometria anual $\sim 1.400\text{ mm}$) | Estação INMET Patos de Minas (A534) ou NASA POWER |
| `Hday` | $\text{MJ/m}^2$ | Radiação solar global incidente diária ($15$ a $25\text{ MJ/m}^2$) | NASA POWER (variável `ALLSKY_SFC_SW_DWN`) |
| `irrigation`| $\text{mm}$ | Irrigação suplementar via arquivo de clima (padrão `0.0`) | RuFaS default |

### 2.4 Arquivo de Configuração Geral: `config_minas_gerais.json`
Localizado em `input/data/config/config_minas_gerais.json`:
```json
{
    "country": "BRA",
    "region_code": 3148004,
    "start_date": "2021:1",
    "end_date": "2022:365",
    "set_seed": true,
    "simulation_type": "full_farm",
    "nutrient_standard": "NASEM",
    "include_detailed_values": false
}
```

---

## 3. Seção 2: Estrutura-Base de Solo e Guia de Mapeamento Científico

### 3.1 Esqueleto Base do Solo: `input/data/soil/soil_minas_gerais.json`
Arquivo estrutural pronto para ser populado pelas bases de pesquisa ou pelo modelador:

```json
{
    "second_moisture_condition_parameter": null,
    "average_subbasin_slope": null,
    "slope_length": null,
    "manning_roughness_coefficient": null,
    "albedo": null,
    "soil_evaporation_compensation_coefficient": 0.95,
    "initial_residue": null,
    "soil_layers": [
        {
            "bottom_depth": 20,
            "soil_water_concentration": null,
            "wilting_point_water_concentration": null,
            "field_capacity_water_concentration": null,
            "saturation_point_water_concentration": null,
            "saturated_hydraulic_conductivity": null,
            "initial_temperature": null,
            "bulk_density": null,
            "organic_carbon_fraction": null,
            "clay_fraction": null,
            "silt_fraction": null,
            "sand_fraction": null,
            "rock_fraction": 0.0,
            "pH": null,
            "initial_labile_inorganic_phosphorus_concentration": null,
            "initial_soil_nitrate_concentration": null,
            "initial_soil_ammonium_concentration": null,
            "ammonium_volatilization_cation_exchange_factor": 0.45
        },
        {
            "bottom_depth": 200,
            "soil_water_concentration": null,
            "wilting_point_water_concentration": null,
            "field_capacity_water_concentration": null,
            "saturation_point_water_concentration": null,
            "saturated_hydraulic_conductivity": null,
            "initial_temperature": null,
            "bulk_density": null,
            "organic_carbon_fraction": null,
            "clay_fraction": null,
            "silt_fraction": null,
            "sand_fraction": null,
            "rock_fraction": 0.0,
            "pH": null,
            "initial_labile_inorganic_phosphorus_concentration": null,
            "initial_soil_nitrate_concentration": null,
            "initial_soil_ammonium_concentration": null,
            "ammonium_volatilization_cation_exchange_factor": 0.45
        },
        {
            "bottom_depth": 600,
            "soil_water_concentration": null,
            "wilting_point_water_concentration": null,
            "field_capacity_water_concentration": null,
            "saturation_point_water_concentration": null,
            "saturated_hydraulic_conductivity": null,
            "initial_temperature": null,
            "bulk_density": null,
            "organic_carbon_fraction": null,
            "clay_fraction": null,
            "silt_fraction": null,
            "sand_fraction": null,
            "rock_fraction": 0.0,
            "pH": null,
            "initial_labile_inorganic_phosphorus_concentration": null,
            "initial_soil_nitrate_concentration": null,
            "initial_soil_ammonium_concentration": null,
            "ammonium_volatilization_cation_exchange_factor": 0.45
        },
        {
            "bottom_depth": 1500,
            "soil_water_concentration": null,
            "wilting_point_water_concentration": null,
            "field_capacity_water_concentration": null,
            "saturation_point_water_concentration": null,
            "saturated_hydraulic_conductivity": null,
            "initial_temperature": null,
            "bulk_density": null,
            "organic_carbon_fraction": null,
            "clay_fraction": null,
            "silt_fraction": null,
            "sand_fraction": null,
            "rock_fraction": 0.0,
            "pH": null,
            "initial_labile_inorganic_phosphorus_concentration": null,
            "initial_soil_nitrate_concentration": null,
            "initial_soil_ammonium_concentration": null,
            "ammonium_volatilization_cation_exchange_factor": 0.45
        }
    ]
}
```

### 3.2 Guia de Mapeamento: Fontes Científicas e Fórmulas de Conversão

| Campo no JSON | Definição no RuFaS | Fonte Embrapa Solos / SiBCS | Fonte ISRIC SoilGrids API | Pedotransferência / Cálculo (Tomasella et al.) |
|---|---|---|---|---|
| `second_moisture_condition_parameter` | Número de Curva SCS ($CN_2$) | Grupo Hidrológico de Latossolos (A ou B) | — | Tabelas SCS/USDA sob boa pastagem ($65 - 72$) |
| `average_subbasin_slope` | Declividade média ($m/m$) | Descrição do relevo do perfil (plano $0.01$, suave $0.03$) | MDE / SRTM nas coordenadas | MDE / Topografia local |
| `slope_length` | Comprimento da rampa ($m$) | Medição de campo | MDE | Vertente local ($20 - 50\text{ m}$) |
| `albedo` | Reflexão solar superficial ($0-1$) | Cor do solo úmido/seco | MODIS Albedo ($0.12 - 0.16$) | — |
| `initial_residue` | Palhada inicial ($\text{kg/ha}$) | Manejo informado | — | Manejo informado ($300 - 1000\text{ kg/ha}$) |
| `bottom_depth` | Profundidade da camada ($\text{mm}$) | Base do horizonte em cm $\times 10$ | Camadas padrão em cm $\times 10$ | $20, 200, 600, 1500\text{ mm}$ |
| `clay_fraction` | Fração de argila ($0-1$) | $\text{Argila \%} / 100$ | Variável `clay` ($\text{g/kg}$) $/ 1000$ | Granulometria |
| `silt_fraction` | Fração de silte ($0-1$) | $\text{Silte \%} / 100$ | Variável `silt` ($\text{g/kg}$) $/ 1000$ | Granulometria |
| `sand_fraction` | Fração de areia ($0-1$) | $\text{Areia total \%} / 100$ | Variável `sand` ($\text{g/kg}$) $/ 1000$ | Granulometria |
| `bulk_density` | Densidade aparente ($\text{Mg/m}^3$) | Densidade do solo ($\text{g/cm}^3$) | Variável `bdod` ($\text{cg/cm}^3$) $/ 100$ | Densidade aparente ($0.95 - 1.20$ em Latossolos) |
| `pH` | Acidez | $\text{pH em H}_2\text{O}$ | Variável `phh2o` $/ 10$ | Análise química de solo |
| `organic_carbon_fraction` | Carbono orgânico ($0-1$) | $\text{C-orgânico (g/kg)} / 1000$ | Variável `soc` ($\text{dg/kg}$) $/ 1000$ | $(\text{MO \%} / 1.724) / 100$ |
| `initial_labile_inorganic_phosphorus_concentration` | Fósforo lábil inicial ($\text{mg/kg}$) | P assimilável Mehlich-1 ($\text{mg/dm}^3$) | Análise química da fazenda | Mehlich-1 ou Resina |
| `wilting_point_water_concentration` | Ponto de murcha ($\text{mm/mm}$) | Umidade a $-1500\text{ kPa}$ | — | Tomasella et al. (2000): $\theta(-1500\text{ kPa})$ |
| `field_capacity_water_concentration` | Capacidade de campo ($\text{mm/mm}$) | Umidade a $-10$ ou $-33\text{ kPa}$ | — | Tomasella et al. (2000): $\theta(-10\text{ kPa})$ |
| `saturation_point_water_concentration` | Saturação ($\text{mm/mm}$) | Porosidade Total ($\text{PT}$) | — | $\text{PT} = 1 - (\text{bulk\_density} / 2.65)$ |
| `saturated_hydraulic_conductivity` | Condutividade hidráulica ($K_{sat}$, $\text{mm/h}$) | Teste de permeabilidade | — | Tomasella & Hodnett (1998) |

### 3.3 Esqueleto do Talhão: `input/data/field/field_minas_gerais.json`
```json
{
    "soil_specification": "soil_minas_gerais",
    "crop_specification": "Corn-Silage-MG",
    "fertilizer_management_specification": "fertilizer_schedule_minas_gerais",
    "manure_management_specification": "manure_schedule_minas_gerais",
    "tillage_management_specification": "tillage_schedule_minas_gerais",
    "field_size": null,
    "latitude": null,
    "longitude": null,
    "minimum_daylength": null,
    "seasonal_high_water_table": false,
    "watering_amount_in_liters": 0.0,
    "watering_interval": 0,
    "simulate_water_stress": true,
    "simulate_temp_stress": true,
    "simulate_nitrogen_stress": true,
    "simulate_phosphorus_stress": true,
    "tractor_size": "medium"
}
```

* **Instruções de Preenchimento:**
  - `field_size`: Área da lavoura em hectares (ex: `20.0`).
  - `latitude`: Coordenada GPS com sinal negativo (ex: `-18.5789`).
  - `longitude`: Coordenada GPS (ex: `-46.5181`).
  - `minimum_daylength`: Comprimento do dia no solstício de inverno ($\approx 10.8\text{ h}$ em Minas Gerais).

---

## 4. Seção 3: Metadados do Cenário e Protocolo de Execução

### 4.1 Estrutura do Metadados: `input/metadata/cenario_minas_gerais_metadata.json`
O arquivo mestre mapeará os 22 blobs obrigatórios do RuFaS:

1. **Blobs Customizados Brasileiros:**
   - `"config"`: `input/data/config/config_minas_gerais.json`
   - `"weather"`: `input/data/weather/weather_minas_gerais.csv`
   - `"field_1"`: `input/data/field/field_minas_gerais.json`
   - `"soil_1"`: `input/data/soil/soil_minas_gerais.json`
   - `"Corn-Silage-MG"`: `input/data/crop/example_alf_corn_silage_rotation.json` (ou rotação de silagem de milho)
2. **Blobs Reutilizados da Base Padrão:**
   - `tractor_dataset`, `manure_processor_connection`, `manure_management`, `feed_storage_configurations`, `feed_storage_instances`, `EEE_constants`, `user_feeds`, `NRC_Comp`, `NASEM_Comp`.

### 4.2 Protocolo de Validação e Execução

1. **Validação de Esquemas e Cross-Validation:**
   ```bash
   python -m tools.rufas_inspector --scenario input/metadata/cenario_minas_gerais_metadata.json
   ```
   *Verifica integridade de tipos, caminhos de arquivo, hierarquia $\theta_{wp} \le \theta_{fc} \le \theta_{sat}$ e coerência das temperaturas do clima.*
2. **Execução com Exportação de Variáveis:**
   ```bash
   python -m tools.rufas_runner --task-metadata input/task_manager_metadata.json --enable-all-csv
   ```
3. **Verificação de Resultados Biofísicos:**
   - Conferir em `output/logs/logs.txt` o cálculo de fotoperíodo: dias longos em dezembro e dias curtos em junho.
   - Avaliar a produção de forragem acumulada (kg MS/ha) e a ausência de instabilidades hidráulicas no perfil do Latossolo.

---

## 5. Rastreabilidade de Arquivos Criados no Passo 2

- `input/data/config/config_minas_gerais.json`
- `input/data/weather/weather_minas_gerais.csv`
- `input/data/soil/soil_minas_gerais.json`
- `input/data/field/field_minas_gerais.json`
- `input/metadata/cenario_minas_gerais_metadata.json`
