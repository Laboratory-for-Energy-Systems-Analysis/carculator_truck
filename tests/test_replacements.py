"""Replacement inputs must survive sizing without capturing partial results."""

import numpy as np
import pytest
import xarray as xr

from carculator_truck import (
    InventoryTruck,
    TruckInputParameters,
    TruckModel,
    fill_xarray_from_input_parameters,
)


def inputs(sizes=("18t", "40t"), powertrains=("BEV",), years=(2025,)):
    parameters = TruckInputParameters()
    parameters.static()
    return fill_xarray_from_input_parameters(
        parameters,
        scope={
            "size": list(sizes),
            "powertrain": list(powertrains),
            "year": list(years),
        },
    )[1]


@pytest.mark.parametrize("size", ["18t", "40t"])
def test_default_truck_replacements_use_completed_battery_and_inventory(size):
    model = TruckModel(inputs(sizes=(size,)), cycle="Regional delivery", country="CH")
    calls = []
    original = model.set_battery_fuel_cell_replacements

    def trace():
        calls.append(float(model["electric energy stored"].item()))
        original()

    model.set_battery_fuel_cell_replacements = trace
    model.set_all()
    assert len(calls) == 1
    assert calls[0] > 200
    # The completed truck does fewer full equivalent cycles than one pack's life.
    cycles = (
        model["lifetime kilometers"]
        * model["TtW energy"]
        / 3600
        / model["electric energy stored"]
    )
    assert bool((cycles < model["battery cycle life"]).all())
    assert model["battery lifetime replacements"].item() == 0

    inventory = InventoryTruck(model, scenario="static", functional_unit="vkm")
    column = inventory.inputs[(f"truck, BEV, {size}", "CH", "unit", "truck")]
    rows = [
        i
        for label, i in inventory.inputs.items()
        if label[0].startswith("market for battery, Li-ion,")
    ]
    pack_mass = float(model["energy battery mass"].item())
    assert -inventory.A[0, rows, column, 0].sum() == pytest.approx(pack_mass)
    used = inventory.inputs[
        ("market for used Li-ion battery", "GLO", "kilogram", "used Li-ion battery")
    ]
    assert inventory.A[0, used, column, 0] == pytest.approx(pack_mass)
    impacts = inventory.calculate_impacts()
    assert np.isfinite(impacts).all()
    assert bool((impacts.sel(impact_category="climate change").sum("impact") > 0).all())


def test_mixed_inputs_and_repeated_runs_keep_automatic_cells_independent():
    array = (
        inputs(years=(2030, 2025))
        .isel(value=[0, 0])
        .assign_coords(value=["auto", "given"])
    )
    # Low cycle-life sensitivity creates positive automatic replacement counts.
    for parameter in array.parameter.values:
        if parameter.startswith("battery cycle life,"):
            array.loc[dict(parameter=parameter)] = 500
    explicit = dict(size="18t", powertrain="BEV", year=2025, value="given")
    array.loc[dict(parameter="battery lifetime replacements", **explicit)] = 1.25
    source = array.copy(deep=True)
    model = TruckModel(array, cycle="Regional delivery")
    model.set_all()
    first = model["battery lifetime replacements"].copy(deep=True)
    assert first.sel(explicit).item() == 1.25
    assert bool((first.sel(value="auto") > 0).all())
    assert bool((first.sel(value="auto") < 3).all())
    np.testing.assert_allclose(first.sel(size="18t", value="auto"), 0.26, atol=2e-6)
    np.testing.assert_allclose(first.sel(size="40t", value="auto"), 1.84, atol=2e-6)
    model.set_all()
    xr.testing.assert_identical(model["battery lifetime replacements"], first)
    model.array = model.array.sel(year=[2025, 2030], value=["given", "auto"])
    model.set_all()
    xr.testing.assert_allclose(
        model["battery lifetime replacements"],
        first.sel(year=[2025, 2030], value=["given", "auto"]),
    )
    # Editing a completed input is picked up by the next complete run.
    model.array.loc[dict(parameter="battery lifetime replacements", **explicit)] = 2
    model.set_all()
    assert model["battery lifetime replacements"].sel(explicit).item() == 2
    xr.testing.assert_identical(array, source)


def test_fuel_cell_override_does_not_suppress_other_samples():
    array = (
        inputs(sizes=("18t",), powertrains=("FCEV",))
        .isel(value=[0, 0])
        .assign_coords(value=["auto", "given"])
    )
    array.loc[dict(parameter="fuel cell lifetime replacements", value="given")] = 2
    array.loc[dict(parameter="fuel cell lifetime hours")] = 1000
    model = TruckModel(array, cycle="Regional delivery")
    model.set_all()
    assert model["fuel cell lifetime replacements"].sel(value="given").item() == 2
    assert model["fuel cell lifetime replacements"].sel(value="auto").item() == 5
