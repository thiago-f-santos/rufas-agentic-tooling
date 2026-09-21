# Especificação Técnica: Passo 3 - Módulo EEE Brasil (Emissões, Energia e Economia Regionalizadas)

**Data:** 20 de Setembro de 2026  
**Status:** Aprovado  
**Tipo:** Arquitetural (Design Spec)  
**Alvo:** `RuFaS/input/data/EEE/`, `rufas-agentic-tooling/tools/rufas_eee_builder.py`  
**Referência Cruzada:** [`docs/superpowers/specs/2026-09-19-passo-2-cenario-piloto-brasil-minas-gerais-design.md`](2026-09-19-passo-2-cenario-piloto-brasil-minas-gerais-design.md)  

---

## 1. Visão Geral e Objetivos

Esta especificação técnica define os requisitos, fontes científicas de dados, arquitetura de arquivos e metodologia de cálculo para regionalizar o módulo **EEE (Economics, Energy & Emissions)** do RuFaS para o Brasil, com foco no cenário piloto de **Minas Gerais** (Patos de Minas, IBGE `3148004`, UF `31`).

### Problema Resolvido
No Passo 2, a simulação biofísica executou 730 dias com sucesso, mas o módulo EEE gerou avisos de dados ausentes (`Missing Regional Feed Emissions` e `Missing Land Use Change Purchased Feed Emissions Data`), pois as tabelas de emissões indexavam apenas condados americanos (FIPS). Com isso, as emissões de Escopo 3 (berço-à-porteira) dos alimentos comprados foram omitidas (zeradas).

### Objetivos do Passo 3
1. **Fatores de Emissão de Alimentos Comprados (Escopo 3):** Mapear os fatores de emissão de produção agrícola/industrial e de mudança no uso da terra (dLUC) para os alimentos prioritários consumidos pelo rebanho piloto, com rigorosa rastreabilidade e proveniência científica (**GFLI v3.0 / Embrapa**).
2. **Matriz Elétrica e Combustíveis (Escopos 1 e 2):** Calibrar o fator de emissão da rede elétrica com base na média oficial do **Sistema Interligado Nacional (SIN/MCTI)** do biênio 2021–2022 ($0,065\text{ kg CO}_2\text{e/kWh}$) e o diesel comercial brasileiro com biodiesel (B12/B14).
3. **Parâmetros Econômicos no Padrão Internacional (USD):** Parametrizar os custos operacionais (diesel, eletricidade, insumos) e receita do leite em dólares (USD) equivalentes para Minas Gerais (2021–2022), permitindo benchmarking direto com cenários internacionais.
4. **Ferramenta Automatizada (`rufas_eee_builder.py`):** Criar gerador no `rufas-agentic-tooling` que constrói os artefatos canônicos e valida o reconhecimento automático das regiões `31` e `3148004` pelo [`emissions.py`](file:///home/thiago/Projects/RuFaS/RUFAS/EEE/emissions.py).

---

## 2. Proveniência e Fatores de Emissão de Alimentos Comprados

O RuFaS separa as emissões de alimentos comprados em dois arquivos complementares:
1. `purchased_feeds_emissions`: Emissões de produção agrícola, fertilizantes na lavoura, processamento industrial e transporte até a fábrica/porteira ($\text{kg CO}_2\text{e / kg matéria seca}$).
2. `purchased_feed_land_use_change_emissions`: Emissões diretas de mudança no uso da terra (dLUC — conversão de vegetação nativa nos últimos 20 anos pela norma PAS 2050 / PEFCR da UE).

### 2.1 Tabela de Fatores e Rastreabilidade

| RuFaS ID | Nome do Alimento | Categoria | Emissões Produção ($\text{kg CO}_2\text{e/kg MS}$) | LUC ($\text{kg CO}_2\text{e/kg MS}$) | Fonte e Proveniência Metodológica |
|:---:|:---|:---:|:---:|:---:|:---|
| **44** | Milho grão moído (*Corn, yellow - grain, ground, dry*) | Concentrado | **0,28** | **0,15** | **GFLI v3.0** (`Maize grain, at farm/BR`). Considera média ponderada safra/safrinha no Cerrado/MG. |
| **50** | Silagem de milho (*Corn silage, immature*) | Volumoso | **0,18** | **0,00** | **Embrapa Milho e Sorgo / Embrapa Pecuária Sudeste**. Produção regional consolidada; LUC nulo em área estabelecida. |
| **23** | Farinha de sangue (*Blood meal, low dRUP*) | Concentrado | **1,10** | **0,00** | **GFLI / Ecoinvent BR** (`Blood meal, at processing/BR`). Alocação econômica de coproduto frigorífico. |
| **95** | Feno de gramíneas (*Grass hay, mature*) | Volumoso | **0,22** | **0,00** | **Embrapa Pecuária Sudeste** (Ruviaro et al., 2020). Feno de *Brachiaria/Panicum* adubado. |
| **104** | Silagem de gramínea-leguminosa | Volumoso | **0,22** | **0,00** | **Embrapa Pecuária Sudeste**. Produção regional conservada. |
| **110** | Silagem de leguminosa (*Legumes, forage - silage*) | Volumoso | **0,20** | **0,00** | **Embrapa Pecuária Sudeste**. Silagem pré-emurchecida; crédito de fixação biológica de nitrogênio. |
| **170** | Farelo de soja (*Soybean meal, solvent extracted*) | Concentrado | **0,45** | **1,85** | **GFLI v3.0** (`Soybean meal, solvent extracted, at plant/BR`). dLUC oficial PAS 2050 (janela de 20 anos) com alocação PEFCR. |
| **202** | Leite integral (*Whole milk*) | Líquido | **0,90** | **0,00** | **Embrapa Gado de Leite**. Pegada média de berço-à-porteira do leite produzido no Sudeste. |
| **216** | Ração inicial de bezerros (*Calf starter 18% PB*) | Concentrado | **0,55** | **0,60** | **Inferido por Composição Ponderada** (ver memória de cálculo 2.2). |
| **301** | Mistura mineral (*Farm ES Mineral Mix*) | Mineral | **0,75** | **0,00** | **Inferido por Composição Ponderada** (ver memória de cálculo 2.3). |
| **302** | Blend de coprodutos (*Farm ES BP Blend*) | Concentrado | **0,35** | **0,10** | **Inferido por Composição Ponderada** (blend típico milho/polpa cítrica/farelo de trigo). |

### 2.2 Memória de Cálculo: Ração Inicial de Bezerros (ID 216)
Composição nutricional padrão para ração inicial (18% PB):
* $65\%$ Milho moído: $0,65 \times 0,28 = 0,182\text{ kg CO}_2\text{e}$
* $30\%$ Farelo de soja: $0,30 \times 0,45 = 0,135\text{ kg CO}_2\text{e}$
* $5\%$ Núcleo mineral/vitamínico: $0,05 \times 0,75 = 0,038\text{ kg CO}_2\text{e}$
* Processamento industrial (moagem, peletização, embalagem): $+0,150\text{ kg CO}_2\text{e}$
* **Total Produção:** $0,182 + 0,135 + 0,038 + 0,150 \approx \mathbf{0,55\text{ kg CO}_2\text{e/kg MS}}$.
* **Total dLUC:** $0,30 \times 1,85\text{ (soja)} + 0,65 \times 0,15\text{ (milho)} = 0,555 + 0,098 \approx \mathbf{0,60\text{ kg CO}_2\text{e/kg MS}}$.

### 2.3 Memória de Cálculo: Mistura Mineral (ID 301)
Composição típica de suplemento mineral para bovinos de leite:
* $45\%$ Fosfato bicálcico: $0,45 \times 1,20 = 0,540\text{ kg CO}_2\text{e}$ (processamento industrial com ácido sulfúrico e rocha fosfática)
* $25\%$ Cloreto de sódio (sal comum): $0,25 \times 0,15 = 0,038\text{ kg CO}_2\text{e}$
* $20\%$ Calcário calcítico: $0,20 \times 0,05 = 0,010\text{ kg CO}_2\text{e}$
* $10\%$ Microminerais, sulfatos e veículo: $0,10 \times 1,00 = 0,100\text{ kg CO}_2\text{e}$
* Mistura, ensaque e transporte: $+0,060\text{ kg CO}_2\text{e}$
* **Total Produção:** $0,540 + 0,038 + 0,010 + 0,100 + 0,060 \approx \mathbf{0,75\text{ kg CO}_2\text{e/kg MS}}$ (dLUC nulo).

---

## 3. Matriz Elétrica, Combustíveis e Parâmetros Econômicos

### 3.1 Fator de Emissão da Rede Elétrica Brasileira (SIN / MCTI)
O Ministério da Ciência, Tecnologia e Inovação (MCTI) publica os fatores oficiais mensais do Sistema Interligado Nacional (SIN).
* **2021:** $0,088\text{ kg CO}_2/\text{kWh}$ (ano atípico de escassez hídrica com acionamento termelétrico).
* **2022:** $0,042\text{ kg CO}_2/\text{kWh}$ (recuperação dos reservatórios hidrelétricos).
* **Fator Adotado para o Biênio 2021–2022:**
  $$\text{Fator}_{\text{SIN}} = \frac{0,088 + 0,042}{2} = \mathbf{0,065\text{ kg CO}_2\text{e/kWh}}$$
  *(Comparação: nos EUA o padrão RuFaS é $0,38\text{ kg CO}_2\text{e/kWh}$; a rede brasileira é ~6 vezes mais limpa).*

### 3.2 Fator do Combustível Diesel Comercial
* Diesel automotivo fóssil puro: $2,68\text{ kg CO}_2/\text{L}$ ($10,14\text{ kg CO}_2/\text{galão}$).
* Diesel B12/B14 comercial brasileiro (mistura com biodiesel de soja/sebo): **$2,64\text{ kg CO}_2\text{e/L}$** ($9,99\text{ kg CO}_2\text{e/galão}$).

### 3.3 Custos Internacionais em USD (Equivalente Minas Gerais 2021–2022)
Para manter o padrão internacional do RuFaS e permitir comparação direta entre fazendas:
* **Diesel:** $\$1,10/\text{L} \approx \mathbf{\$4,16/\text{galão}}$ (média BRL/USD de 2021–2022 com diesel a ~R$ 5,80/L e taxa média de R$ 5,25/USD).
* **Eletricidade:** $\mathbf{\$0,12/\text{kWh}}$ (tarifa média rural da Cemig convertida em USD).
* **Água e Gás Natural:** Mantidos nos padrões do RuFaS ($\$0,008/\text{gal}$ e $\$0,053/\text{kWh}$).

---

## 4. Estrutura de Arquivos e Integração

### 4.1 Novos Arquivos Canônicos em `RuFaS/input/data/EEE/`
1. `purchased_feeds_emissions_minas_gerais.csv`:
   * Coluna 1: `region_code`.
   * Linhas: código `31` (UF Minas Gerais) e código `3148004` (Patos de Minas).
   * Colunas 2..N: IDs de alimentos do RuFaS (`1, 2, ..., 44, 50, ..., 170, ..., 301, 302`), preenchidos com os valores da Seção 2.1 (e zero para os não utilizados).
2. `purchased_feed_land_use_change_emissions_minas_gerais.csv`:
   * Mesma estrutura, contendo os fatores de dLUC da Seção 2.1.
3. `default_emissions_minas_gerais.csv`:
   * Emissões de preparo e coeficientes locais.
4. `default_costs_minas_gerais.csv`:
   * Preços de combustíveis e eletricidade especificados na Seção 3.3.

### 4.2 Atualização de Metadados: `cenario_minas_gerais_metadata.json`
Redirecionamento das 4 chaves no arquivo de metadados mestre:
```json
"economy": {
    "title": "Economy data",
    "description": "Energy prices used in the EEE module for Minas Gerais.",
    "path": "input/data/EEE/default_costs_minas_gerais.csv",
    "type": "csv",
    "properties": "economic_properties"
},
"emission": {
    "title": "Emissions data",
    "description": "General emission values used in the EEE module for Minas Gerais.",
    "path": "input/data/EEE/default_emissions_minas_gerais.csv",
    "type": "csv",
    "properties": "emissions_properties"
},
"purchased_feeds_emissions": {
    "title": "Emissions from purchased feeds",
    "description": "Purchased feeds emission values for Minas Gerais (GFLI/Embrapa).",
    "path": "input/data/EEE/purchased_feeds_emissions_minas_gerais.csv",
    "type": "csv",
    "properties": "feed_emissions_properties"
},
"purchased_feed_land_use_change_emissions": {
    "title": "Land Use Change emissions from purchased feeds",
    "description": "Purchased feeds land use change emission values for Minas Gerais (GFLI PAS 2050).",
    "path": "input/data/EEE/purchased_feed_land_use_change_emissions_minas_gerais.csv",
    "type": "csv",
    "properties": "feed_emissions_properties"
}
```

---

## 5. Critérios de Sucesso e Validação

1. **Eliminação dos Avisos:**
   A execução da simulação não deve registrar avisos de `Missing Regional Feed Emissions` nem `Missing Land Use Change Purchased Feed Emissions Data` no arquivo `Minas_Gerais_Pilot_warnings_*.json`.
2. **Reconhecimento da Região:**
   O método [`_get_feed_emissions_data`](file:///home/thiago/Projects/RuFaS/RUFAS/EEE/emissions.py#L280) deve localizar com sucesso o código `3148004` (ou o prefixo `31`) e carregar o dicionário de fatores de emissão.
3. **Métricas de Saída FPCM e Intensidade de Carbono:**
   * A pegada de carbono da fazenda ($\text{kg CO}_2\text{e} / \text{kg FPCM}$) deve ser calculada e estar na faixa biológica esperada para sistemas leiteiros brasileiros com suplementação de concentrado no Cerrado: **$1,00\text{ a }1,60\text{ kg CO}_2\text{e / kg FPCM}$**.
   * A participação do Escopo 3 (alimentos comprados + LUC) deve representar entre **$15\%\text{ e }35\%$** do total de emissões da fazenda, em estrita conformidade com os benchmarks da literatura de ACV do leite.
