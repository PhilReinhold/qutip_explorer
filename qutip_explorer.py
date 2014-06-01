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


if __name__ == '__main__':
    import sys

    app = QApplication([])
    win = Window()
    win.show()
    sys.exit(app.exec_())
