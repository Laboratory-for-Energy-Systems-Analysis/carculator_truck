# Changelog

Notable user-facing changes to `carculator_truck`. The entry below is prepared for release;
it has not yet been published. Older entries, where present, retain their original record.

## [0.5.1] - Unreleased

- Remove import-time global warning suppression and refresh API/documentation contracts; shared sulfur-table reductions use explicit pandas axis arguments.

### Compatibility and installation

- Require Python 3.12 (`>=3.12,<3.13`); older Python environments must be recreated.
- Use NumPy `>=1.26.4,<2` through the shared runtime.
- Require the stable `carculator_utils>=1.3.6` release, including its Brightpath runtime dependency.
- Build wheels and source distributions from centralized `pyproject.toml` metadata.
- Keep core model/LCIA calculations independent of Brightway projects and imports. Export writers now come through Brightpath; `excel` remains a compatibility alias and `brightway` selects the legacy stack (`bw2io<0.9`, `bw2data<4`, `bw2calc<2`).
- Align documentation versions with the package version and provide complete documentation-build dependencies.

### Model and inventory changes

- Make repeated `set_all()` calls rebuild from retained inputs, with stable costs/energy and retained PHEV components. Preserve explicit input edits and selected sample prices; see the shared repeat-run guide.

- Allocate depot charger production over charger lifetime and capacity-limited fleet throughput, applying depot and PHEV electric-driving shares once. Preserve actual PHEV charger specifications, reject invalid active settings, and verify completed inventories, LCIA and exports. Energy and costs are unchanged; regenerate affected impacts and exports. See [charger inventory accounting](docs/validity.rst#depot-charger-inventory).
- Correct reversed waste-output signs for the 28t and 40t used-lorry treatment routes, removing artificial disposal credits for heavier trucks. Preserve treatment selection and mass scaling; verify completed model/LCIA runs and Brightway/SimaPro exports across years and weight classes. Regenerate affected impacts and exports; see [end-of-life accounting](docs/validity.rst#end-of-life-signs).
- Correct AdBlue costs by applying the dosing ratio to diesel litres and converting AdBlue volume to mass at 1.09 kg/L before billing EUR/kg. Retain dosing rates, prices, PHEV driving-share weighting and maintenance overrides; verify completed diesel/hybrid runs, fuel blends and zero-use controls. See [AdBlue cost accounting](docs/validity.rst#adblue-cost-accounting).
- Use grid electricity consistently for annual depot-charger throughput and per-km infrastructure allocation. Remove the artificial surcharge caused by mixing electricity with and without charger losses; retain financing, capacity ceilings and depot-share assumptions. Verify completed BEV/PHEV runs, capacity transitions, noncharging and zero-demand cases. See [depot throughput accounting](docs/validity.rst#depot-throughput-accounting).
- Bill BEVs and PHEV electric operation from grid electricity consumption, including charger losses. Preserve fuel-mode costs, PHEV driving-share weighting and model-specific cost units; verify costs against completed inventory purchases. See [charging cost accounting](docs/validity.rst#charging-cost-accounting).
- Complete runs after selecting a nonzero sample label. Display payload, weight warnings and availability from the same retained sample: the named sensitivity reference when present, otherwise the first sample. Inherit preserved LCIA sample labels and selected-sample export support from the shared release.
- Gas trucks now emit the methane represented by their additional fuel-purchase allowance; previously the lost gas was absent from direct emissions. Use the shared mass balance, include both origins in impacts/exports, and document the historical loss-rate boundary; see [validation](docs/validity.rst#additional-methane-leakage).
- Repair 21 invalid triangular battery/glider cost distributions by scaling bounds from valid 2020 relative uncertainty. Preserve every central value and all 2025 records; restore sampling of the full defaults and verify completed stochastic models/inventories. Ship original-record provenance and document the shared contextual validation.
- Add native 2025 inputs, explicit component-efficiency priors and consistent temporal extensions across model years.
- Apply corrected shared energy boundaries and regenerative accounting, and apply the CNG efficiency correction before fuel conversion.
- Bound sizing per available vehicle/sample and preserve custom inputs, payload, range, power and cost overrides.
- Correct year-based financial calculations, zero-rate capital recovery, inactive charging infrastructure and insurance calculations.
- Refine charging infrastructure costs and inventory fractions, including annual throughput limits and discounted replacements/residual values.
- Apply availability masks consistently to energy and supply outputs; document VECTO trace provenance and measured-truck comparison limits.
- Inherit corrected fuel blend, PHEV carbon, hot pollutant and multi-year export accounting from the shared release.

### Inventory export

- Inherit Brightpath (`>=1.0.0a6,<1.1`, v1 alpha API) writers for Brightway Excel, SimaPro CSV and foreground-only openLCA JSON-LD from `carculator_utils`; document examples and return values in the [export guide](docs/inventory_export.rst).
- Retain exact ecoinvent 3.9/3.10 cut-off targets, one selected sample per export, every selected year and unchanged source inventories/impacts. Brightway importers still require background matching and writing.
- Document the SimaPro Latin-1 layout and identifier changes, warnings for omitted custom noise flows, and openLCA provider/elementary-flow mapping required before calculation. Remove obsolete presamples and uncertainty-export claims.

### Documentation and verification

- Read uncertainty-bound provenance JSON explicitly as UTF-8 on Windows, preserving euro-denominated units and exact comparisons with the source records.
- Add current installation and executable 2025 quick-start examples, migration notes and a release checklist.
- Record calibration scope, measurement boundaries and numerical consistency separately from empirical validation.
- Verify built wheels and sdist-built wheels, packaged resource hashes, installed tests with export extras and offline core-only model/LCIA smoke runs.

### Known limitations

- VECTO agreement is a simulator comparison. Measured truck comparisons retain road-load, route and AC/DC boundary limitations.
- The retained 32 t VECTO trace remains unverified; the original source trace could not be independently recovered.
- Inspect payload, availability and power-deficit diagnostics before interpreting zero consumption or tonne-kilometre results.

See [validation](docs/validity.rst) and [release preparation](RELEASING.md) for scope and verification instructions.
