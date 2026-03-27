from PyQt6.QtWidgets import QLabel, QFrame, QHBoxLayout, QWidget, QScrollArea, QGridLayout
from PyQt6.QtCore import Qt, QMimeData, pyqtSignal, QTimer
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QColor, QFont

class DraggableLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(40, 40)
        self.setStyleSheet("""
            QLabel {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                font-size: 16px;
            }
            QLabel:hover {
                background-color: #45a049;
            }
        """)
        self.show()
        self.drag_start_position = None

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.MouseButton.LeftButton):
            return
        if not self.drag_start_position:
            return
        
        if (e.position().toPoint() - self.drag_start_position).manhattanLength() < 5:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.text())
        drag.setMimeData(mime)

        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(e.position().toPoint())

        drag.exec(Qt.DropAction.CopyAction)

class DropCell(QLabel):
    dropped = pyqtSignal(int, int, int, bool)
    cleared = pyqtSignal(int)

    def __init__(self, r, c, parent=None):
        super().__init__(parent)
        self.r = r
        self.c = c
        self.setFixedSize(40, 40)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.default_style = """
            QLabel {
                background-color: #f0f0f0;
                border: 2px dashed #aaa;
                border-radius: 3px;
                font-size: 14px;
                color: #333;
                font-weight: bold;
            }
        """
        self.hover_style = """
            QLabel {
                background-color: #e0e0e0;
                border: 2px solid #4CAF50;
                border-radius: 3px;
                font-size: 14px;
                color: #333;
                font-weight: bold;
            }
        """
        self.filled_style = """
            QLabel {
                background-color: #fff;
                border: 2px solid #4CAF50;
                border-radius: 3px;
                font-size: 14px;
                color: #333;
                font-weight: bold;
            }
        """
        self.setStyleSheet(self.default_style)
        self.current_value = None
        self.is_droppable = True

    def dragEnterEvent(self, e):
        if e.mimeData().hasText() and self.current_value is None:
            e.accept()
            self.setStyleSheet(self.hover_style)
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasText() and self.current_value is None:
            e.setDropAction(Qt.DropAction.CopyAction)
            e.accept()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        if self.current_value is None:
            self.setStyleSheet(self.default_style)
        else:
            self.setStyleSheet(self.filled_style)

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self.current_value is not None and self.is_droppable:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(self.current_value))
            drag.setMimeData(mime)
            
            pixmap = QPixmap(self.size())
            self.render(pixmap)
            drag.setPixmap(pixmap)
            drag.setHotSpot(e.position().toPoint())
            
            action = drag.exec(Qt.DropAction.CopyAction)
            
            if action == Qt.DropAction.CopyAction:
                self.reset()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            if self.current_value is not None and self.acceptDrops():
                self.cleared.emit(self.current_value)
                self.reset()

    def dropEvent(self, e):
        text = e.mimeData().text()
        
        # Проверка, сброшено ли на самого себя
        if e.source() == self:
            e.ignore()
            return

        # Если у нас уже есть значение, возвращаем его в банк
        if self.current_value is not None:
            old_val = self.current_value
            QTimer.singleShot(0, lambda v=old_val: self.cleared.emit(v))
            
        self.setText(text)
        self.current_value = int(text)
        self.setStyleSheet(self.filled_style)
        e.setDropAction(Qt.DropAction.CopyAction)
        e.accept()
        
        val = self.current_value
        from_bank = isinstance(e.source(), DraggableLabel)
        QTimer.singleShot(0, lambda r=self.r, c=self.c, v=val, fb=from_bank: self.dropped.emit(r, c, v, fb))

    def reset(self):
        self.setText("")
        self.current_value = None
        self.setStyleSheet(self.default_style)

class NumberBank(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("numberBank")
        self.layout = QGridLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.layout.setSpacing(5)
        self.numbers = []
        self.widget_pool = []  # Пул переиспользуемых виджетов
        self.cols = 4  # Количество столбцов для сетки
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)
        self.setStyleSheet("""
            #numberBank {
                background-color: #f9f9f9;
                border: 2px solid #ccc;
                border-radius: 5px;
            }
        """)

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            if isinstance(e.source(), DraggableLabel):
                e.ignore()
            else:
                e.accept()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasText():
            if isinstance(e.source(), DraggableLabel):
                e.ignore()
            else:
                e.setDropAction(Qt.DropAction.CopyAction)
                e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        text = e.mimeData().text()
        try:
            val = int(text)
            self.add_number(val)
            e.setDropAction(Qt.DropAction.CopyAction)
            e.accept()
        except ValueError:
            e.ignore()

    def set_numbers(self, numbers):
        self.numbers = sorted(numbers)
        self.update_display()

    def update_display(self):
        # Очистка макета (удаляем элементы, но не удаляем виджеты)
        while self.layout.count():
            self.layout.takeAt(0)
        
        # Убеждаемся, что пул достаточно велик
        while len(self.widget_pool) < len(self.numbers):
            self.widget_pool.append(DraggableLabel("", self))
            
        # Скрываем все виджеты в пуле изначально
        for w in self.widget_pool:
            w.hide()
            
        # Обновляем и размещаем необходимые виджеты
        for i, num in enumerate(self.numbers):
            w = self.widget_pool[i]
            w.setText(str(num))
            w.show()
            
            row = i // self.cols
            col = i % self.cols
            self.layout.addWidget(w, row, col)

    def remove_number(self, val):
        if val in self.numbers:
            self.numbers.remove(val)
            self.update_display()
    
    def add_number(self, val):
        self.numbers.append(val)
        self.numbers.sort()
        self.update_display()
