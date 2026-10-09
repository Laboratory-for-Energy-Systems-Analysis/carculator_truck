.. _usage:

Usage
=====

Use the vehicle package’s input, model and inventory classes. Start with a small
static scope before expanding years, sizes or uncertainty samples.

Quick start
-----------

.. code-block:: python

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


Inputs and scope
----------------

The vehicle input classes provide packaged defaults. Call ``static()`` for a
single deterministic sample, or ``stochastic(n, seed=42)`` for seeded parameter
draws. The array builder returns ``(mappings, array)`` and preserves labelled
``size``, ``powertrain``, ``parameter``, ``year`` and ``value`` dimensions.
Scope by actual labels and native input years; interpolate explicitly when a
year is not in the parameter table. The current defaults include 2025.

Change input parameters before constructing a fresh vehicle model. Constructor
overrides such as battery chemistry, capacity, fuel blends and component
efficiencies are copied, preserving the caller's data. Most vehicle overrides
use ``(powertrain, size, year)`` keys; consult the model API for exceptions.
Repeated ``set_all()`` calls on an already completed model are not the supported
way to compare independent scenarios.

Energy and results
------------------

``model["TtW energy"]`` is kJ per vehicle-kilometre. For BEVs it is net
stored-energy depletion; ``model.battery_terminal_energy`` is a separate DC
boundary, and ``model["electricity consumption"]`` is grid electricity in
kWh/km. Multiply the latter by 100 for kWh/100 km.

Construct the inventory with the completed model, not its raw parameter array.
Use ``calculate_impacts()`` and labelled selection/reduction of the returned
xarray. Functional units are ``vkm``, ``pkm`` and ``tkm``. Passenger- and
cargo-normalized results require finite positive loads for active vehicles.
Availability-masked zero consumption does not describe a zero-energy vehicle.

Truck duty cycles are ``Urban delivery``, ``Regional delivery`` and ``Long haul``.
Tonne-kilometres use actual cargo in tonnes, not gross vehicle mass. Review
payload and power-deficit diagnostics when changing mass or target range.
The printed payload table describes the sample labelled ``reference`` when
present, otherwise the first retained sample. Payload, weight warnings and
availability all use that same sample. Model arrays and LCIA results retain
all selected sample labels in their original order; inspect those arrays for
sample-specific results.


Inventory export
----------------

The shared runtime includes Brightpath and its export writers. Continue with
the completed inventory from the quick start:

.. code-block:: python

   workbook = inventory.export_lci(
       ecoinvent_version="3.10",
       software="brightway2", format="file", directory="exports",
   )
   simapro_csv = inventory.export_lci(
       software="simapro", format="file", directory="exports",
   )
   foreground_zip = inventory.export_lci(
       software="openlca", format="file", directory="exports",
   )

Export requires exactly one retained sample, selected before constructing the
model and inventory. The static quick start already has one sample. Every
selected year gets an export; multiple years return a list. The original
inventory, calculated impacts and functional unit remain unchanged.

The default ``export_lci()`` returns an unlinked Brightway ``LCIImporter``.
Supported ecoinvent targets are exactly ``3.9`` and ``3.10``, cut-off. The
openLCA ZIP contains foreground processes without an ecoinvent background or
LCIA methods; map external providers and elementary flows before calculation.
SimaPro uses Latin-1 CSV and warns when custom noise flows are omitted.
See :doc:`inventory_export` for the full format/return-value table, sample
selection and linking requirements.

Reproducibility and interpretation
----------------------------------

Record package versions, input overrides, driving cycle, load, geography,
fuel blend, background scenario, functional unit and energy meter boundary.
Seeded parameter draws do not seed every downstream cost adjustment.
See :doc:`validity` for the scope of
calibration, measurement comparisons and known limitations.


The complete default parameter set is validated before sampling. See
:doc:`uncertainty_bounds` for repaired truck cost distributions, their provenance
and a complete stochastic model/inventory example.


Repeated completion
-------------------

Repeated ``set_all()`` calls reuse retained inputs instead of previous results.
Existing coordinate selections and explicit input-cell edits are supported.
Modify PHEV component inputs in a fresh model rather than aggregated outputs.
See the `shared repeat-run contract
<https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/repeated_runs.rst>`_.
