import sys
import os
import platform
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QComboBox, QPushButton,
                               QRadioButton, QSystemTrayIcon, QMenu, QFrame,
                               QGraphicsDropShadowEffect, QSpacerItem, QSizePolicy,
                               QGraphicsBlurEffect, QCheckBox)
from PySide6.QtGui import (QIcon, QAction, QPixmap, QPainter, QColor, QCursor,
                           QLinearGradient, QBrush, QPainterPath, QFont,
                           QPen, QRadialGradient, QFontDatabase)
from PySide6.QtCore import Qt, Signal, QPoint, QRect, QRectF, QTimer, QPropertyAnimation, QEasingCurve, QSettings

from pynput.keyboard import Key, Listener as KeyboardListener
from pynput.mouse import Listener as MouseListener

OS = platform.system()


def apply_windows_mica(hwnd):
    try:
        from ctypes import windll, byref, sizeof, c_int
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, byref(c_int(2)), sizeof(c_int))
    except Exception:
        pass


def apply_macos_vibrancy(window):
    try:
        import objc
        from AppKit import NSApplication, NSVisualEffectView, NSVisualEffectMaterial
        ns_app = NSApplication.sharedApplication()
        wid = window.winId().__int__()
        ns_view = objc.objc_object(c_void_p=wid)
        vibrancy = NSVisualEffectView.alloc().initWithFrame_(ns_view.bounds())
        vibrancy.setMaterial_(NSVisualEffectMaterial.NSVisualEffectMaterialSidebar)
        vibrancy.setBlendingMode_(0)
        vibrancy.setState_(1)
        ns_view.addSubview_positioned_relativeTo_(vibrancy, 0, None)
    except Exception:
        pass


class Theme:
    if OS == "Darwin":
        FONT_FAMILY    = '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue"'
        FONT_UI        = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue"'
        ACCENT         = "#007AFF"
        ACCENT_HOVER   = "#0062CC"
        TEXT_PRIMARY   = "#1D1D1F"
        TEXT_SECONDARY = "#86868B"
        TEXT_TERTIARY  = "#AEAEB2"
        BG_GLASS       = "rgba(232, 232, 237, 0.78)"
        BG_CONTROL     = "rgba(255, 255, 255, 0.55)"
        BORDER_LIGHT   = "rgba(255, 255, 255, 0.90)"
        BORDER_MID     = "rgba(209, 209, 214, 0.60)"
        RADIUS_WINDOW  = 18
        RADIUS_BTN     = 14
        RADIUS_CTRL    = 10
        SHADOW_ALPHA   = 55
        USE_FRAMELESS  = True
        SHOW_TRAFFIC   = True
        WIN_SIZE       = (340, 420)
        BTN_HEIGHT     = 44

    elif OS == "Windows":
        FONT_FAMILY    = '"Segoe UI Variable Display", "Segoe UI", system-ui'
        FONT_UI        = '"Segoe UI Variable Text", "Segoe UI", system-ui'
        ACCENT         = "#0067C0"
        ACCENT_HOVER   = "#005BA3"
        TEXT_PRIMARY   = "#1A1A1A"
        TEXT_SECONDARY = "#5D5D5D"
        TEXT_TERTIARY  = "#999999"
        BG_GLASS       = "rgba(243, 243, 243, 0.80)"
        BG_CONTROL     = "rgba(255, 255, 255, 0.70)"
        BORDER_LIGHT   = "rgba(255, 255, 255, 0.80)"
        BORDER_MID     = "rgba(200, 200, 200, 0.60)"
        RADIUS_WINDOW  = 12
        RADIUS_BTN     = 6
        RADIUS_CTRL    = 4
        SHADOW_ALPHA   = 30
        USE_FRAMELESS  = False
        SHOW_TRAFFIC   = False
        WIN_SIZE       = (360, 390)
        BTN_HEIGHT     = 36

    else:
        FONT_FAMILY    = '"Cantarell", "Inter", "Ubuntu", "Noto Sans", sans-serif'
        FONT_UI        = '"Cantarell", "Ubuntu", sans-serif'
        ACCENT         = "#3584E4"
        ACCENT_HOVER   = "#1C6EC7"
        TEXT_PRIMARY   = "#1A1A1A"
        TEXT_SECONDARY = "#5E5C64"
        TEXT_TERTIARY  = "#9A9996"
        BG_GLASS       = "rgba(246, 245, 244, 0.95)"
        BG_CONTROL     = "rgba(255, 255, 255, 0.80)"
        BORDER_LIGHT   = "rgba(255, 255, 255, 0.90)"
        BORDER_MID     = "rgba(210, 210, 210, 0.70)"
        RADIUS_WINDOW  = 12
        RADIUS_BTN     = 8
        RADIUS_CTRL    = 6
        SHADOW_ALPHA   = 25
        USE_FRAMELESS  = False
        SHOW_TRAFFIC   = False
        WIN_SIZE       = (340, 390)
        BTN_HEIGHT     = 38


class VietnameseTypingGUI(QMainWindow):
    toggle_signal = Signal()

    def __init__(self):
        super().__init__()
        self.engine = None
        self.is_running = True
        self.current_keys = set()
        self.drag_pos = QPoint()

        self.settings = QSettings("Pai", "VietnameseTyping")
        self.show_startup = self.settings.value("show_startup", True, type=bool)
        self.autostart = self.settings.value("autostart", False, type=bool)

        self.toggle_signal.connect(self.toggle_engine)

        self.init_ui()
        self.init_tray()
        self.apply_settings()

        QTimer.singleShot(100, self._apply_native_effects)

        self.keyboard_listener = KeyboardListener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener = MouseListener(on_click=self.on_mouse_click)
        self.keyboard_listener.start()
        self.mouse_listener.start()

        self.update_state()

    def _apply_native_effects(self):
        if OS == "Windows":
            apply_windows_mica(int(self.winId()))
        elif OS == "Darwin":
            apply_macos_vibrancy(self)

    def on_key_press(self, key):
        self.current_keys.add(key)
        ctrl  = any(k in self.current_keys for k in (Key.ctrl, Key.ctrl_l, Key.ctrl_r))
        shift = any(k in self.current_keys for k in (Key.shift, Key.shift_l, Key.shift_r))
        if ctrl and shift:
            self.toggle_signal.emit()
            self.current_keys.clear()
            return
        if self.is_running and self.engine:
            self.engine.on_press(key)

    def on_key_release(self, key):
        self.current_keys.discard(key)

    def on_mouse_click(self, x, y, button, pressed):
        if self.is_running and self.engine:
            self.engine.on_click(x, y, button, pressed)

    def _generate_icon(self, char, color_hex):
        px = QPixmap(64, 64)
        px.fill(Qt.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        font = QApplication.font()
        font.setPointSize(36)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(color_hex))
        p.drawText(px.rect(), Qt.AlignCenter, char)
        p.end()
        return QIcon(px)

    def _shadow(self, widget, radius=15, dy=5, alpha=None):
        s = QGraphicsDropShadowEffect(self)
        s.setBlurRadius(radius)
        s.setXOffset(0)
        s.setYOffset(dy)
        s.setColor(QColor(0, 0, 0, alpha or Theme.SHADOW_ALPHA))
        widget.setGraphicsEffect(s)

    def init_ui(self):
        w, h = Theme.WIN_SIZE

        if Theme.USE_FRAMELESS:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedSize(w, h)
        self.setWindowTitle("Vietnamese Typing")

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        margin = 14 if Theme.USE_FRAMELESS else 0
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(0)

        self.bg_frame = QFrame()
        self.bg_frame.setObjectName("MainFrame")
        if Theme.USE_FRAMELESS:
            self._shadow(self.bg_frame, radius=28, dy=12, alpha=Theme.SHADOW_ALPHA)

        layout = QVBoxLayout(self.bg_frame)
        layout.setContentsMargins(22, 18, 22, 24)
        layout.setSpacing(0)
        outer.addWidget(self.bg_frame)

        if Theme.SHOW_TRAFFIC:
            self._build_macos_titlebar(layout)
        elif not Theme.USE_FRAMELESS and OS == "Windows":
            self._build_windows_titlebar(layout)

        title_label = QLabel("Bộ Gõ Tiếng Việt")
        title_label.setObjectName("AppTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addSpacing(6 if Theme.SHOW_TRAFFIC else 4)
        layout.addWidget(title_label)

        hint = QLabel("Ctrl + Shift  ·  Bật / Tắt")
        hint.setObjectName("Hint")
        hint.setAlignment(Qt.AlignCenter)
        layout.addSpacing(4)
        layout.addWidget(hint)
        layout.addSpacing(20)

        seg_row = QHBoxLayout()
        seg_row.setSpacing(0)
        self.telex_rb = self._make_radio("Telex", True)
        self.vni_rb   = self._make_radio("VNI",   False)
        self.viqr_rb  = self._make_radio("VIQR",  False)
        self.telex_rb.toggled.connect(self.apply_settings)
        self.vni_rb.toggled.connect(self.apply_settings)
        self.viqr_rb.toggled.connect(self.apply_settings)
        seg_row.addStretch()
        seg_row.addWidget(self.telex_rb)
        seg_row.addSpacing(12)
        seg_row.addWidget(self.vni_rb)
        seg_row.addSpacing(12)
        seg_row.addWidget(self.viqr_rb)
        seg_row.addStretch()
        layout.addLayout(seg_row)
        layout.addSpacing(16)

        combo_row = QHBoxLayout()
        charset_lbl = QLabel("Bảng mã")
        charset_lbl.setObjectName("ControlLabel")
        self.charset_combo = QComboBox()
        self.charset_combo.setObjectName("CharsetCombo")
        self.charset_combo.addItems(["Unicode", "VNI Win", "TCVN3"])
        self.charset_combo.setCursor(Qt.PointingHandCursor)
        self.charset_combo.currentIndexChanged.connect(self.apply_settings)
        if Theme.USE_FRAMELESS:
            self._shadow(self.charset_combo, radius=8, dy=2, alpha=12)
        combo_row.addWidget(charset_lbl)
        combo_row.addStretch()
        combo_row.addWidget(self.charset_combo)
        layout.addLayout(combo_row)
        layout.addSpacing(16)

        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(8)
        
        self.autostart_cb = QCheckBox("Khởi động cùng Windows")
        self.show_startup_cb = QCheckBox("Hiển thị cửa sổ khi khởi động")
        self.autostart_cb.setCursor(Qt.PointingHandCursor)
        self.show_startup_cb.setCursor(Qt.PointingHandCursor)
        
        self.autostart_cb.setChecked(self.autostart)
        self.show_startup_cb.setChecked(self.show_startup)
        
        self.autostart_cb.toggled.connect(self.toggle_autostart)
        self.show_startup_cb.toggled.connect(self.toggle_show_startup)
        
        settings_layout.addWidget(self.autostart_cb)
        settings_layout.addWidget(self.show_startup_cb)
        layout.addLayout(settings_layout)
        
        layout.addStretch()

        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("ToggleBtn")
        self.toggle_btn.setMinimumHeight(Theme.BTN_HEIGHT)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_engine)
        if Theme.USE_FRAMELESS:
            self._shadow(self.toggle_btn, radius=14, dy=5, alpha=22)
        layout.addWidget(self.toggle_btn)

        self._apply_stylesheet()

    def toggle_autostart(self, checked):
        self.settings.setValue("autostart", checked)
        if OS == "Windows":
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
                if checked:
                    path = os.path.abspath(sys.argv[0])
                    if not path.lower().endswith('.exe'):
                        path = f'"{sys.executable}" "{path}"'
                    else:
                        path = f'"{path}"'
                    winreg.SetValueEx(key, "PaiVietnameseTyping", 0, winreg.REG_SZ, path)
                else:
                    try:
                        winreg.DeleteValue(key, "PaiVietnameseTyping")
                    except Exception:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass

    def toggle_show_startup(self, checked):
        self.settings.setValue("show_startup", checked)
        self.show_startup = checked

    def _build_macos_titlebar(self, layout):
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(7)

        for color in ["#FF5F56", "#FFBD2E", "#27C93F"]:
            dot = QPushButton()
            dot.setFixedSize(13, 13)
            dot.setStyleSheet(f"""
                QPushButton {{
                    background:{color}; border-radius:6px;
                    border: 0.5px solid rgba(0,0,0,0.12);
                }}
                QPushButton:hover {{ border: 0.5px solid rgba(0,0,0,0.25); }}
            """)
            dot.setCursor(Qt.PointingHandCursor)
            bar.addWidget(dot)

        self.btn_close    = bar.itemAt(0).widget()
        self.btn_minimize = bar.itemAt(1).widget()
        bar.itemAt(0).widget().clicked.connect(self.close)
        bar.itemAt(1).widget().clicked.connect(self.showMinimized)
        bar.addStretch()
        layout.addLayout(bar)
        layout.addSpacing(4)

    def _build_windows_titlebar(self, layout):
        pass

    def _make_radio(self, text, checked):
        rb = QRadioButton(text)
        rb.setChecked(checked)
        rb.setCursor(Qt.PointingHandCursor)
        return rb

    def _apply_stylesheet(self):
        is_mac = OS == "Darwin"
        self.setStyleSheet(f"""
            * {{
                font-family: {Theme.FONT_UI};
            }}

            #MainFrame {{
                background-color: {Theme.BG_GLASS};
                border-radius: {Theme.RADIUS_WINDOW}px;
                border: 1px solid {Theme.BORDER_LIGHT};
            }}

            #AppTitle {{
                font-family: {Theme.FONT_FAMILY};
                font-size: {"20px" if is_mac else "17px"};
                font-weight: {"600" if is_mac else "500"};
                color: {Theme.TEXT_PRIMARY};
                letter-spacing: {"0.3px" if is_mac else "0px"};
            }}

            #Hint {{
                font-size: 11px;
                color: {Theme.TEXT_TERTIARY};
                letter-spacing: {"0.5px" if is_mac else "0.2px"};
            }}

            #ControlLabel {{
                font-size: 13px;
                color: {Theme.TEXT_SECONDARY};
                font-weight: 500;
            }}

            QRadioButton {{
                color: {Theme.TEXT_PRIMARY};
                font-size: 14px;
                font-weight: {"500" if is_mac else "400"};
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: {"17px" if is_mac else "16px"};
                height: {"17px" if is_mac else "16px"};
                border-radius: {"9px" if is_mac else "8px"};
                border: {"1.5px" if is_mac else "1px"} solid {Theme.BORDER_MID};
                background: {Theme.BG_CONTROL};
            }}
            QRadioButton::indicator:checked {{
                background: {Theme.ACCENT};
                border: {"1.5px" if is_mac else "1px"} solid {Theme.ACCENT};
            }}
            QRadioButton::indicator:hover {{
                border-color: {Theme.ACCENT};
            }}

            QCheckBox {{
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
                font-weight: {"500" if is_mac else "400"};
                spacing: 8px;
            }}

            #CharsetCombo {{
                background: {Theme.BG_CONTROL};
                border: 1px solid {Theme.BORDER_MID};
                border-radius: {Theme.RADIUS_CTRL}px;
                padding: {"5px 14px" if is_mac else "4px 10px"};
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
                min-width: 110px;
            }}
            #CharsetCombo::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 20px;
                border: none;
            }}
            #CharsetCombo::down-arrow {{
                image: none;
                width: 0;
            }}
            #CharsetCombo:hover {{
                border-color: {Theme.ACCENT};
                background: rgba(255, 255, 255, 0.85);
            }}
            QComboBox QAbstractItemView {{
                background: rgba(255, 255, 255, 0.97);
                border: 1px solid {Theme.BORDER_MID};
                border-radius: {Theme.RADIUS_CTRL}px;
                selection-background-color: {Theme.ACCENT};
                selection-color: white;
                padding: 4px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
        """)

    def mousePressEvent(self, event):
        if Theme.USE_FRAMELESS and event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if Theme.USE_FRAMELESS and event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def init_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon = self._generate_icon("V", Theme.ACCENT)
        self.setWindowIcon(icon)
        self.tray.setIcon(icon)

        menu = QMenu()
        show_act = QAction("Mở cấu hình", self)
        show_act.triggered.connect(self.showNormal)
        quit_act = QAction("Thoát", self)
        quit_act.triggered.connect(self.quit_app)
        menu.addAction(show_act)
        menu.addSeparator()
        menu.addAction(quit_act)

        self.tray.setContextMenu(menu)
        self.tray.show()
        self.tray.activated.connect(self.on_tray_activated)

    def apply_settings(self):
        if self.telex_rb.isChecked():
            method = "TELEX"
        elif self.vni_rb.isChecked():
            method = "VNI"
        else:
            method = "VIQR"
            
        charset_text = self.charset_combo.currentText()
        if charset_text == "VNI Win":
            charset_val = "VNI_WIN"
        else:
            charset_val = charset_text.upper()

        try:
            from engine import VietnameseEngine
            self.engine = VietnameseEngine(input_method=method, charset=charset_val)
        except ImportError:
            pass

    def update_state(self):
        if self.is_running:
            self.toggle_btn.setText("● Đang bật  —  Tiếng Việt")
            self.toggle_btn.setStyleSheet(f"""
                #ToggleBtn {{
                    background: {Theme.ACCENT};
                    color: white;
                    border-radius: {Theme.RADIUS_BTN}px;
                    font-size: 13px;
                    font-weight: 600;
                    letter-spacing: 0.2px;
                    border: none;
                }}
                #ToggleBtn:hover {{ background: {Theme.ACCENT_HOVER}; }}
                #ToggleBtn:pressed {{ background: {Theme.ACCENT_HOVER}; }}
            """)
            icon = self._generate_icon("V", Theme.ACCENT)
            self.tray.setToolTip("Vietnamese  ·  Đang bật")
        else:
            self.toggle_btn.setText("○ Đang tắt  —  Tiếng Anh")
            self.toggle_btn.setStyleSheet(f"""
                #ToggleBtn {{
                    background: {Theme.BG_CONTROL};
                    color: {Theme.TEXT_SECONDARY};
                    border-radius: {Theme.RADIUS_BTN}px;
                    font-size: 13px;
                    font-weight: 600;
                    letter-spacing: 0.2px;
                    border: 1px solid {Theme.BORDER_MID};
                }}
                #ToggleBtn:hover {{
                    background: rgba(255,255,255,0.95);
                    color: {Theme.TEXT_PRIMARY};
                    border-color: {Theme.ACCENT};
                }}
            """)
            icon = self._generate_icon("E", Theme.TEXT_SECONDARY)
            self.tray.setToolTip("Vietnamese  ·  Đang tắt")

        self.tray.setIcon(icon)
        self.setWindowIcon(icon)

    def toggle_engine(self):
        self.is_running = not self.is_running
        self.update_state()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_engine()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Đã thu nhỏ",
            "Bộ gõ chạy ngầm.  Ctrl + Shift để bật/tắt.",
            QSystemTrayIcon.Information,
            2500
        )

    def quit_app(self):
        if hasattr(self, 'keyboard_listener'):
            self.keyboard_listener.stop()
        if hasattr(self, 'mouse_listener'):
            self.mouse_listener.stop()
        QApplication.quit()


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setOrganizationName("Đội ngũ phát triển Bộ Gõ Pai")
    app.setApplicationName("Bộ gõ Pai")

    if OS == "Windows":
        app.setStyle("windowsvista")
    elif OS == "Linux":
        app.setStyle("fusion")

    window = VietnameseTypingGUI()
    if window.show_startup:
        window.show()
    sys.exit(app.exec())