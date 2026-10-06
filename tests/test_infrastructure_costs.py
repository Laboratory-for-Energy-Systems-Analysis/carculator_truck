"""Infrastructure costs from cash flows and charger energy throughput."""

import numpy as np
import pytest
import xarray as xr
from carculator_truck.model import TruckModel, _crf


@pytest.mark.parametrize("rate", [0.0, 1e-12, 0.05, -0.01])
def test_capital_recovery_repays_principal(rate):
    # Independent finite sum of discounted annual payments, not the closed form.
    expected = 1 / sum((1 + rate) ** (-year) for year in range(1, 11))
    with np.errstate(all="raise"):
        assert float(_crf(rate, 10)) == pytest.approx(expected, rel=1e-10)


def infrastructure(rate=0, demand=10000, power=10, lifetime=10):
    return TruckModel.__new__(TruckModel).set_depot_infrastructure_costs(
        charger_power_kw=power,
        charger_life_years=lifetime,
        infra_wacc=rate,
        capex_per_kw=100,
        install_per_kw=20,
        connection_per_kw=30,
        fixed_om_share=0.02,
        capacity_charge_per_kw_year=3,
        trucks_per_charger=1,
        annual_km_per_truck=demand,
        consumption_kwh_per_km_at_plug=1,
        availability=1,
        efficiency=1,
    )


@pytest.mark.parametrize("demand", [10000, 100000, 0])
def test_infrastructure_annual_cost_and_energy_limit(demand):
    # EUR 1500 upfront: 150 repayment + 30 maintenance + 30 capacity annually.
    expected = 210 / min(demand, 87600) if demand else 0
    assert float(infrastructure(demand=demand)) == pytest.approx(expected)


def test_infrastructure_preserves_sample_labels_and_broadcasts():
    demand = xr.DataArray(
        [10000.0, 100000.0], dims="value", coords={"value": ["low", "high"]}
    )
    rates = xr.DataArray([0.0, 0.05], dims="year", coords={"year": [2020, 2030]})
    result = infrastructure(rate=rates, demand=demand)
    assert set(result.dims) == {"value", "year"}
    for year, rate in [(2020, 0), (2030, 0.05)]:
        annual = 1500 / sum((1 + rate) ** (-k) for k in range(1, 11)) + 60
        assert result.sel(value="low", year=year).item() == pytest.approx(
            annual / 10000
        )
        assert result.sel(value="high", year=year).item() == pytest.approx(
            annual / 87600
        )


def test_non_charging_vehicle_needs_no_charger_lifetime():
    assert float(infrastructure(power=0, lifetime=0)) == 0


def test_mixed_charging_and_non_charging_vehicles():
    coordinates = {"powertrain": ["ICEV-d", "BEV"]}
    power = xr.DataArray([0.0, 10.0], dims="powertrain", coords=coordinates)
    lifetime = xr.DataArray([0.0, 10.0], dims="powertrain", coords=coordinates)
    result = infrastructure(power=power, lifetime=lifetime)
    assert result.sel(powertrain="ICEV-d").item() == 0
    assert result.sel(powertrain="BEV").item() == pytest.approx(210 / 10000)


def test_active_charger_requires_positive_lifetime():
    with pytest.raises(ValueError, match="years"):
        infrastructure(power=10, lifetime=0)
