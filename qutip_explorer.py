from PyQt4.QtCore import QSettings
from PyQt4.QtGui import QApplication, QMainWindow, QProgressBar, QGroupBox, QRadioButton, QDockWidget
from numpy import linspace
from pyqtgraph import ImageView, PlotWidget
from pyqtgraph.dockarea import DockArea, Dock
from qutip import *
from interface_helpers import *

__author__ = "Phil Reinhold"
__version__ = 0.1
__ui_version__ = 1


class ModeItemEmitter(QObject):
    mode_form_focus_in = pyqtSignal(str)
    mode_form_focus_out = pyqtSignal(str)


class ModeItem(FormItem):
    def __init__(self, group):
        super(ModeItem, self).__init__("Mode", [
            ("dimension", int, 2),
            ("frequency", float, 1),
            ("anharmonicity", float, 0),
            ("decay", float, 0),
            ("dephasing", float, 0),
            ("drive amplitude", float, 0),
            ("drive angle", float, 0),
            ("fock state", int, 0),
            ("initial displacement", float, 0),
            ("leg count", int, 1),
        ])
        self.group = group
        # Initial-leg-phases

        eqn_associations = {
            "Frequency": "freq",
            "Anharmonicity": "kerr",
            "Decay": "decay",
            "Dephasing": "dephasing",
            "Drive Amplitude": "drive_amp",
            "Drive Angle": "drive_phase",
            "Initial State": "init_state",
            "Initial Displacement": "displacement",
            "Leg Count": "leg_count",
            # ("Initial Leg Phases", "leg_phase"),
        }

        def mode_hover_changed(idx):
            name = self.params_model.item(idx.row(), 0).text()
            win.set_eqn_pixmap(eqn_associations.get(str(name), ""))

        self.params_widget.setMouseTracking(True)
        self.params_widget.entered.connect(mode_hover_changed)
        self.params_widget.leaveEvent = lambda e: win.set_eqn_pixmap("")

    def tensor_index(self):
        return self.group.items_list().index(self)

    def hamiltonian(self):
        a = destroy(self.dimension)
        ad = a.dag()
        f0 = self.frequency
        k = self.anharmonicity
        return f0*ad*a + k*ad*ad*a*a

    def drive_hamiltonian(self):
        a = destroy(self.dimension)
        ad = a.dag()
        th = self.drive_angle
        amp = self.drive_amplitude
        return amp*(exp(1j*th)*ad + exp(-1j*th)*a)

    def initial_state(self):
        alpha = self.initial_displacement
        leg_angle = exp(2j*pi/self.leg_count)
        init_state = basis(self.dimension, self.fock_state)
        # leg_phases = list(m.initial_leg_phases)
        # leg_phases += [1]*(m.initial_leg_count - len(leg_phases))
        disp_op = lambda n: displace(self.dimension, alpha*leg_angle**n)
        return sum(disp_op(n)*init_state for n in range(self.leg_count))

    def collapse_ops(self):
        a = destroy(self.dimension)
        return [self.decay*a, self.dephasing*a.dag()*a]


class CrossModeGroupItem(GroupItem):
    def __init__(self, modes_item):
        super(CrossModeGroupItem, self).__init__("Cross-Mode Terms", "Cross-Mode Term", CrossModeItem)
        self.modes_item = modes_item
        self.context_menu.add_action('Add Terms From Matrix', self.add_from_matrix)

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

    def add_from_matrix(self):
        self.array_model.set_n(self.modes_item.rowCount())
        names = [m.text() for m in self.modes_item.items_list()]
        self.array_model.setHorizontalHeaderLabels(names)
        self.array_model.setVerticalHeaderLabels(names)
        if self.dialog.exec_():
            if self.cross_kerr_type_radio.isChecked():
                type_str = "Cross-Kerr"
            elif self.xx_type_radio.isChecked():
                type_str = "X-X"
            else:
                return
            for i, row in enumerate(self.array_model.array):
                for j, val in enumerate(row):
                    if val:
                        self.appendRow(CrossModeItem(type_str, val, i, j, self.modes_item))


class CrossModeItem(FormItem):
    def __init__(self, group, term_type="Cross-Kerr", val=1, mode_1=0, mode_2=1):
        name = term_type + str((mode_1, mode_2))
        modes = group.modes_item.items_list()
        super(CrossModeItem, self).__init__(name, [
            ("term type", ["Cross-Kerr", "X-X"], term_type),
            ("strength", float, val),
            ("mode 1", group.modes_item, modes[mode_1].text()),
            ("mode 2", group.modes_item, modes[mode_2].text()),
        ])

    def hamiltonian(self, mode_list):
        ops_list = [qeye(m.dimension) for m in mode_list]
        if self.term_type == "Cross-Kerr":
            n1 = num(self.mode_list[self.mode_1 - 1].dimension)
            n2 = num(self.mode_list[self.mode_2 - 1].dimension)
            ops_list[self.mode_1 - 1] = n1
            ops_list[self.mode_2 - 1] = n2
            return tensor(*ops_list)
        if self.term_type == "X-X":
            a1 = destroy(self.mode_list[self.mode_1 - 1].dimension)
            a2 = destroy(self.mode_list[self.mode_2 - 1].dimension)
            ops_list[self.mode_1 - 1] = a1
            ops_list[self.mode_2 - 1] = a2.dag()
            return tensor(*ops_list) + tensor(*ops_list).dag()


class OutputsGroupItem(GroupItem):
    def __init__(self, modes_item, sims_item):
        super(OutputsGroupItem, self).__init__("Outputs", "Output", OutputItem)
        self.sims_item = sims_item
        self.modes_item = modes_item


class MyImageView(ImageView):
    def __init__(self):
        super(MyImageView, self).__init__()
        self.ui.histogram.gradient.restoreState(
            {"ticks": [(0.0, (255, 0, 0)), (0.5, (255, 255, 255)), (1.0, (0, 0, 255))], "mode": "rgb"}
        )

    def setImage(self, img, **kwargs):
        super(MyImageView, self).setImage(img, **kwargs)
        max_value = abs(img).max()
        self.setLevels(-max_value, max_value)


class OutputItem(FormItem):
    def __init__(self, group):
        super(OutputItem, self).__init__("Output", [
            ("simulation", group.sims_item, group.sims_item.items_list()[0].name()),
            ("mode", group.modes_item, group.modes_item.items_list()[0].name()),
            ("report type", ["Wigner", "Expect-XYZ"], "Wigner"),
            ("wigner range", float, 5),
            ("wigner resolution", int, 100),
        ])

        self.context_menu.add_action("Re-Compute", self.compute)
        self.data = None
        self.dock = None
        self.plot = None

    def compute(self):
        win.set_status("Computing Output %s" % self.name())
        output_steps = []
        if self.report_type == "Wigner":
            dx = self.wigner_range
            nx = self.wigner_resolution
            axis = linspace(-dx, dx, nx)
            step_function = lambda state: wigner(state, axis, axis)
        else:
            step_function = lambda state: [expect(state, jmat(2, d)) for d in 'xyz']

        n_states = len(self.simulation.states)
        for i, s in enumerate(self.simulation.states):
            output_steps.append(step_function(s.ptrace(self.mode.tensor_index())))
            win.set_progress(i/n_states)
        win.set_status("")

        self.data = np.array(output_steps)
        if self.report_type == "Wigner":
            self.plot_wigner()
        elif self.report_type == "Expect-XYZ":
            self.plot_xyz()

    def plot_type(self):
        return {
            "Wigner": MyImageView,
            "Expect-XYZ": PlotWidget,
        }[self.report_type]

    def check_dock(self):
        if self.dock is None:
            self.plot = self.plot_type()()
            self.dock = Dock(self.name(), widget=self.plot)
            win.outputs_dock_area.addDock(self.dock)

    def plot_wigner(self):
        self.check_dock()
        if not isinstance(self.plot, ImageView):
            self.plot.setParent(None)
            self.plot = ImageView()
        self.plot.setImage(self.data)

    def plot_xyz(self):
        pass


class PulseItem(FormItem):
    def __init__(self):
        super(PulseItem, self).__init__("Pulse", [
            ("frequency", float, 1),
            ("amplitude", float, 1),
            ("phase", float, 1),
            ("profile", ["Square", "Gaussian"], "Square"),
            ("duration", float, 1),
            ("sigma", float, 1),
        ])

    def time_dependence(self):
        td_str = "amp*cos(omega * t + phi)"
        args = {'amp': self.amplitude, 'omega': self.frequency}
        if self.profile == "Gaussian":
            td_str += "*exp((t-t0)**2/sigma**2)"
            args['t0'] = self.duration/2.
            args['sigma'] = self.sigma
        return td_str


class SimulationItem(FormItem):
    def __init__(self):
        super(SimulationItem, self).__init__("Simulation", [
            ("time", float, 10),
            ("steps", int, 100),
        ])

        self.dirty = True
        self.states = None

    def compute(self, hamiltonian, init_state, collapse_ops, args):
        tlist = linspace(0, self.time, self.steps)
        win.set_status("Computing States...")
        self.states = mesolve(hamiltonian, init_state, tlist, collapse_ops, [], args).states
        win.set_status("")
        self.dirty = False


class SetupItem(FormItem):
    def __init__(self):
        super(SetupItem, self).__init__("Setup", [])
        self.modes_item = GroupItem("Modes", "Mode", ModeItem)
        self.cross_mode_terms_item = CrossModeGroupItem(self.modes_item)
        self.simulations_item = GroupItem("Analyses", "Simulation", SimulationItem)
        self.outputs_item = OutputsGroupItem(self.modes_item, self.simulations_item)
        self.pulses_item = GroupItem("Pulses", "Pulse", PulseItem)

        self.appendRow(self.modes_item)
        self.appendRow(self.cross_mode_terms_item)
        self.appendRow(self.pulses_item)
        self.appendRow(self.simulations_item)
        self.appendRow(self.outputs_item)

        self.mode_count = 0

        def increment_mode_count(item):
            self.mode_count += 1

        def decrement_mode_count():
            self.mode_count -= 1

        self.modes_item.emitter.item_created.connect(increment_mode_count)

        def add_compute_action(item):
            item.context_menu.add_action("Compute", lambda: self.compute(item))

        self.simulations_item.emitter.item_added.connect(add_compute_action)

        self.modes_item.add_item(dialog=False)
        self.simulations_item.add_item(dialog=False)
        self.outputs_item.add_item(dialog=False)

    def compute(self, sim_item):
        modes = self.modes_item.items_list()
        H0 = 0
        for i, mode in enumerate(modes):
            ops_list = [qeye(m.dimension) for m in modes]
            ops_list[i] = mode.hamiltonian()
            H0 += tensor(*ops_list)

        for term in self.cross_mode_terms_item.items_list():
            H0 += term.hamiltonian(modes)

        init_state = tensor(*[m.initial_state() for m in modes])

        c_ops = []
        for i, mode in enumerate(modes):
            ops_list = [qeye(m.dimension) for m in modes]
            ops_list[i] = sum(mode.collapse_ops())
            c_ops.append(tensor(*ops_list))

        args = {}

        sim_item.compute(H0, init_state, c_ops, args)

        for output in self.outputs_item.items_list():
            if output.simulation is sim_item:
                output.compute()


class SetupsModel(QStandardItemModel):
    def __init__(self):
        super(SetupsModel, self).__init__()

        def update_handler(item):
            parent = item.parent()
            if parent is None:
                return
            if isinstance(item, FormItem):
                item.params_model.item(0, 1).setText(item.text())
            name = str(parent.child(item.row(), 0).text())
            if isinstance(parent, FormItem) and name in parent.dtypes:
                coerce_fn = parent.dtypes[name]
                item.setData(str(coerce_fn(item.text())))

        self.itemChanged.connect(update_handler)


class SetupsView(ContextMenuStandardTreeView):
    mode_added = pyqtSignal(ModeItem)

    def __init__(self):
        super(SetupsView, self).__init__()
        self.setModel(SetupsModel())
        self.context_menu = ActionsMenu([("Add Simulation", self.add_setup)])

    def expand_item(self, item):
        idx = self.model().indexFromItem(item)
        self.expand(idx)
        for i in range(item.rowCount()):
            self.expand_item(item.child(i, 0))

    def add_setup(self):
        item = SetupItem()
        self.model().appendRow(item)
        self.expand_item(item)
        self.resizeColumnToContents(0)
        item.modes_item.emitter.item_created.connect(self.mode_added.emit)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setStyleSheet("QMainWindow::separator {background: lightGray; width: 2px}")

        self.tree_widget = SetupsView()
        self.eqn_widget = ResizableImage("latex/eqn.png", 100, .5, 2)
        self.outputs_dock_area = DockArea()

        docks = []
        view_menu = self.menuBar().addMenu("View")
        for dock_name in ["Project Manager", "Properties", "Equation"]:
            dock = QDockWidget(dock_name)
            dock.setObjectName(method_style(dock_name))
            view_menu.addAction(dock.toggleViewAction())
            docks.append(dock)
        self.tree_dock, self.props_dock, self.eqn_dock = docks

        self.tree_dock.setWidget(self.tree_widget)
        self.eqn_dock.setWidget(self.eqn_widget)
        placeholder = QLabel("No Item Selected")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setMinimumSize(200, 100)
        self.props_dock.setWidget(placeholder)

        self.setCentralWidget(self.outputs_dock_area)
        self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tree_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.props_dock)
        self.addDockWidget(Qt.TopDockWidgetArea, self.eqn_dock)

        self.tree_widget.add_setup()
        self.tree_widget.clicked.connect(self.set_props_widget)

        self.status_label = QLabel("")
        self.progress_bar = QProgressBar()
        self.statusBar().addWidget(self.status_label)
        self.statusBar().addWidget(self.progress_bar, 1)

        self.restoreGeometry(settings.value("geometry").toByteArray())
        self.restoreState(settings.value("state").toByteArray(), __ui_version__)

    def set_props_widget(self, index):
        item = self.tree_widget.model().itemFromIndex(index)
        if hasattr(item, "params_widget"):
            self.props_dock.setWidget(item.params_widget)

    def set_eqn_pixmap(self, suffix):
        if suffix:
            suffix = "_" + suffix
        path = os.path.join("latex", "eqn%s.png"%suffix)
        self.eqn_widget.set_file(path)

    def set_status(self, msg):
        self.status_label.setText(msg)
        app.processEvents()

    def set_progress(self, percent):
        self.progress_bar.setValue(percent)
        app.processEvents()

    def closeEvent(self, ev):
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState(__ui_version__))
        return super(MainWindow, self).closeEvent(ev)


if __name__ == '__main__':
    app = QApplication([])
    settings = QSettings("philreinhold", "qutip_explorer")
    win = MainWindow()
    win.show()
    win.resize(1000, 800)
    sys.exit(app.exec_())
