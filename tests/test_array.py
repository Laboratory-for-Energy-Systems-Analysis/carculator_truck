from carculator_truck import *
import numpy as np
import pytest


def test_type_cip():
    with pytest.raises(TypeError) as wrapped_error:
        fill_xarray_from_input_parameters("bla")
    assert wrapped_error.type == TypeError


def test_format_array():
    tip = TruckInputParameters()
    tip.static()
    dcts, array = fill_xarray_from_input_parameters(tip)

    assert np.shape(array)[0] == len(dcts[0])
    assert np.shape(array)[1] == len(dcts[1])
    assert np.shape(array)[2] == len(dcts[2])
    assert np.shape(array)[3] == len(dcts[3])


def test_modify_array():
    tip = TruckInputParameters()
    tip.static()
    dcts, array = fill_xarray_from_input_parameters(tip)

    dict_param = {
        ("Driving", "all", "all", "lifetime kilometers", "none"): {
            (2020, "loc"): 150000,
            (2050, "loc"): 150000,
        }
    }

    modify_xarray_from_custom_parameters(dict_param, array)
    assert (
        array.sel(
            powertrain="ICEV-d",
            size="40t",
            year=2020,
            parameter="lifetime kilometers",
        ).sum()
        == 150000
    )


def test_wrong_param_modify_array():
    tip = TruckInputParameters()
    tip.static()
    dcts, array = fill_xarray_from_input_parameters(tip)

    dict_param = {
        ("Driving", "all", "all", "foo", "none"): {
            (2020, "loc"): 150000,
            (2040, "loc"): 150000,
        }
    }

    modify_xarray_from_custom_parameters(dict_param, array)
    with pytest.raises(KeyError) as wrapped_error:
        array.sel(powertrain="ICEV-d", size="40t", year=2020, parameter="foo")
    assert wrapped_error.type == KeyError
