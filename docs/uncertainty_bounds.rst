Truck cost uncertainty bounds
=============================

The complete truck defaults can now be sampled with
``TruckInputParameters().stochastic(n, seed=42)``. Previously, sampling failed
with ``ImproperBoundsError`` because 21 triangular cost distributions placed
their most likely value outside their minimum/maximum bounds. All records are
sampled before vehicle/year scope selection, so even a 2025-only calculation
was blocked by invalid future-year records.

Correction and scope
--------------------

The repair changes only ``minimum`` and ``maximum`` in:

* Six 2030 battery-cost records: LTO, NCA, NMC-111, NMC-532, NMC-622 and NMC-811.
* Fifteen glider-cost records: five size groups in each of 2030, 2040 and 2050.

Each corrected bound uses the same parameter/vehicle group's valid 2020
relative uncertainty:

.. math::

   b_y = b_{2020}\,\frac{m_y}{m_{2020}}

Here :math:`m` is the triangular mode (``loc``) and :math:`b` is either bound.
This follows the endpoint reconstruction already documented when the tabulated
2025 records were constructed. It is a repair of inconsistent uncertainty
definitions, not a new calibration to market observations.

.. list-table:: Examples of corrected bounds
   :header-rows: 1

   * - Parameter
     - Year
     - Unchanged mode
     - Original bounds
     - Corrected bounds
   * - LTO battery cost (EUR/kWh)
     - 2030
     - 119
     - 140--160
     - 112--126
   * - 40t/60t glider cost (EUR/kg)
     - 2030
     - 6.30
     - 7.50--10.50
     - 5.25--7.35

Every central ``amount`` and ``loc`` is preserved, as are all 2025 records,
physical assumptions and unaffected distributions. The mode and bounds keep
their existing interpretation; this update adds no new correlations between
different years. The installed :download:`provenance record
<../carculator_truck/data/cost_uncertainty_provenance.json>` retains each original
record, its 2020 anchor, scale factor, corrected bounds and source hashes.

Example
-------

.. code-block:: python

   from carculator_truck import (
       TruckInputParameters, TruckModel, InventoryTruck,
       fill_xarray_from_input_parameters,
   )

   inputs = TruckInputParameters()
   inputs.stochastic(3, seed=42)
   _, array = fill_xarray_from_input_parameters(
       inputs,
       scope={"size": ["40t"], "powertrain": ["BEV", "ICEV-d"], "year": [2025]},
   )
   model = TruckModel(array, cycle="Urban delivery")
   model.set_all()
   impacts = InventoryTruck(
       model, scenario="static", functional_unit="tkm"
   ).calculate_impacts()

Validation
----------

Shared validation checks triangular distributions when records are loaded:
``minimum < maximum`` and ``minimum <= loc <= maximum``. All three fields must
be supplied and finite. Invalid definitions raise an error identifying the
record, parameter, year, size and powertrain instead of anonymous sampler row
numbers. Boundary modes are valid; deterministic values use
``uncertainty_type=1``. ``amount`` remains the separate static input.

Tests sample every packaged truck record, check bounds and repeatability, and
verify the original-data hash after restoring the 21 old records. Completed
three-sample model and tonne-kilometre inventory/LCIA runs cover BEV and diesel
40t trucks in 2025, 2030, 2040 and 2050, with both default battery chemistry and
explicit LTO. These checks establish numerical validity, not empirical
validation of future cost trajectories or uncertainty widths.
