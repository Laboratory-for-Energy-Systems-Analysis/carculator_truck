.. _usage:

Usage
=====

The example below loads default inputs, calculates the vehicle, and then
calculates its life cycle impacts. Start with one year and a few vehicles. Add
more years, vehicle types or uncertainty samples once that example works.

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

The input classes load the default parameter tables. ``static()`` uses one
set of central values. ``stochastic(n, seed=42)`` draws ``n`` sets from the
specified uncertainty distributions; using the same seed repeats those draws.

The array builder returns ``(mappings, array)``. The array has labelled axes for
``size``, ``powertrain``, ``parameter``, ``year`` and ``value``; ``value`` identifies
the sample. The ``scope`` dictionary selects vehicles and years, rather than
changing their assumptions. Use labels and years present in the parameter
tables, including 2025. For other years, interpolate the input array explicitly
before constructing the vehicle model.

Change input parameters before constructing a fresh vehicle model. Constructor
overrides such as battery chemistry, capacity, fuel blends and component
efficiencies are copied, preserving the caller's data. Most vehicle overrides
use ``(powertrain, size, year)`` keys; consult the model API for exceptions.
Calling ``set_all()`` again is supported: it starts from saved inputs,
including explicit edits, rather than using calculated outputs as new inputs.
Use a fresh model for a separate scenario, new coordinates, or changes to the
component assumptions of a plug-in hybrid.

Energy and results
------------------

See :doc:`interpretation` for units, powertrain abbreviations, and the difference
between energy use, direct emissions and life cycle impacts.

``model["TtW energy"]`` is kJ per vehicle-kilometre. For BEVs it is net
stored-energy depletion; ``model.battery_terminal_energy`` is a separate DC
boundary, and ``model["electricity consumption"]`` is grid electricity in
kWh/km. Multiply the latter by 100 for kWh/100 km.

Construct the inventory with the completed model, not its raw parameter array.
Use ``calculate_impacts()`` and labelled selection/reduction of the returned
xarray. Functional units are ``vkm``, ``pkm`` and ``tkm``. Passenger- and
cargo-normalized results require finite positive loads for active vehicles.
A zero reported for an unavailable or infeasible vehicle is a status marker,
not a prediction of zero energy use.

Truck duty cycles are ``Urban delivery``, ``Regional delivery`` and ``Long haul``.
Tonne-kilometres use actual cargo in tonnes, not gross vehicle mass. Review
payload and power-deficit diagnostics when changing mass or target range.
The printed payload table describes the sample labelled ``reference`` when
present, otherwise the first selected sample. Payload, weight warnings and
availability all use that same sample. Model arrays and LCIA results retain
all selected sample labels in their original order; inspect those arrays for
sample-specific results.


Inventory export
----------------

The shared runtime includes Brightpath and its export writers. Continue with
the completed inventory from the quick start:

.. code-block:: python

   workbook = inventory.export_lci(
       ecoinvent_version="3.12",
       software="brightway2", format="file", directory="exports",
   )
   simapro_csv = inventory.export_lci(
       software="simapro", format="file", directory="exports",
   )
   foreground_zip = inventory.export_lci(
       software="openlca", format="file", directory="exports",
   )

Export requires exactly one selected sample, selected before constructing the
model and inventory. The static quick start already has one sample. Every
selected year gets an export; multiple years return a list. The original
inventory, calculated impacts and functional unit remain unchanged.

The default ``export_lci()`` returns an unlinked Brightway ``LCIImporter``.
Exports default to **ecoinvent 3.12 cutoff**, matching the bundled background.
Older ``3.9`` and ``3.10`` targets raise an error when a required supplier has no
verified counterpart in that version. The
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
See the `shared guide to repeated runs
<https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/repeated_runs.rst>`_.

Additional gas leakage
----------------------

``CNG pump-to-tank leakage`` now defaults to zero at all tabulated years. This
excludes an unqualified overlay beyond the delivered-fuel supplier boundary; it
does not remove upstream emissions or exhaust methane, or assert that actual
vehicle leakage is zero. The former 0.004 prior combined potentially overlapping
delivery/storage/vehicle stages. Supply a documented residual loss (kg lost/kg
engine fuel) for the selected pathway when available. Original records and
source/boundary rationale are packaged in ``data/methane_leakage_provenance.json``.
