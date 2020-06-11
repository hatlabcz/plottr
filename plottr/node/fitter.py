import sys
from typing import Dict
import inspect
from dataclasses import dataclass

import numpy as np
import lmfit

from plottr import QtGui, QtCore, Slot
from plottr.utils import fitting_models
from plottr.icons import paramFixIcon
from ..data.datadict import DataDictBase
from .node import Node, NodeWidget, updateOption

# from PyQt5 import QtGui


__author__ = 'Chao Zhou'
__license__ = 'MIT'


def index_model_functions():
    func_classes = inspect.getmembers(fitting_models, inspect.isclass)
    func_dict = {}
    for c in func_classes:
        funcs = inspect.getmembers(c[1], inspect.isfunction)
        func_dict[c[0]] = {name: func for (name, func) in funcs}
    return func_dict


MODEL_FUNCS = index_model_functions()
MAX_FLOAT = sys.float_info.max

@dataclass
class ParamOptions:
    fixed: bool = False
    initialGuess: float = 0
    lowerBound: float = -MAX_FLOAT
    upperBound: float = MAX_FLOAT


@dataclass
class FittingOptions:
    model: str
    parameters: Dict[str,ParamOptions]


class FittingGui(NodeWidget):
    """ Gui for controlling the fitting function and the initial guess of
    fitting parameters.

    """

    def __init__(self, parent=None, confirm: bool = True, node=None):
        super().__init__(parent)
        self.confirm = confirm
        self.layout = QtGui.QFormLayout()
        self.setLayout(self.layout)

        # set up model function selection widget
        self.model_tree = self.addModelFunctionTree()
        self.model_tree.currentItemChanged.connect(self.modelChanged)

        # set up parameter table
        self.param_table = QtGui.QTableWidget(0, 4)
        self.param_table.setHorizontalHeaderLabels([
            'fix', 'initial guess', 'lower bound', 'upper bound'])
        self.param_table.horizontalHeader(). \
            setSectionResizeMode(0, QtGui.QHeaderView.ResizeToContents)
        self.layout.addWidget(self.param_table)

        self.addConfirm()

        self.optGetters['fitting_options'] = self.fittingOptionGetter
        self.optSetters['fitting_options'] = self.fittingOptionSetter
        #lambda *args: None

    def addModelFunctionTree(self):
        """ Set up the model function tree widget.
        """
        model_tree = QtGui.QTreeWidget()
        model_tree.setHeaderHidden(True)
        for func_type, funcs in MODEL_FUNCS.items():
            model_root = QtGui.QTreeWidgetItem(model_tree, [func_type])
            for func_name, func in funcs.items():
                model_row = QtGui.QTreeWidgetItem(model_root, [func_name])
                model_row.setToolTip(0, func.__doc__)
        if not self.confirm:
            model_tree.currentItemChanged.connect(self.signalAllOptions)

        self.layout.addWidget(model_tree)

        return model_tree

    @Slot(QtGui.QTreeWidgetItem, QtGui.QTreeWidgetItem)
    def modelChanged(self,
                     current: QtGui.QTreeWidgetItem,
                     previous: QtGui.QTreeWidgetItem):
        """ Process a change in fit model selection.
        Will update the parameter table based on the new selection.
        """
        if current.parent() is not None:  # not selecting on root
            print(current.text(0))
            # update parameter table for the current selected model function
            self.updateParamTable(current)

    def updateParamTable(self, model: QtGui.QTreeWidgetItem):
        """ Update the parameter table based on the current selected model
        function.
        :param model: the current selected fitting function model
        """
        print(f"update table: {model.text(0)}")
        # flush param table
        self.param_table.setRowCount(0)
        # rebuild param table based on the selected model function
        func = MODEL_FUNCS[model.parent().text(0)][model.text(0)]
        # assume the first variable is the independent variable
        params = list(inspect.signature(func).parameters)[1:]
        self.param_table.setRowCount(len(params))
        self.param_table.setVerticalHeaderLabels(params)
        # generate fix, initial guess, lower/upper bound option GUIs for each
        # parameter
        for idx, name in enumerate(params):
            fixParamButton = self._paramFixButton()
            initialGuessBox = self._optionSpinbox()
            lowerBoundBox = self._optionSpinbox(default_value=-1 * MAX_FLOAT)
            upperBoundBox = self._optionSpinbox(default_value=MAX_FLOAT)

            lowerBoundBox.valueChanged.connect(initialGuessBox.setMinimum)
            upperBoundBox.valueChanged.connect(initialGuessBox.setMaximum)

            self.param_table.setCellWidget(idx, 0, fixParamButton)
            self.param_table.setCellWidget(idx, 1, initialGuessBox)
            self.param_table.setCellWidget(idx, 2, lowerBoundBox)
            self.param_table.setCellWidget(idx, 3, upperBoundBox)

    def _paramFixButton(self, default_value: bool = False):
        """generate a push button for the parameter fix option
        :param default_value : param is fixed by default or not
        :returns: a button widget
        """
        widget = QtGui.QPushButton(paramFixIcon, '')
        widget.setCheckable(True)
        widget.setChecked(default_value)
        widget.setToolTip("when fixed, the parameter will be fixed to the "
                          "initial guess value during fitting")
        if not self.confirm:
            widget.toggled.connect(self.signalAllOptions)
        return widget

    def _optionSpinbox(self, default_value: float = 0):
        """generate a spinBox for parameter options
        :param default_value : default value of the option
        :returns: a spinbox widget
        """
        # TODO: Support easier input for large numbers
        widget = QtGui.QDoubleSpinBox()
        widget.setRange(-1 * MAX_FLOAT, MAX_FLOAT)
        widget.setValue(default_value)
        if not self.confirm:
            widget.valueChanged.connect(self.signalAllOptions)
        return widget

    def addConfirm(self):
        widget = QtGui.QPushButton('Confirm')
        widget.pressed.connect(self.signalAllOptions)
        self.layout.addWidget(widget)

    def fittingOptionGetter(self) -> FittingOptions:
        """ get all the fitting options and put them into a dictionary
        """
        model_class = self.model_tree.currentItem().parent().text(0)
        model_name = self.model_tree.currentItem().text(0)
        model_str = f"{model_class}.{model_name}"
        parameters = {}
        for i in range(self.param_table.rowCount()):
            param_name = self.param_table.verticalHeaderItem(i).text()
            param_options = ParamOptions()
            get_cell = self.param_table.cellWidget
            param_options.fixed = get_cell(i, 0).isChecked()
            param_options.initialGuess = get_cell(i, 1).value()
            param_options.lowerBound = get_cell(i, 2).value()
            param_options.upperBound = get_cell(i, 3).value()
            parameters[param_name] = param_options

        fitting_options = FittingOptions(model_str, parameters)
        return fitting_options

    def fittingOptionSetter(self, fitting_options: FittingOptions):
        """ Set all the fitting options
        """
        #  Debug
        sep_model = fitting_options.model.split('.')
        func_used  = self.model_tree.findItems('Sinusoidal', QtCore.Qt.MatchRecursive)
        if len(func_used) == 0:
            raise NameError("Function Model doesn't exist")
        if len(func_used) > 1:
            raise NameError("Duplicate function name")
        self.model_tree.setCurrentItem(func_used[0])
        print('hello from setter')

        '''
        for i in range(self.param_table.rowCount()):
            param_name = self.param_table.verticalHeaderItem(i).text()
            param_options = fitting_options.parameters[param_name]
            get_cell = self.param_table.cellWidget
            get_cell(i, 0).setChecked(param_options.fixed)
            get_cell(i, 1).setValue(param_options.initialGuess)
            get_cell(i, 2).setValue(param_options.lowerBound)
            get_cell(i, 3).setValue(param_options.upperBound)
        '''

class FittingNode(Node):
    uiClass = FittingGui
    nodeName = "Fitter"

    def __init__(self, name):
        super().__init__(name)

        self.test_options()

    def process(self, dataIn: DataDictBase = None):
        return print_fitOptions(self, dataIn)

    def test_options(self):
        self._fitting_options = 'not chosen'

        def getter(self):
            return self._fitting_options

        @updateOption('fitting_options')
        def setter(self, val):
            setattr(self, '_fitting_options', val)

        setattr(self.__class__, 'fitting_options', property(getter, setter))



def sinefunc(x, amp, freq, phase):
    return amp * np.sin(2 * np.pi * (freq * x + phase))

def sinefit(self, dataIn: DataDictBase = None):
    if dataIn is None:
        return None

    if len(dataIn.axes()) > 1 or len(dataIn.dependents()) > 1:
        return dict(dataOut=dataIn)

    axname = dataIn.axes()[0]
    x = dataIn.data_vals(axname)
    y = dataIn.data_vals(dataIn.dependents()[0])

    sinemodel = lmfit.Model(sinefunc)
    p0 = sinemodel.make_params(amp=1, freq=0.3, phase=0)
    result = sinemodel.fit(y, p0, x=x)

    dataOut = dataIn.copy()
    if result.success:
        dataOut['fit'] = dict(values=result.best_fit, axes=[axname, ])
        dataOut.add_meta('info', result.fit_report())

    return dict(dataOut=dataOut)


def print_fitOptions(self, dataIn: DataDictBase = None):
    if dataIn is None:
        return None

    if len(dataIn.axes()) > 1 or len(dataIn.dependents()) > 1:
        return dict(dataOut=dataIn)

    print('GUI Selects:', self.fitting_options)
    # self.fitting_options = dataIn.get('__fitting_options__')
    print('From DataIn', dataIn['__fitting_options__'])

    dataOut = dataIn.copy()
    return dict(dataOut=dataOut)


def fitting_process(self, dataIn: DataDictBase = None):
    if dataIn is None:
        return None

    if len(dataIn.axes()) > 1 or len(dataIn.dependents()) > 1:
        return dict(dataOut=dataIn)

    print('GUI Selects:', self.fitting_options)
    print('From DataIn', dataIn['__fitting_options__'])

    print (self.fitting_options)

    dataOut = dataIn.copy()
    return dict(dataOut=dataOut)