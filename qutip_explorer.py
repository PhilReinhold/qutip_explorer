from PyQt4.QtCore import Qt, QObject, pyqtSignal
from PyQt4.QtGui import QApplication, QWidget, QHBoxLayout, QPushButton, QSplitter, QTabWidget, \
    QLabel, QMainWindow, QProgressBar, QPixmap, QFocusEvent, QGroupBox, QRadioButton, QDockWidget
from numpy import linspace
from pyqtgraph import ImageView
from pyqtgraph.dockarea import DockArea
from qutip import *
from copy import copy
from interface_helpers import *


class ModeItem(FormItem):
    def __init__(self):
        super(ModeItem, self).__init__("Mode", [
            ("dimension", int, 2),
            ("frequency", float, 1),
            ("anharmonicity", float, 0),
            ("decay", float, 0),
            ("dephasing", float, 0),
            ("drive amplitude", float, 0),
            ("drive angle", float, 0),
            ("initial state", int, 0),
            ("initial displacement", float, 0),
            ("initial leg count", int, 1),
        ])

        # Initial-leg-phases


class CrossModeGroupItem(GroupItem):
    def __init__(self):
        super(CrossModeGroupItem, self).__init__("Cross-Mode Terms", "Cross-Mode Term", CrossModeItem)
        # self.context_menu = ActionsMenu([("Add Cross-Mode Term", self.add_term)])

        self.array_model = UpperHalfArrayModel()
        array_view = QTableView()
        array_view.setModel(self.array_model)
        type_group = QGroupBox()
        type_layout = QVBoxLayout(type_group)
        self.cross_kerr_type_radio = QRadioButton("Cross-Kerr")
        self.cross_kerr_type_radio.setChecked(True)
        self.xx_type_radio = QRadioButton("X-X")
        type_layout.addWidget(self.cross_kerr_type_radio)
        type_layout.addWidget(self.xx_type_radio)
        self.dialog = OKCancelDialog(QLabel("Mode Array"), array_view, type_group)

    def add_item(self):
        self.array_model.set_n(self.parent().mode_count)
        if self.dialog.exec_():
            if self.cross_kerr_type_radio.isChecked():
                type_str = "Cross-Kerr"
            elif self.xx_type_radio.isChecked():
                type_str = "X-X"
            for i, row in enumerate(self.array_model.array):
                for j, val in enumerate(row):
                    if val:
                        self.appendRow(CrossModeItem(type_str, val, i + 1, j + 1))


class CrossModeItem(FormItem):
    def __init__(self, type, val, mode_1, mode_2):
        name = type + str((mode_1, mode_2))
        super(CrossModeItem, self).__init__(name, [
            ("type", ["Cross-Kerr", "X-X"], type),
            ("strength", float, val),
            ("mode 1", int, mode_1),
            ("mode 2", int, mode_2),
        ])


class OutputItem(FormItem):
    def __init__(self):
        super(OutputItem, self).__init__("Output", [
            ("Mode", int, 1),
            ("Type", ["Wigner", "Expect-XYZ"], "Wigner")
        ])


class PulseItem(FormItem):
    def __init__(self):
        super(PulseItem, self).__init__("Pulse", [
            ("Frequency", float, 1),
            ("Amplitude", float, 1),
            ("Profile", ["Square", "Gaussian"], "Square"),
            ("Duration", float, 1),
        ])


class SimulationItem(FormItem):
    def __init__(self):
        super(SimulationItem, self).__init__("Simulation", [
            ("Time", float, 10),
            ("Steps", int, 100),
        ])
        self.modes_item = GroupItem("Modes", "Mode", ModeItem)
        self.cross_kerr_item = CrossModeGroupItem()
        self.outputs_item = GroupItem("Outputs", "Output", OutputItem)
        self.pulses_item = GroupItem("Pulses", "Pulse", PulseItem)

        self.appendRow(self.modes_item)
        self.appendRow(self.cross_kerr_item)
        self.appendRow(self.outputs_item)
        self.appendRow(self.pulses_item)

        self.mode_count = 0
        def increment_mode_count():
            self.mode_count += 1
        def decrement_mode_count():
            self.mode_count -= 1
        self.modes_item.emitter.item_added.connect(increment_mode_count)



class SimulationsModel(QStandardItemModel):
    mode_added = pyqtSignal(QStandardItem)

    def __init__(self):
        super(SimulationsModel, self).__init__()
        self.itemChanged.connect(self.update_handler)

    def update_handler(self, item):
        parent = item.parent()
        if parent is None:
            return
        if isinstance(item, FormItem):
            item.params_model.item(0, 1).setText(item.text())
        name = str(parent.child(item.row(), 0).text())
        if isinstance(parent, FormItem):
            if name in parent.dtypes:
                item.setData(str(parent.dtypes[name](item.text())))
        if name == "Mode Count":
            n = int(item.text())
            modes = parent.modes_item
            while modes.rowCount() < n:
                m = ModeItem()
                modes.appendRow(m)
                self.mode_added.emit(m)
            while modes.rowCount() > n:
                modes.removeRow(modes.rowCount())


class SimulationsView(ContextMenuStandardTreeView):
    def __init__(self):
        super(SimulationsView, self).__init__()
        self.setModel(SimulationsModel())
        self.model().mode_added.connect(self.expand_item)
        self.context_menu = ActionsMenu([("Add Simulation", self.add_simulation)])

    def expand_item(self, item):
        idx = self.model().indexFromItem(item)
        self.expand(idx)
        for i in range(item.rowCount()):
            self.expand_item(item.child(i, 0))

    def add_simulation(self):
        item = SimulationItem()
        self.model().appendRow(item)
        self.expand_item(item)
        self.resizeColumnToContents(0)




class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.tree_widget = SimulationsView()
        self.eqn_widget = ResizableImage("latex/eqn.png", 100, .5, 2)
        self.outputs_dock = DockArea()

        self.tree_dock = QDockWidget("Project Manager")
        self.props_dock = QDockWidget("Properties")
        self.eqn_dock = QDockWidget("Equation")

        self.tree_dock.setWidget(self.tree_widget)
        self.eqn_dock.setWidget(self.eqn_widget)

        self.setCentralWidget(self.outputs_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tree_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.props_dock)
        self.addDockWidget(Qt.TopDockWidgetArea, self.eqn_dock)

        self.tree_widget.add_simulation()
        self.tree_widget.clicked.connect(self.set_props)

    def set_props(self, index):
        item = self.tree_widget.model().itemFromIndex(index)
        if hasattr(item, "params_widget"):
            self.props_dock.setWidget(item.params_widget)


    def set_eqn(self, suffix):
        if suffix:
            suffix = "_" + suffix
        path = os.path.join("latex", "eqn%s.png"%suffix)
        self.eqn_widget.set_file()
        self.full_pixmap = QPixmap(path)
        self.eqn_widget.setPixmap(self.full_pixmap.scaledToHeight(self.eqn_height, Qt.SmoothTransformation))

    def resize_eqn(self, splitter_pos, idx):
        aspect = float(self.full_pixmap.height())/self.full_pixmap.width()

        self.eqn_height = max(50, int(.9*splitter_pos))
        self.eqn_height = min(aspect*self.width(), self.eqn_height)
        self.eqn_widget.setPixmap(self.full_pixmap.scaledToHeight(self.eqn_height, Qt.SmoothTransformation))


if __name__ == '__main__':
    app = QApplication([])
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


class Window(QMainWindow):
    def __init__(self):
        super(Window, self).__init__()
        central_widget = QSplitter(Qt.Vertical)
        self.setCentralWidget(central_widget)
        # main_layout = QVBoxLayout(central_widget)
        self.eqn_widget = QLabel()
        self.eqn_widget.setAlignment(Qt.AlignHCenter)
        self.eqn_height = 165
        self.set_eqn("")
        central_widget.splitterMoved.connect(self.resize_eqn)
        central_widget.addWidget(self.eqn_widget)
        self.split = split = QSplitter()
        central_widget.addWidget(split)
        side_bar = QWidget()
        split.addWidget(side_bar)
        layout = QVBoxLayout(side_bar)
        self.mode_count_spin = QSpinBox()
        self.mode_count_spin.setValue(1)
        self.mode_count_spin.valueChanged.connect(self.update_count)
        self.mode_box = QTabWidget()
        self.cross_kerr_table = UpperHalfArrayModel()
        self.cross_kerr_box = QTableView()
        self.cross_kerr_box.setModel(self.cross_kerr_table)
        self.change_eqn_on_click(self.cross_kerr_box, "kerr")
        self.modes = []

        mode_count_layout = QHBoxLayout()
        mode_count_layout.addWidget(QLabel("Mode Count"))
        mode_count_layout.addWidget(self.mode_count_spin)
        layout.addLayout(mode_count_layout)
        layout.addWidget(self.mode_box)
        layout.addWidget(QLabel("Second-Order Cross-Mode Terms"))
        layout.addWidget(self.cross_kerr_box)

        # self.drive_params = Form([
        #
        # ])

        self.simulation_params = Form([
            ("time", "float", 10),
            ("steps", "int", 100),
        ])

        calc_button = QPushButton("Calculate")
        layout.addWidget(calc_button)
        calc_button.clicked.connect(self.run_simulation)

        self.status_label = QLabel("")
        self.progress_bar = QProgressBar()
        self.statusBar().addWidget(self.status_label)
        self.statusBar().addWidget(self.progress_bar, 1)

        self.plot_tab_box = QTabWidget()
        self.plots = []
        split.addWidget(self.plot_tab_box)

        self.update_count()

    def resize_eqn(self, splitter_pos, idx):
        aspect = float(self.full_pixmap.height())/self.full_pixmap.width()

        self.eqn_height = max(50, int(.9*splitter_pos))
        self.eqn_height = min(aspect*self.width(), self.eqn_height)
        self.eqn_widget.setPixmap(self.full_pixmap.scaledToHeight(self.eqn_height, Qt.SmoothTransformation))

    def set_eqn(self, suffix):
        if suffix:
            suffix = "_" + suffix
        path = os.path.join("latex", "eqn%s.png"%suffix)
        self.full_pixmap = QPixmap(path)
        self.eqn_widget.setPixmap(self.full_pixmap.scaledToHeight(self.eqn_height, Qt.SmoothTransformation))

    def change_eqn_on_click(self, widget, eqn_suffix):
        class SpinboxClickHandler(QObject):
            focus_in = pyqtSignal()
            focus_out = pyqtSignal()

            def eventFilter(self, obj, ev):
                if ev.type() == QFocusEvent.FocusIn:
                    self.focus_in.emit()
                if ev.type() == QFocusEvent.FocusOut:
                    self.focus_out.emit()
                return False

        widget.click_handler = handler = SpinboxClickHandler()
        widget.installEventFilter(handler)
        widget.focus_in = handler.focus_in
        widget.focus_out = handler.focus_out
        widget.focus_in.connect(lambda: self.set_eqn(eqn_suffix))
        widget.focus_out.connect(lambda: self.set_eqn(""))

    def add_image_view(self, data):
        if not self.plots:
            self.plot_tab_box.show()
        image_view = ImageView()
        self.plots.append(image_view)
        self.plot_tab_box.addTab()
        image_view.ui.histogram.gradient.restoreState(
            {"ticks": [(0.0, (255, 0, 0)), (0.5, (255, 255, 255)), (1.0, (0, 0, 255))], "mode": "rgb"}
        )
        image_view.setImage(data)
        split = self.centralWidget()
        split.addWidget(image_view)
        QApplication.instance().processEvents()
        self.resize(1250, self.height())
        split.setSizes([250, 1000])


    def update_count(self):
        n = self.mode_count_spin.value()
        self.cross_kerr_table.set_n(n)
        self.cross_kerr_box.resizeColumnsToContents()
        while len(self.modes) < n:
            m = Form([
                ("name", "str", "Mode"),
                ("dimension", "int", 2),
                ("frequency", "float", 1),
                ("decay", "float"),
                ("dephasing", "float"),
                ("drive amplitude", "float"),
                ("drive angle", "float"),
                ("initial state", "int"),
                ("initial displacement", "float"),
                ("initial leg count", "int", 1),
                ("initial leg phases", "array", [[1]]),
            ])
            mw = m.widget
            eq_assns = [
                ("frequency", "freq"),
                ("decay", "decay"),
                ("dephasing", "dephasing"),
                ("drive amplitude", "drive_amp"),
                ("drive angle", "drive_phase"),
                ("initial state", "init_state"),
                ("initial displacement", "displacement"),
                ("initial leg count", "leg_count"),
                ("initial leg phases", "leg_phase"),
            ]
            for m_name, eq_name in eq_assns:
                self.change_eqn_on_click(m.child_widgets[m_name], eq_name)

            def update_leg_phases():
                n = m.initial_leg_count
                l = list(m.initial_leg_phases)
                len_diff = n - len(l)
                if len_diff >= 0:
                    m.initial_leg_phases[0].extend([1]*len_diff)
                else:
                    del m.initial_leg_phases[len_diff:]
                w = m.child_widgets["initial leg phases"]
                w.model().modelReset.emit()
                w.model().dtype = complex
                w.resizeColumnsToContents()

            m.child_widgets["initial leg count"].valueChanged.connect(update_leg_phases)

            # Add Output Box
            iv = ImageView()
            iv.ui.histogram.gradient.restoreState({
                "ticks": [
                    (0.0, (255, 0, 0)),
                    (0.5, (255, 255, 255)),
                    (1.0, (0, 0, 255))],
                "mode": "rgb"
            })
            self.modes.append((m, mw))
            self.plots.append(iv)
            self.mode_box.addTab(mw, m.name)
            self.plot_tab_box.addTab(iv, m.name)
            m.child_widgets["name"].textChanged.connect(lambda t: self.update_tabs())
        while len(self.modes) > n:
            m, mw = self.modes.pop(-1)
            iv = self.plots.pop(-1)
            im = self.mode_box.indexOf(mw)
            self.mode_box.removeTab(im)
            self.plot_tab_box.removeTab(im)

    def update_tabs(self):
        for i, (m, mw) in enumerate(self.modes):
            self.mode_box.setTabText(i, m.name)
            self.plot_tab_box.setTabText(i, m.name)

    def set_status(self, msg):
        self.status_label.setText(msg)
        QApplication.instance().processEvents()

    def set_progress(self, percent):
        self.progress_bar.setValue(percent)
        QApplication.instance().processEvents()

    def run_simulation(self):
        modes = [m for m, mw in self.modes]
        id_list = [qeye(m.dimension) for m in modes]
        H0 = 0
        H1 = []
        args = {}
        psi0_list = []
        c_ops = []
        n_ops = []
        for i, m in enumerate(modes):
            n_list = copy(id_list)
            a_list = copy(id_list)
            n_list[i] = num(m.dimension)
            a_list[i] = destroy(m.dimension)
            n_op = tensor(*n_list)
            n_ops.append(n_op)
            a_op = tensor(*a_list)
            H0 += m.frequency*n_op
            if m.drive_amplitude:
                H1 += [m.drive_amplitude*(a_op + a_op.dag()), "cos(df%d*t + phi%d)"%(i, i)]
                args.update({'df%d'%i: m.drive_frequency, 'phi%d'%i: pi*m.drive_phase_degrees/180})

            # Initial State
            alpha = m.initial_displacement
            psi0_i = 0
            leg_angle = exp(2j*pi/m.initial_leg_count)
            vacuum = basis(m.dimension, 0)
            leg_phases = list(m.initial_leg_phases)
            leg_phases += [1]*(m.initial_leg_count - len(leg_phases))
            for n, phase in enumerate(leg_phases):
                psi0_i += phase*displace(m.dimension, leg_angle**n*alpha)*vacuum

            psi0_list.append(psi0_i)
            c_ops += [m.decay*a_op, m.dephasing*n_op]

        for i, row in enumerate(self.cross_kerr_table.array):
            for j, val in enumerate(row):
                H0 += val*n_ops[i]*n_ops[j]

        if H1:
            H = [H0, H1]
        else:
            H = H0

        psi0 = tensor(*psi0_list)
        sim = self.simulation_params
        times = linspace(0, sim.time, sim.steps)
        self.set_status("Computing States")
        result = mesolve(H, psi0, times, c_ops, [], args)

        self.set_status("Computing Wigners")
        for n, m in enumerate(modes):
            axis = linspace(-m.wigner_range, m.wigner_range, m.wigner_resolution)
            wigners = []
            for i, s in enumerate(result.states):
                wigners.append(wigner(s.ptrace(n), axis, axis))
                self.set_progress(int(100*i/sim.steps))
            wigners = np.array(wigners)

            image_view = self.plots[n]
            image_view.setImage(wigners)
            max_value = abs(wigners).max()
            image_view.setLevels(-max_value, max_value)
        self.set_progress(0)
        self.set_status("")


# class ModeParameters(HasTraits):
# name = Str("Mode")
#     dimension = Int(2)
#     frequency = Float(1)
#     decay = Float
#     dephasing = Float
#     drive_amplitude = Float
#     drive_frequency = Float
#     drive_phase_degrees = Float
#     initial_displacement = Float
#     initial_leg_count = Int(1)
#     initial_leg_phases = ListComplex([1])
#     wigner_range = Float(5)
#     wigner_resolution = Float(100)
#
#
#     def __init__(self):
#         super(ModeParameters, self).__init__()
#         self.on_trait_change(self.update_leg_phases, 'initial_leg_count')
#
#     def update_leg_phases(self):
#         n = self.initial_leg_count
#         l = list(self.initial_leg_phases)
#         len_diff = n - len(l)
#         if len_diff >= 0:
#             self.initial_leg_phases.extend([1]*len_diff)
#         else:
#             del self.initial_leg_phases[len_diff:]
#
#
# ModeView = View(Group(
#     Item(name="name"),
#     Item(name="dimension"),
#     Item(name="frequency"),
#     Item(name="decay"),
#     Item(name="dephasing"),
#     Item(name="drive_amplitude"),
#     Item(name="drive_frequency"),
#     Item(name="drive_phase_degrees"),
#     Item(name="initial_displacement"),
#     Item(name="initial_leg_count"),
#     Item(name="initial_leg_phases")
# ))

# class OutputParameters(HasTraits):
#     time = Float(10)
#     steps = Int(100)
#
#
# OutputView = View(Group(
#     Item(name='time'),
#     Item(name='steps'),
# ))

# class SimulationItem(QStandardItem):
#     def __init__(self):
#         super(SimulationModel, self).__init__()
#         root_names = ["Simulation", "Modes", "Cross-Mode Terms", "Outputs"]
#         self.root_categories = {r:QStandardItem(r) for r in root_names}
#         for name in root_names:
#             item = self.root_categories[name]
#             item.setEditable(False)
#             self.appendRow(item)
#         self.insertColumns(1, 1)
#         sim_names = ["Time", "Steps", "Mode Count"]
#         sim_defaults = [10, 100, 1]
#         self.sim_types = [int, float, int]
#         self.sim_categories = {n:QStandardItem(n) for n in sim_names}
#         self.sim_values = {n:QStandardItem(str(val)) for n, val in zip(sim_names, sim_defaults)}
#         sim_val_column = [self.sim_values[n] for n in sim_names]
#         sim = self.root_categories["Simulation"]
#         for name in sim_names:
#             item = self.sim_categories[name]
#             item.setEditable(False)
#             sim.appendRow(item)
#         sim.appendColumn(sim_val_column)
#
#         self.modes = [ModeModel]
#
# class ModeModel(QStandardItem):
#     def __init__(self):
#         root_names = [""]

#
# class SimulationModel(QAbstractItemModel):
#     def __init__(self):
#         self.insertRows(0, 3, self)
#         self.root_categories = ["Simulation", "Modes", "Cross-Mode Terms", "Outputs"]
#
#         self.simulation_categories = ["Time", "Steps", "Mode Count"]
#         self.modes = [ModeModel()]
#         self.cross_mode_terms = []
#         self.outputs = []
#         self.root = {
#             "Simulation": self.simulation_categories,
#             "Modes": self.modes,
#             "Cross-Mode Terms": self.cross_mode_terms,
#             "Outputs": self.outputs,
#             }
#
#         self.time = 10
#         self.steps = 100
#         self.mode_count = 1
#         self.simulation = {
#             "Time": self.time,
#             "Steps": self.steps,
#             "Mode Count": self.mode_count,
#             }
#
#
#
#     def hasChildren(self, parent):
#         pass
#
#     def rowCount(self, parent):
#         if not parent.isValid():
#             return len(self.root_categories)
#         elif not parent.parent().isValid():
#             return len(self.root[self.root_categories[parent.row()]])
#         else:
#             parent.parent().row()
#
#
#     def columnCount(self, parent, *args, **kwargs):
#         return 1
#
#     def data(self, idx, role):
#         if role == Qt.DisplayRole:
#             if idx.parent() is self:
#                 return [idx.row()]
#
#
# class ModeModel():
#     pass
#
#
#
# class Window2(QMainWindow):
#     def __init__(self):
#         v_split = QSplitter(Qt.Vertical)
#         self.setCentralWidget(v_split)
#
#         self.eqn_box = QLabel()
#         h_split = QSplitter()
#         v_split.addWidget(self.eqn_box)
#         v_split.addWidget(h_split)
#
#         main_params = MainParams()
#         mode_params_box = QTabWidget()
#
# class MainParams(QGroupBox):
#     pass
#
#

# class Form(object):
#     def __init__(self, items):
#         self.widget = QWidget()
#         self.child_widgets = {}
#         self.layout = QFormLayout(self.widget)
#         self.layout.setLabelAlignment(Qt.AlignRight)
#         self.getters = {}
#         for i in items:
#             try:
#                 name, type = i
#                 default = None
#             except ValueError:
#                 name, type, default = i
#             w = getattr(self, "make_"+type)(name, default)
#             self.add_widget(name, w)
#
#     def make_int(self, name, default):
#         w = QSpinBox()
#         if default is not None:
#             w.setValue(default)
#         self.getters[methodize(name)] = w.value
#         return w
#
#     def make_float(self, name, default):
#         w = QDoubleSpinBox()
#         if default is not None:
#             w.setValue(default)
#         self.getters[methodize(name)] = w.value
#         return w
#
#     def make_str(self, name, default):
#         w = QLineEdit()
#         if default is not None:
#             w.setText(default)
#         self.getters[methodize(name)] = w.text
#         return w
#
#     def make_array(self, name, default):
#         w = QTableView()
#         m = ArrayModel(default)
#         w.setModel(m)
#         self.getters[methodize(name)] = lambda: m.array
#         return w
#
#     def add_widget(self, name, w):
#         self.layout.addRow(wordify(name)+":", w)
#         self.child_widgets[name] = w
#
#     def __getattr__(self, item):
#         if item in self.getters:
#             return self.getters[item]()
#         else:
#             raise AttributeError(item)
# class ModeGroupItem(ConstantItem):
#     def __init__(self):
#         super(ModeGroupItem, self).__init__("Modes")
#         self.context_menu = ActionsMenu([("New Mode", self.add_mode)])
#
#     def add_mode(self):
#         m = ModeItem()
#         d = OKCancelDialog(m.params_widget)
#         if d.exec_():
#             m.params_widget.setParent(None)
#             self.appendRow(m)
#             self.parent().mode_count += 1
#     def __init__(self):
#         super(OutputsGroupItem, self).__init__("Outputs")
#         self.context_menu = ActionsMenu([('Add Output', self.add_output)])
#
#     def add_output(self):
#         i = OutputItem()
#         d = OKCancelDialog(i.params_widget)
#         if d.exec_():
#             i.params_widget.setParent(None)
#             self.appendRow(i)





# if __name__ == '__main__':
#     app = QApplication.instance()
#     win = Window()
#     win.show()
#     win.resize(1250, win.height())
#     win.split.setSizes([250, 1000])
#     app.exec_()
