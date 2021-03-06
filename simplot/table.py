import ROOT
import StringIO
import pprint
import itertools
import os
import math
import csv

import prettytable
import subprocess

###############################################################################

class StringFormatter:
    def __init__(self, fstr):
        self._fstr = fstr
    def __call__(self, entry):
        return self._fstr.format(entry)

_defaultformatter = StringFormatter("{:.2g}")

###############################################################################

class SignificantFigureFormatter:
    def __init__(self, n):
        self._n = n

    def __call__(self, entry):
        return str(self._round_sig(entry, self._n))

    def _round_sig(self, x, sig):
        #stolen from: http://stackoverflow.com/questions/3410976/how-to-round-a-number-to-significant-figures-in-python
        if x == 0:
            ret = x
        else:
            ret = round(x, sig-int(math.floor(math.log10(abs(x)))) - 1)
        return ret

###############################################################################

class Table:
    def __init__(self, name, headrow):
        self._name = name
        self._headrow = None
        self._setheadrow(headrow)
        self._rows = []
        self._hlines = []
            
    def _setheadrow(self, headrow):
        #ensure that header row is all strings
        if headrow is not None:
            headrow = [str(e) for e in headrow]
        self._headrow = headrow
        return

    def addhline(self):
        self._hlines.append(len(self._rows))

    def pophline(self):
        if len(self._hlines):
            self._hlines.pop()
        return
        
    def addrow(self, row):
        self._rows.append(row)
    
    def get_nrows(self):
        return len(self._rows)
    
    def get_ncols(self):
        return max( (len(l) for l in self._rows) )
    
    def get_rows(self):
        return self._rows
    
    def get_headrow(self):
        return self._headrow

    def _get_rows_with_headrow(self):
        ret = list(self._rows)
        if self._headrow:
            ret.insert(0, list(self._headrow))
        return ret
    
    def get_name(self):
        return self._name

    @staticmethod
    def tablefromdict(name, container, headrow=None):
        table = Table(name, headrow=headrow)
        if headrow:
            table._setheadrow(headrow)
        for key, row in container.iteritems():
            inputrow = [key] + row
            table.addrow(inputrow)
        return table
    
    @staticmethod
    def tablefrommatrix(name, matrix, xlabels=None, ylabels=None):
        nrows = matrix.GetNrows()
        ncols = matrix.GetNcols()
        if xlabels is None:
            xlabels = [str(i) for i in range(ncols)]
        if ylabels is None:
            ylabels = [str(i) for i in range(nrows)]
        tab = Table(name, headrow=ylabels)
        for j in xrange(nrows):
            row = [ xlabels[j] ]
            for i in xrange(ncols):
                v = matrix[i][j]
                row.append(v)
            tab.addrow(row)
        return tab

    def __str__(self):
        return "Table("+self.name+")"
    
###############################################################################

class TableOutputBase(object):
    def __init__(self, formatter):
        if formatter is None:
            formatter = _defaultformatter
        self._formatter = formatter
    
    def write(self, table, filename):
        try:
            os.makedirs(os.path.dirname(filename))
        except os.error:
            pass
        with open(filename,"w") as outfile:
            print >>outfile,self.getstring(table)
    
    def getstring(self, table):
        raise NotImplementedError("Users of this class should override this method.")

    def _get_printed_head_row(self, table):
        result = None
        if table.get_headrow():
            if len(table.get_headrow())==table.get_ncols()-1:
                result = [ "" ] + table.get_headrow()
            else:
                result = list(table.get_headrow())
        return result

    def _convert_row_to_string(self, row):
        strRow = [self._convert_entry_to_string(v) for v in row]
        return strRow

    def _convert_entry_to_string(self, entry):
        strValue = None
        if isinstance(entry, basestring):
            #already a string, copy value
            strValue = str(entry)
        else:
            #not a string, try to get value and format
            try:
                value,error = self._get_value_and_error(entry)
                vs = self._formatter(value)
                es = ""
                if error is not None:
                    es = self._formatter(error)
                    strValue = vs + " +- " + es
                else:
                    strValue = vs
            except Exception:
                #can't convert to string, fall back on standard python string conversion
                strValue = str(entry)
                raise
        return strValue

    def _get_value_and_error(self, entry):
        value,error = None,None
        try:
            #is it a single number?
            value = float(entry)
        except:
            try:
                #try unpacking a tuple
                value, error = entry
                value = float(value)
                error = float(error)
            except:
                #don't know what to do now, raise an exception
                raise Exception("can't convert entry to value and error", entry)
        return value, error

    def _calc_col_widths(self, tab):
        header = self._get_printed_head_row(tab)
        colwidth = [len(str(x)) for x in header]
        for row in tab.get_rows():
            rowstr = [self._convert_entry_to_string(n) for n in row]
            width = [len(x) for x in rowstr]
            for index in xrange(len(width)):
                colwidth[index] = max(colwidth[index], width[index])
        return colwidth

###############################################################################

class TableLatexOutput(TableOutputBase):
    def __init__(self, formatter=None):
        super(TableLatexOutput, self).__init__(formatter)
        
    def getstring(self, table):
        return self._getlatex(table)
    
    def _getlatex(self, table):
        latex = StringIO.StringIO()
        nrows = table.get_nrows()
        ncols = table.get_ncols()
        newLine = " \\\\\n"
        colformat = "|".join(["c"]*ncols)
        print >>latex,"{"
        print >>latex,"%\\tiny" 
        print >>latex,"\\begin{tabular}{"+colformat+"}"
        hrow = self._get_printed_head_row(table)
        if hrow:
            allData = [hrow] + table.get_rows()
        else:
            allData = table.get_rows()
        for row in allData:
            strRow = self._convert_row_to_string(row)
            strRow = self._sanitise_latex_row(strRow)
            line = " & ".join(strRow) + newLine
            print >>latex,line,
        print >>latex,"\\end{tabular}"
        print >>latex,"}" 
        return latex.getvalue()
    
    def _sanitise_latex_row(self, row):
        result = [self._sanitise_latex_string(entry) for entry in row]
        return result
    
    def _sanitise_latex_string(self, entry):
        mathgroups = entry.split("$")
        result = []
        for i, text in enumerate(mathgroups):
            if i%2:
                #even, math mode
                #put the $ back in
                text = "$" + text + "$"
            else:
                #deal with underscores
                text = text.replace("\\_","_")
                text = text.replace("_","\\_")
                #change \pm
                text.replace("+-","\\ensuremath{\\pm}")
            result.append(text)
        return "".join(result)

###############################################################################

class TableAsciiOutput(TableOutputBase):
    def __init__(self, formatter=None, alignment="c"):
        super(TableAsciiOutput, self).__init__(formatter)
        self._alignment = alignment
        if not any([alignment == a for a in ("l", "r", "c")]):
            raise ValueError("TableAsciiOutput given invalid alignment string", alignment)
        
    def getstring(self, table):
        return self._get_ascii_table(table)

    def _get_ascii_table(self, table):
        pt = prettytable.PrettyTable(self._get_printed_head_row(table))
        pt.align = self._alignment
        for row in table.get_rows():
            row = [ self._convert_entry_to_string(n) for n in row]
            pt.add_row(row)
        return str(pt)

###############################################################################

class TableOrgOutput(TableOutputBase):
    def __init__(self, formatter=None):
        super(TableOrgOutput, self).__init__(formatter)

    def getstring(self, table):
        return self._get_org_table(table)

    def _get_org_table(self, table):
        nrows = table.get_nrows()
        ncols = table.get_ncols()
        colwidth = self._calc_col_widths(table)
        #flatten rows to a list of strings
        flattable = []
        for rownum, row in enumerate(table._get_rows_with_headrow()):
            row = [ self._convert_entry_to_string(n) for n in row]
            #pad short rows with whitespace
            row = [r.ljust(w) for r, w in zip(row, colwidth)]
            row = "| " + " | ".join(row) + " |"
            flattable.append(row)
        #create a horizontal rule
        hline = ["-"*(w + 2)  for w in colwidth]
        hline = "|" + "+".join(hline) + "|"
        #inject hlines
        for rnum in reversed(sorted(table._hlines)):
            flattable.insert(rnum + 1, hline)
        if table.get_headrow() is not None:
            flattable.insert(1, hline)
        flattable.insert(0, hline)
        flattable.insert(len(flattable), hline)
        #merge to a single string
        sio = StringIO.StringIO()
        for row in flattable:
            print >>sio, row
        return sio.getvalue()

    def write(self, table, filename, latex=False, pdf=False, html=False):
        super(TableOrgOutput, self).write(table, filename)
        if (latex or pdf or html) and os.path.exists(filename):
            with open("/dev/null", "w") as devnull:
                cmd = ["emacs",  filename, "--batch", "-u", "${USER}", "-f", "org-latex-export-to-latex", "--kill"]
                subprocess.call(cmd, stdout=devnull, stderr=devnull)
                if pdf or html:
                    latexfilename = filename.replace(".org", ".tex")
                    if latexfilename == filename:
                        latexfilename += ".tex"
                    if os.path.exists(latexfilename):
                        if pdf:
                            try:
                                cmd = ["pandoc", "-f", "latex", "-o", latexfilename.replace(".tex", ".pdf"), latexfilename]
                                subprocess.check_call(cmd, stdout=devnull, stderr=devnull)
                            except:
                                cmd = ["pdflatex", "-output-directory", os.path.basename(latexfilename)]
                                subprocess.call(cmd, stdout=devnull, stderr=devnull, cwd=os.path.dirname(latexfilename))
                        if html:
                            cmd = ["htlatex", os.path.basename(latexfilename)]
                            subprocess.call(cmd, stdout=devnull, stderr=devnull, cwd=os.path.dirname(latexfilename))
        return

###############################################################################

class TableCsvOutput(TableOutputBase):
    def __init__(self, formatter=None):
        super(TableCsvOutput, self).__init__(formatter)

    def getstring(self, table):
        return self._get_csv_table(table)

    def _get_csv_table(self, table):
        sio = StringIO.StringIO()
        out = csv.writer(sio)
        for row in table._get_rows_with_headrow():
            row = [ self._convert_entry_to_string(n) for n in row]
            out.writerow(row)
        return sio.getvalue()

###############################################################################

def unitTest():
    #create some random data
    r1 = dict()
    colNames = ["col"+str(i) for i in xrange(3)]
    rowNames = ["row"+str(i) for i in xrange(5)]
    rand = ROOT.TRandom3()
    for ir,rn in enumerate(rowNames):
        r1[rn] = [ float(ir+1)+float(ic+1)/10.0 for ic,n in enumerate(colNames) ]
    #create the table
    table = Table.tablefromdict("table_unitTest", r1, headerRow = colNames)
    canv = table.drawColzPlot()
    canv.SaveAs(canv.GetName()+".eps")
    print table.getLatexTable()
    print table.getAsciiTable()
    table.prettyPrint()
    raw_input("wait")
    return

def main():
    unitTest()
    return
    
    
    
    

if __name__ == "__main__":
    main()
    
    
