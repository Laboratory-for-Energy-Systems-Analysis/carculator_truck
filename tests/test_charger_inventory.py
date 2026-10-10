"""Physical depot charger allocation in completed truck inventories."""

import csv
import io
import warnings
from copy import deepcopy

import numpy as np
import pytest
import xarray as xr
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve

from carculator_truck import (
    InventoryTruck,
    TruckInputParameters,
    TruckModel,
    fill_xarray_from_input_parameters,
)

CHARGER = (
    "EV charger, level 3, plugin, 200 kW",
    "RER",
    "unit",
    "EV charger, level 3, plugin, 200 kW",
)
SPECS = [
    "depot charger power",
    "depot charger lifetime",
    "trucks per depot charger",
    "share depot charging",
]


@pytest.fixture(scope="module", params=[0.0, 0.5, 1.0])
def completed(request):
    inputs = TruckInputParameters()
    inputs.static()
    _, array = fill_xarray_from_input_parameters(
        inputs,
        scope={
            "size": ["7.5t", "40t"],
            "powertrain": ["BEV", "PHEV-d", "ICEV-d", "FCEV"],
            "year": [2025, 2030],
        },
    )
    samples = ["standard", "short", "long", "no-depot", "capped"]
    array = array.sel(year=[2030, 2025]).isel(value=[0] * len(samples))
    array = array.assign_coords(value=samples)
    electric = ["BEV", "PHEV-e"]
    for sample, life in [("short", 6), ("long", 24)]:
        array.loc[
            dict(parameter="depot charger lifetime", powertrain=electric, value=sample)
        ] = life
    array.loc[
        dict(parameter="share depot charging", powertrain=electric, value="no-depot")
    ] = 0
    array.loc[
        dict(parameter="depot charger power", powertrain=electric, value="capped")
    ] = 10
    original = array.copy(deep=True)
    model = TruckModel(
        array, country="CH", cycle="Regional delivery", drop_hybrids=False
    )
    model.set_all(electric_utility_factor=request.param)
    xr.testing.assert_identical(array, original)
    assert (model["TtW energy"] > 0).all()
    return model


def expected_units(model, size, pt, year, sample):
    """Charger-years used by this truck, from the electric-mode fleet service."""
    if pt not in ("BEV", "PHEV-d"):
        return 0.0
    mode = "PHEV-e" if pt == "PHEV-d" else pt
    cell = model.array.sel(size=size, powertrain=mode, year=year, value=sample)
    value = lambda p: float(cell.sel(parameter=p))
    share = value("share depot charging")
    uf = value("electric utility factor") if pt == "PHEV-d" else 1
    if not share or not uf:
        return 0.0
    annual_fleet_km = value("trucks per depot charger") * value("kilometers per year")
    grid_per_km = value("electricity consumption")
    power = value("depot charger power")
    # One charger can supply at most this many electric-mode km per year.
    possible_km = power * 8760 * 0.98 * 0.94 / grid_per_km
    serviced_km = min(annual_fleet_km, possible_km)
    truck_km = float(
        model.array.sel(
            size=size,
            powertrain=pt,
            year=year,
            value=sample,
            parameter="lifetime kilometers",
        )
    )
    years_used = truck_km * uf * share / serviced_km
    return years_used / value("depot charger lifetime") * power / 200


def make_inventory(model, **kwargs):
    model = deepcopy(model)
    model.drop_hybrid()
    return InventoryTruck(model, **kwargs)


def test_phev_preserves_physical_charger_settings(completed):
    xr.testing.assert_equal(
        completed.array.sel(
            powertrain="PHEV-d", parameter=SPECS, drop=True
        ).reset_coords(drop=True),
        completed.array.sel(
            powertrain="PHEV-e", parameter=SPECS, drop=True
        ).reset_coords(drop=True),
    )


def test_charger_allocation_respects_service_and_lifetime(completed):
    inventory = make_inventory(completed, scenario="static")
    for size in inventory.scope["size"]:
        for pt in inventory.scope["powertrain"]:
            column = inventory.inputs[(f"truck, {pt}, {size}", "CH", "unit", "truck")]
            (row,) = inventory.get_vehicle_supply_indices(CHARGER[0], [column])
            for n, sample in enumerate(completed.array.value.values):
                for y, year in enumerate(completed.array.year.values):
                    assert -inventory.A[n, row, column, y] == pytest.approx(
                        expected_units(completed, size, pt, year, sample),
                        rel=2e-6,
                    )


@pytest.mark.parametrize("functional_unit", ["vkm", "tkm"])
@pytest.mark.parametrize(
    "electricity_supplier_count", [1, 2], ids=["single", "multiple"]
)
def test_charger_impacts_follow_physical_allocation(
    completed, functional_unit, electricity_supplier_count
):
    completed = deepcopy(completed)
    # Exact lifetime ratios make electricity-supplier counts independent of
    # platform roundoff: one shared mix, or distinct mixes for the two sizes.
    lifetimes = xr.DataArray(
        [8, 8 if electricity_supplier_count == 1 else 16],
        dims="size",
        coords={"size": completed.array.coords["size"]},
    )
    completed["lifetime kilometers"] = completed["kilometers per year"] * lifetimes
    inventory = make_inventory(
        completed, scenario="SSP2-NPi", functional_unit=functional_unit
    )
    actual = inventory.calculate_impacts()
    assert np.isfinite(actual).all()
    electricity_rows = inventory.find_input_indices(
        ("electricity supply for electric vehicles",)
    )
    assert len(electricity_rows) == electricity_supplier_count
    # Charger manufacturing is outside the vehicle fuel supply chain. Distinct
    # operating mixes must not clone its background manufacturing electricity.
    rows = inventory.find_input_indices((CHARGER[0],))
    assert len(rows) == 1
    without = deepcopy(inventory)
    columns = [i for k, i in inventory.inputs.items() if k[0].startswith("truck, ")]
    for row in rows:
        without.A[:, row, columns, :] = 0
    delta = (
        (actual - without.calculate_impacts())
        .sel(impact_category="climate change")
        .sum("impact")
    )
    demand = np.zeros((inventory.A.shape[1], len(rows)))
    demand[rows, np.arange(len(rows))] = 1
    for y, year in enumerate(completed.array.year.values):
        for n, sample in enumerate(completed.array.value.values):
            # spsolve squeezes a single RHS column; keep the supplier axis.
            supply = spsolve(csc_matrix(inventory.A[n, :, :, y]), demand).reshape(
                demand.shape
            )
            factors = (
                inventory.B.sel(category="climate change").interp(year=year).values
                @ supply
            )
            for size in inventory.scope["size"]:
                for pt in inventory.scope["powertrain"]:
                    cell = completed.array.sel(
                        size=size, powertrain=pt, year=year, value=sample
                    )
                    expected = expected_units(completed, size, pt, year, sample)
                    column = inventory.inputs[
                        (f"truck, {pt}, {size}", "CH", "unit", "truck")
                    ]
                    (row,) = inventory.get_vehicle_supply_indices(CHARGER[0], [column])
                    factor = float(factors[rows.index(row)])
                    expected *= factor / float(
                        cell.sel(parameter="lifetime kilometers")
                    )
                    if functional_unit == "tkm":
                        expected /= float(cell.sel(parameter="cargo mass")) / 1000
                    assert float(
                        delta.sel(size=size, powertrain=pt, year=year, value=sample)
                    ) == pytest.approx(expected, rel=2e-5, abs=1e-9)


@pytest.mark.parametrize("version", ["3.12"])
def test_export_includes_phev_charger_and_preserves_inventory(completed, version):
    model = deepcopy(completed)
    model.array = model.array.sel(value=["standard"])
    inventory = make_inventory(model, scenario="static")
    original, original_inputs = inventory.A.copy(), inventory.inputs.copy()

    def expected(year):
        return sorted(
            expected_units(completed, size, pt, year, "standard")
            for size in inventory.scope["size"]
            for pt in inventory.scope["powertrain"]
        )

    for _ in range(2):
        importers = inventory.export_lci(format="bw2io", ecoinvent_version=version)
        assert len(importers) == 2
        for year, importer in zip(inventory.scope["year"], importers):
            quantities = []
            for activity in importer.data:
                if not activity["name"].startswith("truck, "):
                    continue
                exchanges = [
                    e for e in activity["exchanges"] if e["name"].startswith(CHARGER[0])
                ]
                assert len(exchanges) <= 1
                for e in exchanges:
                    assert (
                        e["name"].split(" [for ")[0],
                        e["location"],
                        e["unit"],
                        e["reference product"],
                    ) == CHARGER
                    assert e["type"] == "technosphere"
                quantities.append(sum(e["amount"] for e in exchanges))
            np.testing.assert_allclose(sorted(quantities), expected(year), rtol=2e-6)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*noise.*", category=UserWarning)
        csvs = inventory.export_lci(
            software="simapro", format="string", ecoinvent_version=version
        )
    assert len(csvs) == 2
    for year, content in zip(inventory.scope["year"], csvs):
        quantities, section = [], None
        for row in csv.reader(io.StringIO(content), delimiter=";"):
            if not row or not row[0]:
                section = None
            elif len(row) == 1:
                section = row[0]
            elif (
                section == "Materials/fuels"
                and len(row) > 2
                and row[0].lower().startswith(CHARGER[0].lower())
                and row[1] == "p"
            ):
                quantities.append(float(row[2]))
        np.testing.assert_allclose(
            sorted(quantities), [v for v in expected(year) if v], rtol=2e-6
        )
    np.testing.assert_array_equal(inventory.A, original)
    assert inventory.inputs == original_inputs


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("depot charger lifetime", 0),
        ("trucks per depot charger", 0),
        ("depot charger power", np.nan),
        ("share depot charging", 1.1),
    ],
)
def test_invalid_active_depot_settings_are_rejected(completed, parameter, value):
    model = deepcopy(completed)
    model.array.loc[
        dict(
            parameter=parameter,
            size="40t",
            powertrain="BEV",
            year=2025,
            value="standard",
        )
    ] = value
    with pytest.raises(ValueError, match=parameter):
        InventoryTruck(model, scenario="static")


def test_zero_demand_allows_zero_charger_settings(completed):
    model = deepcopy(completed)
    model["electricity consumption"] = 0
    model[SPECS] = 0
    inventory = make_inventory(model, scenario="static")
    columns = [i for k, i in inventory.inputs.items() if k[0].startswith("truck, ")]
    for row in inventory.find_input_indices((CHARGER[0],)):
        np.testing.assert_array_equal(inventory.A[:, row, columns, :], 0)
