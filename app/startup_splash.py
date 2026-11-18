"""独立启动画面：在导入界面模块之前就能显示，避免启动前期用户看不到任何反馈。

为什么用顶层窗口而不是主窗口的子控件：
子控件形式的启动画面要等主窗口被平台映射、再收到 paint 事件才会真正画到屏幕上；而紧随其后的
界面构建会长时间阻塞事件循环（本机实测约 2.6 秒），屏幕上往往先露出主窗口自身的空白背景，
于是反复出现「空白页」。独立顶层窗口在 show() 时即可强制同步绘制，主窗口则一直隐藏到界面
构建完成，中间不会再出现半成品窗口。

本模块刻意只依赖 PySide6（可选 qfluentwidgets、module.localization 的惰性导入），
所以可以在 app.py 里早于 app.main_window 的重型导入被调用。
"""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

_splash = None


def _is_dark_theme():
    try:
        from qfluentwidgets import isDarkTheme

        return bool(isDarkTheme())
    except Exception:
        return False


def _translate(text):
    try:
        from module.localization import tr

        return tr(text)
    except Exception:
        return text


def wait_for_exposure(widget, timeout=0.3):
    """阻塞式等待窗口真正被合成器暴露（通常几十毫秒），让画面先上屏再继续。

    紧接着的界面构建/窗口切换会长时间阻塞事件循环，若不确认已上屏，屏幕上会先出现空白。
    """
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        handle = widget.windowHandle()
        if handle is not None and handle.isExposed():
            break
        time.sleep(0.005)
        QApplication.processEvents()
    QApplication.processEvents()


class StartupSplash(QWidget):
    """带图标、标题与加载提示的启动画面。"""

    WIDTH = 440
    HEIGHT = 300

    def __init__(self, icon_path="./assets/logo/March7th.ico"):
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("March7th Assistant")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 28)
        layout.setSpacing(0)

        self._iconLabel = QLabel(self)
        self._iconLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._iconLabel.setFixedHeight(96)
        self._iconLabel.setPixmap(QIcon(icon_path).pixmap(QSize(96, 96)))

        self._titleLabel = QLabel("March7th Assistant", self)
        self._titleLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._titleLabel.setFont(title_font)

        self._hintLabel = QLabel(_translate("正在加载，请稍候…"), self)
        self._hintLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hint_font = QFont()
        hint_font.setPointSize(10)
        self._hintLabel.setFont(hint_font)

        layout.addStretch(1)
        layout.addWidget(self._iconLabel)
        layout.addSpacing(18)
        layout.addWidget(self._titleLabel)
        layout.addSpacing(8)
        layout.addWidget(self._hintLabel)
        layout.addStretch(1)

        self._apply_theme()

    def _apply_theme(self):
        text_color = "#c9c9c9" if _is_dark_theme() else "#5a5a5a"
        self._titleLabel.setStyleSheet(f"color: {text_color}; background: transparent;")
        self._hintLabel.setStyleSheet(f"color: {text_color}; background: transparent;")
        self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = _is_dark_theme()
        painter.setPen(QPen(QColor(70, 70, 70) if dark else QColor(228, 228, 228), 1))
        painter.setBrush(QColor(32, 32, 32) if dark else QColor(255, 255, 255))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)

    def show_centered(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            center = screen.availableGeometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

        self.show()
        self.raise_()
        # 先同步画一帧；随后界面构建会长时间阻塞事件循环，不能指望它来刷新画面。
        self.repaint()
        QApplication.processEvents()
        # 再确认窗口已经真正上屏，然后才允许进入阻塞构建。
        wait_for_exposure(self)


def show_startup_splash():
    """显示启动画面（幂等）：已存在则直接返回现有实例。"""
    global _splash
    if _splash is not None:
        return _splash
    try:
        _splash = StartupSplash()
        _splash.show_centered()
    except Exception:
        _splash = None
    return _splash


def startup_splash():
    return _splash


def close_startup_splash():
    """收起启动画面（幂等）。"""
    global _splash
    splash = _splash
    if splash is None:
        return
    _splash = None
    try:
        splash.close()
        splash.deleteLater()
    except Exception:
        pass
