from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGridLayout, QPushButton, QComboBox, QMessageBox, QLabel)
from PyQt6.QtCore import Qt, QTimer
from game_logic import PuzzleGenerator
from widgets import DropCell, NumberBank

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Математический кроссворд")
        self.resize(800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # Левая часть: Игровое поле
        self.board_container = QWidget()
        self.board_layout = QVBoxLayout(self.board_container)
        
        # Центрирование сетки по горизонтали
        self.grid_centering_layout = QHBoxLayout()
        self.grid_centering_layout.addStretch()
        
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(4)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        
        self.grid_centering_layout.addLayout(self.grid_layout)
        self.grid_centering_layout.addStretch()
        
        self.board_layout.addLayout(self.grid_centering_layout)
        self.board_layout.addStretch()
        
        # Правая часть: Управление и Банк чисел
        self.controls_container = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_container)
        self.controls_container.setFixedWidth(250)

        # Отображение очков
        self.score = 0
        self.score_coeffs = {
            "easy": 10,
            "medium": 20,
            "hard": 30,
            "expert": 50
        }
        self.score_label = QLabel(f"Очки: {self.score}")
        self.score_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        self.controls_layout.addWidget(self.score_label)
        self.controls_layout.addSpacing(10)

        # Выбор сложности
        self.diff_label = QLabel("Сложность:")
        self.diff_combo = QComboBox()
        self.diff_map = {
            "Легко": "easy",
            "Средне": "medium",
            "Сложно": "hard",
            "Эксперт": "expert"
        }
        self.diff_combo.addItems(self.diff_map.keys())
        self.controls_layout.addWidget(self.diff_label)
        self.controls_layout.addWidget(self.diff_combo)

        # Кнопка новой игры
        self.new_game_btn = QPushButton("Новая игра")
        self.new_game_btn.clicked.connect(self.start_new_game)
        self.controls_layout.addWidget(self.new_game_btn)

        self.controls_layout.addSpacing(20)
        self.controls_layout.addWidget(QLabel("Доступные числа:"))
        
        # Банк чисел
        self.number_bank = NumberBank()
        self.controls_layout.addWidget(self.number_bank)
        self.controls_layout.addStretch()

        self.main_layout.addWidget(self.board_container, stretch=1)
        self.main_layout.addWidget(self.controls_container)

        self.current_grid_state = None
        self.solution_grid = None
        self.cells = {} # Карта (r, c) -> DropCell

        # Запуск начальной игры
        self.start_new_game()

    def start_new_game(self):
        diff_text = self.diff_combo.currentText()
        difficulty = self.diff_map.get(diff_text, "easy")
        
        # Генерация головоломки
        # Это может занять некоторое время, (можно вынести в отдельный поток)
        generated = PuzzleGenerator.generate_puzzle(difficulty)
        if not generated:
            QMessageBox.warning(self, "Error", "Failed to generate puzzle. Please try again.")
            return

        self.solution_grid = generated
        playable_grid, removed_numbers = PuzzleGenerator.create_playable_state(generated, difficulty)
        self.current_grid_state = playable_grid

        # Настройка UI сетки
        self.clear_grid()
        
        size = len(playable_grid)
        for r in range(size):
            for c in range(size):
                cell_data = playable_grid[r][c]
                if cell_data:
                    val, type_ = cell_data
                    
                    cell_widget = DropCell(r, c, self)
                    cell_widget.dropped.connect(self.on_cell_dropped)
                    cell_widget.cleared.connect(self.on_cell_cleared)
                    self.cells[(r, c)] = cell_widget
                    
                    if type_ == 'empty_number':
                        cell_widget.setStyleSheet(cell_widget.default_style)
                    else:
                        # Это статическая часть (оператор, равно или данное число)
                        cell_widget.setText(str(val))
                        cell_widget.current_value = val # Для проверки
                        cell_widget.is_droppable = False # Нельзя перетаскивать
                        cell_widget.setAcceptDrops(False) # Сюда нельзя бросать
                        # Стилизуем иначе для статического контента
                        cell_widget.setStyleSheet("""
                            QLabel {
                                background-color: #ddd;
                                border: 1px solid #999;
                                border-radius: 3px;
                                font-size: 14px;
                                font-weight: bold;
                                color: #000;
                            }
                        """)
                    
                    self.grid_layout.addWidget(cell_widget, r, c)
                else:
                    # Пустое пространство, можно добавить разделитель или ничего
                    pass

        # Настройка банка чисел
        self.number_bank.set_numbers(removed_numbers)

    def clear_grid(self):
        # Удаление всех виджетов из макета сетки
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.cells = {}

    def on_cell_dropped(self, r, c, value, from_bank):
        if from_bank:
            self.number_bank.remove_number(value)
        self.check_solution()

    def on_cell_cleared(self, value):
        self.number_bank.add_number(value)
        self.check_solution()

    def evaluate_expression(self, parts):
        if not parts:
            return None
        try:
            # Преобразуем список частей в строку выражения
            # Заменяем '/' на '//' для целочисленного деления
            expr = "".join(str(p) for p in parts).replace('/', '//')
            return eval(expr)
        except (ValueError, IndexError, TypeError, ZeroDivisionError, SyntaxError):
            return None

    def check_solution(self):
        if not self.solution_grid:
            return

        cell_status = {} # (r,c) -> 'neutral', 'valid', 'invalid'
        # Инициализация всех изменяемых ячеек как нейтральных
        for pos, cell in self.cells.items():
            if cell.acceptDrops():
                cell_status[pos] = 'neutral'

        all_equations_correct = True
        
        # Итерация по всем уравнениям, определенным в сетке решения
        for eq_data in self.solution_grid.equations:
            eq_obj, start_r, start_c, direction = eq_data
            dr, dc = direction
            
            # Длина уравнения в сетке: части + '=' + результат
            length = len(eq_obj.parts) + 2
            
            equation_cells = []
            lhs_parts = []
            rhs_val = None
            is_complete = True
            
            for i in range(length):
                r = start_r + i * dr
                c = start_c + i * dc
                
                if (r, c) not in self.cells:
                    is_complete = False
                    break
                    
                cell = self.cells[(r, c)]
                val = cell.current_value
                
                if val is None:
                    is_complete = False
                    break
                
                equation_cells.append((r, c))
                
                if i < len(eq_obj.parts):
                    lhs_parts.append(val)
                elif i == len(eq_obj.parts):
                    # Это '='
                    pass
                elif i == len(eq_obj.parts) + 1:
                    rhs_val = val
            
            if not is_complete:
                all_equations_correct = False
                continue
                
            # Вычисление
            calc_res = self.evaluate_expression(lhs_parts)
            is_correct = False
            if calc_res is not None and rhs_val is not None:
                 if abs(calc_res - float(rhs_val)) < 0.001:
                     is_correct = True
            
            if not is_correct:
                all_equations_correct = False
            
            # Обновление статусов ячеек
            for r, c in equation_cells:
                if (r, c) in cell_status: # Обновляем только изменяемые ячейки
                    if not is_correct:
                        cell_status[(r, c)] = 'invalid'
                    else:
                        # Помечаем как верное, только если оно еще не помечено как неверное (неверное имеет приоритет)
                        if cell_status[(r, c)] != 'invalid':
                            cell_status[(r, c)] = 'valid'

        # Применение стилей
        for (r, c), status in cell_status.items():
            cell = self.cells[(r, c)]
            if cell.current_value is None:
                cell.setStyleSheet(cell.default_style)
                continue
                
            if status == 'invalid':
                cell.setStyleSheet("""
                    QLabel {
                        background-color: #FFB6C1;
                        border: 2px solid #FF69B4;
                        border-radius: 5px;
                        font-size: 18px;
                        color: #000;
                        font-weight: bold;
                    }
                """)
            elif status == 'valid':
                cell.setStyleSheet("""
                    QLabel {
                        background-color: #90EE90;
                        border: 2px solid #228B22;
                        border-radius: 5px;
                        font-size: 18px;
                        color: #000;
                        font-weight: bold;
                    }
                """)
            else:
                cell.setStyleSheet(cell.filled_style)

        if all_equations_correct:
            QTimer.singleShot(500, self.handle_win)

    def handle_win(self):
        diff_text = self.diff_combo.currentText()
        difficulty = self.diff_map.get(diff_text, "easy")
        points = self.score_coeffs.get(difficulty, 10)
        
        self.score += points
        self.score_label.setText(f"Очки: {self.score}")
        
        QMessageBox.information(self, "Победа!", f"Поздравляем! Вы решили кроссворд.\nПолучено очков: {points}\nВсего очков: {self.score}\n\nГенерируем следующий...")
        self.start_new_game()
