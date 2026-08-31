# RuFaS Metadata, Input Schema & Cross-Validation Reference

## 1. Input Architecture Overview

RuFaS decouples configuration architecture into declarative metadata manifests and concrete data files:

```
[CLI Flags] 
    │
    ▼
[task_manager_metadata.json]
    │
    ▼
[Task Data File: tasks/*.json]
    ├── Orchestration: parallel_workers, export_input_data_to_csv
    ├── Task List:
    │     ├── task_type: SIMULATION_SINGLE_RUN | SIMULATION_MULTI_RUN | ...
    │     ├── metadata_file_path: points to Scenario Metadata
    │     ├── cross_validation_file_paths: [list of cross-validation rules]
    │     └── output_prefix & filters_directory
    │
    ▼
[Scenario Metadata: <scenario>_metadata.json]
    ├── files:
    │     ├── 22 REQUIRED_FILE_BLOBS (maps to input/data/... JSONs)
    │     └── Dynamic field/soil/crop blobs
    └── runtime_metadata
```

---

## 2. The 22 Required File Blobs

Every complete scenario metadata JSON must specify the following 22 blobs under `"files"`:

| Blob Key | Role | Typical Data Path |
|---|---|---|
| `config` | General simulation flags (start/end dates, seed, print switches) | `input/data/config/general_config.json` |
| `animal` | Biological parameters, breed specs, mature body weights | `input/data/animal/animal_general.json` |
| `animal_population` | Herd demographic structure and pen distributions | `input/data/animal/animal_population_*.json` |
| `animal_mean_phenotype` | Initial genetic / phenotypic lactation and size means | `input/data/animal_genetics/mean_phenotype_*.json` |
| `animal_top_listing_semen` | Available AI sire breeding values | `input/data/animal_genetics/top_listing_semen_*.json` |
| `lactation` | Lactation curve parameters (Wood / Dijkstra) | `input/data/animal/lactation_constants.json` |
| `economy` | Milk pricing, feed prices, labor, utility rates | `input/data/EEE/economy_constants.json` |
| `emission` | GWP factors, emission constants | `input/data/EEE/emission_constants.json` |
| `purchased_feeds_emissions` | Embodied emission factors per kg purchased feed | `input/data/EEE/purchased_feed_emissions.json` |
| `purchased_feed_land_use_change_emissions` | Land use change (LUC) emission factors | `input/data/EEE/purchased_feed_luc_emissions.json` |
| `feed` | Feed management intervals, planning horizons | `input/data/feed_management/feed_management_constants.json` |
| `NRC_Comp` | NRC 2001 feed nutrient library | `input/data/feed/NRC_Feed_Library.json` |
| `NASEM_Comp` | NASEM 2021 feed nutrient library | `input/data/feed/NASEM_Feed_Library.json` |
| `manure_management` | Housing, separator, storage, digester configs | `input/data/manure/manure_management_constants.json` |
| `manure_processor_connection` | Connectivity graph between manure units | `input/data/manure/manure_processor_connection.json` |
| `crop_configurations` | Farm crop master list and field assignment | `input/data/crop_configurations/crop_config.json` |
| `weather` | Weather station daily data (temp, precip, radiation, wind) | `input/data/weather/weather_*.json` |
| `user_feeds` | On-farm custom feed definitions and costs | `input/data/feed/user_feeds.json` |
| `tractor_dataset` | Tractor specs and implement load parameters | `input/data/EEE/tractors.json` |
| `EEE_constants` | Fuel densities, electricity emission factors | `input/data/EEE/EEE_constants.json` |
| `feed_storage_configurations` | Storage structures (bunkers, silos, bags) | `input/data/feed_management/feed_storage_configurations.json` |
| `feed_storage_instances` | Initial feed inventory and active storage units | `input/data/feed_management/feed_storage_instances.json` |

---

## 3. Cross-Validation System (`CrossValidator`)

Located in `input/metadata/cross_validation/*.json`.

### Structure of a Cross-Validation Rule File
```json
{
  "title": "Animal and Feed Storage Cross Validation",
  "description": "Ensures feed nutrient limits and storage capacities align with herd requirements.",
  "aliases": {
    "herd_pop": "files.animal_population.data.total_cows",
    "storage": "files.feed_storage_instances.data"
  },
  "rules": [
    {
      "name": "check_storage_capacity",
      "condition": "storage.total_capacity >= herd_pop * 10.0",
      "error_message": "Feed storage capacity is insufficient for herd size."
    }
  ]
}
```

### Purpose & Enforcement
Cross-validation prevents multi-file inconsistencies before runtime:
- Weather timeline must encapsulate `simulation_start_date` to `simulation_end_date`.
- Crop root depth in `crop/*.json` must not exceed total depth of layers in `soil/*.json`.
- Feed storage initial dry matter must not exceed maximum container capacity.
- Manure scraper scheduling must match pen animal occupancy.
