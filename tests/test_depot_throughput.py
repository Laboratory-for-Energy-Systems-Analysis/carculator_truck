"""Depot charges from independent annual cash flows and grid throughput."""

from copy import deepcopy

import numpy as np
import pytest
import xarray as xr

from carculator_truck import (
    InventoryTruck,
    TruckInputParameters,
    TruckModel,
    fill_xarray_from_input_parameters,
)


def expected_infrastructure(model, powertrain):
    selected = model.array.sel(size="40t", powertrain=powertrain)
    expected = xr.zeros_like(selected.sel(parameter="energy infrastructure cost"))
    for year in selected.year.values:
        for sample in selected.value.values:
            cell = selected.sel(year=year, value=sample)

            def value(parameter):
                return float(cell.sel(parameter=parameter))

            power = value("depot charger power")
            grid = value("electricity consumption")
            if power == 0 or grid == 0:
                continue
            years = value("depot charger lifetime")
            assert years == int(years)
            rate = value("interest rate")
            investment = power * sum(
                value(p)
                for p in (
                    "depot charger capex per kW",
                    "depot charger installation per kW",
                    "depot charger connection per kW",
                )
            )
            annual_capital = investment / sum(
                (1 + rate) ** (-i) for i in range(1, int(years) + 1)
            )
            annual_cost = (
                annual_capital
                + investment * value("depot charger O&M share")
                + power * value("depot charger capacity charger per kW-year")
            )
            fleet_km = value("trucks per depot charger") * value("kilometers per year")
            demand = fleet_km * grid
            # Existing availability and throughput-cap assumptions are retained.
            capacity = power * 8760 * 0.98 * 0.94
            expected.loc[dict(year=year, value=sample)] = (
                annual_cost
                / min(demand, capacity)
                * grid
                * value("share depot charging")
            )
    return expected


@pytest.fixture(
    scope="module", params=[350, 155, 10], ids=["below-cap", "crossing-cap", "capped"]
)
def completed(request):
    inputs = TruckInputParameters()
    inputs.static()
    _, array = fill_xarray_from_input_parameters(
        inputs,
        scope={
            "size": ["40t"],
            "powertrain": ["BEV", "ICEV-d", "FCEV", "PHEV-d"],
            "year": [2025, 2030],
        },
    )
    array = array.sel(year=[2030, 2025]).isel(value=[0, 0]).assign_coords(value=[9, 2])
    coordinates = {"year": [2030, 2025], "value": [9, 2]}
    electric = ["BEV", "PHEV-e"]
    array.loc[dict(parameter="charger efficiency", powertrain=electric)] = xr.DataArray(
        [[0.8, 1], [0.9, 0.75]], dims=("year", "value"), coords=coordinates
    )
    array.loc[dict(parameter="share depot charging", powertrain=electric)] = (
        xr.DataArray([[0.8, 0], [1, 0.5]], dims=("year", "value"), coords=coordinates)
    )
    array.loc[dict(parameter="depot charger power", powertrain=electric)] = (
        request.param
    )
    original = array.copy(deep=True)
    model = TruckModel(array, country="CH", cycle="Long haul", drop_hybrids=False)
    model.set_all(electric_utility_factor=0.5)
    xr.testing.assert_identical(array, original)
    grid = model["electricity consumption"].sel(powertrain="BEV")
    fleet_km = (model["trucks per depot charger"] * model["kilometers per year"]).sel(
        powertrain="BEV"
    )
    demand = grid * fleet_km
    capacity = request.param * 8760 * 0.98 * 0.94
    if request.param == 350:
        assert (demand < capacity).all()
    elif request.param == 10:
        assert (demand > capacity).all()
    else:
        legacy_demand = demand * model["charger efficiency"].sel(powertrain="BEV")
        assert ((legacy_demand < capacity) & (demand > capacity)).any()
    return model


def test_completed_depot_cost_matches_cash_flow_and_grid_throughput(completed):
    for pt in ("BEV", "PHEV-e", "ICEV-d", "PHEV-c-d", "FCEV"):
        np.testing.assert_allclose(
            completed["energy infrastructure cost"].sel(size="40t", powertrain=pt),
            expected_infrastructure(completed, pt),
            rtol=2e-6,
            atol=1e-10,
        )
    np.testing.assert_allclose(
        completed["energy infrastructure cost"].sel(size="40t", powertrain="PHEV-d"),
        expected_infrastructure(completed, "PHEV-e") * 0.5,
        rtol=2e-6,
        atol=1e-10,
    )


def test_completed_inventory_retains_charging_and_finite_impacts(completed):
    model = deepcopy(completed)
    model.drop_hybrid()
    inventory = InventoryTruck(model, scenario="static", functional_unit="vkm")
    assert np.isfinite(inventory.calculate_impacts()).all()
    for pt in ("BEV", "PHEV-d"):
        (column,) = inventory.find_input_indices((f"transport, truck, {pt},",))
        (row,) = inventory.get_vehicle_supply_indices(
            "electricity supply for electric vehicles", [column]
        )
        np.testing.assert_allclose(
            -inventory.A[:, row, column, :],
            model["electricity consumption"]
            .sel(size="40t", powertrain=pt)
            .transpose("value", "year"),
            rtol=2e-6,
        )


def test_zero_grid_demand_clears_infrastructure_cost(completed):
    # Exercise the cost boundary for an idle charger, independently of sizing.
    model = deepcopy(completed)
    model["electricity consumption"] = 0
    model.set_costs()
    np.testing.assert_array_equal(model["energy infrastructure cost"], 0)
