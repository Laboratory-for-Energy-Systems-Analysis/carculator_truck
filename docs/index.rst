.. image:: /_static/img/mediumsmall_2.png
   :align: center

.. _intro:

Carculator Truck
================

``carculator_truck`` is a parameterized model that allows to generate and characterize life cycle inventories for different
truck configurations, according to selected:

* power train technologies (5): diesel engine, hybrid diesel, plugin-hybrid diesel, battery electric and fuel cell electric,
* year of operation (5): 2000, 2010, 2020, 2040 and 2050,
* and sizes (9): 3.5t, 7.5t, 18t, 26t, 32t, 40t and 60t.

The methodology used to develop ``carculator_truck`` is explained in an article :cite:`ct-1074`.
The tool has a focus on trucks.

``carculator_truck`` uses Brightpath through ``carculator_utils`` to export
Brightway Excel, SimaPro CSV and foreground-only openLCA JSON-LD inventories.
The openLCA files need background-provider and elementary-flow mapping before
calculation; see :doc:`inventory_export`.
``carculator_truck`` also directly provides characterized
results against several midpoint indicators from the impact assessment method ReCiPe, ILCD, as well as life cycle cost indicators.

``carculator_truck`` is special in the way that it uses time- and energy-scenario-differentiated background inventories for the future,
resulting from the coupling between the `ecoinvent database <https://ecoinvent.org>`_ and the scenario outputs of PIK's
integrated assessment model `REMIND <https://www.pik-potsdam.de/research/transformation-pathways/models/remind/remind>`_.
This allows to perform prospective study and consider future expected changes in regard to the production of electricity,
cement, steel, heat, etc.

Objective
---------

The objective is to produce life cycle inventories for trucks in a transparent, comprehensive and quick manner,
to be further used in prospective LCA of transportation technologies.

Why?
----

Several life cycle assessment (LCA) models of trucks exist. Yet, because LCA of vehicles, particularly for electric battery vehicles,
are sensitive to assumptions made in regards to electricity mix used for charging, lifetime of the battery, etc., it has led
to mixed conclusions being published in the scientific literature. Because the underlying calculations are kept undocumented,
it is not always possible to explain the disparity in the results given by these models, which can contribute to adding confusion among the public.

Because ``carculator_truck`` is kept **as open as possible**, the methods and assumptions behind the generation of results are
easily identifiable and adjustable.
Also, there is an effort to keep the different modules (classes) separated, so that improving certain areas of the model is relatively
easy and does not require changing extensive parts of the code. In that regard, contributions are welcome.

Finally, beside being more flexible and transparent, ``carculator_truck`` provides interesting features, such as:

* a stochastic mode, that allows fast Monte Carlo analyses, to include uncertainty at the vehicle level
* possibility to override any or all of the 200+ default input truck parameters (e.g., cargo load, drag coefficient) but also calculated parameters (e.g., driving mass).
* hot pollutants emissions as a function of the driving cycle, using bundled `HBEFA <https://www.hbefa.net/e/index.html>`_ emission factors, further divided between rural, suburban and urban areas
* noise emissions, based on `CNOSSOS-EU <https://ec.europa.eu/jrc/en/publication/reference-reports/common-noise-assessment-methods-europe-cnossos-eu>`_ models for noise emissions and an article by :cite:`ct-1015` for inventory modelling and mid- and endpoint characterization of noise emissions, function of driving cycle and further divided between rural, suburban and urban areas
* export one retained sample per model year as Brightway Excel, SimaPro CSV or
  foreground-only openLCA JSON-LD through Brightpath. External suppliers need
  matching to the destination background; see :doc:`inventory_export`.
* return unlinked Brightway ``LCIImporter`` objects for subsequent matching and
  writing in a Brightway project. Select one sample before building the model
  and inventory; exports do not create uncertainty distributions or presamples.

Get started with :ref:`Installation <install>` and continue with an overview about :ref:`how to use the library <usage>`.

User's Guide
------------

.. toctree::
   :maxdepth: 2

   installation
   usage
   inventory_export
   uncertainty_bounds
   modeling
   structure
   validity

API Reference
-------------

.. toctree::
   :maxdepth: 2

   api

Project information
-------------------

.. toctree::
   :maxdepth: 1

   release

.. toctree::
   :maxdepth: 2
   :hidden:

   references/references
   annexes
