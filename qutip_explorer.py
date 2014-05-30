# Blargh
from traits.etsconfig.api import ETSConfig

ETSConfig.toolkit = 'qt4'
import sip

sip.setapi('QString', 2)
sip.setapi('QVariant', 2)
# End Blargh

from PyQt4.QtCore import QAbstractItemModel, QAbstractTableModel, Qt
from PyQt4.QtGui import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSplitter, QSpinBox, QTabWidget, \
    QTableView, QLabel, QFormLayout
from numpy import linspace
from pyqtgraph import ImageView
from traits.api import HasTraits, Int, Float, ListComplex, Str
from traitsui.api import View, Group, Item
from qutip import *
from copy import copy


class ModeParameters(HasTraits):
    name = Str("Mode")
    dimension = Int(2)
    frequency = Float(1)
    decay = Float
    dephasing = Float
    drive_amplitude = Float
    drive_frequency = Float
    drive_phase_degrees = Float
    initial_displacement = Float
    initial_leg_count = Int(1)
    initial_leg_phases = ListComplex([1])

    def __init__(self):
        super(ModeParameters, self).__init__()
        self.on_trait_change(self.update_leg_phases, 'initial_leg_count')

    def update_leg_phases(self):
        n = self.initial_leg_count
        l = list(self.initial_leg_phases)
        dlen = n - len(l)
        if dlen >= 0:
            self.initial_leg_phases.extend([1]*dlen)
        else:
            del self.initial_leg_phases[dlen:]


ModeView = View(Group(
    Item(name="name"),
    Item(name="dimension"),
    Item(name="frequency"),
    Item(name="decay"),
    Item(name="dephasing"),
    Item(name="drive_amplitude"),
    Item(name="drive_frequency"),
    Item(name="drive_phase_degrees"),
    Item(name="initial_displacement"),
    Item(name="initial_leg_count"),
    Item(name="initial_leg_phases")
))


class UpperHalfArrayModel(QAbstractTableModel):
    def __init__(self):
        super(UpperHalfArrayModel, self).__init__()
        self.n = 0
        self.array = []

    def set_n(self, n):
        dn = n - self.n
        while n > self.n:
            self.n += 1
            self.array.append([0]*self.n)

        while n < self.n:
            self.n -= 1
            self.array.pop(-1)
        self.modelReset.emit()

    def rowCount(self, *args, **kwargs):
        return self.n

    def columnCount(self, *args, **kwargs):
        return self.n

    def data(self, idx, role):
        if role == Qt.DisplayRole:
            i, j = idx.row(), idx.column()
            try:
                return self.array[j][i]
            except IndexError:
                return "-"

    def setData(self, idx, val, role):
        if role == Qt.EditRole:
            i, j = idx.row(), idx.column()
            self.array[j][i] = float(val)
            return True
        else:
            return False

    def flags(self, idx):
        f = super(UpperHalfArrayModel, self).flags(idx)
        i, j = idx.row(), idx.column()
        if j < len(self.array) and i < len(self.array[j]):
            return f | Qt.ItemIsEditable
        else:
            return f


class OutputParameters(HasTraits):
    time = Float(10)
    steps = Int(100)
    wigner_range = Float(5)
    wigner_resolution = Int(100)


OutputView = View(Group(
    Item(name='time'),
    Item(name='steps'),
    Item(name='wigner_range'),
    Item(name='wigner_resolution'),
))


class Window(QSplitter):
    def __init__(self):
        super(Window, self).__init__()
        side_bar = QWidget()
        self.addWidget(side_bar)
        layout = QVBoxLayout(side_bar)
        self.mode_count_spin = QSpinBox()
        self.mode_count_spin.setValue(1)
        self.mode_count_spin.valueChanged.connect(self.update_count)
        self.mode_box = QTabWidget()
        self.cross_kerr_table = UpperHalfArrayModel()
        self.cross_kerr_box = QTableView()
        self.cross_kerr_box.setModel(self.cross_kerr_table)
        self.modes = []

        mode_count_layout = QHBoxLayout()
        mode_count_layout.addWidget(QLabel("Mode Count"))
        mode_count_layout.addWidget(self.mode_count_spin)
        layout.addLayout(mode_count_layout)
        layout.addWidget(self.mode_box)
        layout.addWidget(QLabel("Second-Order Cross-Mode Terms"))
        layout.addWidget(self.cross_kerr_box)
        self.output = OutputParameters()
        layout.addWidget(self.output.edit_traits(parent=self, kind='subpanel', view=OutputView).control)
        calc_button = QPushButton("Calculate")
        layout.addWidget(calc_button)
        calc_button.clicked.connect(self.run_simulation)
        self.image_view = None

        self.update_count()

    def add_image_view(self):
        self.image_view = ImageView()
        self.image_view.ui.histogram.gradient.restoreState(
            {"ticks": [(0.0, (255, 0, 0)), (0.5, (255, 255, 255)), (1.0, (0, 0, 255))], "mode": "rgb"})
        self.addWidget(self.image_view)
        self.resize(1250, self.height())
        self.setSizes([250, 1000])


    def update_count(self):
        n = self.mode_count_spin.value()
        self.cross_kerr_table.set_n(n)
        self.cross_kerr_box.resizeColumnsToContents()
        while len(self.modes) < n:
            m = ModeParameters()
            mw = m.edit_traits(parent=self, kind='subpanel', view=ModeView).control
            self.modes.append((m, mw))
            self.mode_box.addTab(mw, m.name)
            m.on_trait_change(self.update_tabs, "name")
        while len(self.modes) > n:
            m, mw = self.modes.pop(-1)
            im = self.mode_box.indexOf(mw)
            self.mode_box.removeTab(im)

    def update_tabs(self):
        for i, (m, mw) in enumerate(self.modes):
            self.mode_box.setTabText(i, m.name)


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
                H0 += val * n_ops[i] * n_ops[j]

        if H1:
            H = [H0, H1]
        else:
            H = H0

        psi0 = tensor(*psi0_list)
        out = self.output
        tlist = linspace(0, out.time, out.steps)
        result = mesolve(H, psi0, tlist, c_ops, [], args)
        axis = linspace(-out.wigner_range, out.wigner_range, out.wigner_resolution)
        wigners = array([wigner(s, axis, axis) for s in result.states])

        if not self.image_view:
            self.add_image_view()
        self.image_view.setImage(wigners)
        maxval = abs(wigners).max()
        self.image_view.setLevels(-maxval, maxval)


# class TensorParameters(HasTraits):
# mode_count = Int
#     modes = ListInstance(ModeParameters)
#     mode_cross_kerrs = Array
#
#     def __init__(self):
#         super(TensorParameters, self).__init__()
#         self.on_trait_change(self.update_mode_count, 'mode_count')
#
#     def update_mode_cross_kerrs(self):
#         n = self.mode_count
#         print dir(self.mode_cross_kerrs)
#
# TensorView = View(Group(
#     Item(name="mode_count"),
#     Item(name="modes"),
#     Item(name="mode_cross_kerrs")
# ))


# class SimulationParameters(HasTraits):
#     qubit_dimension = Int(1)
#     cavity_dimension = Int(12)
#     qubit_frequency = Float
#     cavity_frequency = Float(1)
#     qubit_anharmonicity = Float
#     cavity_anharmonicity = Float
#     qubit_decay = Float
#     qubit_dephasing = Float
#     cavity_decay = Float
#     cavity_dephasing = Float
#     drive_frequency = Float
#     drive_amplitude = Float
#     drive_phase_degrees = Float
#     initial_displacement = Float(2)
#     initial_leg_count = Int(1)
#     initial_leg_phase = ListComplex([1])
#     time = Float(10)
#     steps = Int(100)
#     wigner_range = Float(6)
#     wigner_resolution = Int(100)
#
#     def __init__(self):
#         super(SimulationParameters, self).__init__()
#         self.on_trait_change(self.update_leg_phases, 'initial_leg_count')
#
#     def update_leg_phases(self):
#         n = self.initial_leg_count
#         l = list(self.initial_leg_phase)
#         dlen = n - len(l)
#         if dlen >= 0:
#             self.initial_leg_phase.extend([1] * dlen)
#         else:
#             del self.initial_leg_phase[dlen:]
#
#
# SimulationView = \
#     View(Group(Group(Item(name='qubit_dimension'),
#                      Item(name='cavity_dimension'),
#                      label='Hilbert Space'),
#                Group(Item(name='qubit_frequency'),
#                      Item(name='cavity_frequency'),
#                      Item(name='qubit_anharmonicity'),
#                      Item(name='cavity_anharmonicity'),
#                      label='Hamiltonian'),
#                Group(Item(name='qubit_decay'),
#                      Item(name='qubit_dephasing'),
#                      Item(name='cavity_decay'),
#                      Item(name='cavity_dephasing'),
#                      label='Loss Rates'),
#                Group(Item(name='drive_frequency'),
#                      Item(name='drive_amplitude'),
#                      Item(name='drive_phase_degrees'),
#                      label='Drive Term'),
#                Group(Item(name='time'),
#                      Item(name='steps'),
#                      Item(name='initial_displacement'),
#                      Item(name='initial_leg_count'),
#                      Item(name='initial_leg_phase'),
#                      label='Simulation Parameters')))


# class Window(QSplitter):
#     def __init__(self):
#         super(Window, self).__init__()
#         self.params = SimulationParameters()
#         #self.params_box = self.params.edit_traits(parent=self, kind='subpanel', view=SimulationView).control
#         self.params_box = SimulationParameters()
#         calc_button = QPushButton("Calculate")
#         calc_button.clicked.connect(self.run_simulation)
#         side_widget = QWidget()
#         side_layout = QVBoxLayout(side_widget)
#         side_layout.addWidget(self.params_box)
#         side_layout.addWidget(calc_button)
#         self.addWidget(side_widget)
#         self.image_view = None
#
#     def add_image_view(self):
#         self.image_view = ImageView()
#         self.image_view.ui.histogram.gradient.restoreState({"ticks":[(0.0,(255,0,0)), (0.5,(255,255,255)), (1.0,(0,0,255))], "mode":"rgb"})
#         self.addWidget(self.image_view)
#
#
#     def run_simulation(self):
#         m = self.params
#
#         dq = m.qubit_dimension
#         dc = m.cavity_dimension
#
#         # Hamiltonian
#         wq = m.qubit_frequency
#         wc = m.cavity_frequency
#         Kq = m.qubit_anharmonicity
#         Kc = m.cavity_anharmonicity
#
#         aq = tensor(destroy(dq), qeye(dc))
#         ac = tensor(qeye(dq), destroy(dc))
#         nq = tensor(num(dq), qeye(dc))
#         nc = tensor(qeye(dq), num(dc))
#
#         H0 = wq*nq + wc*nc + Kq*nq*nq + Kc*nc*nc
#         if m.drive_amplitude:
#             H1 = [m.drive_amplitude*(ac + ac.dag()), "cos(df*t + phi)"]
#             H = [H0, H1]
#             args = {'df':m.drive_frequency, 'phi':pi*m.drive_phase_degrees/180}
#         else:
#             H = H0
#             args = {}
#
#         # Initial State
#         alpha = m.initial_displacement
#         psi_cav = 0
#         leg_angle = exp(2j*pi/m.initial_leg_count)
#         vacuum = basis(dc, 0)
#         leg_phases = list(m.initial_leg_phase)
#         leg_phases += [1]*(m.initial_leg_count - len(leg_phases))
#         for n, phase in enumerate(leg_phases):
#             psi_cav += phase * displace(dc, leg_angle**n * alpha) * vacuum
#
#         psi0 = tensor(basis(dq, 0), psi_cav)
#
#         tlist = linspace(0, m.time, m.steps)
#
#         # Collapse Operators
#         c_ops = [
#             m.qubit_decay * aq,
#             m.qubit_dephasing * nq,
#             m.cavity_decay * ac,
#             m.cavity_dephasing * nc
#         ]
#
#         result = mesolve(H, psi0, tlist, c_ops, [], args)
#         axis = linspace(-m.wigner_range, m.wigner_range, m.wigner_resolution)
#         wigners = array([wigner(s, axis, axis) for s in result.states])
#         if not self.image_view:
#             self.add_image_view()
#         self.image_view.setImage(wigners)
#         maxval = abs(wigners).max()
#         self.image_view.setLevels(-maxval, maxval)



if __name__ == '__main__':
    import sys

    app = QApplication([])
    win = Window()
    win.show()
    sys.exit(app.exec_())
