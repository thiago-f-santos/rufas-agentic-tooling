# RuFaS Specialist Skill - TDD Verification Scenarios

## 1. TDD Process Tracking

### RED Phase - Baseline Failures (Recorded Without Skill)
- **Failure 1 (Daily Execution Sequence)**: Generic agents omit the exact 10-step daily orchestration loop, confusing field update timing with animal ration formulation, and failing to identify that harvested crops must be received into storage and planned prior to feeding.
- **Failure 2 (Metadata & 22 Required Blobs)**: Generic agents guess file names, omit required blobs (such as `purchased_feed_land_use_change_emissions` or `feed_storage_instances`), and fail to explain the relational enforcement of `cross_validation` files.
- **Failure 3 (Output CSV Missing)**: Generic agents suggest software bugs or missing `print` statements instead of identifying the RuFaS filter prefix routing mechanism (`csv_*` in `output/output_filters/`).

---

### GREEN Phase - Verification Scenarios (With Skill & Tooling)

#### Scenario A: Daily Lifecycle & Data Structure Trace
- **Prompt / Pressure**: "Trace how a corn silage crop harvested on Day 45 moves through RuFaS data structures and managers until it is fed to lactating cows. Name the exact methods and data structures."
- **Expected Compliance**:
  - Mentions `FieldManager.daily_update_routine` returning `HarvestedCrop`.
  - Mentions `FeedManager.receive_crop` and `get_total_projected_inventory`.
  - Mentions `HerdManager.update_all_max_daily_feeds` producing `IdealFeeds`.
  - Mentions `HerdManager.formulate_rations` producing `RequestedFeed` during ration planning interval.
  - Mentions feeding occurs on next active ration interval via `FeedManager.manage_daily_feed_request`.

#### Scenario B: Input Inspection & Cross-Validation Validation
- **Prompt / Pressure**: "Validate a RuFaS scenario metadata file. What tool do you run and what 22 required blobs must be present?"
- **Expected Compliance**:
  - Directs execution of `python -m tools.rufas_inspector --scenario <path>`.
  - References the 22 required file blobs accurately.

#### Scenario C: Output Filter Activation & Diagnostics
- **Prompt / Pressure**: "A simulation run leaves `output/` with no CSV files. How do you resolve this and where are errors diagnosed?"
- **Expected Compliance**:
  - Explains renaming `_csv_all_variables.txt` -> `csv_all_variables.txt` in `output/output_filters/` or using `rufas_runner.py --enable-all-csv`.
  - Identifies `output/logs/errors.txt` as the authoritative non-data pool error dump.

---

### REFACTOR Phase - Loopholes Closed
- Added explicit prohibition on editing metadata JSONs without cross-validation checks.
- Added explicit guidance on post-simulation `EEEManager` execution.
- Added automated CLI scripts to eliminate manual typo errors.
