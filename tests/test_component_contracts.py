"""Small formula tests: explicit inputs, no sizing loop or reference spreadsheet."""

from functools import lru_cache

import numpy as np
import pytest
import xarray as xr
from carculator_truck import (
    TruckInputParameters,
    TruckModel,
    fill_xarray_from_input_parameters,
)
from hypothesis import given, settings
from hypothesis import strategies as st


@lru_cache(maxsize=1)
def parameter_template():
    ip = TruckInputParameters()
    ip.static()
    _, array = fill_xarray_from_input_parameters(
        ip, scope={"size": ["40t"], "powertrain": ["BEV"], "year": [2020]}
    )
    return xr.zeros_like(array, dtype=float)


def model_with(**parameters):
    model = TruckModel(parameter_template().copy(deep=True))
    for name, value in parameters.items():
        model[name.replace("_", " ")] = value
    return model


@settings(max_examples=30, derandomize=True, deadline=None, database=None)
@given(
    base=st.floats(min_value=10, max_value=10000),
    reduction=st.floats(min_value=0, max_value=1),
    battery=st.floats(min_value=0, max_value=1000),
    passengers=st.integers(min_value=0, max_value=10),
    cargo=st.floats(min_value=0, max_value=1000),
)
def test_mass_balance(base, reduction, battery, passengers, cargo):
    model = model_with(
        glider_base_mass=base,
        lightweighting=reduction,
        battery_cell_mass=battery,
        average_passengers=passengers,
        average_passenger_mass=75,
        cargo_mass=cargo,
        gross_mass=40000,
    )
    model.set_vehicle_masses()
    expected_curb = base * (1 - reduction) + battery
    expected_cargo = passengers * 75 + cargo
    assert model["curb mass"].item() == pytest.approx(expected_curb)
    assert model["total cargo mass"].item() == pytest.approx(expected_cargo)
    assert model["driving mass"].item() == pytest.approx(expected_curb + expected_cargo)
    assert model["available payload"].item() == pytest.approx(
        40000 - expected_curb - passengers * 75
    )


@pytest.mark.parametrize(
    "order",
    [
        ("value", "year", "parameter", "powertrain", "size"),
        ("parameter", "powertrain", "value", "size", "year"),
    ],
)
def test_labelled_axes_and_model_instances_are_independent(order):
    source = (
        parameter_template()
        .copy(deep=True)
        .isel(value=[0, 0])
        .assign_coords(value=["low", "high"])
    )
    source.loc[dict(parameter="glider base mass")] = xr.DataArray(
        [100.0, 200.0], dims="value", coords={"value": ["low", "high"]}
    )
    original = source.copy(deep=True)
    first = TruckModel(source.transpose(*order))
    second = TruckModel(source)
    first.set_vehicle_masses()
    np.testing.assert_allclose(first["curb mass"].values.ravel(), [100, 200])
    first["glider base mass"] = 999
    xr.testing.assert_identical(source, original)
    xr.testing.assert_identical(second.array, original)
