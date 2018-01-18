"""
Tax-Calculator Input-Output class.
"""
# CODING-STYLE CHECKS:
# pep8 --ignore=E402 taxcalcio.py
# pylint --disable=locally-disabled taxcalcio.py

import os
import copy
import sqlite3
import six
import numpy as np
import pandas as pd
from taxcalc.policy import Policy
from taxcalc.records import Records
from taxcalc.consumption import Consumption
from taxcalc.behavior import Behavior
from taxcalc.growdiff import Growdiff
from taxcalc.growfactors import Growfactors
from taxcalc.calculate import Calculator
from taxcalc.utils import (delete_file, write_graph_file,
                           add_quantile_bins, unweighted_sum, weighted_sum)


class TaxCalcIO(object):
    """
    Constructor for the Tax-Calculator Input-Output class.

    TaxCalcIO class constructor call must be followed by init() call.

    Parameters
    ----------
    input_data: string or Pandas DataFrame
        string is name of INPUT file that is CSV formatted containing
        variable names in the Records.USABLE_READ_VARS set, or
        Pandas DataFrame is INPUT data containing variable names in
        the Records.USABLE_READ_VARS set.  INPUT vsrisbles not in the
        Records.USABLE_READ_VARS set can be present but are ignored.

    tax_year: integer
        calendar year for which taxes will be computed for INPUT.

    reform: None or string
        None implies no policy reform (current-law policy), or
        string is name of optional REFORM file.

    assump: None or string
        None implies economic assumptions are standard assumptions,
        or string is name of optional ASSUMP file.

    outdir: None or string
        None implies output files written to current directory,
        or string is name of optional output directory

    Returns
    -------
    class instance: TaxCalcIO
    """
    # pylint: disable=too-many-instance-attributes

    def __init__(self, input_data, tax_year, reform, assump, outdir=None):
        # pylint: disable=too-many-arguments
        # pylint: disable=too-many-branches,too-many-statements
        self.errmsg = ''
        # check name and existence of INPUT file
        inp = 'x'
        if isinstance(input_data, six.string_types):
            # remove any leading directory path from INPUT filename
            fname = os.path.basename(input_data)
            # check if fname ends with ".csv"
            if fname.endswith('.csv'):
                inp = '{}-{}'.format(fname[:-4], str(tax_year)[2:])
            else:
                msg = 'INPUT file name does not end in .csv'
                self.errmsg += 'ERROR: {}\n'.format(msg)
            # check existence of INPUT file
            self.cps_input_data = input_data.endswith('cps.csv')
            if not self.cps_input_data and not os.path.isfile(input_data):
                msg = 'INPUT file could not be found'
                self.errmsg += 'ERROR: {}\n'.format(msg)
        elif isinstance(input_data, pd.DataFrame):
            inp = 'df-{}'.format(str(tax_year)[2:])
        else:
            msg = 'INPUT is neither string nor Pandas DataFrame'
            self.errmsg += 'ERROR: {}\n'.format(msg)
        # check name and existence of REFORM file
        ref = '-x'
        if reform is None:
            self.specified_reform = False
            ref = '-#'
        elif isinstance(reform, six.string_types):
            self.specified_reform = True
            # remove any leading directory path from REFORM filename
            fname = os.path.basename(reform)
            # check if fname ends with ".json"
            if fname.endswith('.json'):
                ref = '-{}'.format(fname[:-5])
            else:
                msg = 'REFORM file name does not end in .json'
                self.errmsg += 'ERROR: {}\n'.format(msg)
            # check existence of REFORM file
            if not os.path.isfile(reform):
                msg = 'REFORM file could not be found'
                self.errmsg += 'ERROR: {}\n'.format(msg)
        else:
            msg = 'TaxCalcIO.ctor: reform is neither None nor str'
            self.errmsg += 'ERROR: {}\n'.format(msg)
        # check name and existence of ASSUMP file
        asm = '-x'
        if assump is None:
            asm = '-#'
        elif isinstance(assump, six.string_types):
            # remove any leading directory path from ASSUMP filename
            fname = os.path.basename(assump)
            # check if fname ends with ".json"
            if fname.endswith('.json'):
                asm = '-{}'.format(fname[:-5])
            else:
                msg = 'ASSUMP file name does not end in .json'
                self.errmsg += 'ERROR: {}\n'.format(msg)
            # check existence of ASSUMP file
            if not os.path.isfile(assump):
                msg = 'ASSUMP file could not be found'
                self.errmsg += 'ERROR: {}\n'.format(msg)
        else:
            msg = 'TaxCalcIO.ctor: assump is neither None nor str'
            self.errmsg += 'ERROR: {}\n'.format(msg)
        # check name and existence of OUTDIR
        if outdir is None:
            valid_outdir = True
        elif isinstance(outdir, six.string_types):
            # check existence of OUTDIR
            if os.path.isdir(outdir):
                valid_outdir = True
            else:
                valid_outdir = False
                msg = 'OUTDIR could not be found'
                self.errmsg += 'ERROR: {}\n'.format(msg)
        else:
            valid_outdir = False
            msg = 'TaxCalcIO.ctor: outdir is neither None nor str'
            self.errmsg += 'ERROR: {}\n'.format(msg)
        # create OUTPUT file name and delete any existing output files
        output_filename = '{}{}{}.csv'.format(inp, ref, asm)
        if outdir is None:
            self._output_filename = output_filename
            delete_old_files = True
        elif valid_outdir:
            self._output_filename = os.path.join(outdir, output_filename)
            delete_old_files = True
        else:
            delete_old_files = False
        if delete_old_files:
            delete_file(self._output_filename)
            delete_file(self._output_filename.replace('.csv', '.db'))
            delete_file(self._output_filename.replace('.csv', '-doc.text'))
            delete_file(self._output_filename.replace('.csv', '-tab.text'))
            delete_file(self._output_filename.replace('.csv', '-atr.html'))
            delete_file(self._output_filename.replace('.csv', '-mtr.html'))
        # initialize variables whose values are set in init method
        self.behavior_has_any_response = False
        self.calc = None
        self.calc_base = None
        self.param_dict = None

    def init(self, input_data, tax_year, reform, assump,
             growdiff_response,
             aging_input_data, exact_calculations):
        """
        TaxCalcIO class post-constructor method that completes initialization.

        Parameters
        ----------
        First four parameters are same as for TaxCalcIO constructor:
            input_data, tax_year, reform, assump.

        growdiff_response: Growdiff object or None
            growdiff_response Growdiff object is used only by the
            TaxCalcIO.growmodel_analysis method;
            must be None in all other cases.

        aging_input_data: boolean
            whether or not to extrapolate Records data from data year to
            tax_year.

        exact_calculations: boolean
            specifies whether or not exact tax calculations are done without
            any smoothing of "stair-step" provisions in the tax law.
        """
        # pylint: disable=too-many-arguments,too-many-locals
        # pylint: disable=too-many-statements,too-many-branches
        self.errmsg = ''
        # get parameter dictionaries from --reform and --assump files
        paramdict = Calculator.read_json_param_objects(reform, assump)
        # create Behavior object
        beh = Behavior()
        beh.update_behavior(paramdict['behavior'])
        self.behavior_has_any_response = beh.has_any_response()
        # create gdiff_baseline object
        gdiff_baseline = Growdiff()
        gdiff_baseline.update_growdiff(paramdict['growdiff_baseline'])
        # create Growfactors base object that incorporates gdiff_baseline
        gfactors_base = Growfactors()
        gdiff_baseline.apply_to(gfactors_base)
        # specify gdiff_response object
        if growdiff_response is None:
            gdiff_response = Growdiff()
            gdiff_response.update_growdiff(paramdict['growdiff_response'])
        elif isinstance(growdiff_response, Growdiff):
            gdiff_response = growdiff_response
        else:
            gdiff_response = None
            msg = 'TaxCalcIO.more_init: growdiff_response is neither None '
            msg += 'nor a Growdiff object'
            self.errmsg += 'ERROR: {}\n'.format(msg)
        if gdiff_response is not None:
            some_gdiff_response = gdiff_response.has_any_response()
            if self.behavior_has_any_response and some_gdiff_response:
                msg = 'ASSUMP file cannot specify any "behavior" when using '
                msg += 'GrowModel or when ASSUMP file has "growdiff_response"'
                self.errmsg += 'ERROR: {}\n'.format(msg)
        # create Growfactors ref object that has both gdiff objects applied
        gfactors_ref = Growfactors()
        gdiff_baseline.apply_to(gfactors_ref)
        if gdiff_response is not None:
            gdiff_response.apply_to(gfactors_ref)
        # create Policy objects
        if self.specified_reform:
            pol = Policy(gfactors=gfactors_ref)
            try:
                pol.implement_reform(paramdict['policy'])
                self.errmsg += pol.reform_errors
            except ValueError as valerr_msg:
                self.errmsg += valerr_msg.__str__()
        else:
            pol = Policy(gfactors=gfactors_base)
        base = Policy(gfactors=gfactors_base)
        # check for valid tax_year value
        if tax_year < pol.start_year:
            msg = 'tax_year {} less than policy.start_year {}'
            msg = msg.format(tax_year, pol.start_year)
            self.errmsg += 'ERROR: {}\n'.format(msg)
        if tax_year > pol.end_year:
            msg = 'tax_year {} greater than policy.end_year {}'
            msg = msg.format(tax_year, pol.end_year)
            self.errmsg += 'ERROR: {}\n'.format(msg)
        # any errors imply cannot proceed with calculations
        if self.errmsg:
            return
        # set policy to tax_year
        pol.set_year(tax_year)
        base.set_year(tax_year)
        # read input file contents into Records objects
        if aging_input_data:
            if self.cps_input_data:
                recs = Records.cps_constructor(
                    gfactors=gfactors_ref,
                    exact_calculations=exact_calculations
                )
                recs_base = Records.cps_constructor(
                    gfactors=gfactors_base,
                    exact_calculations=exact_calculations
                )
            else:  # if not cps_input_data
                recs = Records(
                    data=input_data,
                    gfactors=gfactors_ref,
                    exact_calculations=exact_calculations
                )
                recs_base = Records(
                    data=input_data,
                    gfactors=gfactors_base,
                    exact_calculations=exact_calculations
                )
        else:  # input_data are raw data that are not being aged
            recs = Records(data=input_data,
                           gfactors=None,
                           exact_calculations=exact_calculations,
                           weights=None,
                           adjust_ratios=None,
                           start_year=tax_year)
            recs_base = copy.deepcopy(recs)
        if tax_year < recs.data_year:
            msg = 'tax_year {} less than records.data_year {}'
            msg = msg.format(tax_year, recs.data_year)
            self.errmsg += 'ERROR: {}\n'.format(msg)
        # create Calculator objects
        con = Consumption()
        con.update_consumption(paramdict['consumption'])
        self.calc = Calculator(policy=pol, records=recs,
                               verbose=True,
                               consumption=con,
                               behavior=beh,
                               sync_years=aging_input_data)
        self.calc_base = Calculator(policy=base, records=recs_base,
                                    verbose=False,
                                    consumption=con,
                                    sync_years=aging_input_data)
        # remember parameter dictionary for reform documentation
        self.param_dict = paramdict

    def custom_dump_variables(self, tcdumpvars_str):
        """
        Return set of variable names extracted from tcdumpvars_str, which
        contains the contents of the tcdumpvars file in the current directory.
        Also, builds self.errmsg if any custom variables are not valid.
        """
        assert isinstance(tcdumpvars_str, six.string_types)
        self.errmsg = ''
        # change some common delimiter characters into spaces
        dump_vars_str = tcdumpvars_str.replace(',', ' ')
        dump_vars_str = dump_vars_str.replace(';', ' ')
        dump_vars_str = dump_vars_str.replace('|', ' ')
        # split dump_vars_str into a list of dump variables
        dump_vars_list = dump_vars_str.split()
        # check that all dump_vars_list items are valid
        valid_set = Records.USABLE_READ_VARS | Records.CALCULATED_VARS
        for var in dump_vars_list:
            if var not in valid_set:
                msg = 'invalid variable name in tcdumpvars file: {}'
                msg = msg.format(var)
                self.errmsg += 'ERROR: {}\n'.format(msg)
        # add essential variables even if not on custom list
        if 'RECID' not in dump_vars_list:
            dump_vars_list.append('RECID')
        if 'FLPDYR' not in dump_vars_list:
            dump_vars_list.append('FLPDYR')
        # convert list into a set and return
        return set(dump_vars_list)

    def tax_year(self):
        """
        Return calendar year for which TaxCalcIO calculations are being done.
        """
        return self.calc.policy.current_year

    def output_filepath(self):
        """
        Return full path to output file named in TaxCalcIO constructor.
        """
        dirpath = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(dirpath, self._output_filename)

    def analyze(self, writing_output_file=False,
                output_tables=False,
                output_graphs=False,
                output_ceeu=False,
                dump_varset=None,
                output_dump=False,
                output_sqldb=False):
        """
        Conduct tax analysis.

        Parameters
        ----------
        writing_output_file: boolean
           whether or not to generate and write output file

        output_tables: boolean
           whether or not to generate and write distributional tables
           to a text file

        output_graphs: boolean
           whether or not to generate and write HTML graphs of average
           and marginal tax rates by income percentile

        output_ceeu: boolean
           whether or not to calculate and write to stdout standard
           certainty-equivalent expected-utility statistics

        dump_varset: set
           custom set of variables to include in dump and sqldb output;
           None implies include all variables in dump and sqldb output

        output_dump: boolean
           whether or not to replace standard output with all input and
           calculated variables using their Tax-Calculator names

        output_sqldb: boolean
           whether or not to write SQLite3 database with dump table
           containing same output as written by output_dump to a csv file

        Returns
        -------
        Nothing
        """
        # pylint: disable=too-many-arguments,too-many-branches
        # in order to use print(), pylint: disable=superfluous-parens
        if self.calc.policy.reform_warnings:
            warn = 'PARAMETER VALUE WARNING(S):  {}\n{}{}'
            print(warn.format('(read documentation for each parameter)',
                              self.calc.policy.reform_warnings,
                              'CONTINUING WITH CALCULATIONS...'))
        calc_base_calculated = False
        if output_dump or output_sqldb:
            # might need marginal tax rates
            (mtr_paytax, mtr_inctax,
             _) = self.calc.mtr(wrt_full_compensation=False)
        else:
            # definitely do not need marginal tax rates
            mtr_paytax = None
            mtr_inctax = None
        if self.behavior_has_any_response:
            self.calc = Behavior.response(self.calc_base, self.calc)
            calc_base_calculated = True
        else:
            self.calc.calc_all()
        # optionally conduct normative welfare analysis
        if output_ceeu:
            if self.behavior_has_any_response:
                ceeu_results = 'SKIP --ceeu output because baseline and '
                ceeu_results += 'reform cannot be sensibly compared\n '
                ceeu_results += '                  '
                ceeu_results += 'when specifying "behavior" with --assump '
                ceeu_results += 'option'
            elif self.calc.total_weight() <= 0.:
                ceeu_results = 'SKIP --ceeu output because '
                ceeu_results += 'sum of weights is not positive'
            else:
                self.calc_base.calc_all()
                calc_base_calculated = True
                cedict = self.calc_base.ce_aftertax_income(
                    self.calc,
                    custom_params=None,
                    require_no_agg_tax_change=False)
                ceeu_results = TaxCalcIO.ceeu_output(cedict)
        else:
            ceeu_results = None
        # extract output if writing_output_file
        if writing_output_file:
            self.write_output_file(output_dump, dump_varset,
                                   mtr_paytax, mtr_inctax)
            self.write_doc_file()
        # optionally write --sqldb output to SQLite3 database
        if output_sqldb:
            self.write_sqldb_file(dump_varset, mtr_paytax, mtr_inctax)
        # optionally write --tables output to text file
        if output_tables:
            if not calc_base_calculated:
                self.calc_base.calc_all()
                calc_base_calculated = True
            self.write_tables_file()
        # optionally write --graphs output to HTML files
        if output_graphs:
            if not calc_base_calculated:
                self.calc_base.calc_all()
                calc_base_calculated = True
            self.write_graph_files()
        # optionally write --ceeu output to stdout
        if ceeu_results:
            print(ceeu_results)

    def write_output_file(self, output_dump, dump_varset,
                          mtr_paytax, mtr_inctax):
        """
        Write output to CSV-formatted file.
        """
        if output_dump:
            outdf = self.dump_output(dump_varset, mtr_inctax, mtr_paytax)
            column_order = sorted(outdf.columns)
        else:
            outdf = self.minimal_output()
            column_order = outdf.columns
        assert len(outdf.index) == self.calc.array_len
        outdf.to_csv(self._output_filename, columns=column_order,
                     index=False, float_format='%.2f')

    def write_doc_file(self):
        """
        Write reform documentation to text file.
        """
        doc = Calculator.reform_documentation(self.param_dict)
        doc_fname = self._output_filename.replace('.csv', '-doc.text')
        with open(doc_fname, 'w') as dfile:
            dfile.write(doc)

    def write_sqldb_file(self, dump_varset, mtr_paytax, mtr_inctax):
        """
        Write dump output to SQLite3 database table dump.
        """
        outdf = self.dump_output(dump_varset, mtr_inctax, mtr_paytax)
        assert len(outdf.index) == self.calc.array_len
        db_fname = self._output_filename.replace('.csv', '.db')
        dbcon = sqlite3.connect(db_fname)
        outdf.to_sql('dump', dbcon, if_exists='replace', index=False)
        dbcon.close()

    def write_tables_file(self):
        """
        Write tables to text file.
        """
        # pylint: disable=too-many-locals
        tab_fname = self._output_filename.replace('.csv', '-tab.text')
        # skip tables if there are not some positive weights
        if self.calc_base.total_weight() <= 0.:
            with open(tab_fname, 'w') as tfile:
                msg = 'No tables because sum of weights is not positive\n'
                tfile.write(msg)
            return
        # create list of results for nontax variables
        # - weights don't change with reform
        # - expanded_income may change, so always use baseline expanded income
        nontax_vars = ['s006', 'expanded_income']
        nontax = [self.calc_base.array(var) for var in nontax_vars]
        # create list of results for tax variables from reform Calculator
        tax_vars = ['iitax', 'payrolltax', 'lumpsum_tax', 'combined']
        reform = [self.calc.array(var) for var in tax_vars]
        # create DataFrame with tax distribution under reform
        dist = nontax + reform  # using expanded_income under baseline policy
        all_vars = nontax_vars + tax_vars
        distdf = pd.DataFrame(data=np.column_stack(dist), columns=all_vars)
        # create DataFrame with tax differences (reform - baseline)
        base = [self.calc_base.array(var) for var in tax_vars]
        change = [(reform[idx] - base[idx]) for idx in range(0, len(tax_vars))]
        diff = nontax + change  # using expanded_income under baseline policy
        diffdf = pd.DataFrame(data=np.column_stack(diff), columns=all_vars)
        # write each kind of distributional table
        with open(tab_fname, 'w') as tfile:
            TaxCalcIO.write_decile_table(distdf, tfile, tkind='Reform Totals')
            tfile.write('\n')
            TaxCalcIO.write_decile_table(diffdf, tfile, tkind='Differences')

    @staticmethod
    def write_decile_table(dfx, tfile, tkind='Totals'):
        """
        Write to tfile the tkind decile table using dfx DataFrame.
        """
        dfx = add_quantile_bins(dfx, 'expanded_income', 10,
                                weight_by_income_measure=False)
        gdfx = dfx.groupby('bins', as_index=False)
        rtns_series = gdfx.apply(unweighted_sum, 's006')
        xinc_series = gdfx.apply(weighted_sum, 'expanded_income')
        itax_series = gdfx.apply(weighted_sum, 'iitax')
        ptax_series = gdfx.apply(weighted_sum, 'payrolltax')
        htax_series = gdfx.apply(weighted_sum, 'lumpsum_tax')
        ctax_series = gdfx.apply(weighted_sum, 'combined')
        # write decile table to text file
        row = 'Weighted Tax {} by Baseline Expanded-Income Decile\n'
        tfile.write(row.format(tkind))
        rowfmt = '{}{}{}{}{}{}\n'
        row = rowfmt.format('    Returns',
                            '    ExpInc',
                            '    IncTax',
                            '    PayTax',
                            '     LSTax',
                            '    AllTax')
        tfile.write(row)
        row = rowfmt.format('       (#m)',
                            '      ($b)',
                            '      ($b)',
                            '      ($b)',
                            '      ($b)',
                            '      ($b)')
        tfile.write(row)
        rowfmt = '{:9.2f}{:10.1f}{:10.1f}{:10.1f}{:10.1f}{:10.1f}\n'
        for decile in range(0, 10):
            row = '{:2d}'.format(decile)
            row += rowfmt.format(rtns_series[decile] * 1e-6,
                                 xinc_series[decile] * 1e-9,
                                 itax_series[decile] * 1e-9,
                                 ptax_series[decile] * 1e-9,
                                 htax_series[decile] * 1e-9,
                                 ctax_series[decile] * 1e-9)
            tfile.write(row)
        row = ' A'
        row += rowfmt.format(rtns_series.sum() * 1e-6,
                             xinc_series.sum() * 1e-9,
                             itax_series.sum() * 1e-9,
                             ptax_series.sum() * 1e-9,
                             htax_series.sum() * 1e-9,
                             ctax_series.sum() * 1e-9)
        tfile.write(row)

    def write_graph_files(self):
        """
        Write graphs to HTML files.
        """
        pos_wght_sum = self.calc.records.s006.sum() > 0.
        # income-change-by-decile graph
        dec_fname = self._output_filename.replace('.csv', '-dec.html')
        dec_title = 'Income Change by Income Decile'
        if pos_wght_sum:
            fig = self.calc_base.decile_graph(self.calc)
            write_graph_file(fig, dec_fname, dec_title)
        else:
            reason = 'No graph because sum of weights is not positive'
            TaxCalcIO.write_empty_graph_file(dec_fname, dec_title, reason)
        # average-tax-rate graph
        atr_fname = self._output_filename.replace('.csv', '-atr.html')
        atr_title = 'ATR by Income Percentile'
        if pos_wght_sum:
            fig = self.calc_base.atr_graph(self.calc)
            write_graph_file(fig, atr_fname, atr_title)
        else:
            reason = 'No graph because sum of weights is not positive'
            TaxCalcIO.write_empty_graph_file(atr_fname, atr_title, reason)
        # marginal-tax-rate graph
        mtr_fname = self._output_filename.replace('.csv', '-mtr.html')
        mtr_title = 'MTR by Income Percentile'
        if pos_wght_sum:
            fig = self.calc_base.mtr_graph(
                self.calc, alt_e00200p_text='Taxpayer Earnings')
            write_graph_file(fig, mtr_fname, mtr_title)
        else:
            reason = 'No graph because sum of weights is not positive'
            TaxCalcIO.write_empty_graph_file(mtr_fname, mtr_title, reason)

    @staticmethod
    def write_empty_graph_file(fname, title, reason):
        """
        Write HTML graph file with title but no graph for specified reason.
        """
        txt = ('<html>\n'
               '<head><title>{}</title></head>\n'
               '<body><center<h1>{}</h1></center></body>\n'
               '</html>\n').format(title, reason)
        with open(fname, 'w') as gfile:
            gfile.write(txt)

    def minimal_output(self):
        """
        Extract minimal output and return it as Pandas DataFrame.
        """
        varlist = ['RECID', 'YEAR', 'WEIGHT', 'INCTAX', 'LSTAX', 'PAYTAX']
        odict = dict()
        scalc = self.calc
        odict['RECID'] = scalc.array('RECID')  # id for tax filing unit
        odict['YEAR'] = self.tax_year()  # tax calculation year
        odict['WEIGHT'] = scalc.array('s006')  # sample weight
        odict['INCTAX'] = scalc.array('iitax')  # federal income taxes
        odict['LSTAX'] = scalc.array('lumpsum_tax')  # lump-sum tax
        odict['PAYTAX'] = scalc.array('payrolltax')  # payroll taxes (ee+er)
        odf = pd.DataFrame(data=odict, columns=varlist)
        return odf

    @staticmethod
    def ceeu_output(cedict):
        """
        Extract --ceeu output and return as text string.
        """
        text = ('Aggregate {} Pre-Tax Expanded Income and '
                'Tax Revenue ($billion)\n')
        txt = text.format(cedict['year'])
        txt += '           baseline     reform   difference\n'
        fmt = '{} {:12.3f} {:10.3f} {:12.3f}\n'
        txt += fmt.format('income', cedict['inc1'], cedict['inc2'],
                          cedict['inc2'] - cedict['inc1'])
        alltaxdiff = cedict['tax2'] - cedict['tax1']
        txt += fmt.format('alltax', cedict['tax1'], cedict['tax2'],
                          alltaxdiff)
        txt += ('Certainty Equivalent of Expected Utility of '
                'After-Tax Expanded Income ($)\n')
        txt += ('(assuming consumption equals '
                'after-tax expanded income)\n')
        txt += 'crra       baseline     reform     pctdiff\n'
        fmt = '{} {:17.2f} {:10.2f} {:11.2f}\n'
        for crra, ceeu1, ceeu2 in zip(cedict['crra'],
                                      cedict['ceeu1'],
                                      cedict['ceeu2']):
            txt += fmt.format(crra, ceeu1, ceeu2,
                              100.0 * (ceeu2 - ceeu1) / ceeu1)
        if abs(alltaxdiff) >= 0.0005:
            txt += ('WARN: baseline and reform cannot be '
                    'sensibly compared\n')
            text = ('      because "alltax difference" is '
                    '{:.3f} which is not zero\n')
            txt += text.format(alltaxdiff)
            txt += ('FIX: adjust _LST or another reform policy parameter '
                    'to bracket\n')
            txt += ('     "alltax difference" equals zero and '
                    'then interpolate')
        else:
            txt += 'NOTE: baseline and reform can be sensibly compared\n'
            txt += '      because "alltax difference" is essentially zero'
        return txt

    def dump_output(self, dump_varset, mtr_inctax, mtr_paytax):
        """
        Extract dump output and return it as Pandas DataFrame.
        """
        if dump_varset is None:
            varset = Records.USABLE_READ_VARS | Records.CALCULATED_VARS
        else:
            varset = dump_varset
        # create and return dump output DataFrame
        odf = pd.DataFrame()
        for varname in varset:
            vardata = self.calc.array(varname)
            if varname in Records.INTEGER_VARS:
                odf[varname] = vardata
            else:
                odf[varname] = vardata.round(2)  # rounded to nearest cent
        # specify mtr values in percentage terms
        if 'mtr_inctax' in varset:
            odf['mtr_inctax'] = (mtr_inctax * 100).round(2)
        if 'mtr_paytax' in varset:
            odf['mtr_paytax'] = (mtr_paytax * 100).round(2)
        # specify tax calculation year
        odf['FLPDYR'] = self.tax_year()
        return odf

    @staticmethod
    def growmodel_analysis(input_data, tax_year, reform, assump,
                           aging_input_data, exact_calculations,
                           writing_output_file=False,
                           output_tables=False,
                           output_graphs=False,
                           output_ceeu=False,
                           output_dump=False):
        """
        High-level logic for dynamic analysis using GrowModel class.

        Parameters
        ----------
        First six parameters are same as the first six parameters of
        the TaxCalcIO.init method.

        Last five parameters are same as the first five parameters of
        the TaxCalcIO.analyze method.

        Returns
        -------
        Nothing
        """
        # pylint: disable=too-many-arguments,too-many-locals
        progress = 'STARTING ANALYSIS FOR YEAR {}'
        gdiff_dict = {Policy.JSON_START_YEAR: {}}
        for year in range(Policy.JSON_START_YEAR, tax_year + 1):
            print(progress.format(year))  # pylint: disable=superfluous-parens
            # specify growdiff_response using gdiff_dict
            growdiff_response = Growdiff()
            growdiff_response.update_growdiff(gdiff_dict)
            gd_dict = TaxCalcIO.annual_analysis(input_data, tax_year,
                                                reform, assump,
                                                aging_input_data,
                                                exact_calculations,
                                                growdiff_response, year,
                                                writing_output_file,
                                                output_tables,
                                                output_graphs,
                                                output_ceeu,
                                                output_dump)
            gdiff_dict[year + 1] = gd_dict

    @staticmethod
    def annual_analysis(input_data, tax_year, reform, assump,
                        aging_input_data, exact_calculations,
                        growdiff_response, year,
                        writing_output_file,
                        output_tables,
                        output_graphs,
                        output_ceeu,
                        output_dump):
        """
        Conduct static analysis for specifed year and growdiff_response.

        Parameters
        ----------
        First six parameters are same as the first six parameters of
        the TaxCalcIO.init method.

        Last five parameters are same as the first five parameters of
        the TaxCalcIO.analyze method.

        Returns
        -------
        gd_dict: Growdiff sub-dictionary for year+1
        """
        # pylint: disable=too-many-arguments
        # instantiate TaxCalcIO object for specified year and growdiff_response
        tcio = TaxCalcIO(input_data=input_data,
                         tax_year=year,
                         reform=reform,
                         assump=assump)
        tcio.init(input_data=input_data,
                  tax_year=year,
                  reform=reform,
                  assump=assump,
                  growdiff_response=growdiff_response,
                  aging_input_data=aging_input_data,
                  exact_calculations=exact_calculations)
        if year == tax_year:
            # conduct final tax analysis for year equal to tax_year
            tcio.analyze(writing_output_file=writing_output_file,
                         output_tables=output_tables,
                         output_graphs=output_graphs,
                         output_ceeu=output_ceeu,
                         output_dump=output_dump)
            gd_dict = {}
        else:
            # conduct intermediate tax analysis for year less than tax_year
            tcio.analyze()
            # build dict in gdiff_dict key:dict pair for key equal to next year
            # ... extract tcio results for year needed by GrowModel class
            # >>>>> add logic here <<<<<
            # ... use extracted results to advance GrowModel to next year
            # >>>>> add logic here <<<<<
            # ... extract next year GrowModel results for next year gdiff_dict
            # >>>>> add logic here <<<<<
            gd_dict = {}  # TEMPORARY CODE
        return gd_dict
