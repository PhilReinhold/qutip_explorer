from PyQt4.QtCore import QSettings
from PyQt4.QtGui import QApplication, QMainWindow, QProgressBar, QGroupBox, QRadioButton, QDockWidget, QWidget, \
    QHBoxLayout, QPushButton, QMessageBox
import itertools
from numpy import linspace
from pyqtgraph import ImageView, PlotWidget, setConfigOption, mkPen
from pyqtgraph.dockarea import DockArea, Dock
from qutip import *
from interface_helpers import *

__author__ = "Phil Reinhold"
__version__ = 0.1
__ui_version__ = 1
setConfigOption('background', 'w')
setConfigOption('foreground', 'k')
pen_list = [mkPen(color, width=2) for color in 'bgrcmyk']
pen_generator = itertools.cycle(pen_list)

class ModeItemEmitter(QObject):
    mode_form_focus_in = pyqtSignal(str)
    mode_form_focus_out = pyqtSignal(str)


class ModeItem(GroupItemChild):
    def __init__(self, group):
        super(ModeItem, self).__init__("Mode_1", [
            ("dimension", int, 2),
            ("frequency", float, 1),
            ("anharmonicity", float, 0),
            ("decay", float, 0),
            ("dephasing", float, 0),
            ("drive amplitude", float, 1),
            ("drive angle degrees", float, 0),
            ("fock state", int, 0),
            ("initial displacement", float, 0),
            ("leg count", int, 1),
        ], group)
        # TODO: Initial-leg-phases

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

    def operator_on_self(self, op):
        return self.group.operator_on_indices([(op, self.tensor_index())])

    def destroy(self):
        return self.operator_on_self(destroy(self.dimension))

    def hamiltonian(self):
        a = self.destroy()
        ad = a.dag()
        f0 = self.frequency
        k = self.anharmonicity
        return f0*ad*a + k*ad*ad*a*a

    def drive_hamiltonian(self):
        a = self.destroy()
        ad = a.dag()
        th = pi * self.drive_angle_degrees / 180
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
        a = self.destroy()
        return [self.decay*a, self.dephasing*a.dag()*a]

class ModesGroupItem(GroupItem):
    def __init__(self, setup):
        super(ModesGroupItem, self).__init__("Modes", [("Mode", ModeItem)], setup)

    def operator_on_indices(self, h_idx_pairs):
        op_list = [qeye(m.dimension) for m in self.items_list()]
        for h, idx in h_idx_pairs:
            op_list[idx] = h
        return tensor(*op_list)

    def initial_state(self):
        return tensor(*[m.initial_state for m in self.items_list()])


class CrossModeGroupItem(GroupItem):
    def __init__(self, setup):
        super(CrossModeGroupItem, self).__init__("Cross-Mode Terms", [("Cross-Mode Term", CrossModeItem)], setup)
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

    def add_item(self, dialog=True):
        if self.setup.modes_item.rowCount() < 2:
            message_box.setIcon(QMessageBox.Warning)
            message_box.setText("Need more than two modes")
            message_box.exec_()
        else:
            return super(CrossModeGroupItem, self).add_item(dialog=dialog)

    def add_from_matrix(self):
        self.array_model.set_n(self.setup.modes_item.rowCount())
        names = [m.text() for m in self.setup.modes_item.items_list()]
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
                        self.appendRow(CrossModeItem(type_str, val, i, j, self.setup.modes_item))


class CrossModeItem(GroupItemChild):
    def __init__(self, group, term_type="Cross-Kerr", val=1, mode_1=0, mode_2=1):
        name = term_type + str((mode_1, mode_2))
        super(CrossModeItem, self).__init__(name, [
            ("term type", ["Cross-Kerr", "X-X"], term_type),
            ("strength", float, val),
            ("mode 1", group.setup.modes_item, None),
            ("mode 2", group.setup.modes_item, None),
        ], group)

    def hamiltonian(self):
        idx_1 = self.mode_1.tensor_index()
        idx_2 = self.mode_2.tensor_index()
        op = num if self.term_type == "Cross-Kerr" else destroy
        op_1 = op(self.mode_1.dimension)
        op_2 = op(self.mode_2.dimension)
        h = self.group.setup.modes_item.operator_on_indices([(op_1, idx_1), (op_2, idx_2)])
        if self.term_type == "X-X":
            h += h.dag()
        return h

class OutputsGroupItem(GroupItem):
    def __init__(self, setup):
        super(OutputsGroupItem, self).__init__("Outputs", [("Output", OutputItem)], setup)

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


class OutputItem(GroupItemChild):
    def __init__(self, group):
        super(OutputItem, self).__init__("Output_1", [
            ("simulation", group.setup.sims_item, group.setup.sims_item.items_list()[0].name()),
            ("mode", group.setup.modes_item, group.setup.modes_item.items_list()[0].name()),
            ("report type", ["Wigner", "Expect-XYZ"], "Wigner"),
            ("wigner range", float, 5),
            ("wigner resolution", int, 100),
        ], group)

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
            dim = self.mode.dimension
            a = destroy(dim)
            ad = a.dag()
            ops = [a + ad, 1j*(a - ad), a*ad]
            step_function = lambda state: [expect(op, state) for op in ops]

        n_states = len(self.simulation.states)
        for i, s in enumerate(self.simulation.states):
            output_steps.append(step_function(s.ptrace(self.mode.tensor_index())))
            win.set_progress(100*float(i)/n_states)
        win.set_progress(0)
        win.set_status("")

        if output_steps:
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
        if self.plot is not None:
            self.plot.setParent(None)
        self.plot = self.plot_type()()
        if self.dock is None:
            self.dock = Dock(self.name(), widget=self.plot)
            win.outputs_dock_area.addDock(self.dock)
        else:
            self.dock.addWidget(self.plot)

    def plot_wigner(self):
        if not isinstance(self.plot, ImageView):
            self.check_dock()
        self.plot.setImage(self.data)

    # TODO: Bloch/XYZ plot output implementation
    def plot_xyz(self):
        if not isinstance(self.plot, PlotWidget):
            self.check_dock()
        self.plot.clear()
        self.plot.addLegend()
        for trace, name, pen in zip(self.data.transpose(), 'XYZ', pen_generator):
            self.plot.plot(self.simulation.times, trace, pen=pen, name=name)


class PulseItem(GroupItemChild):
    def __init__(self, group):
        super(PulseItem, self).__init__("Pulse_1", [
            ("frequency", float, 1),
            ("amplitude", float, 1),
            ("phase", float, 0),
            ("profile", ["Square", "Gaussian"], "Square"),
            ("duration", float, 1),
            ("sigma", float, 1),
        ], group)

    def mesolve_args(self):
        return {
            'amp': self.amplitude,
            'omega': self.frequency,
            'phase': self.phase,
            't0': self.duration/2.,
            'sigma': self.sigma,
        }

    def time_dependence(self):
        td_str = "amp*cos(omega * t + phase)"
        if self.profile == "Gaussian":
            td_str += "*exp((t-t0)**2/sigma**2)"
        return td_str

    def hamiltonian(self, modes):
        modes_item = self.group.setup.modes_item
        h = sum(m.drive_hamiltonian() for m in modes_item.items_list())
        return [h, self.time_dependence()]


class SequencesGroupItem(GroupItem):
    def __init__(self, setup):
        super(SequencesGroupItem, self).__init__("Pulse Sequences", [("Sequence", SequenceItem)], setup)


class SequenceItem(GroupItemChild):
    def __init__(self, group):
        super(SequenceItem, self).__init__("Sequence_1", [], group)
        add_pulse_button = QPushButton("Add Pulse")
        add_wait_button = QPushButton("Add Wait")
        add_item_layout = QHBoxLayout()
        add_item_layout.addWidget(add_pulse_button)
        add_item_layout.addWidget(add_wait_button)
        add_pulse_button.clicked.connect(self.add_pulse)
        add_wait_button.clicked.connect(self.add_wait)
        params_widget = QWidget()
        params_layout = QVBoxLayout(params_widget)
        params_layout.addWidget(self.params_widget)
        params_layout.addLayout(add_item_layout)
        self.params_widget = params_widget
        self.n_steps = 0

    def add_pulse(self):
        self.n_steps += 1
        self.add_field("Pulse Step %d" % self.n_steps, self.group.setup.pulses_item, None)

    def add_wait(self):
        self.n_steps += 1
        self.add_field("Wait Step %d" % self.n_steps, float, 1)

    def get_steps(self):
        steps = []
        for i in range(1, self.n_steps + 1):
            try:
                pulse_item = self.__getattr__("pulse_step_%d" % i)
                steps.append(
                    (pulse_item.hamiltonian(self.group.setup.modes_item.items_list()),
                     pulse_item.duration,  pulse_item.mesolve_args())
                )
            except AttributeError as e:
                try:
                    wait_time = self.__getattr__("wait_step_%d" % i)
                except AttributeError:
                    raise e
                steps.append((None, wait_time, {}))
        return steps


class SimulationsGroupItem(GroupItem):
    def __init__(self, setup):
        super(SimulationsGroupItem, self).__init__("Analysis", [("Simulation", SimulationItem)], setup)

# TODO: Better name than Simulation
# TODO: Simple Simulations & Sequence Simulations
class SimulationItem(GroupItemChild):
    def __init__(self, group):
        super(SimulationItem, self).__init__("Simulation_1", [
            #("time", float, 10),
            ("sequence", group.setup.sequences_item, None),
            ("time step", float, 0.1),
        ], group)
        self.dirty = True
        self.states = None
        self.context_menu.add_action("Compute", lambda: self.group.setup.compute(self))

    def compute(self, h0, init_state, collapse_ops):
        self.states = []
        start_time = 0
        steps = self.sequence.get_steps()
        self.times = []
        if not steps:
            message_box.setText("No Steps in Sequence to Simulate")
            message_box.exec_()
            return
        for i, (h1, duration, args) in enumerate(steps):
            end_time = start_time + duration
            time_list = arange(start_time, end_time, self.time_step)
            self.times.extend(list(time_list))
            if h1 is not None:
                hamiltonian = [h0, h1]
            else:
                hamiltonian = h0
            win.set_status("Computing States for Step %d..." % (i+1))
            new_states = mesolve(hamiltonian, init_state, time_list, collapse_ops, [], args).states
            self.states.extend(new_states)
            init_state = new_states[-1]
            start_time = end_time
            win.set_status("")
            self.dirty = False

class SweepsGroupItem(GroupItem):
    def __init__(self, setup):
        super(SweepsGroupItem, self).__init__(
            "Sweeps", [("Parameter Sweep", SweepItem)], setup
        )

class SweepItem(GroupItemChild):
    def __init__(self, group):
        param_names = [v.name for v in group.setup.variables.values()]
        super(SweepItem, self).__init__("Sweep_1", [
            ("Parameter Name", param_names, param_names[0]),
            ("Initial value", float, 0),
            ("Final value", float, 1),
            ("Steps", int, 10)
        ], group)

# TODO: Parametric Sweep Group
class SetupItem(VarRootItem):
    def __init__(self):
        super(SetupItem, self).__init__("Setup")
        self.variables = {}
        self.modes_item = ModesGroupItem(self)
        self.cross_mode_terms_item = CrossModeGroupItem(self)
        self.pulses_item = GroupItem("Pulses", [("Pulse", PulseItem)], self)
        self.sequences_item = SequencesGroupItem(self)
        self.sims_item = SimulationsGroupItem(self)
        self.sweeps_item = SweepsGroupItem(self)
        self.outputs_item = OutputsGroupItem(self)

        self.appendRow(self.modes_item)
        self.appendRow(self.cross_mode_terms_item)
        self.appendRow(self.pulses_item)
        self.appendRow(self.sequences_item)
        self.appendRow(self.sims_item)
        self.appendRow(self.sweeps_item)
        self.appendRow(self.outputs_item)

        self.modes_item.add_item(dialog=False)
        self.pulses_item.add_item(dialog=False)
        seq = self.sequences_item.add_item(dialog=False)
        self.sims_item.add_item(dialog=False)
        self.outputs_item.add_item(dialog=False)

        seq.add_pulse()

    def compute(self, sim_item):
        modes = self.modes_item.items_list()
        H0 = sum(m.hamiltonian() for m in modes) + \
             sum(t.hamiltonian() for t in self.cross_mode_terms_item.items_list())
        init_state = tensor(*[m.initial_state() for m in modes])
        c_ops = sum([m.collapse_ops() for m in modes], [])

        sim_item.compute(H0, init_state, c_ops)

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
        path = os.path.join("latex", "eqn%s.png" % suffix)
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
    message_box = QMessageBox()
    sys.exit(app.exec_())
