"""Small formula tests: explicit inputs, no sizing loop or reference spreadsheet."""

from functools import lru_cache

import numpy as np
import pytest
import xarray as xr
from hypothesis import given, settings
from hypothesis import strategies as st

from carculator_truck import (
    TruckInputParameters,
    TruckModel,
    fill_xarray_from_input_parameters,
)


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


@pytest.mark.parametrize(
    "labels,available,driving,expected",
    [
        ([7], [1], [20000], "1.2"),
        ([9, 2], [1, 0], [20000, 42000], "1.2"),
        (["changed", "reference"], [0, 1], [20000, 42000], "-2.0-"),
        (["changed", "reference"], [1, 0], [20000, 21000], "/"),
    ],
)
def test_payload_table_uses_one_retained_sample(
    labels, available, driving, expected, capsys
):
    source = (
        parameter_template().isel(value=[0] * len(labels)).assign_coords(value=labels)
    )
    model = TruckModel(source)
    model["gross mass"] = 40000
    model["driving mass"] = xr.DataArray(
        driving, dims="value", coords={"value": labels}
    )
    model["cargo mass"] = xr.DataArray(
        [1200, 2400][: len(labels)], dims="value", coords={"value": labels}
    )
    model["is_available"] = xr.DataArray(
        available, dims="value", coords={"value": labels}
    )
    model["is_compliant"] = 1
    model["TtW energy"] = 100
    capsys.readouterr()
    model.remove_energy_consumption_from_unavailable_vehicles()
    (row,) = [
        line for line in capsys.readouterr().out.splitlines() if "BEV, 2020" in line
    ]
    assert row.split("|")[2].strip() == expected
    np.testing.assert_array_equal(model.array.value, labels)
    # Reporting must leave the per-sample physical masks intact.
    np.testing.assert_array_equal(
        model["TtW energy"].values.ravel(),
        np.where((np.asarray(available) != 0) & (np.asarray(driving) <= 40000), 100, 0),
    )
