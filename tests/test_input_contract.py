import json
from copy import deepcopy

import pytest
from carculator_truck import TruckInputParameters, fill_xarray_from_input_parameters


@pytest.mark.parametrize("from_file", [False, True])
def test_custom_inputs_are_used_without_modifying_the_caller(tmp_path, from_file):
    parameters = {
        "custom": {
            "name": "custom mass",
            "amount": 42.0,
            "kind": "distribution",
            "uncertainty_type": 1,
            "sizes": ["test size"],
            "powertrain": ["test powertrain"],
            "year": 2020,
        }
    }
    extra = ["custom derived"]
    before = deepcopy(parameters)
    source = parameters
    if from_file:
        source = tmp_path / "parameters.json"
        source.write_text(json.dumps(parameters))
    ip = TruckInputParameters(parameters=source, extra=extra)
    ip.static()
    _, array = fill_xarray_from_input_parameters(ip)
    assert array.sel(parameter="custom mass").item() == 42.0
    assert array.sel(parameter="custom derived").item() == 0.0
    assert parameters == before
    assert extra == ["custom derived"]
