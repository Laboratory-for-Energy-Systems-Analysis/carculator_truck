"""Shared throughput boundary for depot charger costs and physical inventories."""

import numpy as np
import xarray as xr


def annual_charger_throughput(
    power_kw, trucks, annual_km, grid_kwh_per_km, availability=0.98, efficiency=0.94
):
    """Return grid kWh/year served by one charger, limited by its capacity.

    For hybrids, consumption refers to the electric mode before utility-factor
    weighting. Depot share and electric-driving share are applied when allocating
    costs or hardware to vehicle-km, retaining the existing service convention.
    The capacity factors are assumptions, not additional electricity losses.
    """
    demand = trucks * annual_km * grid_kwh_per_km
    capacity = power_kw * 8760.0 * availability * efficiency
    return xr.apply_ufunc(np.minimum, demand, capacity)
