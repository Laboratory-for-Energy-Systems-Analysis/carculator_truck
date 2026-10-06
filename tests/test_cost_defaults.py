"""Independent cash-flow checks and mixed explicit/default truck costs."""

from copy import deepcopy
from functools import lru_cache

import numpy as np
import pytest
import xarray as xr
from carculator_truck import (
    TruckInputParameters,
    TruckModel,
    fill_xarray_from_input_parameters,
)


@lru_cache(maxsize=1)
def template():
    inputs = TruckInputParameters()
    inputs.static()
    _, array = fill_xarray_from_input_parameters(
        inputs, scope={"size": ["40t"], "powertrain": ["BEV"], "year": [2020]}
    )
    return xr.zeros_like(array, dtype=float)


def model_with_costs(**kwargs):
    source = template().isel(value=[0, 0]).assign_coords(value=["custom", "default"])
    model = TruckModel(source, **kwargs)
    values = {
        "glider base mass": 1000,
        "glider base cost per kg": 100,
        "markup factor": 1,
        "kilometers per year": 1000,
        "lifetime kilometers": 10000,
        "target range": 200,
        "battery charge efficiency": 1,
        "maintenance cost per km": 0.2,
        "road toll cost per km": 0.4,
        "share tolled roads": 0.5,
        "CO2 road charge per km": 0.3,
        "insured share of purchase cost": 1,
        "property insurance rate": 0.01,
        "liability insurance rate per km": 0.02,
    }
    for parameter, value in values.items():
        model[parameter] = value
    return model


@pytest.mark.parametrize(
    "parameter,default",
    [
        ("purchase cost", 70000),
        ("maintenance cost", 0.2),
        ("insurance cost", 0.72),
        ("toll cost", 0.2),
        ("CO2 tax cost", 0.3),
    ],
)
def test_nonzero_override_survives_another_samples_missing_cost(parameter, default):
    model = model_with_costs()
    model.array.loc[dict(parameter=parameter, value="custom")] = 42
    model.set_costs()
    assert model[parameter].sel(value="custom").item() == 42
    assert model[parameter].sel(value="default").item() == pytest.approx(default)


def test_explicit_zero_overrides_are_distinct_from_legacy_default_zeros():
    overrides = {
        name: {("BEV", "40t", 2020): 0}
        for name in [
            "purchase cost",
            "maintenance cost",
            "insurance cost",
            "toll cost",
            "CO2 tax cost",
        ]
    }
    original = deepcopy(overrides)
    model = model_with_costs(cost_overrides=overrides)
    model.set_costs()
    assert overrides == original
    for parameter in overrides:
        assert (model[parameter] == 0).all()
    assert (model["amortised purchase cost"] == 0).all()
    assert (model["total cost per km"] == 0).all()


@pytest.mark.parametrize(
    "rate,depreciation",
    [
        (0, 0),
        (1e-15, 0),
        (0.05, 0.18),
        (0.05, 1),
    ],
)
def test_insurance_matches_discounted_premiums_at_rate_limits(rate, depreciation):
    model = model_with_costs()
    model["interest rate"] = rate
    model["depreciation rate per year"] = depreciation
    with np.errstate(divide="raise", invalid="raise", over="raise"):
        model.set_costs()
    annual_repayment = 1 / sum((1 + rate) ** (-t) for t in range(1, 11))
    property_pv = 700 * sum(
        (1 - depreciation) ** t / (1 + rate) ** t for t in range(10)
    )
    liability_pv = 20 * sum((1 + rate) ** (-t) for t in range(1, 11))
    expected = (property_pv + liability_pv) * annual_repayment / 1000
    np.testing.assert_allclose(model["insurance cost"], expected, rtol=1e-12)


@pytest.mark.parametrize(
    "override,match",
    [
        ({"unknown": {}}, "Unsupported"),
        ({"purchase cost": {("BEV", "missing", 2020): 1}}, "unknown size"),
        ({"purchase cost": {"BEV": 1}}, "keys"),
        ({"purchase cost": {("BEV", "40t", 2020): -1}}, "nonnegative"),
        ({"purchase cost": {("BEV", "40t", 2020): np.nan}}, "finite"),
    ],
)
def test_invalid_explicit_cost_overrides_fail_at_construction(override, match):
    with pytest.raises(ValueError, match=match):
        model_with_costs(cost_overrides=override)


@pytest.mark.parametrize("depreciation", [-0.1, 1.1, np.nan, np.inf])
def test_invalid_depreciation_is_rejected(depreciation):
    model = model_with_costs()
    model["depreciation rate per year"] = depreciation
    with pytest.raises(ValueError, match="depreciation rate per year"):
        model.set_costs()


def test_explicit_override_takes_precedence_and_does_not_follow_caller_mutation():
    overrides = {"purchase cost": {("BEV", "40t", 2020): 12345}}
    model = model_with_costs(cost_overrides=overrides)
    overrides["purchase cost"][("BEV", "40t", 2020)] = 67890
    model["purchase cost"] = 42
    model.set_costs()
    assert (model["purchase cost"] == 12345).all()
