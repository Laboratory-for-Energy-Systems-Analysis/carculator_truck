"""Used trucks are waste outputs, with treatment allocated over vehicle use."""

import csv
import io
import warnings
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

# Existing nominal-gross-mass classes and their treatment reference vehicles.
TREATMENT_TONNES = {
    "3.5t": 16,
    "7.5t": 16,
    "18t": 16,
    "26t": 28,
    "32t": 28,
    "40t": 40,
    "60t": 40,
}


def treatment_rows(inventory):
    return [
        inventory.inputs[
            (
                f"treatment of used lorry, {tonnes} metric ton",
                "CH",
                "unit",
                f"used lorry, {tonnes} metric ton",
            )
        ]
        for tonnes in (16, 28, 40)
    ]


def vehicle_column(inventory, size, powertrain):
    return inventory.inputs[(f"truck, {powertrain}, {size}", "CH", "unit", "truck")]


@pytest.fixture(scope="module", params=["diesel", "other-powertrains"])
def completed(request):
    sizes = list(TREATMENT_TONNES) if request.param == "diesel" else ["26t", "40t"]
    powertrains = (
        ["ICEV-d"]
        if request.param == "diesel"
        else ["BEV", "FCEV", "ICEV-g", "HEV-d", "PHEV-d"]
    )
    inputs = TruckInputParameters()
    inputs.static()
    _, array = fill_xarray_from_input_parameters(
        inputs, scope={"size": sizes, "powertrain": powertrains, "year": [2025, 2030]}
    )
    array = array.sel(year=[2030, 2025]).isel(value=[0, 0]).assign_coords(value=[9, 2])
    array.loc[dict(parameter="lifetime kilometers", value=2)] *= 1.1
    original = array.copy(deep=True)
    model = TruckModel(array, cycle="Regional delivery", country="CH")
    model.set_all(electric_utility_factor=0.5)
    xr.testing.assert_identical(array, original)
    assert (model["TtW energy"] > 0).all()
    return model


def test_disposal_has_one_positive_waste_output_and_conserves_scaled_mass(completed):
    inventory = InventoryTruck(completed, scenario="static")
    rows = treatment_rows(inventory)
    for size in completed.array.coords["size"].values:
        tonnes = TREATMENT_TONNES[size]
        for powertrain in completed.array.powertrain.values:
            column = vehicle_column(inventory, size, powertrain)
            quantities = inventory.A[:, rows, column, :]
            assert (quantities >= 0).all()
            np.testing.assert_array_equal(np.count_nonzero(quantities, axis=1), 1)
            np.testing.assert_allclose(
                quantities[:, (16, 28, 40).index(tonnes), :],
                float(size[:-1]) / tonnes,
            )
            disposed_kg = (
                quantities * np.array([16000, 28000, 40000])[None, :, None]
            ).sum(axis=1)
            np.testing.assert_allclose(
                disposed_kg,
                completed["gross mass"]
                .sel(size=size, powertrain=powertrain)
                .transpose("value", "year"),
            )


@pytest.mark.parametrize("scenario", ["static", "SSP2-NPi"])
@pytest.mark.parametrize("functional_unit", ["vkm", "tkm"])
def test_disposal_lcia_matches_treatment_demand_over_lifetime(
    completed, scenario, functional_unit
):
    inventory = InventoryTruck(
        completed, scenario=scenario, functional_unit=functional_unit
    )
    rows = treatment_rows(inventory)
    columns = [
        vehicle_column(inventory, size, pt)
        for size in completed.array.coords["size"].values
        for pt in completed.array.powertrain.values
    ]
    actual = inventory.calculate_impacts()
    assert np.isfinite(actual).all()
    without = deepcopy(inventory)
    for row in rows:
        without.A[:, row, columns, :] = 0
    # Isolate the actual treatment contribution without reconstructing LCIA.
    disposal = (
        (actual - without.calculate_impacts())
        .sel(impact_category="climate change")
        .sum("impact")
    )
    for size in completed.array.coords["size"].values:
        row = rows[(16, 28, 40).index(TREATMENT_TONNES[size])]
        factor = inventory.B.sel(category="climate change").isel(activity=row)
        for year in completed.array.year.values:
            per_unit = float(
                factor.isel(year=0)
                if scenario == "static"
                else factor.interp(year=year)
            )
            # Bundled factors are per +1 used-lorry product. Physical treatment
            # requires a negative product demand; it is not a recycling credit.
            treatment_per_vehicle = -float(size[:-1]) / TREATMENT_TONNES[size]
            cell = completed.array.sel(size=size, year=year)
            expected = (
                treatment_per_vehicle
                * per_unit
                / cell.sel(parameter="lifetime kilometers")
            )
            if functional_unit == "tkm":
                expected /= cell.sel(parameter="cargo mass") / 1000
            np.testing.assert_allclose(
                disposal.sel(size=size, year=year), expected, rtol=2e-6, atol=1e-10
            )
    assert (disposal > 0).all()


@pytest.mark.parametrize("version", ["3.9", "3.10"])
def test_exported_disposal_signs_and_repeated_exports(completed, version):
    model = deepcopy(completed)
    model.array = model.array.sel(value=[2])
    original_model = model.array.copy(deep=True)
    inventory = InventoryTruck(model, scenario="static")
    original_matrix, original_inputs = inventory.A.copy(), inventory.inputs.copy()
    importers = inventory.export_lci(ecoinvent_version=version, format="bw2io")
    assert len(importers) == 2
    expected_count = model.array.sizes["size"] * model.array.sizes["powertrain"]
    for importer in importers:
        vehicles = [a for a in importer.data if a["name"].startswith("truck, ")]
        assert len(vehicles) == expected_count
        for vehicle in vehicles:
            size = vehicle["name"].rsplit(", ", 1)[1]
            (exchange,) = [
                e
                for e in vehicle["exchanges"]
                if e["name"].startswith("treatment of used lorry, ")
            ]
            assert exchange["type"] == "technosphere"
            assert exchange["unit"] == "unit"
            assert exchange["location"] == "CH"
            tonnes = TREATMENT_TONNES[size]
            assert exchange["reference product"] == f"used lorry, {tonnes} metric ton"
            assert exchange["amount"] == pytest.approx(-float(size[:-1]) / tonnes)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*noise.*", category=UserWarning)
        csvs = inventory.export_lci(
            ecoinvent_version=version, software="simapro", format="string"
        )
    assert len(csvs) == 2
    expected_amounts = sorted(
        float(size[:-1]) / TREATMENT_TONNES[size]
        for size in model.array.coords["size"].values
        for _ in model.array.powertrain.values
    )
    for content in csvs:
        amounts = []
        section = None
        for row in csv.reader(io.StringIO(content), delimiter=";"):
            if not row or not row[0]:
                section = None
            elif len(row) == 1:
                section = row[0]
            elif (
                section == "Waste to treatment"
                and "treatment of used lorry" in row[0].lower()
            ):
                assert row[1] == "p"  # SimaPro's unit for one vehicle.
                amounts.append(float(row[2]))
        np.testing.assert_allclose(sorted(amounts), expected_amounts)
    np.testing.assert_array_equal(inventory.A, original_matrix)
    assert inventory.inputs == original_inputs
    xr.testing.assert_identical(model.array, original_model)
