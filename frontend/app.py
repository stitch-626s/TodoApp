# PySide6 客户端主程序
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, Optional, Any
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit, QScrollArea, 
    QFileDialog, QFrame, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap, QFont, QMouseEvent
from loguru import logger
import requests

# 配置常量
API_URL = "http://127.0.0.1:8088"
NO_PROXY = {"http": "", "https": ""}
WINDOW_WIDTH = 360
WINDOW_HEIGHT = 650
TITLE_BAR_HEIGHT = 45

logger.add("msg.log", format="{time} - {level} - {message}")

class CustomTitleBar(QWidget):
    """
    自定义标题栏组件，包含拖动、关闭、最小化、置顶、折叠功能
    """
    
    # 定义自定义信号，用于通知主窗口进行折叠操作
    fold_requested = Signal(bool)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(TITLE_BAR_HEIGHT)
        self._parent_window = parent

        # 拖动偏移量
        self._drag_pos = QPoint()
        
        # 状态标志
        self.is_pinned = False
        self.is_folded = False
        
        # 布局初始化
        self._init_ui()

    def _init_ui(self) -> None:
        """
        初始化 UI 布局
        """

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 10, 0)
        layout.setSpacing(8)

        # 标题文本
        self.title_label = QLabel("Todo List")
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        
        # 功能按钮
        self.pin_btn = self._create_btn("︿", self._toggle_pin, "pin-btn")
        self.fold_btn = self._create_btn("▲", self._toggle_fold, "fold-btn")
        self.min_btn = self._create_btn("─", self._parent_window.showMinimized, "min-btn")
        self.close_btn = self._create_btn("✕", self._parent_window.close, "close-btn")

        layout.addWidget(self.title_label)
        layout.addStretch() # 将按钮推向右侧
        layout.addWidget(self.pin_btn)
        layout.addWidget(self.fold_btn)
        layout.addWidget(self.min_btn)
        layout.addWidget(self.close_btn)

    def _create_btn(self, text: str, slot: Any, obj_name: str) -> QPushButton:
        """
        辅助函数：快速创建顶部按钮
        """

        btn = QPushButton(text)
        btn.setFixedSize(30, 30)
        btn.setObjectName(obj_name)
        btn.setProperty("class", "icon-btn") # 用于 CSS 选择器
        btn.clicked.connect(slot)
        return btn

    def _toggle_pin(self) -> None:
        """
        切换置顶状态
        """

        self.is_pinned = not self.is_pinned
        # 设置动态属性以更新 QSS 样式
        self.pin_btn.setProperty("pinned", str(self.is_pinned).lower())
        # 刷新样式
        self.pin_btn.style().unpolish(self.pin_btn)
        self.pin_btn.style().polish(self.pin_btn)

        # 切换窗口 Flag
        flags = self._parent_window.windowFlags()
        if self.is_pinned:
            self._parent_window.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self._parent_window.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        
        self._parent_window.show() # 更改 Flag 后需要重新 Show

    def _toggle_fold(self) -> None:
        """
        切换折叠/展开状态
        """

        self.is_folded = not self.is_folded
        self.fold_btn.setText("▼" if self.is_folded else "▲")
        # 发送信号通知主窗口改变高度
        self.fold_requested.emit(self.is_folded)

    # 窗口拖动逻辑
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
        # 计算鼠标按下点相对于窗口左上角的偏移量，存到 self._drag_pos 中
            self._drag_pos = event.globalPosition().toPoint() - self._parent_window.frameGeometry().topLeft()
            event.accept()      
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton:
            # 使用 self._drag_pos 计算新位置并移动窗口
            self._parent_window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

class TodoItem(QFrame):
    """
    单条待办事项卡片组件
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        super().__init__()
        self.setProperty("class", "todo-card")
        self._init_ui(data)

    def _init_ui(self, data: Dict[str, Any]) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        # 解析时间格式
        create_at_str = data.get("created_at", "")
        if create_at_str:
            dt = datetime.fromisoformat(str(create_at_str))
            time_str = dt.strftime("%H:%M")
        else:
            time_str = "--:--"

        time_lbl = QLabel(time_str)
        time_lbl.setProperty("class", "time-label")

        header_layout = QHBoxLayout()
        header_layout.addWidget(time_lbl)
        header_layout.addStretch()

        self.is_completed = data.get("is_completed", False)
        self.toggle_btn = QPushButton("●" if self.is_completed else "○")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet("border: none; background: transparent; font-size: 16px; color: #555;")
        self.toggle_btn.clicked.connect(self._toggle_status)
        header_layout.addWidget(self.toggle_btn)

        self.todo_id = data.get("id")
        self.delete_btn = QPushButton("×")
        self.delete_btn.setFixedSize(30, 30)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setStyleSheet("border: none; background: transparent; font-size: 20px; color: #555;")
        self.delete_btn.clicked.connect(self._delete_todo)
        header_layout.addWidget(self.delete_btn)


        layout.addLayout(header_layout)
        
        content_text: str = data.get('content', '')
        if content_text:
            self.content_lbl = QLabel(content_text)
            self.content_lbl.setWordWrap(True)
            self._update_content_style()
            layout.addWidget(self.content_lbl)

        
        image_path: Optional[str] = data.get('image_path')
        if image_path:
            self._load_image(image_path, layout)

    def _load_image(self, image_path: str, layout: QVBoxLayout) -> None:
        """
        加载并显示图片
        """

        img_url = f"{API_URL}/{image_path}"
        try:
            response = requests.get(img_url, timeout=3, proxies=NO_PROXY)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                # 高质量缩放
                scaled_pixmap = pixmap.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation)
                img_lbl = QLabel()
                img_lbl.setPixmap(scaled_pixmap)
                layout.addWidget(img_lbl)
        except Exception as e:
            logger.error(f"Failed to load image: {e}")

    def _toggle_status(self) -> None:
        """
        切换待办事项完成状态
        """
        self.is_completed = not self.is_completed
        self.toggle_btn.setText("●" if self.is_completed else "○")
        
        if hasattr(self, 'content_lbl'):
            self._update_content_style()

    def _update_content_style(self) -> None:
        """
        根据待办事项是否完成状态，应用删除线
        """

        font = self.content_lbl.font()
        font.setStrikeOut(self.is_completed)
        self.content_lbl.setFont(font)

    def _delete_todo(self) -> None:
        """
        删除当前待办事项
        """        

        if hasattr(self, "todo_id") and self.todo_id is not None:
            try:
                requests.delete(f"{API_URL}/todos/{self.todo_id}", proxies=NO_PROXY)
            except Exception as e:
                logger.error(f"Failed to delete todo: {e}")

        self.deleteLater()

class TodoApp(QWidget):
    """
    应用程序主窗口
    """
    
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowIcon(QIcon("logo.ico")) 
        
        # 窗口属性设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # 记录正常高度用于恢复
        self.normal_height = WINDOW_HEIGHT

        self._init_ui()
        self._load_stylesheet()
        self.refresh_todos()


    def _init_ui(self) -> None:
        """
        初始化主窗口 UI
        """

        # 添加阴影效果，增加层次感
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(0, 0, 0, 60))

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(0)

        # 容器(用于承载所有内容)
        self.container = QWidget()
        self.container.setObjectName("Container")
        self.container.setGraphicsEffect(shadow)

        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)

        # 标题栏
        self.title_bar = CustomTitleBar(self)
        self.title_bar.fold_requested.connect(self.on_fold_window)
        self.container_layout.addWidget(self.title_bar)

        # 滚动区域(待办列表)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setStyleSheet("background: transparent;") 
        self.scroll_content.setStyleSheet("background: transparent;")

        self.scroll_area.setWidget(self.scroll_content)
        self.container_layout.addWidget(self.scroll_area)

        # 底部输入区
        self._setup_input_area()
        self.container_layout.addWidget(self.input_frame)
        self.main_layout.addWidget(self.container)

    def _setup_input_area(self) -> None:
        """
        底部输入区域
        """
        self.input_frame = QFrame()
        self.input_frame.setObjectName("InputArea")
        self.input_frame.setFixedHeight(150) 

        self.input_layout = QVBoxLayout(self.input_frame)

        # 文本输入框
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("添加待办事项……")
        self.text_input.setFixedHeight(40)

        # 按钮行，包含添加按钮、添加照片按钮
        btn_layout = QHBoxLayout()

        self.img_btn = QPushButton("📷")
        self.img_btn.setFixedSize(30, 30)
        self.img_btn.setProperty("class", "icon-btn")
        self.img_btn.clicked.connect(self.select_image)
        
        self.img_path_label = QLabel("")
        self.img_path_label.setStyleSheet("color:#999; font-size:10px;")

        self.add_btn = QPushButton("添加")
        self.add_btn.setObjectName("add-btn")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self.add_todo)

        btn_layout.addWidget(self.img_btn)
        btn_layout.addWidget(self.img_path_label)
        btn_layout.addStretch()
        btn_layout.addWidget(self.add_btn)

        self.input_layout.addWidget(self.text_input)
        self.input_layout.addLayout(btn_layout)

        # self.main_layout.addWidget(self.input_frame)
        
        self.selected_image_path = None

    def _load_stylesheet(self) -> None:
        """加载外部 QSS 文件 (使用绝对路径修复白屏问题)"""
        try:
            if getattr(sys, 'frozen', False):
                base_dir = getattr(sys, '_MEIPASS')
            else:
                # 获取当前 app.py 所在的文件夹路径
                base_dir = os.path.dirname(os.path.abspath(__file__))

            # 拼接出 styles.qss 的完整路径
            qss_path = os.path.join(base_dir, "styles.qss")
            
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
            print(f"成功加载样式表: {qss_path}") # 调试信息
        except FileNotFoundError:
            # 如果找不到样式表，给一个保底背景色，防止白屏
            self.setStyleSheet("QWidget { background-color: #f0f0f0; color: black; }")

    def on_fold_window(self, is_folded: bool) -> None:
        """
        窗口折叠逻辑
        """

        if is_folded:
            # 记录当前高度
            self.normal_height = self.height()
            # 计算折叠后的高度：标题栏 + 边距
            collapsed_height = TITLE_BAR_HEIGHT + 20
            self.setFixedHeight(collapsed_height)
            self.scroll_area.hide()
            self.input_frame.hide()
        else:
            self.setFixedHeight(self.normal_height)
            self.scroll_area.show()
            self.input_frame.show()

    def select_image(self) -> None:
        """
        选择图片
        """

        file_name, _ = QFileDialog().getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_name:
            self.selected_image_path = file_name
            self.img_path_label.setText(os.path.basename(file_name))
    
    def add_todo(self) -> None:
        """
        发送网络请求添加待办事项
        """

        content = self.text_input.toPlainText().strip()
        if not content and not self.selected_image_path:
            return
        
        data = {"content": content}
        files = None

        if self.selected_image_path:
            files = {"file": open(self.selected_image_path, "rb")}

        try:
            requests.post(f"{API_URL}/todos", data=data, files=files, proxies=NO_PROXY)

            self.text_input.clear()
            self.selected_image_path = None
            self.img_path_label.setText("")
            if files:
                files["file"].close()
            
            self.refresh_todos()
        except requests.RequestException as e:
            logger.error(f"Network error:{e}")
     
    def refresh_todos(self) -> None:
        """
        获取并刷新代办列表
        """

        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        try:
            response = requests.get(f"{API_URL}/todos", timeout=3, proxies=NO_PROXY)
            if response.status_code == 200:
                todos = response.json()
                
                current_date_str = None
                
                for todo in todos:
                    # 按照日期分块逻辑
                    dt = datetime.fromisoformat(todo["created_at"])
                    date_str = f"{dt.year}年{dt.month:02d}月{dt.day:02d}日"

                    if date_str != current_date_str:
                        header = QLabel(date_str)
                        header.setProperty("class", "date-header")
                        self.scroll_layout.addWidget(header)
                        current_date_str = date_str

                    item_widget = TodoItem(todo)
                    self.scroll_layout.addWidget(item_widget)
        except requests.RequestException as e:
            logger.error(f"Fetch error: {e}")
    

if __name__ == "__main__":
    app = QApplication(sys.argv)

    #启动客户端程序时，拉起服务端
    server_process = None

    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    server_exe_path = os.path.join(base_dir, "TodoServer.exe")

    if not os.path.exists(server_exe_path):
        parent_dir = os.path.dirname(base_dir)
        server_exe_path = os.path.join(parent_dir, "TodoServer.exe")

    if os.path.exists(server_exe_path):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        server_process = subprocess.Popen([server_exe_path], startupinfo=startupinfo)
        
        time.sleep(1)
    else:
        print("未找到服务端程序 TodoServer.exe，将以无后端模式尝试启动。")
        logger.error("Found Process error：未找到服务端程序 TodoServer.exe，将以无后端模式尝试启动")

    def cleanup() -> None:
        """
        退出事件：当 GUI 客户端关闭时，连带把后台的服务端也杀掉
        """
        
        if server_process:
            server_process.terminate()

    app.aboutToQuit.connect(cleanup)

    window = TodoApp()
    window.show()
    sys.exit(app.exec())