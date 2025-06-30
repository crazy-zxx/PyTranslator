import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import darkdetect
import qdarktheme
from PyQt5.QtCore import Qt, QPoint, QFile, QRectF, QObject, pyqtSignal, QThread
from PyQt5.QtGui import QGuiApplication, QIcon, QColor, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (QApplication, QMenu, QActionGroup, QAction,
                             QHBoxLayout, QDialog, QLineEdit, QMessageBox)
from PyQt5.QtXml import QDomDocument
from qframelesswindow import FramelessWindow, StandardTitleBar, TitleBarButton

from main_window import Ui_MainForm
from proxy_setting import Ui_ProxySettingForm
from web_translator import BaiduTranslator, YoudaoTranslator, AliTranslator, CaiyunTranslator, \
    TencentTranSmartTranslator, GoogleTranslator, DeepLTranslator


class TranslationSignals(QObject):
    """翻译信号类，用于在线程间传递结果"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

class InitTranslatorThread(QThread):
    """初始化翻译器的线程"""
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, window):
        super().__init__()
        self.window = window

    def run(self):
        try:
            self.window.init_translator()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

# 重写，解决 svg 图像的前景色 fill 问题
class SvgTitleBarButton(TitleBarButton):
    """ Title bar button using svg icon """

    def __init__(self, iconPath, parent=None):
        """
        Parameters
        ----------
        iconPath: str
            the path of icon

        parent: QWidget
            parent widget
        """
        super().__init__(parent)
        self._svgDom = QDomDocument()
        self.setIcon(iconPath)

    def setIcon(self, iconPath):
        """ set the icon of button

        Parameters
        ----------
        iconPath: str
            the path of icon
        """
        f = QFile(iconPath)
        f.open(QFile.ReadOnly)
        self._svgDom.setContent(f.readAll())
        f.close()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        color, bgColor = self._getColors()

        # draw background
        painter.setBrush(bgColor)
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

        # draw icon
        color = color.name()
        pathNodes = self._svgDom.elementsByTagName('path')
        for i in range(pathNodes.length()):
            element = pathNodes.at(i).toElement()
            # fill属性设置对象内部的颜色，stroke属性设置绘制对象的线条的颜色。
            # lement.setAttribute('stroke', color)  # 原始代码
            element.setAttribute('fill', color)

        renderer = QSvgRenderer(self._svgDom.toByteArray())
        renderer.render(painter, QRectF(self.rect()))

# 主窗口
class Window(FramelessWindow, Ui_MainForm):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        # 获取屏幕尺寸并居中显示窗口
        screen = QGuiApplication.primaryScreen().geometry()
        window_width, window_height = 600, 500
        x = (screen.width() - window_width) // 2
        y = (screen.height() - window_height) // 2
        self.setGeometry(x, y, window_width, window_height)

        # 使用标准标题栏，显示标题栏图标、文字
        self.setTitleBar(StandardTitleBar(self))
        self.setWindowIcon(QIcon("resources/logo.ico"))
        self.setWindowTitle("PyTranslator")

        # 标题栏按钮：网络代理、切换主题、窗口置顶
        self.themeButton = SvgTitleBarButton('resources/theme.svg', self)
        self.pinButton = SvgTitleBarButton('resources/pin.svg', self)
        self.proxyButton = SvgTitleBarButton('resources/proxy.svg', self)
        # 设置按钮提示
        self.proxyButton.setToolTip("网络代理")
        self.themeButton.setToolTip("切换主题")
        self.pinButton.setToolTip("窗口置顶")
        # 添加按钮
        layout = QHBoxLayout()
        self.titleBar.hBoxLayout.insertLayout(4, layout)
        layout.addWidget(self.proxyButton, 0, Qt.AlignRight)
        layout.addWidget(self.themeButton, 0, Qt.AlignRight)
        layout.addWidget(self.pinButton, 0, Qt.AlignRight)

        # 网络代理
        self.proxy_using = False
        self.proxy_protocol = 'http'
        self.proxy_address = '127.0.0.1'
        self.proxy_port = 7890
        self.proxy_username = ''
        self.proxy_password = ''

        # 初始化翻译器和线程池
        self.driver_path = os.path.abspath('./browser_driver/msedgedriver.exe')
        self.translator = None
        self.translation_signals = TranslationSignals()
        self.translation_signals.finished.connect(self.on_translation_finished)
        self.translation_signals.error.connect(self.on_translation_error)
        self.thread_pool = ThreadPoolExecutor(max_workers=1)

        # 翻译器初始化状态
        self.translator_initializing = False
        self.translator_ready = False
        # 在后台线程中初始化翻译器
        self.init_translator_in_background()

        # 初始化主题菜单
        self.theme = 'auto'
        self.init_theme_menu()
        self.set_theme(self.theme)
        # auto模式下的自动修改标题栏按钮主题监听
        self.t = threading.Thread(target=darkdetect.listener, args=(self.toggle_title_bar_buttons_theme,))
        self.t.daemon = True
        self.t.start()

        # 连接信号和槽
        self.themeButton.clicked.connect(self.show_theme_menu)
        self.pinButton.clicked.connect(self.toggle_window_stay_on_top)
        self.proxyButton.clicked.connect(self.show_proxy_settings)
        self.clear_source_pushButton.clicked.connect(self.clear_source)
        self.clear_newline_pushButton.clicked.connect(self.clear_newline)
        self.clear_all_newline_pushButton.clicked.connect(self.clear_newline_all)
        self.clear_blank_pushButton.clicked.connect(self.clear_blank)
        self.clear_all_blank_pushButton.clicked.connect(self.clear_blank_all)
        self.copy_source_pushButton.clicked.connect(self.copy_source)
        self.copy_target_pushButton.clicked.connect(self.copy_target)
        self.exchange_lang_pushButton.clicked.connect(self.exchange_language)
        self.translate_pushButton.clicked.connect(self.translate)
        self.translate_comboBox.currentIndexChanged.connect(self.init_translator)

    def init_theme_menu(self):
        # 创建主题菜单
        self.theme_menu = QMenu(self.themeButton)

        # 创建主题动作组
        self.theme_group = QActionGroup(self.theme_menu)
        self.theme_group.setExclusive(True)

        # 添加主题选项
        self.light_action = QAction("浅色模式", self.theme_group)
        self.light_action.setCheckable(True)
        self.light_action.triggered.connect(lambda: self.set_theme('light'))

        self.dark_action = QAction("深色模式", self.theme_group)
        self.dark_action.setCheckable(True)
        self.dark_action.triggered.connect(lambda: self.set_theme('dark'))

        self.auto_action = QAction("自动跟随系统", self.theme_group)
        self.auto_action.setCheckable(True)
        self.auto_action.setChecked(True)
        self.auto_action.triggered.connect(lambda: self.set_theme('auto'))

        # 将动作添加到菜单
        self.theme_menu.addAction(self.light_action)
        self.theme_menu.addAction(self.dark_action)
        self.theme_menu.addAction(self.auto_action)

    def show_theme_menu(self):
        # 显示菜单在按钮下方
        pos = self.themeButton.mapToGlobal(QPoint(0, self.themeButton.height()))
        self.theme_menu.exec_(pos)

    def set_theme(self, theme):
        qdarktheme.setup_theme(theme)
        # 更新当前选中的主题
        if theme == 'light':
            self.theme = 'light'
            self.light_action.setChecked(True)
        elif theme == 'dark':
            self.theme = 'dark'
            self.dark_action.setChecked(True)
        else:
            self.theme = 'auto'
            self.auto_action.setChecked(True)

        self.toggle_title_bar_buttons_theme(self.theme)

    def toggle_title_bar_buttons_theme(self, theme: str):
        # light、dark、auto 是手动选择的，Light、Dark 是监听系统的返回值
        if theme == 'light' or (theme.lower() == 'auto' and darkdetect.isLight()):
            color = QColor(0, 0, 0)
        elif theme == 'dark' or (theme.lower() == 'auto' and darkdetect.isDark()):
            color = QColor(255, 255, 255)
        elif self.theme == 'auto': # 在这里 self.theme 和 theme 可能不同，前者来源于用户设置，后者来自于监听系统的返回值
            if theme == 'Light':
                color = QColor(0, 0, 0)
            else:
                color = QColor(255, 255, 255)
        else:
            return

        self.toggle_buttons_theme(self.titleBar.minBtn, color)
        self.toggle_buttons_theme(self.titleBar.maxBtn, color)
        self.toggle_buttons_theme(self.titleBar.closeBtn, color)
        self.titleBar.closeBtn.setHoverBackgroundColor(QColor(232, 17, 35))
        self.titleBar.closeBtn.setPressedBackgroundColor(QColor(241, 112, 122))
        self.toggle_buttons_theme(self.proxyButton, color)
        self.toggle_buttons_theme(self.themeButton, color)
        self.toggle_buttons_theme(self.pinButton, color)

    def toggle_buttons_theme(self, btn: TitleBarButton, color: QColor):
        btn.setNormalColor(color)
        btn.setHoverColor(color)
        btn.setPressedColor(color)
        btn.setNormalBackgroundColor(color.fromRgb(color.red(), color.green(), color.blue(), 0))
        btn.setHoverBackgroundColor(color.fromRgb(color.red(), color.green(), color.blue(), 26))
        btn.setPressedBackgroundColor(color.fromRgb(color.red(), color.green(), color.blue(), 51))

    def toggle_window_stay_on_top(self):
        self.toggleStayOnTop()

        # 更新置顶按钮图标
        icon_path = 'resources/pin_active.svg' if self.windowFlags() & Qt.WindowStaysOnTopHint else 'resources/pin.svg'
        self.pinButton.setIcon(icon_path)

    def show_proxy_settings(self):
        """ 显示代理设置窗口 """
        self.proxy_dialog = QDialog(self)
        self.proxy_dialog.setModal(Qt.WindowModal)
        self.proxy_ui = Ui_ProxySettingForm()
        self.proxy_ui.setupUi(self.proxy_dialog)

        # 初始化代理设置
        self.proxy_ui.protocol_comboBox.setCurrentText(self.proxy_protocol)
        self.proxy_ui.address_comboBox.setCurrentText(self.proxy_address)
        self.proxy_ui.port_spinBox.setValue(self.proxy_port)
        self.proxy_ui.username_lineEdit.setText(self.proxy_username)
        self.proxy_ui.password_lineEdit.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.proxy_ui.password_lineEdit.setText(self.proxy_password)

        self.proxy_ui.start_proxy_pushButton.setEnabled(not self.proxy_using)
        self.proxy_ui.stop_proxy_pushButton.setEnabled(self.proxy_using)

        # 连接信号槽
        self.proxy_ui.start_proxy_pushButton.clicked.connect(self.save_proxy_settings)
        self.proxy_ui.stop_proxy_pushButton.clicked.connect(self.disable_proxy)

        self.proxy_dialog.show()

    def save_proxy_settings(self):
        """ 保存代理设置 """
        self.proxy_protocol = self.proxy_ui.protocol_comboBox.currentText()
        self.proxy_address = self.proxy_ui.address_comboBox.currentText()
        self.proxy_port = self.proxy_ui.port_spinBox.value()
        self.proxy_username = self.proxy_ui.username_lineEdit.text()
        self.proxy_password = self.proxy_ui.password_lineEdit.text()

        self.proxy_using = True
        self.proxy_ui.start_proxy_pushButton.setEnabled(not self.proxy_using)
        self.proxy_ui.stop_proxy_pushButton.setEnabled(self.proxy_using)
        self.proxy_dialog.close()

    def disable_proxy(self):
        """ 停用代理 """
        self.proxy_using = False
        self.proxy_ui.start_proxy_pushButton.setEnabled(not self.proxy_using)
        self.proxy_ui.stop_proxy_pushButton.setEnabled(self.proxy_using)
        self.proxy_dialog.close()

    def clear_source(self):
        self.source_plainTextEdit.setPlainText('')
        self.target_plainTextEdit.setPlainText('')

    def clear_newline(self):
        source_text = self.source_plainTextEdit.toPlainText()
        # 处理 Windows 换行符 \r\n
        processed_text = re.sub(r'(\r\n)+', r'\r\n', source_text)
        # 处理 Unix 换行符 \n
        processed_text = re.sub(r'([^\r])\n+', r'\1\n', processed_text)
        # 处理连续的 \r（Mac OS 9 及之前的系统）
        processed_text = re.sub(r'\r+', r'\r', processed_text)
        self.source_plainTextEdit.setPlainText(processed_text)

    def clear_newline_all(self):
        source_text = self.source_plainTextEdit.toPlainText()
        # 处理换行符 \r\n
        processed_text = re.sub(r'[\r\n]+', '', source_text)
        self.source_plainTextEdit.setPlainText(processed_text)

    # 中文直接没空格、英文单词之间只有一个空格，删除多余的空格
    def clear_blank(self):
        source_text = self.source_plainTextEdit.toPlainText()
        # 1. 删除中文文本中的多余空格
        processed_text = re.sub(
            r'([\u4e00-\u9fa5\u3000-\u303f\uff00-\uffef])([\t \u3000]+)([\u4e00-\u9fa5\u3000-\u303f\uff00-\uffef])', r'\1\3',
            source_text)

        # 2. 处理英文文本中的连续空格
        processed_text = re.sub(r'[\t \u3000]+', r' ', processed_text)

        # 3. 处理连字符与字母之间的空格
        # 删除字母与连字符之间的空格
        processed_text = re.sub(r'([a-zA-Z]*)[\t \u3000]*-[\t \u3000]*([a-zA-Z]*)', r'\1-\2', processed_text)

        # 4. 保留英文单词之间的空格
        processed_text = re.sub(r'(\b[a-zA-Z0-9]+\b)[\t \u3000]+(\b[a-zA-Z0-9]+\b)', r'\1 \2', processed_text)

        # 5. 处理中英文混合场景
        processed_text = re.sub(r'([\u4e00-\u9fa5])([\t \u3000]*)([a-zA-Z])', r'\1\3', processed_text)
        processed_text = re.sub(r'([a-zA-Z])([\t \u3000]*)([\u4e00-\u9fa5])', r'\1\3', processed_text)

        # 6. 清理剩余空格
        processed_text = processed_text.strip()
        self.source_plainTextEdit.setPlainText(processed_text)

    def clear_blank_all(self):
        source_text = self.source_plainTextEdit.toPlainText()
        processed_text = re.sub(r'[\t \u3000]+', r'', source_text)
        self.source_plainTextEdit.setPlainText(processed_text)

    def copy_source(self):
        source_text = self.source_plainTextEdit.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(source_text)

    def copy_target(self):
        target_text = self.target_plainTextEdit.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(target_text)

    def exchange_language(self):
        source_lang = self.source_lang_comboBox.currentText()
        target_lang = self.target_lang_comboBox.currentText()
        if source_lang != target_lang:
            self.source_lang_comboBox.setCurrentText(target_lang)
            self.target_lang_comboBox.setCurrentText(source_lang)

    def init_translator_in_background(self):
        """在后台线程中初始化翻译器"""
        if self.translator_initializing or self.translator_ready:
            return

        self.translator_initializing = True
        self.init_thread = InitTranslatorThread(self)
        self.init_thread.finished.connect(self.on_translator_ready)
        self.init_thread.error.connect(self.on_translator_error)
        self.init_thread.start()

    def init_translator(self):
        """初始化翻译器"""
        try:
            proxy_config = {
                "using": self.proxy_using,
                "protocol": self.proxy_protocol,
                "address": self.proxy_address,
                "port": self.proxy_port,
                "username": self.proxy_username,
                "password": self.proxy_password,
            }

            # 检查驱动文件是否存在
            if not os.path.exists(self.driver_path):
                raise FileNotFoundError(f"浏览器驱动文件不存在: {self.driver_path}")

            if self.translate_comboBox.currentText() == "百度翻译":
                self.translator = BaiduTranslator(
                    self.driver_path,
                    is_headless=True,
                    proxy_config=proxy_config
                )
            elif self.translate_comboBox.currentText() == "有道翻译":
                self.translator = YoudaoTranslator(
                    self.driver_path,
                    is_headless=True,
                    proxy_config=proxy_config
                )
            elif self.translate_comboBox.currentText() == "彩云翻译":
                self.translator = CaiyunTranslator(
                    self.driver_path,
                    is_headless=True,
                    proxy_config=proxy_config
                )
            elif self.translate_comboBox.currentText() == "阿里翻译":
                self.translator = AliTranslator(
                    self.driver_path,
                    is_headless=True,
                    proxy_config=proxy_config
                )
            elif self.translate_comboBox.currentText() == "腾讯翻译":
                self.translator = TencentTranSmartTranslator(
                    self.driver_path,
                    is_headless=True,
                    proxy_config=proxy_config
                )
            elif self.translate_comboBox.currentText() == "谷歌翻译":
                self.translator = GoogleTranslator(
                    self.driver_path,
                    is_headless=True,
                    proxy_config=proxy_config
                )
            elif self.translate_comboBox.currentText() == "DeepL翻译":
                self.translator = DeepLTranslator(
                    self.driver_path,
                    is_headless=True,
                    proxy_config=proxy_config
                )
            else:
                # 默认百度翻译
                self.translator = BaiduTranslator(
                    self.driver_path,
                    is_headless=True,
                    proxy_config=proxy_config
                )
        except Exception as e:
            print(f"翻译器初始化失败: {str(e)}")

    def on_translator_ready(self):
        """翻译器初始化完成后的回调"""
        self.translator_initializing = False
        self.translator_ready = True
        # 更新翻译按钮状态
        self.translate_pushButton.setEnabled(True)

    def on_translator_error(self, error_msg):
        """翻译器初始化失败的回调"""
        self.translator_initializing = False
        self.translator_ready = False
        QMessageBox.critical(self, "初始化失败", f"翻译引擎初始化失败:\n{error_msg}")
        # 更新翻译按钮状态
        self.translate_pushButton.setEnabled(False)

    def translate(self):
        if not self.translator:
            self.init_translator()

        text = self.source_plainTextEdit.toPlainText()
        if not text.strip():
            return

        # 在线程池中执行翻译任务
        self.thread_pool.submit(self._translate_task, text)

    def _translate_task(self, text):
        try:
            result = self.translator.translate(text)
            if result:
                self.translation_signals.finished.emit(result)
            else:
                self.translation_signals.error.emit("翻译失败，未获取到结果")
        except Exception as e:
            self.translation_signals.error.emit(f"翻译过程中发生错误: {str(e)}")

    def on_translation_finished(self, result):
        self.target_plainTextEdit.setPlainText(result)

    def on_translation_error(self, error_msg):
        self.target_plainTextEdit.setPlainText(f"翻译错误: {error_msg}")

if __name__ == '__main__':
    qdarktheme.enable_hi_dpi()

    app = QApplication(sys.argv)

    qdarktheme.setup_theme('auto')

    window = Window()
    window.show()

    sys.exit(app.exec_())