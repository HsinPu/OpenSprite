from opensprite.tools.verification_output_policy import pytest_collected_no_tests


def test_pytest_collected_no_tests_detects_standard_pytest_outputs():
    assert pytest_collected_no_tests("collected 0 items")
    assert pytest_collected_no_tests("============== no tests ran in 0.02s ==============")


def test_pytest_collected_no_tests_ignores_regular_failures():
    assert not pytest_collected_no_tests("1 failed, 3 passed")
