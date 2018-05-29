"""
Test example JSON response assumption files in taxcalc/responses directory
"""
# CODING-STYLE CHECKS:
# pycodestyle est_responses.py
# pylint --disable=locally-disabled test_responses.py

import os
import glob
import pytest  # pylint: disable=unused-import
# pylint: disable=import-error
from taxcalc import Calculator, Consumption, Behavior, GrowDiff, GrowModel


def test_response_json(tests_path):
    """
    Check that each JSON file can be converted into dictionaries that
    can be used to construct objects needed for a Calculator object.
    """
    # pylint: disable=too-many-locals
    responses_path = os.path.join(tests_path, '..', 'responses', '*.json')
    for jpf in glob.glob(responses_path):
        # read contents of jpf (JSON parameter filename)
        jfile = open(jpf, 'r')
        jpf_text = jfile.read()
        # check that jpf_text can be used to construct objects
        response_file = ('"consumption"' in jpf_text and
                         '"behavior"' in jpf_text and
                         '"growdiff_baseline"' in jpf_text and
                         '"growdiff_response"' in jpf_text and
                         '"growmodel"' in jpf_text)
        if response_file:
            # pylint: disable=protected-access
            (con, beh, gdiff_base, gdiff_resp,
             grow_model) = Calculator._read_json_econ_assump_text(jpf_text)
            cons = Consumption()
            cons.update_consumption(con)
            behv = Behavior()
            behv.update_behavior(beh)
            growdiff_baseline = GrowDiff()
            growdiff_baseline.update_growdiff(gdiff_base)
            growdiff_response = GrowDiff()
            growdiff_response.update_growdiff(gdiff_resp)
            growmodel = GrowModel()
            growmodel.update_growmodel(grow_model)
        else:  # jpf_text is not a valid JSON response assumption file
            print('test-failing-filename: ' +
                  jpf)
            assert False


def test_growmodel_json():
    """
    Check dictionaries returned by Calculator._read_json_econ_assump_text(txt)
    when txt includes a "growmodel":value pair.
    """
    txt = """
    {
    "consumption": {},
    "behavior": {},
    "growdiff_baseline": {},
    "growdiff_response": {},
    "growmodel": {}
    }
    """
    # pylint: disable=protected-access
    (con, beh, gdiff_base, gdiff_resp,
     growmod) = Calculator._read_json_econ_assump_text(txt)
    empty_dict = dict()
    assert con == empty_dict
    assert beh == empty_dict
    assert gdiff_base == empty_dict
    assert gdiff_resp == empty_dict
    assert growmod == empty_dict
