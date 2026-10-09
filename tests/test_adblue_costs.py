"""AdBlue billing closes the volume/mass balance of purchased diesel."""

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

DIESEL_MODES = ["ICEV-d", "HEV-d", "PHEV-c-d"]


@pytest.fixture(
    scope="module",
    params=[
        ("default", 0.5),
        ("fossil", 0.5),
        ("biodiesel", 0.5),
        ("mixed", 0.5),
        ("mixed", 0),
        ("mixed", 1),
    ],
    ids=["default", "fossil", "biodiesel", "mixed", "no-electric", "all-electric"],
)
def completed(request):
    blend_name, utility = request.param
    inputs = TruckInputParameters()
    inputs.static()
    _, source = fill_xarray_from_input_parameters(
        inputs,
        scope={
            "size": ["40t"],
            "powertrain": ["ICEV-d", "HEV-d", "PHEV-d", "BEV", "ICEV-g", "FCEV"],
            "year": [2025, 2030],
        },
    )
    source = (
        source.sel(year=[2030, 2025]).isel(value=[0, 0]).assign_coords(value=[9, 2])
    )
    coordinates = {"year": source.year, "value": source.value}
    rates = xr.DataArray(
        [[0.04, 0.06], [0.05, 0]], dims=("year", "value"), coords=coordinates
    )
    prices = xr.DataArray(
        [[1.2, 1.8], [1.4, 1.6]], dims=("year", "value"), coords=coordinates
    )
    source.loc[
        dict(parameter="adblue use per liter diesel", powertrain=DIESEL_MODES)
    ] = rates
    source.loc[dict(parameter="adblue cost per kg", powertrain=DIESEL_MODES)] = prices
    blend = None
    if blend_name != "default":
        share = {"fossil": 1, "biodiesel": 0, "mixed": [0.25, 0.75]}[blend_name]
        blend = {
            "diesel": {
                "primary": {"type": "diesel", "share": share},
                "secondary": {
                    "type": "diesel - biodiesel - cooking oil",
                    "share": (1 - np.asarray(share)).tolist(),
                },
            }
        }
        if blend_name == "mixed":
            # Distinct component densities in year order exercise volume accounting.
            blend["diesel"]["primary"]["density"] = [0.81, 0.83]
            blend["diesel"]["secondary"]["density"] = [0.90, 0.88]
    overrides = {
        "maintenance cost": {("ICEV-d", "40t", 2030): 0, ("HEV-d", "40t", 2030): 0.37}
    }
    original = source.copy(deep=True)
    original_blend = deepcopy(blend)
    original_overrides = deepcopy(overrides)
    model = TruckModel(
        source,
        country="CH",
        cycle="Long haul",
        fuel_blend=blend,
        cost_overrides=overrides,
        drop_hybrids=False,
    )
    model.set_all(electric_utility_factor=utility)
    xr.testing.assert_identical(source, original)
    assert blend == original_blend
    assert overrides == original_overrides
    return model, rates, prices, utility


def test_cost_matches_diesel_purchases_and_adblue_units(completed):
    model, rates, prices, _ = completed
    retained = deepcopy(model)
    retained.drop_hybrid()
    inventory = InventoryTruck(retained, scenario="static", functional_unit="vkm")
    assert np.isfinite(inventory.calculate_impacts()).all()
    np.testing.assert_array_equal(inventory.array.year, [2030, 2025])
    np.testing.assert_array_equal(inventory.array.value, [9, 2])
    for pt in ("ICEV-d", "HEV-d", "PHEV-d"):
        (column,) = inventory.find_input_indices((f"transport, truck, {pt},",))
        (supplier,) = inventory.get_vehicle_supply_indices(
            "fuel supply for diesel vehicles", [column]
        )
        for y, year in enumerate(retained.array.year.values):
            # One kg of the supplied mass-fraction blend occupies this many litres.
            litres_per_kg = sum(
                np.asarray(component["share"])[y]
                / np.broadcast_to(
                    component.get(
                        "density", retained.bs.fuel_specs[component["type"]]["density"]
                    ),
                    (retained.array.sizes["year"],),
                )[y]
                for component in retained.fuel_blend["diesel"].values()
            )
            for v, sample in enumerate(retained.array.value.values):
                mass = -inventory.A[v, supplier, column, y]
                volume = mass * litres_per_kg
                selected = dict(year=year, value=sample)
                # The supplier specifies 1090 kg/m3; the dosing ratio uses L/L.
                adblue_mass = volume * float(rates.sel(**selected)) / 1000 * 1090
                expected = adblue_mass * float(prices.sel(**selected))
                actual = retained["adblue cost"].sel(powertrain=pt, **selected).item()
                assert actual == pytest.approx(expected, rel=2e-6, abs=1e-10)


def test_diesel_share_maintenance_and_non_diesel_controls(completed):
    model, _, _, utility = completed
    np.testing.assert_allclose(
        model["adblue cost"].sel(powertrain="PHEV-d"),
        model["adblue cost"].sel(powertrain="PHEV-c-d") * (1 - utility),
        rtol=2e-6,
        atol=1e-10,
    )
    np.testing.assert_array_equal(
        model["adblue cost"].sel(powertrain=["BEV", "PHEV-e", "ICEV-g", "FCEV"]), 0
    )
    np.testing.assert_array_equal(model["adblue cost"].sel(year=2025, value=2), 0)
    for pt in ("ICEV-d", "HEV-d", "PHEV-d", "PHEV-c-d"):
        expected = model["maintenance cost per km"].sel(powertrain=pt) + model[
            "adblue cost"
        ].sel(powertrain=pt)
        if pt == "ICEV-d":
            expected.loc[dict(year=2030)] = 0
        elif pt == "HEV-d":
            expected.loc[dict(year=2030)] = 0.37
        np.testing.assert_allclose(
            model["maintenance cost"].sel(powertrain=pt),
            expected,
            rtol=2e-6,
            atol=1e-10,
        )
    if utility == 1:
        np.testing.assert_array_equal(model["adblue cost"].sel(powertrain="PHEV-d"), 0)
