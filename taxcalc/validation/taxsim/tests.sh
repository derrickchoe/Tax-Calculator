#!/bin/bash
# Executes Internet-TAXSIM validation TESTS by calling test bash script.
# .... delete testerror file if it exists
rm -f testerror
# .... check number of command-line arguments
if [[ "$#" -gt 1 ]]; then
    echo "ERROR: can specify at most one command-line argument"
    echo "USAGE: ./tests.sh [all]"
    echo "       (using the 'all' option may execute many tests at a time)"
    exit 1
fi
# .... specify whether or not to execute all tests
ALLTESTS=false
if [[ "$#" -eq 1 ]]; then
    if [[ "$1" == "all" ]]; then
        ALLTESTS=true
    else
        echo "ERROR: optional command-line argument must be all"
        echo "USAGE: ./tests.sh [all]"
        exit 1
    fi
fi
# .... execute validation tests
rm -f testerror
if [[ "$ALLTESTS" == true ]] ; then
    bash test.sh a15 &
    bash test.sh d15 &
    wait
else
    bash test.sh d15
fi
if [[ -f "testerror" ]]; then
    ERROR=1
else
    ERROR=0
fi
rm -f testerror
RED=$(tput setaf 1)
GRN=$(tput setaf 2)
BOLD=$(tput bold)
NORMAL=$(tput sgr0)
VALID="TAXSIM VALIDATION TESTS"
if [[ "$ERROR" -eq 1 ]] ; then
    echo "TEST FAILURE: any red lines starting with F between the"
    echo "              STARTING... and FINISHED... lines above"
    echo "              indicate a test failure caused by the actual"
    echo "              *.taxdiffs results being different from the"
    echo "              expected *.taxdiffs results."
    printf "$BOLD$RED============ SOME EXECUTED $VALID FAIL$NORMAL\n"
else
    printf "$BOLD$GRN============ ALL EXECUTED $VALID PASS$NORMAL\n"
fi
exit $ERROR
