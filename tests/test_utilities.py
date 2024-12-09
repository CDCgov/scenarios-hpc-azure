from argparse import ArgumentError

import pytest

import scenarios_hpc_azure.utils as utils


def test_combine_dict_no_override():
    a = {"a": True}
    b = {"a": False}
    combined = utils._combine_dicts(a, b)
    assert combined["a"], "dict `a` was overriden when it should not have been"


def test_combine_dict_yes_override():
    a = {"a": None}
    b = {"a": True}
    combined = utils._combine_dicts(a, b)
    assert combined["a"], "dict `a` was not overriden when it should have been"


def test_combine_dict_new_param():
    a = {"a": True}
    b = {"b": True}
    combined = utils._combine_dicts(a, b)
    assert combined[
        "b"
    ], "dict `a` was not given a key b when it should have been"


def test_combine_dict_both_none():
    a = {"a": None}
    b = {"a": None}
    combined = utils._combine_dicts(a, b)
    assert combined["a"] is None, "a['a'] should remain None"


def test_validate_args_exists():
    test = {"a": 1}
    # will not error, passes
    utils.validate_args(test, required_args=["a"])


def test_validate_args_no_required_args():
    test = {"a": None}
    # will not error, passes
    utils.validate_args(test, required_args=[])


def test_validate_args_required_none():
    test = {"a": None}
    # will error
    with pytest.raises(ArgumentError):
        utils.validate_args(test, required_args=["a"])


def test_validate_args_required_does_not_exist():
    test = {"a": 1}
    # will error
    with pytest.raises(ArgumentError):
        utils.validate_args(test, required_args=["b"])


def test_validate_args_non_required_none():
    test = {"a": 1, "b": None}
    # "b" not required, so it being None is fine
    utils.validate_args(test, required_args=["a"])
