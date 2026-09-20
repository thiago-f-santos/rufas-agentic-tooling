# Especificação Técnica: Passo 1 - Suporte ao Hemisfério Sul e Modularização de País/Região no RuFaS

**Data:** 19 de Setembro de 2026  
**Status:** Aprovado  
**Tipo:** Arquitetural (Design Spec)  
**Alvo:** `RuFaS/` (Core Engine)  

---

## 1. Visão Geral e Objetivos

O RuFaS (Ruminant Farm Systems) foi originalmente concebido com premissas acopladas aos Estados Unidos e ao Hemisfério Norte. Esta especificação detalha as alterações necessárias no código-fonte do RuFaS para:
1. **Corrigir o cálculo astronômico do fotoperíodo (horas de sol) para o Hemisfério Sul**, permitindo que fazendas em latitudes negativas (como o Brasil, ~$-5^\circ$ a $-33^\circ$) tenham as estações do ano e o crescimento de culturas em sincronia com o calendário real (verão em dez–fev, inverno em jun–ago).
2. **Generalizar a identificação regional e administrativa**, permitindo a especificação de país (`country: "BRA"` ou `"USA"`) e código regional unificado (`region_code`), integrando códigos do IBGE (estados e municípios brasileiros) com total retrocompatibilidade para o padrão legado de condados americanos (`FIPS_county_code`).

---

## 2. Seção 1: Latitude com Sinal e Fotoperíodo do Hemisfério Sul

### 2.1 Diagnóstico do Problema
- Em [`field_manager.py`](file:///home/thiago/Projects/RuFaS/RUFAS/biophysical/field/manager/field_manager.py#L94), o cálculo diário de horas de luz é invocado repassando a latitude absoluta positiva:
  ```python
  current_conditions = weather.get_current_day_conditions(time, field.field_data.absolute_latitude)
  ```
- No arquivo [`current_day_conditions.py`](file:///home/thiago/Projects/RuFaS/RUFAS/current_day_conditions.py#L81-L99), a fórmula de declinação solar do SWAT:
  $$\delta = \arcsin\left(0.4 \cdot \sin\left(\frac{2\pi}{365} \cdot (jday - 82)\right)\right)$$
  $$\text{tangent\_product} = -\tan(\delta) \cdot \tan(\phi_{\text{lat}})$$
  $$D_{\text{hours}} = \frac{2 \cdot \arccos(\text{tangent\_product})}{\Omega_{\text{earth}}}$$
  já é matematicamente válida para o Hemisfério Sul, **desde que** $\phi_{\text{lat}}$ seja negativa. Quando $\phi_{\text{lat}}$ é forçada a ser positiva, os dias em junho resultam $> 12\text{ h}$ e em dezembro $< 12\text{ h}$, invertendo as estações em 6 meses para o Brasil.

### 2.2 Alterações Detalhadas

#### A. Esquema de Metadados: `RUFAS/input/metadata/properties/default.json`
No grupo `field_properties`:
- Adicionar o campo `"latitude"`:
  ```json
  "latitude": {
    "type": "number",
    "description": "The geographic latitude of the center of this field (degrees, negative for Southern Hemisphere).\nUnits: degrees.",
    "minimum": -90.0,
    "maximum": 90.0,
    "default": 43.5
  }
  ```
- Manter o campo `"absolute_latitude"` existente como opcional/depreciado para garantir retrocompatibilidade com cenários legados.

#### B. Objeto de Dados do Campo: `RUFAS/biophysical/field/field/field_data.py`
- Adicionar o atributo:
  ```python
  latitude: float | None = None
  ```
- No método `__post_init__`:
  ```python
  if self.latitude is None:
      self.latitude = self.absolute_latitude
  else:
      self.absolute_latitude = abs(self.latitude)

  self.dormancy_threshold = Dormancy.find_dormancy_threshold(abs(self.latitude))
  ```
  *(Nota: O cálculo de dormência utiliza `abs(latitude)`, pois a sensibilidade térmica depende da distância modular à linha do equador).*

#### C. Gerenciador de Campos: `RUFAS/biophysical/field/manager/field_manager.py`
- Em `_setup_field_data`:
  ```python
  latitude = field_configuration_data.get("latitude")
  if latitude is None:
      latitude = field_configuration_data.get("absolute_latitude", 43.5)
  ```
- Em `daily_update_routine` (linha 94):
  ```python
  # Passar a latitude com sinal (negativa para o Hemisfério Sul):
  current_conditions = weather.get_current_day_conditions(time, field.field_data.latitude)
  ```

---

## 3. Seção 2: Generalização de País e Região (`country` e `region_code`)

### 3.1 Diagnóstico do Acoplamento
Apenas dois pontos no RuFaS leem a localização regional da fazenda:
1. [`emissions.py`](file:///home/thiago/Projects/RuFaS/RUFAS/EEE/emissions.py#L141): busca fatores de emissão de alimentos comprados no CSV por código de condado.
2. [`lactation_curve.py`](file:///home/thiago/Projects/RuFaS/RUFAS/biophysical/animal/milk/lactation_curve.py#L90): busca a macrorregião da curva de Wood por FIPS estadual (FIPS / 1000).

### 3.2 Alterações Detalhadas

#### A. Esquema de Configuração: `RUFAS/input/metadata/properties/default.json`
No grupo `config_properties`:
- Adicionar `"country"`:
  ```json
  "country": {
    "type": "string",
    "description": "Three-letter country ISO code for the simulation location (e.g. 'USA', 'BRA').",
    "pattern": "^[A-Z]{3}$",
    "default": "USA"
  }
  ```
- Adicionar `"region_code"`:
  ```json
  "region_code": {
    "type": "number",
    "description": "Administrative region code (e.g. 5-digit FIPS for USA, 2-digit UF or 7-digit municipality IBGE code for Brazil).",
    "minimum": 1
  }
  ```
- Tornar `"FIPS_county_code"` opcional com anotação de retrocompatibilidade.

#### B. Módulo de Emissões de Alimentos: `RUFAS/EEE/emissions.py`
- Em `EmissionsEstimator.__init__`:
  ```python
  country = self.im.get_data("config.country", required=False) or "USA"
  region_code = self.im.get_data("config.region_code", required=False)
  if region_code is None:
      region_code = self.im.get_data("config.FIPS_county_code", required=False)
  ```
- Em `_get_feed_emissions_data`:
  ```python
  # Suportar tanto a coluna legada "county_code" quanto a genérica "region_code":
  code_column_key = "region_code" if "region_code" in feed_emissions_data else "county_code"
  codes = feed_emissions_data[code_column_key]
  try:
      emissions_index = codes.index(region_code)
  except ValueError:
      ...
  ```

#### C. Módulo de Curva de Lactação: `RUFAS/biophysical/animal/milk/lactation_curve.py`
- Em `set_lactation_parameters`:
  ```python
  country = im.get_data("config.country", required=False) or "USA"
  region_code = im.get_data("config.region_code", required=False)
  if region_code is None:
      region_code = im.get_data("config.FIPS_county_code", required=False)

  all_region_adjustments = lactation_inputs["adjustments"]["region"]
  region_mapping = lactation_inputs.get("state_to_region_mapping", {})
  region_adjustments = cls._get_region_adjustments(
      all_region_adjustments, region_mapping, region_code, country
  )
  ```
- Em `_get_region_adjustments`:
  ```python
  @classmethod
  def _get_region_adjustments(
      cls,
      region_adjustment_values: dict[str, dict[str, float]],
      region_mapping: dict[str, str],
      region_code: int | None,
      country: str = "USA",
  ) -> dict[str, float]:
      neutral_adjustments = {"l": 1.0, "m": 1.0, "n": 1.0}
      if region_code is None:
          return neutral_adjustments

      if country == "USA":
          state_fips_code = int(region_code / 1000)
          region = region_mapping.get(str(state_fips_code))
          return region_adjustment_values.get(region, neutral_adjustments)
      elif country == "BRA":
          # No padrão IBGE: município tem 7 dígitos (ex: 3106200), estado tem 2 dígitos (ex: 31)
          code_str = str(region_code)
          state_ibge_code = int(code_str[:2]) if len(code_str) >= 2 else region_code
          region = region_mapping.get(str(state_ibge_code))
          if region and region in region_adjustment_values:
              return region_adjustment_values[region]
          return neutral_adjustments
      else:
          return neutral_adjustments
  ```

---

## 4. Seção 3: Validações, Retrocompatibilidade e Testes

### 4.1 Regras de Retrocompatibilidade
1. **Fallback Transparente:**
   - Cenários que possuem apenas `absolute_latitude` funcionam sem alterações.
   - Cenários que possuem apenas `FIPS_county_code` funcionam sem alterações (assumem `country: "USA"`).
2. **Ausência de Conflitos em Cross-Validation:**
   - As regras em `input/metadata/cross_validation/` não impõem restrições rígidas sobre `FIPS_county_code` ou `absolute_latitude`.

### 4.2 Matriz de Testes Automatizados (TDD)

| Teste | Arquivo de Teste | Entradas | Saída Esperada |
|---|---|---|---|
| **Fotoperíodo Norte (EUA)** | `tests/test_weather.py` | Latitude $+42.4^\circ$, dias 172 e 355 | Dia 172 $> 15\text{ h}$; Dia 355 $< 9.5\text{ h}$ |
| **Fotoperíodo Sul (Brasil)** | `tests/test_weather.py` | Latitude $-22.5^\circ$, dias 172 e 355 | Dia 172 $< 11.0\text{ h}$; Dia 355 $> 13.5\text{ h}$ |
| **Repasse em FieldData** | `tests/test_biophysical/.../test_field.py` | `latitude: -22.5` | `field_data.latitude == -22.5`, `abs_latitude == 22.5` |
| **Fallback de Latitude** | `tests/test_biophysical/.../test_field.py` | `absolute_latitude: 43.5` (sem `latitude`) | `field_data.latitude == 43.5` |
| **Emissões Legado EUA** | `tests/test_eee/` | `FIPS_county_code: 55025` | Executa sem erro, busca dados de Wisconsin |
| **Emissões Novo Padrão EUA** | `tests/test_eee/` | `country: "USA"`, `region_code: 55025` | Resultado idêntico ao legado |
| **Lactação Brasil IBGE** | `tests/test_biophysical/.../test_lactation.py` | `country: "BRA"`, `region_code: 3106200` | Retorna `neutral_adjustments` ou bacia MG sem erro |

---

## 5. Rastreabilidade de Arquivos Afetados

- [`RUFAS/biophysical/field/field/field_data.py`](file:///home/thiago/Projects/RuFaS/RUFAS/biophysical/field/field/field_data.py)
- [`RUFAS/biophysical/field/manager/field_manager.py`](file:///home/thiago/Projects/RuFaS/RUFAS/biophysical/field/manager/field_manager.py)
- [`RUFAS/biophysical/animal/milk/lactation_curve.py`](file:///home/thiago/Projects/RuFaS/RUFAS/biophysical/animal/milk/lactation_curve.py)
- [`RUFAS/EEE/emissions.py`](file:///home/thiago/Projects/RuFaS/RUFAS/EEE/emissions.py)
- [`RUFAS/input/metadata/properties/default.json`](file:///home/thiago/Projects/RuFaS/RUFAS/input/metadata/properties/default.json)
