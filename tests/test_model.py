import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from carculator_utils.array import fill_xarray_from_input_parameters

from carculator_truck import TruckInputParameters, TruckModel


@pytest.fixture(scope="module")
def array():
    ip = TruckInputParameters()
    ip.static()
    return fill_xarray_from_input_parameters(ip, scope={})[1]


@pytest.fixture(scope="module")
def _model(array):
    model = TruckModel(array, country="CH")
    model.set_all()
    return model


@pytest.fixture
def tm(_model):
    # Tests may modify model state; preserve independence without import-time work.
    return deepcopy(_model)


def test_presence_PHEVe(tm):
    # PHEV-e should be dropped
    assert "PHEV-e" not in tm.array.powertrain.values.tolist()


def test_ttw_energy_against_VECTO(tm):
    # Use the actual urban-delivery envelope: the former lower bound came
    # from long haul. The fixture records primary .vmod hashes and calculation.
    # This is a simulation screening check, not empirical validation.
    reference = json.loads(
        (Path(__file__).parent / "fixtures/vecto_urban_delivery_40t.json").read_text()
    )
    assert tm.cycle == reference["cycle"]
    vecto_empty, vecto_full = [r["energy_kJ_km"] for r in reference["references"]]

    assert (
        vecto_empty
        <= tm.array.sel(
            powertrain="ICEV-d", year=2020, size="40t", parameter="TtW energy", value=0
        )
        <= vecto_full
    )


def test_auxiliary_power_demand(tm):
    # The auxilliary power demand must be lower for combustion trucks
    assert np.all(
        tm.array.sel(
            powertrain="ICEV-d", year=2020, parameter="auxiliary power demand", value=0
        )
        < tm.array.sel(
            powertrain="BEV", year=2020, parameter="auxiliary power demand", value=0
        )
    )


def test_battery_replacement(tm):
    # Battery replacements cannot be lower than 0
    assert np.all(tm["battery lifetime replacements"] >= 0)


def test_cargo_mass(tm):
    # Cargo mass must equal the available payload * load factor

    assert np.allclose(
        (
            tm.array.sel(
                parameter="available payload",
                powertrain="ICEV-d",
                year=2020,
                size="40t",
            )
            * tm.array.sel(
                parameter="capacity utilization",
                powertrain="ICEV-d",
                year=2020,
                size="40t",
            )
        ),
        tm.array.sel(
            parameter="cargo mass", powertrain="ICEV-d", year=2020, size="40t"
        ),
        rtol=1e-3,
    )


def test_electric_utility_factor(tm):
    # Electric utility factor must be between 0 and 1
    assert bool(
        (
            (tm["electric utility factor"] >= 0) & (tm["electric utility factor"] <= 1)
        ).all()
    )
    assert (
        tm.array.sel(parameter="electric utility factor", powertrain="PHEV-d").all() > 0
    )


def test_fuel_blends(tm):
    # Shares of a fuel blend must equal 1
    for fuel in tm.fuel_blend:
        np.testing.assert_array_equal(
            np.array(tm.fuel_blend[fuel]["primary"]["share"])
            + np.array(tm.fuel_blend[fuel]["secondary"]["share"]),
            np.ones(tm.array.sizes["year"]),
        )

    # A fuel cannot be specified both as primary and secondary fuel
    for fuel in tm.fuel_blend:
        assert (
            tm.fuel_blend[fuel]["primary"]["type"]
            != tm.fuel_blend[fuel]["secondary"]["type"]
        )


def test_battery_mass(tm):
    # Battery mass must equal cell mass and BoP mass

    assert np.allclose(
        tm.array.sel(
            parameter="energy battery mass", powertrain="BEV", year=2030, size="40t"
        ),
        tm.array.sel(
            parameter="battery cell mass", powertrain="BEV", year=2030, size="40t"
        )
        + tm.array.sel(
            parameter="battery BoP mass", powertrain="BEV", year=2030, size="40t"
        ),
    )

    # Cell mass must equal capacity divided by energy density of cells

    assert np.allclose(
        tm.array.sel(
            parameter="battery cell mass", powertrain="BEV", year=2030, size="40t"
        ),
        tm.array.sel(
            parameter="electric energy stored", powertrain="BEV", year=2030, size="40t"
        )
        / tm.array.sel(
            parameter="battery cell energy density",
            powertrain="BEV",
            year=2030,
            size="40t",
        ),
    )


def test_model_results(tm):
    # Assert useful physical invariants rather than writing an unchecked workbook.
    selected = tm.array.sel(year=2020)
    for parameter in ("curb mass", "driving mass", "TtW energy"):
        values = selected.sel(parameter=parameter)
        assert np.all(np.isfinite(values)), parameter
        assert np.all(values >= 0), parameter
    assert np.all(
        selected.sel(parameter="driving mass") >= selected.sel(parameter="curb mass")
    )
