from PyQt4.QtCore import QAbstractTableModel, Qt, pyqtSignal, QObject, QPoint
from PyQt4.QtGui import QStandardItem, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QStandardItemModel, QTableView, \
    QStyledItemDelegate, QMenu, QAction, QDialog, QVBoxLayout, QDialogButtonBox, QTreeView, QLabel, QPixmap


def print_fn(*s):
    print ",".join(map(str, s))


def method_style(s):
    return s.lower().replace(" ", "_")


def word_style(s):
    return " ".join("".join([w[0].upper(), w[1:]]) for w in s.replace("_", " ").split())


class ArrayModel(QAbstractTableModel):
    def __init__(self, array=None):
        super(ArrayModel, self).__init__()
        self.dtype = float
        if array is None:
            self.array = []
        else:
            self.array = array

    def rowCount(self, *args, **kwargs):
        return len(self.array)

    def columnCount(self, *args, **kwargs):
        try:
            return max(map(len, self.array))
        except ValueError:
            return 0

    def data(self, idx, role=None):
        if role == Qt.DisplayRole:
            i, j = idx.row(), idx.column()
            try:
                return str(self.array[i][j])
            except IndexError:
                return "-"

    def setData(self, idx, val, role=None):
        if role == Qt.EditRole:
            i, j = idx.row(), idx.column()
            self.array[i][j] = self.dtype(str(val.toString()))
            return True
        else:
            return False

    def flags(self, idx):
        f = super(ArrayModel, self).flags(idx)
        i, j = idx.row(), idx.column()
        if i < len(self.array) and j < len(self.array[i]):
            return f | Qt.ItemIsEditable
        else:
            return f


class UpperHalfArrayModel(ArrayModel):
    def __init__(self):
        super(UpperHalfArrayModel, self).__init__()
        self.n = 0

    def set_n(self, n):
        while n > self.n:
            self.n += 1
            self.array.append([0]*self.n)

        while n < self.n:
            self.n -= 1
            self.array.pop(-1)
        self.modelReset.emit()


class ConstantItem(QStandardItem):
    def __init__(self, *args):
        super(ConstantItem, self).__init__(*args)
        self.setEditable(False)


class MyComboBox(QComboBox):
    def __init__(self, items, *args, **kwargs):
        super(MyComboBox, self).__init__(*args, **kwargs)
        self.addItems(items)

    def set_current_text(self, text):
        self.setCurrentIndex(self.findText(text))


class MySpinBox(QSpinBox):
    def __init__(self, *args, **kwargs):
        super(MySpinBox, self).__init__(*args, **kwargs)
        self.setMaximum(10000000)


class ItemsComboBox(MyComboBox):
    def __init__(self, group_item, *args, **kwargs):
        self.items_list = group_item.items_list()
        names = [str(i.text()) for i in self.items_list]
        super(ItemsComboBox, self).__init__(names, *args, **kwargs)

    def get_item(self):
        return self.items_list[self.currentIndex()]


# TODO: Variables system for FormItems
# TODO: Copy/Paste system for FormItems/GroupItems
class FormItem(QStandardItem):
    def __init__(self, name, fields):
        super(FormItem, self).__init__(name)
        fields = [("Name", str, name)] + fields
        self.name = lambda: str(self.text())
        self.names, _, _ = zip(*fields)
        self.dtypes = {}
        self.widgets = {}
        self.method_names = []
        self.val_items = {method_style(n): QStandardItem(str(v)) for n, _, v in fields}
        self.params_model = QStandardItemModel()
        self.params_model.itemChanged.connect(self.update_name)
        self.params_widget = QTableView()
        self.params_widget.setModel(self.params_model)
        self.params_widget.setItemDelegate(FormDelegate(self.params_model, self.widgets))
        self.params_widget.horizontalHeader().hide()
        self.params_widget.verticalHeader().hide()

        for name, item_type, default in fields:
            self.add_field(name, item_type, default)
        self.params_widget.resizeRowsToContents()
        self.context_menu = ActionsMenu([("Properties", self.params_widget.show)])

    def add_field(self, word_name, item_type, value):
        word_name = word_style(word_name)
        method_name = method_style(word_name)
        if item_type is int:
            self.dtypes[method_name] = int
            self.widgets[word_name] = MySpinBox, "value", "setValue"
        elif item_type is float:
            self.dtypes[method_name] = float
            self.widgets[word_name] = QDoubleSpinBox, "value", "setValue"
        elif isinstance(item_type, bool):
            self.dtypes[method_name] = bool
            self.widgets[word_name] = QCheckBox, "isChecked", "setChecked"
        elif isinstance(item_type, (list, tuple)):
            self.dtypes[method_name] = str
            self.widgets[word_name] = \
                lambda grp=item_type, **kwargs: MyComboBox(grp, **kwargs), "currentText", "set_current_text"
        elif isinstance(item_type, GroupItem):
            value = item_type.items_list()[0].text()
            self.dtypes[method_name] = lambda i_name, grp=item_type: grp.item_from_name(i_name)
            self.widgets[word_name] = \
                lambda grp=item_type, **kwargs: ItemsComboBox(grp, **kwargs), "currentText", "set_current_text"
        self.val_items[method_name] = QStandardItem(str(value))
        self.params_model.appendRow([ConstantItem(word_name), self.val_items[method_name]])
        self.method_names.append(method_name)

    def set_name(self, name):
        self.setText(name)
        self.params_model.item(0, 1).setText(name)

    def update_name(self):
        self.setText(self.params_model.item(0, 1).text())

    def __getattr__(self, item):
        if item in self.method_names:
            dtype = self.dtypes[item]
            return dtype(self.val_items[item].text())
        else:
            raise AttributeError(item)


class FormDelegate(QStyledItemDelegate):
    item_editor_activated = pyqtSignal(str)

    def __init__(self, model, widgets_dict):
        super(FormDelegate, self).__init__()
        self.model = model
        self.widgets_dict = widgets_dict

    def createEditor(self, parent, style, idx):
        if idx.column() == 1:
            name = str(self.model.itemFromIndex(idx.sibling(idx.row(), 0)).text())
            self.item_editor_activated.emit(name)
            if name in self.widgets_dict:
                w = self.widgets_dict[name][0]()
                w.setParent(parent)
                return w

        return super(FormDelegate, self).createEditor(parent, style, idx)


class ActionsMenu(QMenu):
    def __init__(self, rows):
        super(ActionsMenu, self).__init__()
        self.add_actions(rows)

    def add_action(self, name, func):
        a = QAction(name, self)
        self.addAction(a)
        a.triggered.connect(lambda x: func())

    def add_actions(self, rows):
        for name, func in rows:
            self.add_action(name, func)


class OKCancelDialog(QDialog):
    def __init__(self, *widgets):
        super(OKCancelDialog, self).__init__()
        self.setModal(True)
        layout = QVBoxLayout(self)
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        for w in widgets:
            w.setAttribute(Qt.WA_DeleteOnClose, False)
            layout.addWidget(w)
        layout.addWidget(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.setAttribute(Qt.WA_DeleteOnClose, False)


def increment_name(name):
    n = ""
    for c in reversed(name):
        if not (c + n).isdigit():
            break
        n = c + n
    if not n:
        return name + "_1"
    else:
        new_n = str(int(n) + 1)
        return name.replace(n, new_n)


class GroupItemEmitter(QObject):
    item_added = pyqtSignal(QStandardItem)
    item_created = pyqtSignal(QStandardItem)


class GroupItem(ConstantItem):
    def __init__(self, group_name, item_name, item_class, setup=None):
        super(GroupItem, self).__init__(group_name)
        self.context_menu = ActionsMenu([('Add ' + item_name, self.add_item)])
        self.item_class = item_class
        self.emitter = GroupItemEmitter()
        self.setup = setup

    def add_item(self, dialog=True):
        try:
            i = self.item_class()
        except TypeError:
            i = self.item_class(self)
        child_texts = [self.child(n).text() for n in range(self.rowCount())]
        self.emitter.item_created.emit(i)
        while i.text() in child_texts:
            i.set_name(increment_name(str(i.text())))
        if dialog and hasattr(i, 'params_widget'):
            d = OKCancelDialog(i.params_widget)
            if d.exec_():
                i.params_widget.setParent(None)
                self.appendRow(i)
                self.emitter.item_added.emit(i)
        else:
            self.appendRow(i)
            self.emitter.item_added.emit(i)

    def items_list(self):
        return [self.child(i) for i in range(self.rowCount())]

    def item_from_name(self, name):
        for i in self.items_list():
            if str(i.text()) == name:
                return i


class ContextMenuStandardTreeView(QTreeView):
    def __init__(self):
        super(ContextMenuStandardTreeView, self).__init__()
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, point):
        item = self.model().itemFromIndex(self.indexAt(point))
        if hasattr(item, "context_menu"):
            # TODO: Fix context menu positioning hack
            item.context_menu.exec_(self.mapToGlobal(point) + QPoint(0, 25))
            return True
        elif item is None and hasattr(self, "context_menu"):
            self.context_menu.exec_(self.mapToGlobal(point))
            return True
        return False


class ResizableImage(QLabel):
    def __init__(self, filename, height, min_scale, max_scale):
        super(ResizableImage, self).__init__()
        self.setAlignment(Qt.AlignCenter)
        self.full_pixmap = None
        self.scaled_pixmap = None
        self.aspect = None
        self.set_file(filename)
        self.set_height(height)
        self.min_height = self.full_pixmap.height() * min_scale * self.aspect
        self.min_width = self.full_pixmap.width() * min_scale / self.aspect
        self.max_height = self.full_pixmap.height() * max_scale * self.aspect
        self.max_width = self.full_pixmap.width() * max_scale / self.aspect

    def set_file(self, filename):
        self.full_pixmap = QPixmap(filename)
        self.aspect = float(self.full_pixmap.height()) / self.full_pixmap.width()
        if self.scaled_pixmap is not None:
            self.set_height(self.scaled_pixmap.height())

    def set_height(self, height):
        self.scaled_pixmap = self.full_pixmap.scaledToHeight(height, Qt.SmoothTransformation)
        self.setPixmap(self.scaled_pixmap)

    def set_width(self, width):
        self.scaled_pixmap = self.full_pixmap.scaledToWidth(width, Qt.SmoothTransformation)
        self.setPixmap(self.scaled_pixmap)

    def resizeEvent(self, ev):
        width, height = ev.size().width(), ev.size().height()
        label_aspect = height / width
        if label_aspect > self.aspect:
            self.set_width(min(max(.9 * width, self.min_width), self.max_width))
        else:
            self.set_height(min(max(.9 * height, self.min_height), self.max_height))
