.. _validity:

Truck calibration and validation
================================

The historical VECTO comparison in :doc:`modeling` is calibration against a
simulator, not an independent measurement of every truck class. Its reported
sub-1% agreement applies to that original configuration and model version.
The current 2025 evidence review separates measurement boundaries, road load,
vehicle vintage and route before interpreting discrepancies.

Delivery-truck evidence
-----------------------

Full-model diagnostics use the source dynamometer road-load polynomials and
documented test inertias: 13,175 lb for the Smith Newton and 11,500 lb for the
MT-45. All runs still use 2025 technology assumptions, so these historical
vehicles are screening checks rather than calibration targets.

.. list-table:: Source-road-load comparisons
   :header-rows: 1

   * - Vehicle / cycle
     - Boundary and unit
     - Model
     - Measured
   * - Smith Newton / OCBC
     - Battery DC, kWh/100 km
     - 44.99
     - 44.74
   * - Smith Newton / OCBC
     - Charging AC, kWh/100 km
     - 52.42
     - 54.68
   * - MT-45 / OCBC
     - Diesel, L/100 km
     - 21.32
     - 24.71
   * - MT-45 / NYCC x 3
     - Diesel, L/100 km
     - 30.42
     - 38.69

The MT-45 cases remove the generic class's small electric-power share to
represent the conventional test vehicle. Smith's remaining deviations are
+0.6% at the battery and -4.1% at charging; MT-45 remains low by 13.7% and
21.4%. The road-load match does not prove the component efficiencies correct,
and the two electrical boundaries are not independent vehicles.

Heavy electric trucks
---------------------

The eActros 600 tour reports 103 kWh/100 km and the Volvo FH Electric road test
110 kWh/100 km, both at 40 t. Their published electrical boundaries are
insufficiently precise for a like-for-like residual. The generic long-haul
model gives respectively 143.00/123.75 and 142.33/123.15 kWh/100 km at charging
AC/battery DC. Flat-grade and road-load sensitivities reduce the differences,
but do not recreate either measured route. No generic default was fitted to
these results.

The measurement catalog includes six paired observations for four trucks.
See `truck diagnostics, primary sources and reproduction
<https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/truck_energy_diagnostics.rst>`_ for the source polynomials, trace lengths,
power constraints and individual sensitivity runs. Stronger evidence is still
needed for route elevation, vehicle-specific road loads, auxiliaries and
matched AC/DC meters. The retained 32 t VECTO trace is explicitly unverified;
its source trace could not be independently recovered.

Coverage limits
---------------

Diesel controls and low-speed operation remain important diagnostic targets.
The car-only opt-in petrol controller is not implemented for trucks. The
available comparisons do not establish independent consumption validation for
every size, gas, hybrid, plug-in hybrid or fuel-cell truck. Inspect availability,
payload and power-deficit diagnostics before accepting a result.

Energy boundaries and time trends
---------------------------------

``TtW energy`` is kJ/km. For a BEV it represents net stored-energy depletion;
``model.battery_terminal_energy`` reports net terminal DC energy separately.
``electricity consumption`` is charging electricity in kWh/km. Multiplying it
by 100 gives kWh/100 km. A meter boundary must be identified before comparing
these outputs. Regeneration and battery/charger losses must not be counted twice.

The 2025 motor/inverter (0.90), electric transmission (0.97), charger (0.90)
and symmetric battery one-way (sqrt(0.97)) values are component priors in their
documented scopes, not universally measured efficiencies. For relevant hybrid
scopes, the independent motor peak/system-power ratio is 0.65. The temporal
update preserves all 2025 scalar values and uncertainty distributions. Storage
and charger trends preserve relative legacy losses; newly explicit component
priors are extended across native years to avoid interpolating from missing
zero values. Historical estimates and future projections therefore change.

The family audit completes 546 annual cases (21 configurations, 2015–2040),
including availability-masked historical cells. The former inputs caused 20
sizing failures in this grid. All 40 existing 2025 measurement-comparison runs
retain their energy use and driving mass exactly. These are consistency and
regression checks, not 546 empirical validations. See
`temporal method, plots and limitations <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/temporal_energy.rst>`_.

Reproducibility
---------------

The installed package includes :download:`2025 record provenance
<../carculator_truck/data/defaults_2025_provenance.json>` and
:download:`temporal provenance and original affected records
<../carculator_truck/data/temporal_energy_provenance.json>`. Overrides should use measured
vehicle-specific inputs where available. Retain source, year, cycle, driving
mass, meter boundary and uncertainty assumptions with each comparison.

With matching Python 3.12 sibling checkouts, run from ``carculator_utils``::

   python scripts/validate_energy_measurements.py --output /tmp/measurements-new
   python scripts/audit_energy_time_trends.py --output /tmp/temporal-new

The shared `measurement catalog and outputs <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/energy_measurements.rst>`_
record excluded observations as well as paired values. Multiple cycles of one
vehicle and AC/DC measurements from one run are not independent vehicles.
