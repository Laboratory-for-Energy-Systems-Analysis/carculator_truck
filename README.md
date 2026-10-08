# carculator_truck

Prospective environmental and economic life cycle assessment of freight vehicles, with coupled payload, range, energy storage and charging infrastructure.

[![Installed artifacts](https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_truck/actions/workflows/main.yml/badge.svg?branch=master)](https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_truck/actions/workflows/main.yml)
[![PyPI](https://img.shields.io/pypi/v/carculator_truck)](https://pypi.org/project/carculator_truck/)

Developed at the [Paul Scherrer Institute](https://www.psi.ch/en).
This checkout prepares **0.5.1**; see [CHANGELOG.md](https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_truck/blob/master/CHANGELOG.md) for release status and changes.

## Installation

Use **Python 3.12** (`>=3.12,<3.13`) and a fresh environment. The shared runtime
requires NumPy `>=1.26.4,<2`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

On Windows, activate with `.venv\Scripts\activate`. After publication, install
this release from PyPI:

```bash
python -m pip install "carculator_truck==0.5.1"
```

Before publication, use the matching source checkouts as described under development.
Core calculations use bundled resources and need no Brightway project, ecoinvent
installation or network access. Inventory export has optional dependencies:

```bash
python -m pip install "carculator_truck[excel,brightway]==0.5.1"
```

The Brightway extra supports the legacy stack (`bw2io<0.9`, `bw2data<4`,
`bw2calc<2`). Export currently targets ecoinvent 3.9 and 3.10; importing those
inventories requires the corresponding background database in the destination tool.

## Quick start

```python
from carculator_truck import (
    TruckInputParameters,
    TruckModel,
    InventoryTruck,
    fill_xarray_from_input_parameters,
)

inputs = TruckInputParameters()
inputs.static()
_, array = fill_xarray_from_input_parameters(
    inputs,
    scope={"size": ["40t"], "powertrain": ["ICEV-d", "BEV"], "year": [2025]},
)
model = TruckModel(array, cycle="Long haul")
model.set_all()
print(model["TtW energy"])  # kJ per vehicle-kilometre

inventory = InventoryTruck(model, functional_unit="tkm")
impacts = inventory.calculate_impacts()
print(impacts.sel(impact_category="climate change").sum("impact"))
```

Truck model costs are per vehicle-kilometre; the example reports impacts per tonne-kilometre of actual cargo.

## Modelling and validation

The vehicle models include native **2025** parameters and documented temporal
extensions. These combine engineering priors and selected calibration evidence;
they are not independent measurements for every vehicle configuration.

`TtW energy` is in kJ/km. For BEVs it is net stored-energy depletion;
`model.battery_terminal_energy` reports terminal DC separately, while
`electricity consumption` is grid electricity in kWh/km. Identify the measurement
boundary before comparing energy outputs. Availability-masked zeroes do not
represent physically zero consumption.

Supported background scenarios are `SSP2-NPi`, `SSP2-PkBudg1000`,
`SSP2-PkBudg650`, and `static`. ReCiPe supports midpoint/endpoint and EF midpoint.
Use fresh model instances for independent cases. `inputs.stochastic(n, seed=...)`
seeds parameter sampling, not every downstream cost adjustment.

See [validation and limitations](https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_truck/blob/master/docs/validity.rst), [migration notes](https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_truck/blob/master/docs/release.rst)
and the [documentation](https://carculator-truck.readthedocs.io/en/latest/).

## Development and release

Use matching sibling checkouts, especially `carculator_utils` **1.3.6 or newer**:

```bash
python -m pip install -e "../carculator_utils[test,excel,brightway]" -e ".[test,docs,excel,brightway]"
python -m pip check
python -m pytest
python -m sphinx -b html docs docs/_build/html
```

The `docs` extra includes the extensions used by this repository.
See [RELEASING.md](https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_truck/blob/master/RELEASING.md) for artifact verification, release order and publication.

## Support and license

Contact [carculator@psi.ch](mailto:carculator@psi.ch) or open an [issue](https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_truck/issues).
Maintained by [Romain Sacchi](https://github.com/romainsacchi), with contributions
from the carculator development team. See [contributing](https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_truck/blob/master/CONTRIBUTING.md).
Licensed under [BSD-3-Clause](https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_truck/blob/master/LICENSE).

Scientific background: [Sacchi, Bauer and Cox (2021), Does Size Matter?](https://doi.org/10.1021/acs.est.0c07773).
