import ast
from PyQt4.QtCore import QAbstractTableModel, Qt, pyqtSignal, QObject, QPoint
from PyQt4.QtGui import QStandardItem, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QStandardItemModel, QTableView, \
    QStyledItemDelegate, QMenu, QAction, QDialog, QVBoxLayout, QDialogButtonBox, QTreeView, QLabel, QPixmap, QMessageBox, \
    QLineEdit


def print_fn(*s):
    print ",".join(map(str, s))


def method_style(s):
    return str(s).lower().replace(" ", "_")


def word_style(s):
    return " ".join("".join([w[0].upper(), w[1:]]) for w in str(s).replace("_", " ").split())


def error_message(message, title=None, warning=False):
    message_box = QMessageBox()
    message_box.setText(message)
    if title is not None:
        message_box.setWindowTitle(title)
    if warning:
        message_box.setIcon(QMessageBox.Warning)
    else:
        message_box.setIcon(QMessageBox.Critical)
    message_box.exec_()

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

class VarLineEdit(QLineEdit):
    variable_added = pyqtSignal(str)
    value_changed = pyqtSignal(float)
    spinbox = QDoubleSpinBox
    def __init__(self, variables):
        self.variables = variables
        super(VarLineEdit, self).__init__()
        self.value_text = "0"

    def check_variables(self):
        text = str(self.text())
        try:
            self.set_value(int(text))
        except ValueError:
            try:
                expr = ast.parse(text)
            except SyntaxError:
                # TODO: Error Message Box
                raise
            for item in ast.walk(expr):
                if isinstance(item, ast.Name):
                    var_name = item.id
                    if var_name not in self.variables:
                        if not self.new_variable_dialog(var_name):
                            self.reject()

    def evaluate(self):
        text = str(self.text())
        try:
            return str(int(text)), ""
        except ValueError:
            return text, eval(text, self.variables)

    def set_value(self, value):
        self.value_text = str(self.text())
        self.value = value
        self.value_changed.emit(value)

    def reject(self):
        self.setText(self.value_text)

    def new_variable_dialog(self, var_name):
        dialog = QDialog()
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Create Variable %s" % var_name))
        spinbox = self.spinbox()
        layout.addWidget(spinbox)
        layout.addWidget(button_box)
        if dialog.exec_():
            self.variables[var_name] = spinbox.value()
            print self.variables
            #self.variable_added.emit(var_name)
            return True
        return False

class IntVarLineEdit(VarLineEdit):
    spinbox = QSpinBox
    value_changed = pyqtSignal(int)


# TODO: Variables system for FormItems
# TODO: Copy/Paste system for FormItems/GroupItems
class FormItem(QStandardItem):
    def __init__(self, name, fields, setup):
        super(FormItem, self).__init__(name)
        fields = [("Name", str, name)] + fields
        self.name = lambda: str(self.text())
        self.names, _, _ = zip(*fields)
        self.dtypes = {}
        self.widgets = {}
        self.method_names = []
        self.val_items = {}
        self.expr_items = {}
        self.group_items = {}
        self.setup = setup
        self.params_model = QStandardItemModel()
        self.params_model.itemChanged.connect(self.update_name)
        self.params_model.setHorizontalHeaderLabels(["Name", "Formula", "Evaluated"])
        self.params_widget = QTableView()
        self.params_widget.setModel(self.params_model)
        self.params_widget.setItemDelegate(FormDelegate(self.params_model, self.widgets))
        self.params_widget.verticalHeader().hide()

        for name, item_type, default in fields:
            self.add_field(name, item_type, default)
        self.params_widget.resizeRowsToContents()
        self.context_menu = ActionsMenu([])

        self.params_model.itemChanged.connect(self.notify_group_item_children)

    def notify_group_item_children(self, item):
        method_name = method_style(self.params_model.item(item.row(), 0).text())
        if method_name in self.group_items:
            current_item = self.dtypes[method_name](item.text())
            previous_item = self.dtypes[method_name](self.group_items[method_name])
            self.group_items[method_name] = current_item

            current_item.register_dependency(self)
            previous_item.unregister_dependency(self)


    def add_field(self, word_name, item_type, value):
        word_name = word_style(word_name)
        method_name = method_style(word_name)
        if item_type is int:
            self.dtypes[method_name] = int
            self.widgets[word_name] = lambda: IntVarLineEdit(self.setup.variables)
        elif item_type is float:
            self.dtypes[method_name] = float
            self.widgets[word_name] = lambda: VarLineEdit(self.setup.variables)
        elif isinstance(item_type, bool):
            self.dtypes[method_name] = bool
            self.widgets[word_name] = QCheckBox
        elif isinstance(item_type, (list, tuple)):
            self.dtypes[method_name] = str
            self.widgets[word_name] = \
                lambda grp=item_type, **kwargs: MyComboBox(grp, **kwargs)
        elif isinstance(item_type, GroupItem):
            group = item_type
            value = group.items_list()[0].text()
            self.dtypes[method_name] = lambda i_name, grp=group: grp.item_from_name(i_name)
            self.widgets[word_name] = \
                lambda grp=group, **kwargs: ItemsComboBox(grp, **kwargs)
            self.group_items[method_name] = value
            group.item_from_name(value).register_dependency(self)
        self.expr_items[method_name] = QStandardItem(str(value))
        self.val_items[method_name] = ConstantItem("")
        self.params_model.appendRow([ConstantItem(word_name), self.expr_items[method_name], self.val_items[method_name]])
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
                w = self.widgets_dict[name]()
                w.setParent(parent)
                return w

        return super(FormDelegate, self).createEditor(parent, style, idx)

    def setModelData(self, editor, model, idx):
        if isinstance(editor, VarLineEdit):
            editor.check_variables()
            editor_text, eval_text = editor.evaluate()
            model.setData(idx, editor_text, Qt.DisplayRole)
            eval_idx = model.index(idx.row(), 2)
            model.setData(eval_idx, eval_text, Qt.DisplayRole)
        else:
            super(FormDelegate, self).setModelData(editor, model, idx)




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
    def __init__(self, group_name, child_classes, setup):
        super(GroupItem, self).__init__(group_name)
        self.child_classes = child_classes
        self.context_menu = ActionsMenu([('Add ' + name, lambda c=cls: self.add_item(c)) for name, cls in child_classes])
        self.emitter = GroupItemEmitter()
        self.setup = setup
        self.current_items = []

    def add_item(self, cls=None, dialog=True):
        if cls is None:
            cls = self.child_classes[0][1]
        child = cls(self)
        child_texts = [self.child(n).text() for n in range(self.rowCount())]
        self.emitter.item_created.emit(child)
        while child.text() in child_texts:
            child.set_name(increment_name(str(child.text())))
        if dialog and hasattr(child, 'params_widget'):
            d = OKCancelDialog(child.params_widget)
            if not d.exec_():
                return None
            else:
                child.params_widget.setParent(None)
        self.current_items.append(child)
        self.appendRow(child)
        self.emitter.item_added.emit(child)
        return child

    def remove_item(self, item):
        idx = self.current_items.index(item)
        self.current_items.pop(idx)
        self.removeRow(idx)

    def items_list(self):
        return [self.child(i) for i in range(self.rowCount())]

    def item_from_name(self, name):
        for i in self.items_list():
            if str(i.text()) == name:
                return i

class GroupItemChild(FormItem):
    def __init__(self, name, fields, group):
        self.dependents = []
        self.dependencies = []
        self.group = group
        super(GroupItemChild, self).__init__(name, fields, group.setup)
        self.context_menu.add_action("Delete", self.delete_self)

    def delete_self(self):
        for other in self.dependencies:
            other.unregister_dependency(self)
        if self.dependents:
            dependents_str = ",".join([i.name() for i in self.dependents])
            error_message("Cannot delete %s:\n%s depends on it" % (self.name(), dependents_str))
            return
        self.params_widget.setParent(None)
        self.group.remove_item(self)

    def register_dependency(self, other):
        print 'register', self, other
        if other not in self.dependents:
            self.dependents.append(other)
        if self not in other.dependencies:
            other.dependencies.append(self)

    def unregister_dependency(self, other):
        print 'unregister', self, other
        self.dependents.remove(other)


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
