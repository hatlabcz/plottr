import sys
from typing import Dict
import inspect
from dataclasses import dataclass
import numbers

import numpy as np
import lmfit

from plottr import QtGui, QtCore, Slot, Signal
from plottr.utils import fitting_models
from plottr.icons import paramFixIcon
from ..data.datadict import DataDictBase
from .node import Node, NodeWidget, updateOption, updateGuiFromNode

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

@dataclass # TODO : add opther options for parameters, e.g. constrains
class ParamOptions: # Maybe just use the lmfit.Parameter object instead?
    fixed: bool = False
    initialGuess: float = 0
    lowerBound: float = None
    upperBound: float = None


@dataclass
class FittingOptions:
    model: str
    parameters: Dict[str,ParamOptions]


class FittingGui(NodeWidget):
    """ Gui for controlling the fitting function and the initial guess of
    fitting parameters.

    """

    def __init__(self, parent=None, node=None):
        super().__init__(parent)
        self.param_signals = []
        self.default_options = None

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

        self.addUpdateOptions()

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
            # update parameter table for the current selected model function
            self.updateParamTable(current)

    def updateParamTable(self, model: QtGui.QTreeWidgetItem):
        """ Update the parameter table based on the current selected model
        function.
        :param model: the current selected fitting function model
        """
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
        self.param_signals = []
        for idx, name in enumerate(params):
            fixParamButton = self._paramFixButton()

            initialGuessBox = OptionSpinbox(1.0, self)
            lowerBoundBox = NumberInput(None, self)
            upperBoundBox = NumberInput(None, self)
            lowerBoundBox.newTextEntered.connect(initialGuessBox.setMinimum)
            upperBoundBox.newTextEntered.connect(initialGuessBox.setMaximum)

            self.param_signals.extend((fixParamButton.toggled,
                                       initialGuessBox.valueChanged,
                                       lowerBoundBox.newTextEntered,
                                       upperBoundBox.newTextEntered))

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
        return widget

    def addUpdateOptions(self):
        widget = QtGui.QWidget()
        grid = QtGui.QGridLayout()
        liveUpdateCheck = QtGui.QCheckBox('Live Update')
        grid.addWidget(liveUpdateCheck, 0, 0)
        updateButton = QtGui.QPushButton("Update")
        grid.addWidget(updateButton, 0, 1)
        recallButton = QtGui.QPushButton("Recall")
        grid.addWidget(recallButton, 0, 2)

        def _signalAllOptions(*args):# to make it accept signals w/ milti args
            self.signalAllOptions()

        @Slot(QtCore.Qt.CheckState)
        def setLiveUpdate(live:QtCore.Qt.CheckState):
            if live==QtCore.Qt.Checked:
                self.model_tree.currentItemChanged.connect(_signalAllOptions)
                for sig in self.param_signals:
                    sig.connect(_signalAllOptions)
            else:
                try:
                    self.model_tree.currentItemChanged.disconnect(
                        _signalAllOptions)
                except TypeError:
                    pass
                for sig in self.param_signals:
                    try:
                        sig.disconnect(_signalAllOptions)
                    except TypeError:
                        pass


        @Slot()
        def reloadDefaultOption():
            self.fittingOptionSetter(self.default_options)

        liveUpdateCheck.stateChanged.connect(setLiveUpdate)
        updateButton.pressed.connect(self.signalAllOptions)
        recallButton.pressed.connect(reloadDefaultOption)
        recallButton.setToolTip('recall the fitting options stored in the data')

        widget.setLayout(grid)
        self.layout.addWidget(widget)

    def fittingOptionGetter(self) -> FittingOptions:
        """ get all the fitting options and put them into a dictionary
        """
        print('getter in gui called')
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
        print('getter in gui got', fitting_options)
        return fitting_options

    def fittingOptionSetter(self, fitting_options: FittingOptions):
        """ Set all the fitting options
        """
        print('setter in gui called')
        sep_model = fitting_options.model.split('.')
        func_used  = self.model_tree.findItems(sep_model[-1],
                                               QtCore.Qt.MatchRecursive)

        if len(func_used) == 0:
            raise NameError("Function Model doesn't exist")
        if len(func_used) > 1:
            raise NameError("Duplicate function name")
        self.model_tree.setCurrentItem(func_used[0])
        print('in setter, function set to ', sep_model)
        print('now fitting_options is ', fitting_options)
        print('all_param_options is ', fitting_options.parameters)

        for i in range(self.param_table.rowCount()):
            param_name = self.param_table.verticalHeaderItem(i).text()
            param_options = fitting_options.parameters[param_name]
            get_cell = self.param_table.cellWidget
            get_cell(i, 0).setChecked(param_options.fixed)
            get_cell(i, 1).setValue(param_options.initialGuess)
            get_cell(i, 2).setValue(param_options.lowerBound)
            get_cell(i, 3).setValue(param_options.upperBound)

    @updateGuiFromNode
    def setDefaultFit(self, fitting_options):
        print(f'updateGuiFromNode function got {fitting_options}')
        self.fittingOptionSetter(fitting_options)
        if self.default_options is None:
            self.default_options = fitting_options

class OptionSpinbox(QtGui.QDoubleSpinBox):
    """A spinBox widget for parameter options
    :param default_value : default value of the option
    """
    # TODO: Support easier input for large numbers
    def __init__(self, default_value=0, parent=None):
        super().__init__(parent)
        self.setRange(-1 * MAX_FLOAT, MAX_FLOAT)
        self.setValue(default_value)

    def setMaximum(self, maximum):
        try:
            value = eval(maximum)
        except:
            value = MAX_FLOAT
        if isinstance(value, numbers.Number):
            super().setMaximum(value)
        else:
            super().setMaximum(MAX_FLOAT)

    def setMinimum(self, minimum):
        try:
            value = eval(minimum)
        except:
            value = -1 * MAX_FLOAT
        if isinstance(value, numbers.Number):
            super().setMinimum(value)
        else:
            super().setMinimum(-1 * MAX_FLOAT)


class NumberInput(QtGui.QLineEdit):
    """A text edit widget that checks whether its input can be read as a
    number.
    This is copied form the parameter GUI that Wolfgang wrote for the server
    """
    newTextEntered = Signal(str)
    def __init__(self, default_value, parent=None):
        super().__init__(parent)
        self.setValue(default_value)
        self.textChanged.connect(self.checkIfNumber)
        self.editingFinished.connect(self.emitNewText)

    def checkIfNumber(self, value: str):
        try:
            val = eval(value)
        except:
            val = None

    def value(self):
        try:
            value = eval(self.text())
        except:
            return None
        if isinstance(value, numbers.Number):
            return value
        else:
            return None

    def setValue(self, value):
        self.setText(str(value))

    def emitNewText(self):
        self.newTextEntered.emit(self.text())


# ================= Node ==============================
class FittingNode(Node):
    uiClass = FittingGui
    nodeName = "Fitter"
    default_fitting_options = Signal(object)
    def __init__(self, name):
        super().__init__(name)

        self._fitting_options = None

    def process(self, dataIn: DataDictBase = None):
        return self.fitting_process(dataIn)


    @property
    def fitting_options(self):
        return self._fitting_options

    @fitting_options.setter
    @updateOption('fitting_options')
    def fitting_options(self, opt):
        if isinstance(opt, FittingOptions):
            self._fitting_options = opt
        else:
            raise TypeError('Wrong fitting options')




    def fitting_process(self, dataIn: DataDictBase = None):
        if dataIn is None:
            return None

        if len(dataIn.axes()) > 1 or len(dataIn.dependents()) > 1:
            return dict(dataOut=dataIn)

        dataIn_opt = dataIn.get('__fitting_options__')
        dataOut = dataIn.copy()

        if self.fitting_options is None:
            if dataIn_opt is not None:
                self.default_fitting_options.emit(dataIn_opt)
                self._fitting_options = dataIn_opt
            else:
                return dict(dataOut=dataOut)

        print (self.fitting_options)
        # fitting process
        axname = dataIn.axes()[0]
        x = dataIn.data_vals(axname)
        y = dataIn.data_vals(dataIn.dependents()[0])

        model_str = self.fitting_options.model.split('.')
        model_func = MODEL_FUNCS[model_str[0]][model_str[1]]
        fit_params = self.fitting_options.parameters
        p0 = lmfit.Parameters()
        for name, opt in fit_params.items():
            p0.add(name, opt.initialGuess, not opt.fixed,
                   opt.lowerBound, opt.upperBound)
        print ("in process",self.fitting_options)
        fit_model = lmfit.Model(model_func, nan_policy = 'omit')
        result = fit_model.fit(y, p0, x=x)


        if result.success:
            dataOut['fit'] = dict(values=result.best_fit, axes=[axname, ])
            dataOut.add_meta('info', result.fit_report())

        return dict(dataOut=dataOut)

    def setupUi(self):
        super().setupUi()
        self.default_fitting_options.connect(self.ui.setDefaultFit)

        # debug
        # axname = dataIn.axes()[0]
        # x = dataIn.data_vals(axname)
        # model_str = self.fitting_options.model.split('.')
        # func = MODEL_FUNCS[model_str[0]][model_str[1]]
        # fit_params = self.fitting_options.parameters
        # func_args = {arg: fit_params[arg].initialGuess for arg in fit_params}
        #
        # dataOut = dataIn.copy()
        # dataOut['fit'] = dict(values=func(x,**func_args), axes=[axname, ])
        # return dict(dataOut=dataOut)


