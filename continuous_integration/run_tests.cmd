call activate %CONDA_ENV%

@echo on

set PYTHONFAULTHANDLER=1

@rem `--capture=sys` avoids clobbering faulthandler tracebacks on crash
set PYTEST=py.test --capture=sys

@rem %PYTEST% -v --runslow dask\dataframe\tests\test_groupby.py
%PYTEST% -v -m "not requires_pufcsv and not pre_release and not local" --pep8
