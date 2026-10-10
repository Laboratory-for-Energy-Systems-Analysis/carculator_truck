"""Completed trucks must use the same mass for sizing, energy and inventory."""

from copy import deepcopy

import numpy as np
import pytest
import xarray as xr
from carculator_utils.numerical import ConvergenceError

from carculator_truck import (
    InventoryTruck,
    TruckInputParameters,
    TruckModel,
    fill_xarray_from_input_parameters,
)


def inputs(powertrains, years=(2025,), size="26t"):
    parameters = TruckInputParameters()
    parameters.static()
    return fill_xarray_from_input_parameters(
        parameters,
        scope={"size": [size], "powertrain": powertrains, "year": list(years)},
    )[1]


def assert_final_mass_matches_cycle(model):
    speed = model.energy.sel(parameter="velocity").values
    mass = model["driving mass"].transpose("value", "year", "powertrain", "size").values
    rolling = (
        model["rolling resistance coefficient"]
        .transpose("value", "year", "powertrain", "size")
        .values
    )
    slopes = np.nan_to_num(model.ecm.gradient)[:, None, None, None, :]
    expected = mass[None] * 9.81 * rolling[None] * np.cos(slopes) * speed / 1000
    np.testing.assert_allclose(
        model.energy.sel(parameter="rolling resistance"), expected, rtol=2e-6, atol=1e-9
    )
    np.testing.assert_allclose(
        model["driving mass"],
        model["curb mass"]
        + model["cargo mass"]
        + model["average passengers"] * model["average passenger mass"],
    )


@pytest.mark.parametrize(
    "powertrain,options",
    [
        ("FCEV", {"cycle": "Regional delivery", "country": "DE"}),
        (
            "FCEV",
            {
                "cycle": "Regional delivery",
                "target_mass": {("FCEV", "26t", 2025): 12000},
            },
        ),
        ("BEV", {"cycle": "Urban delivery"}),
        ("ICEV-d", {"cycle": "Regional delivery"}),
    ],
)
def test_final_energy_storage_and_lcia_share_one_vehicle_state(powertrain, options):
    model = TruckModel(inputs([powertrain]), **options)
    model.set_all()
    assert_final_mass_matches_cycle(model)
    energy = model["TtW energy"].item()
    if powertrain == "BEV":
        usable_kj = (
            model["electric energy stored"] * model["battery DoD"] * 3600
        ).item()
    else:
        usable_kj = (model["fuel mass"] * model["LHV fuel MJ per kg"] * 1000).item()
    assert usable_kj / energy == pytest.approx(model["target range"].item(), rel=1e-5)
    fresh_energy = deepcopy(model)
    fresh_energy.calculate_ttw_energy()
    np.testing.assert_array_equal(fresh_energy["TtW energy"], model["TtW energy"])
    if model.target_mass:
        assert model["curb mass"].item() == pytest.approx(12000, rel=1e-5)
    inventory = InventoryTruck(model, scenario="static", functional_unit="tkm")
    result = inventory.calculate_impacts()
    assert np.isfinite(result).all()
    assert float(result.sel(impact_category="climate change").sum()) > 0
    (transport,) = [
        i
        for i, label in inventory.rev_inputs.items()
        if label[0].startswith("transport, truck, ")
    ]
    (supply,) = [
        i
        for i, label in inventory.rev_inputs.items()
        if label[0].startswith(
            ("fuel supply for ", "electricity supply for electric vehicles")
        )
        and inventory.A[0, i, transport, 0] != 0
    ]
    if powertrain == "BEV":
        expected = energy / (
            3600
            * model["battery charge efficiency"].item()
            * model["charger efficiency"].item()
        )
    else:
        expected = energy / (1000 * model["LHV fuel MJ per kg"].item())
    assert -inventory.A[0, supply, transport, 0] == pytest.approx(expected, rel=1e-5)


def test_payload_limit_is_included_in_sizing_and_final_force_balance():
    model = TruckModel(
        inputs(["ICEV-d"], size="18t"),
        cycle="Urban delivery",
        payload={("ICEV-d", "18t", 2025): 20000},
    )
    model.set_all()
    assert 0 < model["cargo mass"].item() < 20000
    assert model["driving mass"].item() == pytest.approx(18000, abs=0.01)
    assert model["cargo mass"].item() == pytest.approx(
        model["available payload"].item()
    )
    assert_final_mass_matches_cycle(model)
    expected_range = (
        model["fuel mass"] * model["LHV fuel MJ per kg"] * 1000 / model["TtW energy"]
    ).item()
    assert expected_range == pytest.approx(150, rel=1e-5)


def test_labelled_samples_and_years_keep_independent_final_states():
    array = inputs(["BEV", "FCEV", "ICEV-d"], years=(2025, 2030))
    array = array.isel(value=[0, 0]).assign_coords(value=["light", "heavy"])
    array.loc[dict(parameter="glider base mass", value="heavy")] *= 1.2
    original = array.copy(deep=True)
    model = TruckModel(array, cycle="Regional delivery")
    model.set_all()
    assert_final_mass_matches_cycle(model)
    for label in array.value.values:
        separate = TruckModel(array.sel(value=[label]), cycle="Regional delivery")
        separate.set_all()
        for parameter in [
            "TtW energy",
            "driving mass",
            "fuel mass",
            "electric energy stored",
        ]:
            np.testing.assert_allclose(
                model[parameter].sel(value=[label]), separate[parameter], rtol=1e-5
            )
    xr.testing.assert_identical(array, original)


def test_unavailable_electric_trucks_remain_masked():
    model = TruckModel(inputs(["BEV", "FCEV", "ICEV-d"], years=(2010, 2025)))
    model.set_all()
    assert (model["TtW energy"].sel(year=2010, powertrain=["BEV", "FCEV"]) == 0).all()
    assert (model["TtW energy"].sel(year=2025) > 0).all()


def test_sizing_remains_bounded():
    model = TruckModel(inputs(["FCEV"]), cycle="Regional delivery", max_iterations=1)
    with pytest.raises(ConvergenceError, match="iteration limit.*FCEV"):
        model.set_all()
