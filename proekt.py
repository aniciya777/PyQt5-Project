from PyQt5.QtWidgets import QApplication, QWidget, QTextEdit, QPushButton, QLabel, QStyleFactory, \
    QFileDialog, QMainWindow, QDesktopWidget, QVBoxLayout, QScrollArea, QSpacerItem, QSizePolicy, \
    QErrorMessage
from PyQt5.QtCore import QRect, Qt, QTimer, QEvent
from PyQt5.QtGui import QIcon, QPainter, QColor, QPainterPath, QBrush
from PyQt5 import uic
import math
import sys
import os
from PIL import Image


EXAMPLES_PATH = 'examples/'
BACK_AREA = 'background-color: white;'
CONST_3_2_PI = math.sqrt(3) / 2
DEFAULT_SPEED = 1


class Document:
    def __init__(self, parent=None):
        self.step = 0
        self.figures = []
        self.widget = None
        self.width = parent.scrollArea_3.width() - 2
        self.height = parent.scrollArea_3.height() - 2
        self.figuresCount = 0
        self.timer = QTimer()
        self.parent = parent
        self.btn_list = []
        self.select_figure = None
        self.dur_anims_cycle = []
        self.dur_anims_no_cycle = []
        self.duration = 0
        self.update_list()

    def set_widget(self, widget):
        self.widget = widget
        self.widget.setFixedWidth(self.width)
        self.widget.setFixedHeight(self.height)

    def load_file(self, f):
        self.width, self.height = map(int, f.readline().split())
        self.figuresCount = int(f.readline())
        for i in range(self.figuresCount):
            name, *args = f.readline().split()
            args = list(map(float, args[:-1])) + args[-1:]
            if name == 'rectangle':
                fig = Rectangle(*args, self)
            elif name == 'circle':
                fig = Circle(*args, self)
            elif name == 'triangle':
                fig = Triangle(*args, self)
            figureAnimationsCount = int(f.readline())
            for j in range(figureAnimationsCount):
                fig.add_anim_str(f.readline().strip())
            self.figures.append(fig)
        self.update_list()
        self.calc_duration()
        self.parent.countStepsLabel.setText(str(self.duration))
        self.parent.slider.setMaximum(self.duration)

    def calc_duration(self):
        dur_cycle = 1
        for x in self.dur_anims_cycle:
            dur_cycle *= x // math.gcd(dur_cycle, x)
        self.duration = max(self.dur_anims_no_cycle + [dur_cycle])

    def save_file(self, f):
        print(self.width, self.height, file=f)
        print(self.figuresCount, file=f)
        for fig in self.figures:
            fig.save_file(f)

    def update_list(self):
        self.parent.figures_widget = QWidget()
        self.parent.scrollArea.setWidget(self.parent.figures_widget)
        layout = QVBoxLayout()
        self.btn_lis = []
        for fig in self.figures:
            btn = QPushButton(str(fig))
            btn.figure = fig
            btn.setCheckable(True)
            btn.clicked.connect(self.parent.select_figure)
            layout.addWidget(btn)
            self.btn_list.append(btn)
        spacer = QSpacerItem(0, 0, QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        layout.addItem(spacer)
        self.parent.figures_widget.setLayout(layout)

    def unset_figures(self):
        for btn in self.btn_list:
            btn.setChecked(False)

    def draw(self):
        for fig in self.figures:
            fig.draw()
        self.parent.currentStepLabel.setText(f'Текущий кадр: {self.step + 1}')
        self.parent.slider.setValue(self.step + 1)

    def set_step(self, step):
        step = int(step)
        if step < 0:
            step = 0
        elif step >= self.duration:
            step = self.duration - 1
            self.parent.is_draw = False
        self.step = step


class Animation:
    def __init__(self, parent, time, cycle=''):
        self.parent = parent
        self.cycle = cycle
        self.time = int(time)
        if self.cycle:
            self.parent.parent.dur_anims_cycle.append(self.time * 2)
        else:
            self.parent.parent.dur_anims_no_cycle.append(self.time)

    def coeff(self):
        if self.cycle:
            n = self.parent.parent.step // self.time
            if n % 2:  # Обратный ход
                return 1 - (self.parent.parent.step % self.time) / self.time
            else:  # Прямой ход
                return (self.parent.parent.step % self.time) / self.time
        else:
            return min(1, self.parent.parent.step / self.time)


class Move(Animation):
    def __init__(self, parent, destX, destY, time, cycle=''):
        super().__init__(parent, time, cycle)
        self.destX = float(destX)
        self.destY = float(destY)

    def draw(self):
        x = (self.destX - self.parent.centerX) * self.coeff()
        y = (self.destY - self.parent.centerY) * self.coeff()
        self.parent.qp.translate(x, y)

    def save_file(self, f):
        print('move', self.destX, self.destY, self.time, self.cycle, file=f)


class Rotate(Animation):
    def __init__(self, parent, angle, time, cycle=''):
        super().__init__(parent, time, cycle)
        self.angle = float(angle)

    def draw(self):
        self.parent.qp.rotate(self.parent.angle + self.angle * self.coeff())

    def save_file(self, f):
        print('rotate', self.angle, self.time, self.cycle, file=f)


class Scale(Animation):
    def __init__(self, parent, destScale, time, cycle=''):
        super().__init__(parent, time, cycle)
        self.destScale = float(destScale)

    def draw(self):
        self.parent.qp.scale(self.destScale * self.coeff(), self.destScale * self.coeff())

    def save_file(self, f):
        print('scale', self.destScale, self.time, self.cycle, file=f)


class Figure:
    def __init__(self, parent, centerX, centerY, color, angle):

        self.qp = None
        self.parent = parent
        self.centerX = centerX
        self.centerY = centerY
        self.color = color
        self.anims = []
        self.angle = angle

    def draw_start(self):
        self.qp = QPainter()
        if self.parent.widget:
            self.qp.begin(self.parent.widget)
        if self is self.parent.select_figure:
            color = QColor(self.color)
            rgb = color.getRgb()[:-1]
            rgb = [255 - x for x in rgb]
            self.qp.setBrush(QColor(*rgb, 255))
        else:
            self.qp.setBrush(QColor(self.color))
        self.qp.setPen(QColor(self.color))
        self.qp.translate(self.centerX, self.centerY)
        for anim in self.anims:
            anim.draw()

    def draw_end(self):
        self.qp.end()

    def add_anim_str(self, s):
        name, *s = s.split()
        if name == 'move':
            self.add_anim(Move(self, *s))
        elif name == 'rotate':
            self.add_anim(Rotate(self, *s))
        elif name == 'scale':
            self.add_anim(Scale(self, *s))

    def add_anim(self, anim):
        self.anims.append(anim)

    def save_file(self, f):
        print(len(self.anims), file=f)
        for anim in self.anims:
            anim.save_file(f)


class Rectangle(Figure):
    def __init__(self, centerX, centerY, width, height, angle, color, parent):
        super().__init__(parent, centerX, centerY, color, angle)
        self.width = width
        self.height = height
        self.angle = angle

    def __str__(self):
        return 'Прямоугольник'

    def draw(self):
        self.draw_start()
        x = -self.width / 2
        y = -self.height / 2
        self.qp.drawRect(x, y, self.width, self.height)
        self.draw_end()

    def save_file(self, f):
        print('rectangle', self.centerX, self.centerY, self.width, self.height, self.angle,
              self.color, file=f)
        super().save_file(f)


class Circle(Figure):
    def __init__(self, centerX, centerY, radius, color, parent):
        super().__init__(parent, centerX, centerY, color, 0)
        self.radius = radius

    def __str__(self):
        return 'Круг'

    def draw(self):
        self.draw_start()
        self.qp.drawEllipse(0, 0, self.radius, self.radius)
        self.draw_end()

    def save_file(self, f):
        print('circle', self.centerX, self.centerY, self.radius, self.color, file=f)
        super().save_file(f)


class Triangle(Figure):
    def __init__(self, centerX, centerY, radius, angle, color, parent):
        super().__init__(parent, centerX, centerY, color, 0)
        self.radius = radius
        self.angle = angle
        self.point1 = (0, -self.radius)
        self.x = self.radius * CONST_3_2_PI
        self.point2 = (self.x, self.radius / 2)
        self.point3 = (-self.x, self.radius / 2)

    def __str__(self):
        return 'Треугольник'

    def draw(self):
        self.draw_start()
        path = QPainterPath()
        path.moveTo(*self.point3)
        path.lineTo(*self.point1)
        path.lineTo(*self.point2)
        path.lineTo(*self.point3)
        self.qp.drawPath(path)
        self.draw_end()

    def save_file(self, f):
        print('triangle', self.centerX, self.centerY, self.radius, self.angle, self.color, file=f)
        super().save_file(f)


class Form(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('proekt.ui', self)
        self.file_name = None
        self.document = Document(self)
        self.is_animations = [False, False, False]
        self.is_figures = [True, False, False]
        self.setWindowIcon(QIcon('ikona.jpg'))
        self.speed = DEFAULT_SPEED
        self.is_draw = False
        self.history_list = []
        try:
            with open('history.log', 'r', encoding='utf-8') as f:
                for s in f.readlines():
                    s = s.strip()
                    if s:
                        self.history_list.append(s)
        except:
            pass
        self.init_ui()

    def init_ui(self):
        self.widget = QWidget()
        self.widget.setStyleSheet(BACK_AREA)
        self.document.set_widget(self.widget)
        self.scrollArea_3.setWidget(self.widget)
        self.saveButton.clicked.connect(self.save)
        self.saveAsButton.clicked.connect(self.save_as)
        self.skrinButton.clicked.connect(self.skrin)
        self.cleanButton.clicked.connect(self.clean_all)
        self.historyButton.clicked.connect(self.history)
        self.exampleButton.clicked.connect(self.example)
        self.spravkaButton.clicked.connect(self.spravka)
        self.animatedButton.clicked.connect(self.animated)
        self.openButton.clicked.connect(self.open)
        self.nonAnimatedCheckBox.clicked.connect(self.set_non_animated)
        self.increaseAnimatedCheckBox.clicked.connect(self.set_increase_animated)
        self.rotationAnimatedCheckBox.clicked.connect(self.set_rotation_animated)
        self.flyAnimatedCheckBox.clicked.connect(self.set_fly_animated)
        self.squareFigureCheckBox.clicked.connect(self.set_figure_check_box)
        self.circleFigureCheckBox.clicked.connect(self.set_figure_check_box)
        self.triangleFigureCheckBox.clicked.connect(self.set_figure_check_box)
        self.prevStepButton.clicked.connect(self.prev_step)
        self.nextStepButton.clicked.connect(self.next_step)
        self.slider.valueChanged.connect(self.change_step)
        self.startButton.clicked.connect(self.start)
        self.pauseButton.clicked.connect(self.pause)
        self.upSpeedButton.clicked.connect(self.speed_up)
        self.downSpeedButton.clicked.connect(self.speed_down)
        self.widget.paintEvent = lambda event: form.document.draw()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.drawing)
        self.timer.start(self.speed)

    def save(self):
        if self.file_name:
            self.save_to_file(self.file_name)
        else:
            self.save_as()

    def save_as(self):
        f_as_name = QFileDialog.getSaveFileName(self, 'Сохранение', '', "Скрипт анимации (*.txt)")[
            0]
        if f_as_name:
            self.save_to_file(f_as_name)

    def save_to_file(self, file_name):
        if file_name:
            self.file_name = file_name
            try:
                with open(file_name, 'w') as f:
                    self.document.save_file(f)
            except:
                QErrorMessage().showMessage('Ошибка сохранения')

    def skrin(self):
        # изображение результата работы программы
        pixmap = self.widget.grab()
        filename, format = QFileDialog.getSaveFileName(self, 'Сохранение скриншота', '',
                                                       'JPEG - Joint Photographic Experts Group(*.jpg *.jpeg);;PNG - Portable Network Graphics(*.png);;BMP - Windows Bitmap (*.bmp);;PPM - Portable Pixmap (*.ppm);;XBM - X11 Bitmap (*.xbm);;XPM - X11 Pixmap (*.xpm)')
        if filename:
            try:
                format = format.strip().split()[0]
                pixmap.save(filename, format)
            except:
                QErrorMessage().showMessage('Ошибка сохранения скриншрота')

    def clean_all(self):
        # очищение строки текста и прекращение показа анимации
        self.textEdit.setText('')
        self.document = Document(self)
        self.document.set_widget(self.widget)

    def history(self):
        # вывод списка в виде таблице время/текст анимации
        self.history_form = HistoryForm(self)
        self.history_form.show()

    def example(self):
        # окошко выбора из 10 Сашиных анимаций с пойманным моментом отображения текста
        self.examples_from = ExamplesForm(self)
        self.examples_from.show()

    def spravka(self):
        # справка = реадми  указания по работе с приложением  открывается отдельное окошко с текстом
        self.help_form = HelpForm()
        self.help_form.show()

    def animated(self):
        text = self.textEdit.toPlainText().strip().upper()
        if text:
            if text in self.history_list:
                self.history_list.remove(text)
            self.history_list.append(text)
            self.history_list = self.history_list[:10]
            try:
                with open('history.log', 'w', encoding='utf-8') as f:
                    for s in self.history_list:
                        print(s, file=f)
            except:
                pass
            print(text)

    def open(self):
        f_as_name, _ = QFileDialog.getOpenFileName(self)
        if f_as_name:
            self.open_file(f_as_name)

    def open_file(self, file_name):
        self.file_name = file_name
        try:
            with open(file_name, 'r') as f:
                self.is_draw = False
                self.document = Document(self)
                self.document.load_file(f)
                self.document.set_widget(self.widget)
        except:
            self.file_name = None
            QErrorMessage().showMessage('Ошибка чтения файла!')

    def set_non_animated(self):
        state = not self.nonAnimatedCheckBox.isChecked()
        self.increaseAnimatedCheckBox.setChecked(state)
        self.rotationAnimatedCheckBox.setChecked(state)
        self.flyAnimatedCheckBox.setChecked(state)
        self.is_animations = [state, state, state]

    def set_increase_animated(self):
        state = self.increaseAnimatedCheckBox.isChecked()
        self.is_animations[0] = state
        self.check_no_animated(state)

    def set_rotation_animated(self):
        state = self.rotationAnimatedCheckBox.isChecked()
        self.is_animations[1] = state
        self.check_no_animated(state)

    def set_fly_animated(self):
        state = self.flyAnimatedCheckBox.isChecked()
        self.is_animations[2] = state
        self.check_no_animated(state)

    def check_no_animated(self, state):
        if state:
            self.nonAnimatedCheckBox.setChecked(False)
        else:
            self.nonAnimatedCheckBox.setChecked(not any(self.is_animations))

    def set_figure_check_box(self):
        self.is_figures = [
            self.squareFigureCheckBox.isChecked(),
            self.circleFigureCheckBox.isChecked(),
            self.triangleFigureCheckBox.isChecked(),
        ]
        if not any(self.is_figures):
            self.sender().setChecked(True)

    def select_figure(self):
        self.document.unset_figures()
        self.sender().setChecked(True)
        self.document.select_figure = self.sender().figure
        self.widget.update()

    def start(self):
        self.is_draw = True

    def pause(self):
        self.is_draw = False

    def speed_up(self):
        self.speed = self.speed // 2 + 1
        self.timer.setInterval(self.speed)

    def speed_down(self):
        self.speed *= 2
        self.timer.setInterval(self.speed)

    def prev_step(self):
        self.document.set_step(self.document.step - 1)
        self.widget.update()

    def next_step(self):
        self.document.set_step(self.document.step + 1)
        self.widget.update()

    def change_step(self):
        self.document.set_step(self.slider.value() - 1)
        self.widget.update()

    def drawing(self):
        if self.is_draw:
            self.next_step()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.is_draw = not self.is_draw


class VBoxForm(QScrollArea):
    def __init__(self, parent_from):
        super().__init__()
        self.parent_form = parent_from
        self.init_ui()

    def init_ui(self):
        self.setFixedWidth(self.GEOMETRY[2])
        self.setGeometry(*self.GEOMETRY)
        set_to_screen_center(self)
        self.widget = QWidget(self)
        self.v_layout = QVBoxLayout()
        self.show_list()
        self.v_layout.setAlignment(Qt.AlignTop)
        self.widget.setLayout(self.v_layout)
        self.widget.setFixedWidth(self.GEOMETRY[2] - self.v_layout.getContentsMargins()[1]
                                  - self.v_layout.getContentsMargins()[3])
        self.setWidget(self.widget)


class ExamplesForm(VBoxForm):
    def __init__(self, parent_from):
        super().__init__(parent_from)

    def init_ui(self):
        self.GEOMETRY = (0, 0, 300, 300)
        self.setWindowTitle('Примеры')
        super().init_ui()

    def show_list(self):
        files = os.listdir(EXAMPLES_PATH)
        examples_name = filter(lambda x: x.endswith('.txt'), files)
        for name in sorted(examples_name, key=lambda s: int((s.split('.')[0]).split()[1])):
            btn = QPushButton(name, self.widget)
            btn.clicked.connect(self.open_example)
            self.v_layout.addWidget(btn)

    def open_example(self):
        filename = EXAMPLES_PATH + self.sender().text()
        self.close()
        self.parent_form.open_file(filename)


class HistoryForm(VBoxForm):
    def __init__(self, parent_from):
        super().__init__(parent_from)

    def init_ui(self):
        self.GEOMETRY = (0, 0, 600, 300)
        self.setWindowTitle('История')
        super().init_ui()

    def show_list(self):
        if self.parent_form.history_list:
            for s in reversed(self.parent_form.history_list):
                btn = QPushButton(s, self.widget)
                btn.clicked.connect(self.open_query)
                self.v_layout.addWidget(btn)
        else:
            label = QLabel('История пуста', self.widget)
            self.v_layout.addWidget(label)

    def open_query(self):
        s = self.sender().text()
        self.close()
        self.parent_form.textEdit.setPlainText(s)
        self.parent_form.animated()


class HelpForm(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi('help.ui', self)
        try:
            with open('READ_ME.txt', 'r', encoding='utf-8') as f:
                self.textEdit.setText(f.read())
        except:
            QErrorMessage().showMessage('Ошибка загрузки справки!')


def set_to_screen_center(form):
    desktop = QDesktopWidget()
    rect = desktop.availableGeometry(desktop.primaryScreen())
    center = rect.center()
    center.setX(center.x() - (form.width() // 2))
    center.setY(center.y() - (form.height() // 2))
    form.move(center)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    QApplication.setStyle(QStyleFactory.create('Fusion'))
    form = Form()
    form.setFixedSize(1025, 800)
    form.show()
    form.open_file(EXAMPLES_PATH + 'Пример 1.txt')
    form.update()
    sys.exit(app.exec())
