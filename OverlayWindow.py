import sys
import os
import ctypes
import math
import time
from threading import Thread, Event

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu, QAction,
    QWidget, QVBoxLayout
)
from PyQt5.QtCore import (
    Qt, QTimer, QPoint, QPointF, QRect, QEvent, pyqtSignal
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QPolygon, QCursor, QIcon, QScreen
)
import win32gui
import win32con
import win32api
import pywintypes


class OverlayWindow(QWidget):
    """透明叠加窗口，显示固定地平线和跟随鼠标的粒子"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |  # 置顶
            Qt.FramelessWindowHint |  # 无边框
            Qt.Tool |                # 工具窗口，不显示在任务栏
            Qt.X11BypassWindowManagerHint  # 绕过窗口管理器
        )
        
        # 设置透明属性
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # 鼠标穿透
        self.setAttribute(Qt.WA_NoSystemBackground)
        
        # 设置初始几何形状为全屏
        self.update_geometry()
        
        # 粒子设置
        self.particles = []
        self.init_particles()
        
        # 鼠标位置
        self.mouse_pos = QPoint(0, 0)
        self.track_mouse = True
        
        # 定时器用于更新界面
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_overlay)
        self.update_timer.setInterval(16)  # ~60fps
        
        # 鼠标跟踪定时器
        self.mouse_timer = QTimer(self)
        self.mouse_timer.timeout.connect(self.update_mouse_position)
        self.mouse_timer.setInterval(16)
    
    def update_geometry(self):
        """更新窗口几何形状为全屏"""
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        else:
            # 备用方案
            desktop = QApplication.desktop()
            self.setGeometry(desktop.screenGeometry())
    
    def init_particles(self):
        """初始化粒子"""
        center = self.rect().center()
        # 创建多个环形分布的粒子
        for i in range(12):
            angle = i * (2 * math.pi / 12)
            radius = min(self.width(), self.height()) * 0.15
            x = center.x() + math.cos(angle) * radius
            y = center.y() + math.sin(angle) * radius
            self.particles.append({
                'pos': QPointF(x, y),
                'target_pos': QPointF(x, y),
                'size': 4 + i % 3,
                'color': QColor(255, 255, 255, 180 - i * 10),
                'angle': angle,
                'radius': radius
            })
    
    def start_overlay(self):
        """启动叠加层"""
        self.show()
        self.update_timer.start()
        self.mouse_timer.start()
    
    def stop_overlay(self):
        """停止叠加层"""
        self.update_timer.stop()
        self.mouse_timer.stop()
        self.hide()
    
    def update_mouse_position(self):
        """更新鼠标位置"""
        if not self.track_mouse:
            return
            
        try:
            # 获取全局鼠标位置
            cursor_pos = win32gui.GetCursorPos()
            self.mouse_pos = QPoint(cursor_pos[0], cursor_pos[1])
            self.update_particles()
        except Exception as e:
            print(f"Error updating mouse position: {e}")
    
    def update_particles(self):
        """更新粒子位置，使它们围绕鼠标位置"""
        if not self.isVisible():
            return
            
        center = self.rect().center()
        screen_center = center
        
        # 计算鼠标相对于屏幕中心的偏移
        mouse_offset = self.mouse_pos - screen_center
        
        # 粒子跟随鼠标但有一定衰减，创建"视觉锚点"效果
        for p in self.particles:
            # 计算目标位置：基于鼠标偏移但有衰减
            offset_factor = 0.2  # 衰减系数
            target_x = center.x() + math.cos(p['angle']) * p['radius'] + mouse_offset.x() * offset_factor
            target_y = center.y() + math.sin(p['angle']) * p['radius'] + mouse_offset.y() * offset_factor
            p['target_pos'] = QPointF(target_x, target_y)
            
            # 平滑移动到目标位置
            p['pos'] = p['pos'] * 0.9 + p['target_pos'] * 0.1
    
    def update_overlay(self):
        """强制更新界面"""
        self.update()
    
    def paintEvent(self, event):
        """绘制叠加层内容"""
        if not self.isVisible():
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制固定地平线
        self.draw_horizon_line(painter)
        
        # 绘制粒子
        self.draw_particles(painter)
    
    def draw_horizon_line(self, painter):
        """绘制固定地平线"""
        rect = self.rect()
        center_y = rect.center().y()
        
        # 地平线样式
        line_width = 2
        line_length = min(rect.width() * 0.7, 1000)
        line_x_start = rect.center().x() - line_length // 2
        line_x_end = rect.center().x() + line_length // 2
        
        # 绘制主线条
        pen = QPen(QColor(64, 160, 255, 180), line_width, Qt.SolidLine)
        painter.setPen(pen)
        painter.drawLine(line_x_start, center_y, line_x_end, center_y)
        
        # 绘制短垂直线作为参考
        marker_pen = QPen(QColor(64, 160, 255, 120), 1, Qt.SolidLine)
        painter.setPen(marker_pen)
        for i in range(-3, 4):
            if i == 0:
                continue  # 跳过中心点
            x = rect.center().x() + i * 50
            if line_x_start <= x <= line_x_end:
                painter.drawLine(x, center_y - 5, x, center_y + 5)
    
    def draw_particles(self, painter):
        """绘制跟随鼠标的粒子"""
        for p in self.particles:
            painter.setPen(Qt.NoPen)
            painter.setBrush(p['color'])
            painter.drawEllipse(p['pos'], p['size'], p['size'])
    
    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        # 尝试设置窗口为穿透模式，并确保置顶
        hwnd = self.winId().__int__()
        try:
            # 设置窗口样式，确保可穿透且置顶
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            style |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TOPMOST
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
            )
        except Exception as e:
            print(f"Error setting window properties: {e}")


class AntiMotionSicknessApp(QApplication):
    """主应用程序类"""
    
    def __init__(self, argv):
        super().__init__(argv)
        
        # 检查并获取管理员权限
        self.ensure_admin_rights()
        
        # 创建透明叠加窗口
        self.overlay = OverlayWindow()
        
        # 创建系统托盘
        self.tray_icon = QSystemTrayIcon(self)
        self.create_tray_icon()
        
        # 状态变量
        self.overlay_active = False
        
        # 处理退出
        self.aboutToQuit.connect(self.cleanup)
        
        # 显示托盘图标
        self.tray_icon.show()
        
        # 初始隐藏主窗口
        self.setQuitOnLastWindowClosed(False)
    
    def ensure_admin_rights(self):
        """确保程序以管理员权限运行"""
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False
            
        if not is_admin:
            # 重新以管理员权限启动
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit(0)
    
    def create_tray_icon(self):
        """创建系统托盘图标和菜单"""
        # 创建一个简单的图标
        icon = self.create_tray_icon_pixmap()
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Anti 3D Motion Sickness\nClick to toggle overlay")
        
        # 创建菜单
        tray_menu = QMenu()
        
        # 创建动作
        self.toggle_action = QAction("Enable Overlay", tray_menu)
        self.toggle_action.triggered.connect(self.toggle_overlay)
        
        exit_action = QAction("Exit", tray_menu)
        exit_action.triggered.connect(self.quit_application)
        
        # 添加动作到菜单
        tray_menu.addAction(self.toggle_action)
        tray_menu.addAction(exit_action)
        
        # 设置托盘菜单
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
    
    def create_tray_icon_pixmap(self):
        """创建一个简单的托盘图标"""
        from PyQt5.QtGui import QPixmap, QPainter, QBrush, QPen
        
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制一个简单的图标
        painter.setBrush(QBrush(QColor(64, 160, 255)))
        painter.setPen(QPen(QColor(30, 120, 220), 2))
        
        # 绘制一个简单的地平线图标
        painter.drawRect(4, 14, 24, 4)  # 水平线
        painter.drawEllipse(14, 8, 4, 4)  # 中心点
        
        painter.end()
        return QIcon(pixmap)
    
    def tray_icon_activated(self, reason):
        """处理托盘图标激活事件"""
        if reason == QSystemTrayIcon.Trigger:  # 左键单击
            self.toggle_overlay()
    
    def toggle_overlay(self):
        """切换叠加层状态"""
        self.overlay_active = not self.overlay_active
        
        if self.overlay_active:
            self.overlay.start_overlay()
            self.toggle_action.setText("Disable Overlay")
            self.tray_icon.setToolTip("Anti 3D Motion Sickness\nOverlay: ON")
        else:
            self.overlay.stop_overlay()
            self.toggle_action.setText("Enable Overlay")
            self.tray_icon.setToolTip("Anti 3D Motion Sickness\nOverlay: OFF")
    
    def quit_application(self):
        """退出应用程序"""
        self.overlay.stop_overlay()
        self.tray_icon.hide()
        self.quit()
    
    def cleanup(self):
        """清理资源"""
        self.overlay.stop_overlay()
        self.overlay.deleteLater()
        self.tray_icon.hide()
        self.tray_icon.deleteLater()


if __name__ == "__main__":
    # 创建应用程序
    app = AntiMotionSicknessApp(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 运行事件循环
    sys.exit(app.exec_())