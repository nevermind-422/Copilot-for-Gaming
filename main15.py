import cv2
import numpy as np
import mediapipe as mp
import win32api
import win32con
import win32gui
import win32ui
import time
from collections import deque
from ctypes import windll, c_int, c_uint, c_char_p, c_void_p, c_float, c_bool, POINTER, Structure, c_long, byref
import math
import pyautogui
import keyboard
import os
from datetime import datetime
import sys
import logging
from absl import logging as absl_logging
import random
from threading import Thread

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
absl_logging.use_absl_handler()
absl_logging.set_verbosity(absl_logging.INFO)

# Инициализация MediaPipe
print("Initializing MediaPipe...")
mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Настройки для MediaPipe
holistic = mp_holistic.Holistic(
    static_image_mode=False,  # Режим видео
    model_complexity=0,       # Минимальная сложность для максимальной производительности
    enable_segmentation=False,  # Отключаем сегментацию для производительности
    smooth_landmarks=False,    # Отключаем сглаживание для производительности
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    refine_face_landmarks=False  # Отключаем для производительности
)

print("MediaPipe initialized successfully")

# Константы для эмуляции мыши
MOUSEEVENTF_MOVE = 0x0001
user32 = windll.user32

class PerformanceCounter:
    def __init__(self, name):
        self.name = name
        self.total_time = 0.0
        self.count = 0
        self.last_time = 0.0
        self.current_time = 0.0
        self.avg_time = 0.0
        self.last_reset_time = time.time()
        
    def start(self):
        self.last_time = time.time()
        
    def stop(self):
        try:
            self.current_time = time.time() - self.last_time
            self.total_time += self.current_time
            self.count += 1
            
            # Обновляем среднее каждую секунду
            current_time = time.time()
            if current_time - self.last_reset_time >= 1.0:
                if self.count > 0:
                    self.avg_time = self.total_time / self.count
                self.total_time = 0.0
                self.count = 0
                self.last_reset_time = current_time
        except Exception as e:
            print(f"Error in PerformanceCounter.stop for {self.name}: {str(e)}")

class PerformanceMonitor:
    def __init__(self):
        self.counters = {
            'capture': PerformanceCounter('Screen Capture'),
            'process': PerformanceCounter('Frame Processing'),
            'detection': PerformanceCounter('Object Detection'),
            'drawing': PerformanceCounter('Drawing'),
            'overlay': PerformanceCounter('Overlay Update'),
            'cursor': PerformanceCounter('Cursor Control')
        }
        self.last_reset = time.time()
        self.reset_interval = 1.0
        
    def start(self, counter_name):
        if counter_name in self.counters:
            self.counters[counter_name].start()
        
    def stop(self, counter_name):
        if counter_name in self.counters:
            self.counters[counter_name].stop()
        
    def get_stats(self):
        current_time = time.time()
        if current_time - self.last_reset >= self.reset_interval:
            self.last_reset = current_time
        return {name: counter for name, counter in self.counters.items()}

class OverlayWindow:
    def __init__(self):
        # Создаем окно
        self.hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST,
            "Static",
            "Overlay",
            win32con.WS_POPUP | win32con.WS_VISIBLE,
            0, 0,
            win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN),
            win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN),
            0, 0, 0, None
        )
        
        # Устанавливаем прозрачность окна
        win32gui.SetLayeredWindowAttributes(
            self.hwnd,
            0,
            128,  # 50% прозрачности
            win32con.LWA_ALPHA
        )
        
        # Создаем DC и битмап
        self.hdc = win32gui.GetDC(self.hwnd)
        self.mfc_dc = win32ui.CreateDCFromHandle(self.hdc)
        self.save_dc = self.mfc_dc.CreateCompatibleDC()
        
        # Создаем битмап
        self.bitmap = win32ui.CreateBitmap()
        self.bitmap.CreateCompatibleBitmap(self.mfc_dc, 1920, 1080)
        self.save_dc.SelectObject(self.bitmap)
        
        # Создаем шрифт
        self.font = win32ui.CreateFont({
            'name': 'Consolas',
            'height': 20,
            'weight': win32con.FW_NORMAL,
            'charset': win32con.ANSI_CHARSET
        })
        
        # Цвета и размеры для прицела
        self.crosshair_color = 0x00FF00  # Зеленый для абсолютного режима
        self.crosshair_relative_color = 0x00FFFF  # Голубой для относительного режима
        self.crosshair_size = 15  # Уменьшенный размер прицела
        self.crosshair_thickness = 2
        self.crosshair_dot_radius = 3  # Радиус точек на концах линий
        
        self.last_update_time = time.time()
        self.update_interval = 1.0 / 60.0  # 60 FPS
        
        # Флаг для отрисовки скелета
        self.draw_skeleton_enabled = False
        
        # Цвета для индикации состояния
        self.following_color = 0x00FF00  # Зеленый для активного состояния
        self.following_disabled_color = 0xFF0000  # Красный для неактивного состояния
        
        # Добавляем новые параметры для отрисовки движения
        self.last_cursor_pos = None
        self.last_target_pos = None
        self.movement_history = deque(maxlen=10)

    def draw_skeleton(self, landmarks, color):
        """Рисует скелет с помощью линий и точек"""
        if not landmarks or not self.draw_skeleton_enabled:
            return
        pen = win32ui.CreatePen(win32con.PS_SOLID, 2, color[2] << 16 | color[1] << 8 | color[0])
        self.save_dc.SelectObject(pen)
        for connection in mp_holistic.POSE_CONNECTIONS:
            start_point = landmarks.landmark[connection[0]]
            end_point = landmarks.landmark[connection[1]]
            start_x = int(start_point.x * 1920)
            start_y = int(start_point.y * 1080)
            end_x = int(end_point.x * 1920)
            end_y = int(end_point.y * 1080)
            self.save_dc.MoveTo((start_x, start_y))
            self.save_dc.LineTo((end_x, end_y))
            for point_x, point_y in [(start_x, start_y), (end_x, end_y)]:
                outer_brush = win32ui.CreateBrush(win32con.BS_SOLID, color[2] << 16 | color[1] << 8 | color[0], 0)
                self.save_dc.SelectObject(outer_brush)
                self.save_dc.Ellipse((point_x - 5, point_y - 5, point_x + 5, point_y + 5))
                white_brush = win32ui.CreateBrush(win32con.BS_SOLID, 0xFFFFFF, 0)
                self.save_dc.SelectObject(white_brush)
                self.save_dc.Ellipse((point_x - 3, point_y - 3, point_x + 3, point_y + 3))
                yellow_brush = win32ui.CreateBrush(win32con.BS_SOLID, 0x00FFFF, 0)
                self.save_dc.SelectObject(yellow_brush)
                self.save_dc.Ellipse((point_x - 1, point_y - 1, point_x + 1, point_y + 1))

    def draw_movement_vector(self, cursor_pos, target_pos, speed, direction):
        """Рисует вектор движения с градиентом скорости"""
        try:
            if not cursor_pos or not target_pos or speed <= 0:
                return
                
            # Создаем перо для рисования
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0x0000FF)  # Красный цвет, толщина 2
            old_pen = self.save_dc.SelectObject(pen)
            
            try:
                # Рисуем линию движения
                start_x, start_y = cursor_pos
                end_x, end_y = target_pos
                
                # Нормализуем вектор движения
                dx = end_x - start_x
                dy = end_y - start_y
                length = (dx * dx + dy * dy) ** 0.5
                
                if length > 0:
                    dx /= length
                    dy /= length
                    
                    # Рисуем стрелку
                    arrow_length = min(length, 50)  # Ограничиваем длину стрелки
                    end_x = start_x + dx * arrow_length
                    end_y = start_y + dy * arrow_length
                    
                    # Рисуем основную линию
                    self.save_dc.MoveTo((int(start_x), int(start_y)))
                    self.save_dc.LineTo((int(end_x), int(end_y)))
                    
                    # Рисуем наконечник стрелки
                    arrow_size = 10
                    angle = math.atan2(dy, dx)
                    arrow_angle = math.pi / 6  # 30 градусов
                    
                    # Первая часть наконечника
                    ax = end_x - arrow_size * math.cos(angle + arrow_angle)
                    ay = end_y - arrow_size * math.sin(angle + arrow_angle)
                    self.save_dc.MoveTo((int(end_x), int(end_y)))
                    self.save_dc.LineTo((int(ax), int(ay)))
                    
                    # Вторая часть наконечника
                    ax = end_x - arrow_size * math.cos(angle - arrow_angle)
                    ay = end_y - arrow_size * math.sin(angle - arrow_angle)
                    self.save_dc.MoveTo((int(end_x), int(end_y)))
                    self.save_dc.LineTo((int(ax), int(ay)))
            finally:
                # Восстанавливаем старое перо
                self.save_dc.SelectObject(old_pen)
                try:
                    pen.DeleteObject()
                except:
                    pass  # Игнорируем ошибку удаления пера
                
        except Exception as e:
            print(f"Error in draw_movement_vector: {str(e)}")

    def draw_bounding_box(self, box, color):
        if not box:
            return
        min_x, min_y, max_x, max_y = box
        # Только перо, без кисти (заливки)
        pen = win32ui.CreatePen(win32con.PS_SOLID, 2, color[2] << 16 | color[1] << 8 | color[0])
        self.save_dc.SelectObject(pen)
        # Убираем заливку: не выбираем кисть вообще
        self.save_dc.Rectangle((min_x, min_y, max_x, max_y))
        # Центр
        center_x = (min_x + max_x) // 2
        center_y = (min_y + max_y) // 2
        yellow_pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0x00FFFF)
        self.save_dc.SelectObject(yellow_pen)
        cross = 10
        self.save_dc.MoveTo((center_x - cross, center_y)); self.save_dc.LineTo((center_x + cross, center_y))
        self.save_dc.MoveTo((center_x, center_y - cross)); self.save_dc.LineTo((center_x, center_y + cross))
        self.save_dc.Ellipse((center_x - cross, center_y - cross, center_x + cross, center_y + cross))

    def draw_landmark_labels(self, landmarks):
        if not landmarks:
            return
        for idx, landmark in enumerate(landmarks.landmark):
            x = int(landmark.x * 1920)
            y = int(landmark.y * 1080)
            if hasattr(DrawingUtils, 'BODY_PARTS') and idx in DrawingUtils.BODY_PARTS:
                label = DrawingUtils.BODY_PARTS[idx]
                self.save_dc.SetTextColor(0xFFFFFF)
                self.save_dc.TextOut(x + 5, y - 15, label)

    def draw_debug_info(self, cursor_pos, target_pos, distance, speed, direction, fps):
        # Аналогично OpenCV-версии, но через self.save_dc
        info = [
            f"FPS: {fps:.1f}",
            f"Distance: {distance:.2f}m" if distance is not None else "Distance: ---",
            f"Speed: {speed:.2f} m/s" if speed is not None else "Speed: ---",
            f"Direction: {math.degrees(direction):.1f}°" if direction is not None and speed >= 0.1 else "Direction: ---",
            f"Cursor: {cursor_pos}" if cursor_pos else "Cursor: ---",
            f"Target: {target_pos}" if target_pos else "Target: ---"
        ]
        self.save_dc.FillSolidRect((20, 20, 350, 200), 0x202020)
        self.save_dc.SetTextColor(0x00FF00)
        for i, line in enumerate(info):
            self.save_dc.TextOut(30, 30 + i * 25, line)

    def draw_crosshair(self, cursor_controller):
        """Рисует прицел в зависимости от режима"""
        try:
            # Получаем цвет прицела в зависимости от режима
            color = self.crosshair_relative_color if cursor_controller.relative_mode else self.crosshair_color
            
            # Рисуем прицел в центре экрана
            center_x = cursor_controller.center_x
            center_y = cursor_controller.center_y
            
            # Создаем перо для линий прицела
            pen = win32ui.CreatePen(win32con.PS_SOLID, self.crosshair_thickness, color)
            self.save_dc.SelectObject(pen)
            
            # Рисуем горизонтальную линию
            self.save_dc.MoveTo((center_x - self.crosshair_size, center_y))
            self.save_dc.LineTo((center_x + self.crosshair_size, center_y))
            
            # Рисуем вертикальную линию
            self.save_dc.MoveTo((center_x, center_y - self.crosshair_size))
            self.save_dc.LineTo((center_x, center_y + self.crosshair_size))
            
            # Рисуем круги для относительного режима
            if cursor_controller.relative_mode:
                # Внешний круг
                self.save_dc.Ellipse((
                    center_x - self.crosshair_size * 2,
                    center_y - self.crosshair_size * 2,
                    center_x + self.crosshair_size * 2,
                    center_y + self.crosshair_size * 2
                ))
                # Внутренний круг
                self.save_dc.Ellipse((
                    center_x - self.crosshair_size,
                    center_y - self.crosshair_size,
                    center_x + self.crosshair_size,
                    center_y + self.crosshair_size
                ))
                
                # Добавляем точки на концах линий
                dot_size = 4
                self.save_dc.Ellipse((
                    center_x - self.crosshair_size - dot_size,
                    center_y - dot_size,
                    center_x - self.crosshair_size + dot_size,
                    center_y + dot_size
                ))
                self.save_dc.Ellipse((
                    center_x + self.crosshair_size - dot_size,
                    center_y - dot_size,
                    center_x + self.crosshair_size + dot_size,
                    center_y + dot_size
                ))
                self.save_dc.Ellipse((
                    center_x - dot_size,
                    center_y - self.crosshair_size - dot_size,
                    center_x + dot_size,
                    center_y - self.crosshair_size + dot_size
                ))
                self.save_dc.Ellipse((
                    center_x - dot_size,
                    center_y + self.crosshair_size - dot_size,
                    center_x + dot_size,
                    center_y + self.crosshair_size + dot_size
                ))
            
        except Exception as e:
            print(f"Error drawing crosshair: {str(e)}")

    def draw_following_status(self, cursor_controller):
        """Рисует индикатор состояния следования в виде кнопки"""
        try:
            # Позиция и размеры кнопки
            button_width = 120
            button_height = 40
            button_x = 570  # 100 + 450 (ширина блока таймеров) + 20 (отступ)
            button_y = 60   # Выравниваем по верхнему краю блока таймеров
            
            # Цвета
            bg_color = 0x00FF00 if cursor_controller.following_enabled else 0xFF0000  # Зеленый или красный
            text_color = 0xFFFFFF  # Белый текст
            
            # Рисуем фон кнопки
            brush = win32ui.CreateBrush(win32con.BS_SOLID, bg_color, 0)
            self.save_dc.SelectObject(brush)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем рамку кнопки
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0xFFFFFF)  # Белая рамка
            self.save_dc.SelectObject(pen)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем текст
            self.save_dc.SetTextColor(text_color)
            status = "FOLLOWING: ON" if cursor_controller.following_enabled else "FOLLOWING: OFF"
            
            # Центрируем текст
            text_width = self.save_dc.GetTextExtent(status)[0]
            text_x = button_x + (button_width - text_width) // 2
            text_y = button_y + (button_height - 20) // 2
            
            self.save_dc.TextOut(text_x, text_y, status)
            
            # Добавляем подсказку с хоткеем
            hotkey_text = "+ :"
            hotkey_width = self.save_dc.GetTextExtent(hotkey_text)[0]
            hotkey_x = button_x - hotkey_width - 5  # 5 пикселей отступа от кнопки
            self.save_dc.SetTextColor(0x00FF00)  # Зеленый цвет для подсказки
            self.save_dc.TextOut(hotkey_x, button_y + (button_height - 20) // 2, hotkey_text)
            
            # Очищаем ресурсы
            try:
                brush.DeleteObject()
            except:
                pass
            
        except Exception as e:
            print(f"Error drawing following status: {str(e)}")

    def draw_mode_status(self, cursor_controller):
        """Рисует индикатор режима мыши в виде кнопки"""
        try:
            # Позиция и размеры кнопки
            button_width = 120
            button_height = 40
            button_x = 570  # Та же x-координата, что и у кнопки following
            button_y = 110  # Располагаем под кнопкой following
            
            # Цвета
            bg_color = 0x00FFFF if cursor_controller.relative_mode else 0x00FF00  # Голубой для относительного, зеленый для абсолютного
            text_color = 0xFFFFFF  # Белый текст
            
            # Рисуем фон кнопки
            brush = win32ui.CreateBrush(win32con.BS_SOLID, bg_color, 0)
            self.save_dc.SelectObject(brush)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем рамку кнопки
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0xFFFFFF)  # Белая рамка
            self.save_dc.SelectObject(pen)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем текст
            self.save_dc.SetTextColor(text_color)
            status = "MODE: RELATIVE" if cursor_controller.relative_mode else "MODE: ABSOLUTE"
            
            # Центрируем текст
            text_width = self.save_dc.GetTextExtent(status)[0]
            text_x = button_x + (button_width - text_width) // 2
            text_y = button_y + (button_height - 20) // 2
            
            self.save_dc.TextOut(text_x, text_y, status)
            
            # Добавляем подсказку с хоткеем
            hotkey_text = "- :"
            hotkey_width = self.save_dc.GetTextExtent(hotkey_text)[0]
            hotkey_x = button_x - hotkey_width - 5  # 5 пикселей отступа от кнопки
            self.save_dc.SetTextColor(0x00FF00)  # Зеленый цвет для подсказки
            self.save_dc.TextOut(hotkey_x, button_y + (button_height - 20) // 2, hotkey_text)
            
            # Очищаем ресурсы
            try:
                brush.DeleteObject()
            except:
                pass
            
        except Exception as e:
            print(f"Error drawing mode status: {str(e)}")

    def draw_attack_status(self, cursor_controller):
        """Рисует индикатор режима атаки в виде кнопки"""
        try:
            # Позиция и размеры кнопки
            button_width = 120
            button_height = 40
            button_x = 570  # Та же x-координата, что и у других кнопок
            button_y = 160  # Располагаем под кнопкой режима
            
            # Цвета
            bg_color = 0xFF0000 if cursor_controller.attack_enabled else 0x404040  # Красный для активного, серый для неактивного
            text_color = 0xFFFFFF  # Белый текст
            
            # Рисуем фон кнопки
            brush = win32ui.CreateBrush(win32con.BS_SOLID, bg_color, 0)
            self.save_dc.SelectObject(brush)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем рамку кнопки
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0xFFFFFF)  # Белая рамка
            self.save_dc.SelectObject(pen)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем текст
            self.save_dc.SetTextColor(text_color)
            status = "ATTACKING: ON" if cursor_controller.attack_enabled else "ATTACKING: OFF"
            
            # Центрируем текст
            text_width = self.save_dc.GetTextExtent(status)[0]
            text_x = button_x + (button_width - text_width) // 2
            text_y = button_y + (button_height - 20) // 2
            
            self.save_dc.TextOut(text_x, text_y, status)
            
            # Добавляем подсказку с хоткеем
            hotkey_text = "BS :"
            hotkey_width = self.save_dc.GetTextExtent(hotkey_text)[0]
            hotkey_x = button_x - hotkey_width - 5  # 5 пикселей отступа от кнопки
            self.save_dc.SetTextColor(0x00FF00)  # Зеленый цвет для подсказки
            self.save_dc.TextOut(hotkey_x, button_y + (button_height - 20) // 2, hotkey_text)
            
            # Очищаем ресурсы
            try:
                brush.DeleteObject()
            except:
                pass
            
        except Exception as e:
            print(f"Error drawing attack status: {str(e)}")

    def draw_movement_debug(self, cursor_controller):
        """Отрисовка отладочной информации о движении"""
        try:
            current_pos = win32api.GetCursorPos()
            target_pos = (cursor_controller.target_x, cursor_controller.target_y)
            
            # Рисуем вектор движения
            if current_pos and target_pos:
                dx = target_pos[0] - current_pos[0]
                dy = target_pos[1] - current_pos[1]
                distance = (dx**2 + dy**2)**0.5
                
                if distance > 10:  # Минимальный порог для отрисовки
                    # Рисуем линию движения
                    pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0x0000FF)
                    self.save_dc.SelectObject(pen)
                    self.save_dc.MoveTo((int(current_pos[0]), int(current_pos[1])))
                    self.save_dc.LineTo((int(target_pos[0]), int(target_pos[1])))
                    
                    # Рисуем стрелку
                    arrow_size = 10
                    angle = math.atan2(dy, dx)
                    arrow_angle = math.pi / 6
                    
                    # Первая часть наконечника
                    ax = target_pos[0] - arrow_size * math.cos(angle + arrow_angle)
                    ay = target_pos[1] - arrow_size * math.sin(angle + arrow_angle)
                    self.save_dc.MoveTo((int(target_pos[0]), int(target_pos[1])))
                    self.save_dc.LineTo((int(ax), int(ay)))
                    
                    # Вторая часть наконечника
                    ax = target_pos[0] - arrow_size * math.cos(angle - arrow_angle)
                    ay = target_pos[1] - arrow_size * math.sin(angle - arrow_angle)
                    self.save_dc.MoveTo((int(target_pos[0]), int(target_pos[1])))
                    self.save_dc.LineTo((int(ax), int(ay)))
                    
                    # Рисуем информацию о движении
                    self.save_dc.SetTextColor(0x00FF00)
                    speed_text = f"Speed: {distance:.1f}px"
                    angle_text = f"Angle: {math.degrees(angle):.1f}°"
                    self.save_dc.TextOut(int(target_pos[0] + 10), int(target_pos[1]), speed_text)
                    self.save_dc.TextOut(int(target_pos[0] + 10), int(target_pos[1] + 20), angle_text)
                    
                    # Добавляем информацию о расстоянии и статусе W
                    w_status = "W: PRESSED" if cursor_controller.w_key_pressed else "W: RELEASED"
                    distance_text = f"Distance: {cursor_controller.last_distance:.2f}m"
                    movement_status = "MOVING" if cursor_controller.w_key_pressed else "STOPPED"
                    
                    self.save_dc.SetTextColor(cursor_controller.w_key_pressed and 0x0000FF or 0x00FF00)
                    self.save_dc.TextOut(int(target_pos[0] + 10), int(target_pos[1] + 40), w_status)
                    self.save_dc.TextOut(int(target_pos[0] + 10), int(target_pos[1] + 60), distance_text)
                    self.save_dc.TextOut(int(target_pos[0] + 10), int(target_pos[1] + 80), movement_status)
            
            # Обновляем историю позиций
            self.last_cursor_pos = current_pos
            self.last_target_pos = target_pos
            
        except Exception as e:
            print(f"Error in draw_movement_debug: {str(e)}")

    def update_info(self, cursor_pos, target_pos, distance, movement, detected_objects=None, fps=0, perf_stats=None, speed=0, direction=0, cursor_controller=None):
        current_time = time.time()
        if current_time - self.last_update_time < self.update_interval:
            return
        self.last_update_time = current_time
        try:
            self.save_dc.FillSolidRect((0, 0, 1920, 1080), 0x000000)
            
            if cursor_controller:
                self.draw_crosshair(cursor_controller)
                self.draw_following_status(cursor_controller)
                self.draw_mode_status(cursor_controller)
                self.draw_attack_status(cursor_controller)
                self.draw_movement_debug(cursor_controller)  # Добавляем отрисовку отладки движения
                
                # Добавляем статус информации про клавишу W и расстояние
                try:
                    # Позиция и размеры блока информации
                    info_width = 300
                    info_height = 120
                    info_x = 570  # Та же x-координата, что и у других кнопок
                    info_y = 210  # Располагаем под кнопками статуса
                    
                    # Цвета для блока
                    bg_color = 0x404040  # Серый фон
                    text_color = 0xFFFFFF  # Белый текст
                    highlight_color = 0x00FF00  # Зеленый для выделения
                    warning_color = 0x0000FF  # Красный для предупреждений
                    
                    # Рисуем фон блока
                    brush = win32ui.CreateBrush(win32con.BS_SOLID, bg_color, 0)
                    self.save_dc.SelectObject(brush)
                    self.save_dc.Rectangle((info_x, info_y, info_x + info_width, info_y + info_height))
                    
                    # Рисуем рамку блока
                    pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0xFFFFFF)  # Белая рамка
                    self.save_dc.SelectObject(pen)
                    self.save_dc.Rectangle((info_x, info_y, info_x + info_width, info_y + info_height))
                    
                    # Рисуем заголовок
                    self.save_dc.SetTextColor(text_color)
                    self.save_dc.TextOut(info_x + 10, info_y + 10, "MOVEMENT STATUS")
                    
                    # Рисуем информацию о статусе клавиши W
                    w_status = "PRESSED" if cursor_controller.w_key_pressed else "RELEASED"
                    w_color = warning_color if cursor_controller.w_key_pressed else highlight_color
                    self.save_dc.SetTextColor(w_color)
                    self.save_dc.TextOut(info_x + 10, info_y + 40, f"W Key: {w_status}")
                    
                    # Рисуем информацию о расстоянии
                    distance_color = warning_color if cursor_controller.last_distance > 2.0 else highlight_color
                    self.save_dc.SetTextColor(distance_color)
                    self.save_dc.TextOut(info_x + 10, info_y + 70, f"Distance: {cursor_controller.last_distance:.2f}m")
                    
                    # Рисуем статус движения
                    movement_status = "MOVING FORWARD" if cursor_controller.w_key_pressed else "STOPPED"
                    movement_color = warning_color if cursor_controller.w_key_pressed else highlight_color
                    self.save_dc.SetTextColor(movement_color)
                    self.save_dc.TextOut(info_x + 10, info_y + 100, f"Status: {movement_status}")
                    
                except Exception as e:
                    print(f"Error drawing movement status: {str(e)}")
            
            if detected_objects:
                for obj in detected_objects:
                    if obj['type'] == 'body':
                        if self.draw_skeleton_enabled:
                            self.draw_skeleton(obj['landmarks'], obj['color'])
                        if 'box' in obj:
                            self.draw_bounding_box(obj['box'], obj['color'])
            
            self.save_dc.SelectObject(self.font)
            
            # Серый фон для всей отладочной информации
            self.save_dc.FillSolidRect((100, 60, 450, 520), 0x404040)  # Увеличена высота на 30 пикселей
            
            # FPS, Distance, Speed, Movement Angle
            fps_str   = f"FPS: {fps:.1f}"
            distance_str = f"Distance: {distance:.2f} m" if distance is not None else "Distance: ---"
            speed_str    = f"Speed:    {speed:.2f} m/s" if speed is not None else "Speed: ---"
            angle_str     = f"Movement Angle: {math.degrees(direction):.1f}°" if direction is not None and speed >= 0.1 else "Movement Angle: ---"
            
            self.save_dc.SetTextColor(0x00FF00)
            self.save_dc.TextOut(110, 70, fps_str)
            self.save_dc.TextOut(110, 90, distance_str)
            self.save_dc.TextOut(110, 110, speed_str)
            self.save_dc.TextOut(110, 130, angle_str)
            
            # Добавляем статусы W и движения
            if cursor_controller:
                self.save_dc.SetTextColor(cursor_controller.w_key_pressed and 0x0000FF or 0x00FF00)
                self.save_dc.TextOut(110, 150, f"W Key: {cursor_controller.w_key_pressed and 'PRESSED' or 'RELEASED'}")
                self.save_dc.TextOut(110, 170, f"Last Distance: {cursor_controller.last_distance:.2f}m")
                threshold_text = f"Thresholds: Press>{2.1}m, Release<{1.9}m"
                self.save_dc.TextOut(110, 190, threshold_text)
            
            # Счетчики производительности
            if perf_stats:
                self.save_dc.SetTextColor(0x00FF00)
                text = "Performance (ms):\n"
                text += "Component        Current    Avg\n"
                text += "----------------------------\n"
                for name, counter in perf_stats.items():
                    short_name = {
                        'capture': 'Capture',
                        'process': 'Process',
                        'detection': 'Detect',
                        'drawing': 'Draw',
                        'overlay': 'Overlay',
                        'cursor': 'Cursor'
                    }.get(name, name)
                    current_ms = round(counter.current_time * 1000, 1)
                    avg_ms = round(counter.avg_time * 1000, 1)
                    current_ms = min(max(current_ms, 0), 9999.9)
                    avg_ms = min(max(avg_ms, 0), 9999.9)
                    text += f"{short_name:<12} {current_ms:>8.1f} {avg_ms:>8.1f}\n"
                self.save_dc.DrawText(
                    text,
                    (110, 210, 460, 490),
                    win32con.DT_LEFT | win32con.DT_TOP
                )
            self.mfc_dc.BitBlt(
                (0, 0), (1920, 1080),
                self.save_dc,
                (0, 0),
                win32con.SRCCOPY
            )
            win32gui.SetWindowPos(
                self.hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
            )
        except Exception as e:
            print(f"Error updating overlay: {str(e)}")
            import traceback
            traceback.print_exc()

    def __del__(self):
        try:
            # Освобождаем ресурсы в правильном порядке
            if hasattr(self, 'save_dc'):
                self.save_dc.DeleteDC()
            if hasattr(self, 'mfc_dc'):
                self.mfc_dc.DeleteDC()
            if hasattr(self, 'hdc'):
                win32gui.ReleaseDC(self.hwnd, self.hdc)
            if hasattr(self, 'bitmap'):
                try:
                    win32gui.DeleteObject(self.bitmap.GetHandle())
                except:
                    pass  # Игнорируем ошибку удаления битмапа
            if hasattr(self, 'hwnd'):
                win32gui.DestroyWindow(self.hwnd)
        except Exception as e:
            print(f"Error in OverlayWindow cleanup: {str(e)}")
            pass  # Игнорируем ошибки при очистке

class KalmanFilter:
    """Реализация простого фильтра Калмана для сглаживания координат"""
    def __init__(self, process_variance=0.001, measurement_variance=0.1):
        self.process_variance = process_variance  # малое значение = сильное сглаживание
        self.measurement_variance = measurement_variance
        self.kalman_gain = 0
        self.estimated_value = None
        self.estimate_error = 1.0
        
    def update(self, measurement):
        # Инициализация при первом измерении
        if self.estimated_value is None:
            self.estimated_value = measurement
            return self.estimated_value
            
        # Предсказание
        predicted_value = self.estimated_value
        prediction_error = self.estimate_error + self.process_variance
        
        # Обновление
        self.kalman_gain = prediction_error / (prediction_error + self.measurement_variance)
        self.estimated_value = predicted_value + self.kalman_gain * (measurement - predicted_value)
        self.estimate_error = (1 - self.kalman_gain) * prediction_error
        
        return self.estimated_value

class CursorController:
    def __init__(self):
        # Системные параметры
        self.screen_width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        self.screen_height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        self.center_x = self.screen_width // 2
        self.center_y = self.screen_height // 2
        
        # Параметры движения
        self.current_x, self.current_y = win32api.GetCursorPos()
        self.target_x = self.current_x
        self.target_y = self.current_y
        self.relative_mode = False
        self.smoothing_factor = 0.3
        self.sensitivity = 1.0
        self.min_distance = 0.5  # Уменьшаем минимальное расстояние для большей точности
        self.max_speed = 100
        self.move_history = deque(maxlen=5)
        
        # Параметры высокочастотного обновления
        self.update_interval = 1/500  # 500 Hz
        self.running = True
        self.update_thread = Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        # Параметры состояния
        self.following_enabled = True
        self.attack_enabled = False
        self.last_attack_time = 0
        self.attack_interval = random.uniform(0.1, 0.3)  # Случайный интервал между кликами
        self.last_position = None
        self.last_box = None
        
        # Фильтры Калмана для координат рамки
        self.kalman_x_min = KalmanFilter(process_variance=0.0005, measurement_variance=0.2)
        self.kalman_y_min = KalmanFilter(process_variance=0.0005, measurement_variance=0.2)
        self.kalman_x_max = KalmanFilter(process_variance=0.0005, measurement_variance=0.2)
        self.kalman_y_max = KalmanFilter(process_variance=0.0005, measurement_variance=0.2)
        self.filtered_box = None
        
        # Параметры движения вперед
        self.w_key_pressed = False
        self.manual_key_pressed = False  # Флаг для отслеживания ручного нажатия клавиши W
        self.distance_filter = KalmanFilter(process_variance=0.003, measurement_variance=0.05)  # Увеличиваем process_variance и уменьшаем measurement_variance для более быстрой реакции
        self.last_distance_check_time = 0
        self.distance_check_interval = 0.05  # Уменьшаем интервал проверки до 50 мс для более быстрой реакции
        self.distance_threshold = 2.0  # Порог в метрах
        self.target_lost_timeout = 0.3  # Уменьшаем время до признания цели потерянной
        
        # Добавляем атрибут для отслеживания последнего расстояния
        self.last_distance = 0.0
    
    def calculate_3d_position(self, landmarks, screen_width, screen_height):
        """Вычисляет экранную позицию цели и примерное расстояние в метрах
           на основе размера рамки с учетом законов перспективы"""
        # Получаем экранные координаты плеч для центра цели
        lmk = landmarks.landmark
        x1, y1 = int(lmk[mp_holistic.PoseLandmark.LEFT_SHOULDER].x * screen_width), \
                 int(lmk[mp_holistic.PoseLandmark.LEFT_SHOULDER].y * screen_height)
        x2, y2 = int(lmk[mp_holistic.PoseLandmark.RIGHT_SHOULDER].x * screen_width), \
                 int(lmk[mp_holistic.PoseLandmark.RIGHT_SHOULDER].y * screen_height)

        # Центр цели
        target_x = (x1 + x2) // 2
        target_y = (y1 + y2) // 2

        # Находим крайние точки тела для расчета общего размера рамки
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for landmark in landmarks.landmark:
            x = int(landmark.x * screen_width)
            y = int(landmark.y * screen_height)
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
        
        # Размеры рамки тела в пикселях
        box_width = max_x - min_x
        box_height = max_y - min_y
        
        # Вычисляем площадь рамки
        box_area = box_width * box_height
        screen_area = screen_width * screen_height
        
        # Отношение площади рамки к площади экрана
        area_ratio = box_area / screen_area
        
        # Защита от деления на ноль или очень маленькие значения
        if area_ratio < 0.0001:
            area_ratio = 0.0001
        
        # Константы для калибровки
        CALIBRATION_AREA = 1/9  # 1/3 * 1/3 экрана по площади = 1 метр
        
        # По законам перспективы, площадь объекта обратно пропорциональна
        # квадрату расстояния, поэтому используем квадратный корень
        # для восстановления линейной зависимости
        distance = math.sqrt(CALIBRATION_AREA / area_ratio)
        
        # Ограничение максимального значения расстояния
        distance = min(distance, 10.0)
        
        # Улучшенная диагностика
        print(f"Box size: {box_width}x{box_height} pixels, Area ratio: {area_ratio:.6f}")
        print(f"Calculated distance: {distance:.2f} meters")
        
        # Рассчитываем скорость и направление движения
        now = time.time()
        if not hasattr(self, 'last_pixel_pos'):
            self.last_pixel_pos = (target_x, target_y)
            self.last_pixel_time = now
            speed = 0.0
            direction = 0.0
        else:
            dt = now - self.last_pixel_time
            if dt > 0:
                dx, dy = target_x - self.last_pixel_pos[0], target_y - self.last_pixel_pos[1]
                speed = math.hypot(dx, dy) / dt
                direction = math.atan2(dy, dx)
                self.last_pixel_pos = (target_x, target_y)
                self.last_pixel_time = now
            else:
                speed = 0.0
                direction = 0.0

        return target_x, target_y, distance, speed, direction

    def toggle_following(self):
        """Переключает режим следования за целью"""
        self.following_enabled = not self.following_enabled
        return True
        
    def toggle_mode(self):
        """Переключает режим управления мышью (абсолютный/относительный)"""
        self.relative_mode = not self.relative_mode
        return True
        
    def toggle_attack(self):
        """Переключает режим атаки"""
        self.attack_enabled = not self.attack_enabled
        return True
        
    def handle_attack(self):
        """Обрабатывает режим атаки"""
        if self.attack_enabled:
            current_time = time.time()
            if current_time - self.last_attack_time >= self.attack_interval:
                # Выполняем клик
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                
                # Обновляем время и интервал
                self.last_attack_time = current_time
                self.attack_interval = random.uniform(0.1, 0.3)
                
    def handle_auto_movement(self, distance, box):
        """Обрабатывает автоматическое движение курсора и управление движением с клавишей W"""
        current_time = time.time()
        
        # ВАЖНАЯ МОДИФИКАЦИЯ: Не проверяем нажатие клавиши W вручную,
        # чтобы не мешать пользователю управлять движением самостоятельно
        
        # Сохраняем расстояние для отображения в любом случае
        if distance is not None and distance > 0:
            self.last_distance = distance
        
        # Проверка на потерю цели
        if not box:
            print(f"No box detected - target lost (w_key_pressed={self.w_key_pressed})")
            # Не отпускаем клавишу W автоматически - пусть пользователь сам управляет
            # Только автоматически нажатую клавишу отпускаем
            if self.w_key_pressed and self.following_enabled and not self.manual_key_pressed:
                try:
                    print("Releasing W key due to target loss")
                    keyboard.release('w')
                    self.w_key_pressed = False
                    # Имитируем небольшую паузу для более быстрой остановки
                    time.sleep(0.01)
                except Exception as e:
                    print(f"Error releasing W key: {e}")
            return
        
        # Проверка валидности расстояния
        if distance is None or distance <= 0:
            print(f"Invalid distance value: {distance}")
            # Не отпускаем клавишу W автоматически - пусть пользователь сам управляет
            return
        
        # Применяем фильтр Калмана к координатам рамки
        min_x, min_y, max_x, max_y = box
        
        filtered_min_x = self.kalman_x_min.update(min_x)
        filtered_min_y = self.kalman_y_min.update(min_y)
        filtered_max_x = self.kalman_x_max.update(max_x)
        filtered_max_y = self.kalman_y_max.update(max_y)
        
        # Округляем до целых
        filtered_min_x = int(filtered_min_x)
        filtered_min_y = int(filtered_min_y)
        filtered_max_x = int(filtered_max_x)
        filtered_max_y = int(filtered_max_y)
        
        # Сохраняем отфильтрованные данные
        self.filtered_box = (filtered_min_x, filtered_min_y, filtered_max_x, filtered_max_y)
        self.last_box = self.filtered_box
        
        # Центр цели
        target_x = (filtered_min_x + filtered_max_x) // 2
        target_y = (filtered_min_y + filtered_max_y) // 2
        
        # Применяем фильтр к расстоянию для сглаживания колебаний
        filtered_distance = self.distance_filter.update(distance)
        
        # Сохраняем отфильтрованное расстояние для отображения в оверлее
        self.last_distance = filtered_distance
        
        # Быстрая проверка - если расстояние меньше порога, немедленно отпускаем клавишу W
        # Это обеспечит более быструю реакцию при остановке
        if self.w_key_pressed and not self.manual_key_pressed and self.following_enabled and filtered_distance < 1.9:
            try:
                print(f"Quick stop: Distance {filtered_distance:.2f}m < threshold 1.9m - IMMEDIATELY RELEASING W key")
                keyboard.release('w')
                self.w_key_pressed = False
                # Когда быстро остановились, возвращаемся
                return
            except Exception as e:
                print(f"Error in quick stop release: {e}")
        
        # Управляем движением вперед только если режим Following включен
        if self.following_enabled:
            # Проверка, не нажата ли клавиша W пользователем вручную
            try:
                # Если пользователь сам нажал W - не вмешиваемся в управление
                manual_w_pressed = keyboard.is_pressed('w')
                if manual_w_pressed and not self.w_key_pressed:
                    self.manual_key_pressed = True
                    print("Manual W key press detected - Auto mode temporarily disabled")
                    # Не будем управлять W пока пользователь не отпустит клавишу
                    return
                if not manual_w_pressed and self.manual_key_pressed:
                    self.manual_key_pressed = False
                    print("Manual W key released - Auto mode re-enabled")
            except:
                pass
            
            # Если это не ручной режим - применяем автоматическое управление
            if not self.manual_key_pressed:
                release_threshold = 1.9  # Порог отпускания клавиши (повысили до 1.9 метра)
                press_threshold = 2.1    # Порог нажатия клавиши (повысили до 2.1 метра)
                
                if not self.w_key_pressed and filtered_distance > press_threshold:
                    try:
                        print(f"Distance > {press_threshold}m ({filtered_distance:.2f}m) - PRESSING W key")
                        keyboard.press('w')
                        self.w_key_pressed = True
                    except Exception as e:
                        print(f"Error pressing W key: {e}")
                elif self.w_key_pressed and filtered_distance < release_threshold:
                    try:
                        print(f"Distance <= {release_threshold}m ({filtered_distance:.2f}m) - RELEASING W key")
                        keyboard.release('w')
                        self.w_key_pressed = False
                    except Exception as e:
                        print(f"Error releasing W key: {e}")
        else:
            # Режим Following отключен - отпускаем только если мы сами нажимали
            if self.w_key_pressed and not self.manual_key_pressed:
                try:
                    print("Following disabled - stopping movement")
                    keyboard.release('w')
                    self.w_key_pressed = False
                except Exception as e:
                    print(f"Error releasing W key: {e}")
        
        # Устанавливаем целевую позицию курсора
        self.move_cursor(target_x, target_y)
    
    def _update_loop(self):
        """Основной цикл обновления позиции мыши с частотой 500 Hz"""
        last_time = time.perf_counter()
        
        while self.running:
            current_time = time.perf_counter()
            dt = current_time - last_time
            
            if dt >= self.update_interval:
                try:
                    if self.relative_mode:
                        self._update_relative_mode()
                    else:
                        self._update_absolute_mode()
                    
                    last_time = current_time
                except Exception as e:
                    print(f"Error in update loop: {str(e)}")
                    
            time.sleep(max(0, self.update_interval - dt))
    
    def _update_relative_mode(self):
        """Обновление в относительном режиме: однократное движение к рамке со смещением самой рамки."""
        # Проверка наличия цели (если нет рамки - останавливаемся)
        if not self.last_box:
            print("No target detected - stopping movement")
            return
        
        # Получаем разницу между целью и центром экрана
        dx = self.target_x - self.center_x
        dy = self.target_y - self.center_y
        
        # Вычисляем расстояние до цели
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Порог остановки - если достигли цели
        stop_threshold = 80
        
        print(f"Relative: dist={distance:.1f}, dx={dx}, dy={dy}")
        
        # Если близко к цели - останавливаемся
        if distance <= stop_threshold:
            print(f"TARGET REACHED - stopping at distance {distance:.1f}")
            return
        
        # Нормализуем направление для получения вектора единичной длины
        if distance > 0:
            norm_dx = dx / distance
            norm_dy = dy / distance
        else:
            norm_dx = 0
            norm_dy = 0
        
        # Фактор скорости - текущее значение оптимально
        slow_factor = 500
        
        # Вычисляем шаг движения
        move_x = norm_dx * 100 / slow_factor
        move_y = norm_dy * 100 / slow_factor
        
        # Обеспечиваем минимальное движение
        if abs(move_x) < 0.1 and norm_dx != 0:
            move_x = 0.1 if norm_dx > 0 else -0.1
        
        if abs(move_y) < 0.1 and norm_dy != 0:
            move_y = 0.1 if norm_dy > 0 else -0.1
        
        # Округляем для mouse_event с минимумом ±1
        move_amount_x = int(move_x * 10)
        move_amount_y = int(move_y * 10)
        
        if move_amount_x == 0 and norm_dx != 0:
            move_amount_x = 1 if norm_dx > 0 else -1
        
        if move_amount_y == 0 and norm_dy != 0:
            move_amount_y = 1 if norm_dy > 0 else -1
        
        print(f"Move=({move_amount_x},{move_amount_y})")
        
        # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Перемещаем виртуальную цель НАВСТРЕЧУ движению
        # Это создает эффект сходимости курсора и цели
        virtual_target_shift = 5  # Шаг смещения виртуальной цели
        
        # Сдвигаем виртуальную цель навстречу движению
        self.target_x -= move_amount_x * virtual_target_shift
        self.target_y -= move_amount_y * virtual_target_shift
        
        print(f"Adjusted target to ({self.target_x}, {self.target_y})")
        
        # Перемещаем курсор в направлении цели
        win32api.mouse_event(
            win32con.MOUSEEVENTF_MOVE, 
            move_amount_x, move_amount_y, 
            0, 0
        )
        
        # Мгновенно возвращаем курсор в центр экрана
        win32api.SetCursorPos((self.center_x, self.center_y))
    
    def _update_absolute_mode(self):
        """Обновление в абсолютном режиме с улучшенным движением к цели"""
        current_x, current_y = win32api.GetCursorPos()
        
        # Вычисляем разницу до цели
        dx = self.target_x - current_x
        dy = self.target_y - current_y
        distance = (dx**2 + dy**2)**0.5
        
        # Отладка с более подробной информацией
        print(f"Absolute: dist={distance:.1f}, dx={dx}, dy={dy}, target=({self.target_x},{self.target_y})")
        
        # Порог остановки - если достигли цели
        stop_threshold = 5
        if distance <= stop_threshold:
            print(f"TARGET REACHED - stopping at distance {distance:.1f}")
            return
        
        # Замедление абсолютного режима
        slow_factor = 100
        
        # Вычисляем нормализованное направление
        if distance > 0:
            norm_dx = dx / distance
            norm_dy = dy / distance
        else:
            norm_dx = 0
            norm_dy = 0
        
        # Применяем двухэтапный расчет:
        # 1. Cначала учитываем расстояние и сглаживание (для больших расстояний)
        # 2. Затем гарантируем минимальное движение в правильном направлении
        
        # Основной расчет движения
        move_x = dx * self.smoothing_factor / slow_factor
        move_y = dy * self.smoothing_factor / slow_factor
        
        # Минимальное движение вдоль каждой оси
        min_move = 1.0 / slow_factor
        
        # Гарантируем минимальное движение в нужном направлении
        if abs(move_x) < min_move and norm_dx != 0:
            move_x = min_move if norm_dx > 0 else -min_move
        
        if abs(move_y) < min_move and norm_dy != 0:
            move_y = min_move if norm_dy > 0 else -min_move
        
        # Преобразуем в целые пиксели
        new_x = int(current_x + move_x)
        new_y = int(current_y + move_y)
        
        # Не допускаем "прилипания" к одной координате
        if new_x == current_x and dx != 0:
            new_x += 1 if dx > 0 else -1
        
        if new_y == current_y and dy != 0:
            new_y += 1 if dy > 0 else -1
        
        # Диагностика
        print(f"Absolute move: ({current_x},{current_y}) → ({new_x},{new_y}), delta=({move_x:.2f},{move_y:.2f})")
        
        # Ограничиваем координаты экраном
        new_x = max(0, min(new_x, self.screen_width - 1))
        new_y = max(0, min(new_y, self.screen_height - 1))
        
        # Устанавливаем новую позицию
        win32api.SetCursorPos((new_x, new_y))
    
    def move_cursor(self, target_x, target_y):
        """Установка целевой позиции курсора"""
        try:
            # Всегда обновляем целевую позицию без каких-либо коррекций
            self.target_x = target_x
            self.target_y = target_y
            return win32api.GetCursorPos()
        except Exception as e:
            print(f"Error in move_cursor: {str(e)}")
            return win32api.GetCursorPos()
    
    def cleanup(self):
        """Очистка ресурсов при завершении, гарантирует отпускание всех клавиш"""
        print("Running CursorController cleanup...")
        # Отпускаем клавишу W, если она была зажата
        if hasattr(self, 'w_key_pressed') and self.w_key_pressed:
            try:
                print("Cleanup: Releasing W key")
                keyboard.release('w')
                time.sleep(0.02)  # Небольшая задержка для обработки
                
                # Двойная проверка отпускания
                if keyboard.is_pressed('w'):
                    print("W key still pressed after release! Trying again...")
                    keyboard.release('w')
                    time.sleep(0.02)
            except Exception as e:
                print(f"Error releasing W key during cleanup: {e}")
            
            self.w_key_pressed = False
        
        # Останавливаем поток обновления
        self.running = False
        if hasattr(self, 'update_thread') and self.update_thread and self.update_thread.is_alive():
            try:
                self.update_thread.join(timeout=1.0)
                print("Update thread stopped")
            except Exception as e:
                print(f"Error stopping update thread: {e}")
        
        print("CursorController cleanup completed")
    
    def __del__(self):
        self.cleanup()

class VideoRecorder:
    def __init__(self):
        self.is_recording = False
        self.video_writer = None
        self.record_start_time = None
        self.last_frame_time = None
        self.frame_interval = 1.0 / 30.0  # 30 FPS
        self.frame_count = 0
        
    def start_recording(self, frame):
        if self.is_recording:
            self.stop_recording()
            return
            
        # Создаем папку для записей, если её нет
        if not os.path.exists('recordings'):
            os.makedirs('recordings')
        
        # Генерируем имя файла с текущей датой и временем
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recordings/screen_recording_{timestamp}.mp4"
        
        # Получаем размеры кадра
        height, width = frame.shape[:2]
        
        # Создаем VideoWriter с кодеком H.264
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        fps = 30  # Стандартный FPS
        self.video_writer = cv2.VideoWriter(filename, fourcc, fps, (width, height))
        self.is_recording = True
        self.record_start_time = time.time()
        self.last_frame_time = time.time()
        self.frame_count = 0
        print(f"Started recording to {filename}")
            
    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
                duration = time.time() - self.record_start_time
                print(f"Stopped recording. Duration: {duration:.1f} seconds")
                print(f"Recorded {self.frame_count} frames")
                
    def write_frame(self, frame):
        if self.is_recording and self.video_writer is not None:
            try:
                self.video_writer.write(frame)
                self.frame_count += 1
            except Exception as e:
                print(f"Error writing frame: {e}")
                self.stop_recording()
                    
    def __del__(self):
        self.stop_recording()

class DrawingUtils:
    # Словарь с названиями частей тела
    BODY_PARTS = {
        mp_holistic.PoseLandmark.NOSE: "NOSE",
        mp_holistic.PoseLandmark.LEFT_EYE: "L_EYE",
        mp_holistic.PoseLandmark.RIGHT_EYE: "R_EYE",
        mp_holistic.PoseLandmark.LEFT_SHOULDER: "L_SHOULDER",
        mp_holistic.PoseLandmark.RIGHT_SHOULDER: "R_SHOULDER",
        mp_holistic.PoseLandmark.LEFT_ELBOW: "L_ELBOW",
        mp_holistic.PoseLandmark.RIGHT_ELBOW: "R_ELBOW",
        mp_holistic.PoseLandmark.LEFT_WRIST: "L_WRIST",
        mp_holistic.PoseLandmark.RIGHT_WRIST: "R_WRIST",
        mp_holistic.PoseLandmark.LEFT_HIP: "L_HIP",
        mp_holistic.PoseLandmark.RIGHT_HIP: "R_HIP",
        mp_holistic.PoseLandmark.LEFT_KNEE: "L_KNEE",
        mp_holistic.PoseLandmark.RIGHT_KNEE: "R_KNEE",
        mp_holistic.PoseLandmark.LEFT_ANKLE: "L_ANKLE",
        mp_holistic.PoseLandmark.RIGHT_ANKLE: "R_ANKLE"
    }

    @staticmethod
    def draw_landmarks(frame, landmarks, connections, color, thickness=2, circle_radius=4):
        """Рисует точки и соединения между ними с подписями"""
        if not landmarks:
            return

        # Рисуем точки и подписи
        for idx, landmark in enumerate(landmarks.landmark):
            x = int(landmark.x * frame.shape[1])
            y = int(landmark.y * frame.shape[0])
            
            # Рисуем белую точку
            cv2.circle(frame, (x, y), circle_radius, (255, 255, 255), -1)
            # Рисуем цветную обводку
            cv2.circle(frame, (x, y), circle_radius + 1, color, 1)
            
            # Добавляем подпись, если это известная часть тела
            if idx in DrawingUtils.BODY_PARTS:
                label = DrawingUtils.BODY_PARTS[idx]
                # Рисуем черный фон для текста
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x - 2, y - h - 10), (x + w + 2, y - 10), (0, 0, 0), -1)
                # Рисуем белый текст
                cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Рисуем соединения
        for connection in connections:
            start_point = landmarks.landmark[connection[0]]
            end_point = landmarks.landmark[connection[1]]
            
            start_x = int(start_point.x * frame.shape[1])
            start_y = int(start_point.y * frame.shape[0])
            end_x = int(end_point.x * frame.shape[1])
            end_y = int(end_point.y * frame.shape[0])
            
            # Рисуем линию с градиентом
            cv2.line(frame, (start_x, start_y), (end_x, end_y), color, thickness)

    @staticmethod
    def draw_bounding_box(frame, landmarks, color, padding=10, thickness=2):
        """Рисует улучшенную рамку вокруг набора точек"""
        if not landmarks:
            return None

        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')

        # Находим границы
        for landmark in landmarks.landmark:
            x = int(landmark.x * frame.shape[1])
            y = int(landmark.y * frame.shape[0])
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

        # Добавляем отступ
        min_x = max(0, min_x - padding)
        min_y = max(0, min_y - padding)
        max_x = min(frame.shape[1], max_x + padding)
        max_y = min(frame.shape[0], max_y + padding)

        # Рисуем основную рамку
        cv2.rectangle(frame, (min_x, min_y), (max_x, max_y), color, thickness)

        # Рисуем углы рамки
        corner_length = 20
        # Верхний левый угол
        cv2.line(frame, (min_x, min_y), (min_x + corner_length, min_y), (255, 255, 255), thickness + 1)
        cv2.line(frame, (min_x, min_y), (min_x, min_y + corner_length), (255, 255, 255), thickness + 1)
        # Верхний правый угол
        cv2.line(frame, (max_x - corner_length, min_y), (max_x, min_y), (255, 255, 255), thickness + 1)
        cv2.line(frame, (max_x, min_y), (max_x, min_y + corner_length), (255, 255, 255), thickness + 1)
        # Нижний левый угол
        cv2.line(frame, (min_x, max_y - corner_length), (min_x, max_y), (255, 255, 255), thickness + 1)
        cv2.line(frame, (min_x, max_y), (min_x + corner_length, max_y), (255, 255, 255), thickness + 1)
        # Нижний правый угол
        cv2.line(frame, (max_x - corner_length, max_y), (max_x, max_y), (255, 255, 255), thickness + 1)
        cv2.line(frame, (max_x, max_y - corner_length), (max_x, max_y), (255, 255, 255), thickness + 1)
        
        # Рисуем центр рамки
        center_x = (min_x + max_x) // 2
        center_y = (min_y + max_y) // 2
        
        # Рисуем перекрестие в центре
        cross_size = 10
        cv2.line(frame, (center_x - cross_size, center_y), (center_x + cross_size, center_y), (0, 255, 255), 2)
        cv2.line(frame, (center_x, center_y - cross_size), (center_x, center_y + cross_size), (0, 255, 255), 2)
        
        # Рисуем круг в центре
        cv2.circle(frame, (center_x, center_y), cross_size, (0, 255, 255), 2)
        
        # Добавляем информацию о размерах рамки
        width = max_x - min_x
        height = max_y - min_y
        info_text = f"Box: {width}x{height}px"
        cv2.putText(frame, info_text, (min_x, min_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return (min_x, min_y, max_x, max_y)

    @staticmethod
    def draw_debug_info(frame, target_x, target_y, distance, speed, direction, fps):
        margin = 10
        padding = 10
        line_height = 25
        num_lines = 8
        overlay = frame.copy()
        cv2.rectangle(overlay, 
                     (margin, margin), 
                     (margin + 300, margin + (line_height * num_lines) + padding * 2), 
                     (0, 0, 0), 
                     -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        y = margin + padding + line_height
        cv2.putText(frame, f"FPS: {fps:.1f}", 
                   (margin + padding, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y += line_height
        target_str = f"({int(target_x)}, {int(target_y)})" if target_x is not None and target_y is not None else "(---, ---)"
        cv2.putText(frame, f"Target: {target_str}", 
                   (margin + padding, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y += line_height
        distance_str = f"{distance:.2f}m" if distance is not None else "---"
        cv2.putText(frame, f"Distance: {distance_str}", 
                   (margin + padding, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y += line_height
        speed_str = f"{speed:.2f} m/s" if speed is not None else "---"
        cv2.putText(frame, f"Speed: {speed_str}", 
                   (margin + padding, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y += line_height
        direction_str = f"{math.degrees(direction):.1f}°" if direction is not None and speed >= 0.1 else "---"
        cv2.putText(frame, f"Direction: {direction_str}", 
                   (margin + padding, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y += line_height
        cv2.putText(frame, f"Frame: {frame.shape[1]}x{frame.shape[0]}", 
                   (margin + padding, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y += line_height
        current_time = datetime.now().strftime("%H:%M:%S.%f")[:-4]
        cv2.putText(frame, f"Time: {current_time}", 
                   (margin + padding, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    @staticmethod
    def draw_movement_vector(frame, start_point, end_point, color, thickness=2):
        """Рисует вектор движения"""
        if start_point is None or end_point is None:
            return

        # Вычисляем длину и угол вектора
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        length = (dx**2 + dy**2)**0.5
        angle = math.degrees(math.atan2(dy, dx))

        # Рисуем стрелку только если есть движение
        if length > 10:  # Минимальный порог движения
            # Рисуем линию движения (красный в BGR)
            cv2.line(frame, start_point, end_point, (0, 0, 255), 1)
            
            # Рисуем стрелку
            cv2.arrowedLine(
                frame,
                start_point,
                end_point,
                color,
                thickness,
                tipLength=0.2
            )

            # Рисуем информацию о движении
            cv2.putText(
                frame,
                f"Speed: {length:.1f}px",
                (end_point[0] + 10, end_point[1]),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2
            )
            cv2.putText(
                frame,
                f"Angle: {angle:.1f}°",
                (end_point[0] + 10, end_point[1] + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2
            )

def capture_screen():
    """Захватывает изображение с экрана"""
    # Получаем размеры экрана
    screen_width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
    screen_height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
    
    # Создаем DC для экрана
    hwindc = win32gui.GetWindowDC(win32gui.GetDesktopWindow())
    srcdc = win32ui.CreateDCFromHandle(hwindc)
    memdc = srcdc.CreateCompatibleDC()
    
    # Создаем битмап
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(srcdc, screen_width, screen_height)
    memdc.SelectObject(bmp)
    
    try:
        # Копируем изображение с экрана
        memdc.BitBlt((0, 0), (screen_width, screen_height), srcdc, (0, 0), win32con.SRCCOPY)
        
        # Конвертируем в numpy array
        signedIntsArray = bmp.GetBitmapBits(True)
        img = np.frombuffer(signedIntsArray, dtype='uint8')
        img.shape = (screen_height, screen_width, 4)
        
        # Конвертируем в BGR для OpenCV
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    finally:
        # Освобождаем ресурсы
        srcdc.DeleteDC()
        memdc.DeleteDC()
        win32gui.ReleaseDC(win32gui.GetDesktopWindow(), hwindc)
        win32gui.DeleteObject(bmp.GetHandle())

def process_frame(frame, cursor_controller, overlay, fps, perf_monitor):
    try:
        # Минимизируем логирование для лучшей производительности
        #print("Starting process_frame...")
        
        if frame is None or frame.size == 0:
            print("Error: Invalid frame")
            # Обязательно вызовем handle_auto_movement с box=None
            cursor_controller.handle_auto_movement(None, None)
            return None, None, None, 0.0, 0.0, []
            
        perf_monitor.start('process')
        
        # Получаем размеры экрана
        screen_width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        screen_height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        
        # Конвертируем в RGB для MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Получаем результаты от MediaPipe
        perf_monitor.start('detection')
        results = holistic.process(rgb_frame)
        perf_monitor.stop('detection')
        
        # Список для хранения всех найденных объектов
        detected_objects = []
        target_x, target_y, target_distance, speed, direction = None, None, None, 0.0, 0.0
        box = None  # Инициализируем box как None
        
        # Обрабатываем результаты распознавания
        if results.pose_landmarks:
            #print("Pose landmarks detected")
            try:
                # Получаем 3D позицию цели
                target_x, target_y, target_distance, speed, direction = cursor_controller.calculate_3d_position(
                    results.pose_landmarks,
                    screen_width,
                    screen_height
                )
                
                # Создаем рамку для объекта
                box = DrawingUtils.draw_bounding_box(
                    frame,
                    results.pose_landmarks,
                    (0, 255, 0),
                    20,
                    2
                )
                
                # Сохраняем рамку в контроллере
                cursor_controller.last_box = box
                
                # Добавляем тело в список объектов
                detected_objects.append({
                    'type': 'body',
                    'landmarks': results.pose_landmarks,
                    'color': (0, 255, 0),
                    'box': box
                })
            except Exception as e:
                print(f"Error processing pose landmarks: {str(e)}")
                import traceback
                traceback.print_exc()
                box = None  # Сбрасываем box при ошибке
        else:
            #print("No pose landmarks detected")
            cursor_controller.last_box = None
            box = None
        
        # Важно: всегда вызываем handle_auto_movement, передавая текущее расстояние и box (или None)
        cursor_controller.handle_auto_movement(target_distance, box)
        
        # Перемещаем курсор к цели, только если найдены ландмарки
        if target_x is not None and target_y is not None:
            perf_monitor.start('cursor')
            cursor_x, cursor_y = cursor_controller.move_cursor(target_x, target_y)
            perf_monitor.stop('cursor')
            
            # Рисуем только необходимые элементы
            perf_monitor.start('drawing')
            # Рисуем рамку вокруг тела
            if detected_objects and detected_objects[0]['box']:
                min_x, min_y, max_x, max_y = detected_objects[0]['box']
                cv2.rectangle(frame, (min_x, min_y), (max_x, max_y), (0, 255, 0), 2)
                
                # Рисуем центр объекта
                center_x = (min_x + max_x) // 2
                center_y = (min_y + max_y) // 2
                cv2.circle(frame, (center_x, center_y), 5, (0, 255, 255), -1)
            
            # Рисуем курсор
            cv2.circle(frame, (cursor_x, cursor_y), 5, (0, 0, 255), -1)
            
            # Рисуем вектор движения
            if cursor_controller.last_position is not None:
                dx = target_x - cursor_controller.last_position[0]
                dy = target_y - cursor_controller.last_position[1]
                movement = (dx**2 + dy**2)**0.5
                
                if movement > 10:
                    cv2.arrowedLine(
                        frame,
                        cursor_controller.last_position,
                        (target_x, target_y),
                        (0, 255, 0),
                        2,
                        tipLength=0.2
                    )
            perf_monitor.stop('drawing')
        
        # Показываем результат в отдельном окне
        try:
            cv2.imshow('Debug View', frame)
            cv2.waitKey(1)
        except Exception as e:
            print(f"Error showing debug window: {str(e)}")
        
        perf_monitor.stop('process')
        return target_x, target_y, target_distance, speed, direction, detected_objects
        
    except Exception as e:
        print(f"Error in process_frame: {str(e)}")
        import traceback
        traceback.print_exc()
        perf_monitor.stop('process')
        # Гарантируем вызов handle_auto_movement даже при ошибке
        cursor_controller.handle_auto_movement(None, None)
        return None, None, None, 0.0, 0.0, []

def main():
    try:
        print("Starting initialization...")
        
        # Отключаем защиту PyAutoGUI
        pyautogui.FAILSAFE = False
        print("PyAutoGUI failsafe disabled")
        
        # Инициализация компонентов
        print("Initializing CursorController...")
        cursor_controller = CursorController()
        print("CursorController initialized")
        
        print("Initializing OverlayWindow...")
        overlay = OverlayWindow()
        print("OverlayWindow initialized")
        
        print("Initializing VideoRecorder...")
        recorder = VideoRecorder()
        print("VideoRecorder initialized")
        
        print("Initializing PerformanceMonitor...")
        perf_monitor = PerformanceMonitor()
        print("PerformanceMonitor initialized")
        
        # Создаем окно для отладки
        print("Creating debug window...")
        cv2.namedWindow('Debug View', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Debug View', 1280, 720)
        print("Debug window created")
        
        # Основной цикл
        cursor_pos = (0, 0)
        target_pos = (0, 0)
        distance = 0.0
        speed = 0.0
        direction = 0.0
        fps = 0.0
        frame_count = 0
        start_time = time.time()
        last_stats_time = time.time()
        last_process_time = time.time()
        process_interval = 1.0 / 60.0  # 60 Hz для process_frame
        
        print("Starting main loop...")
        print("Press '-' to toggle between absolute and relative mouse movement modes")
        print("Press '+' to toggle following mode")
        print("Press 'Backspace' to toggle attack mode")
        print("Press 'F1' to exit")
        print("Press '.' to start/stop recording")
        
        while True:
            try:
                current_time = time.time()
                
                # Проверяем нажатие клавиш перед обработкой кадра
                if keyboard.is_pressed('F1'):
                    print("F1 pressed, exiting...")
                    break
                elif keyboard.is_pressed('.'):
                    if not recorder.is_recording:
                        print("Starting recording...")
                        recorder.start_recording(frame)
                    else:
                        print("Stopping recording...")
                        recorder.stop_recording()
                elif keyboard.is_pressed('-'):
                    if cursor_controller.toggle_mode():
                        print("Toggled mouse mode")
                        time.sleep(0.1)
                elif keyboard.is_pressed('+'):
                    if cursor_controller.toggle_following():
                        print("Toggled following mode")
                        time.sleep(0.1)
                elif keyboard.is_pressed('backspace'):
                    if cursor_controller.toggle_attack():
                        print("Toggled attack mode")
                        time.sleep(0.1)
                
                # Обработка кадра с ограничением частоты до 60 Hz
                if current_time - last_process_time >= process_interval:
                    perf_monitor.start('capture')
                    frame = capture_screen()
                    perf_monitor.stop('capture')
                    
                    if frame is not None:
                        target_x, target_y, target_distance, speed, direction, detected_objects = process_frame(
                            frame, cursor_controller, overlay, fps, perf_monitor
                        )
                        
                        if target_x is not None and target_y is not None:
                            target_pos = (target_x, target_y)
                            distance = target_distance
                            cursor_pos = cursor_controller.move_cursor(target_pos[0], target_pos[1])
                            movement = (int(target_pos[0] - cursor_pos[0]), int(target_pos[1] - cursor_pos[1]))
                        else:
                            movement = (0, 0)
                            
                        # Обновление оверлея
                        perf_monitor.start('overlay')
                        try:
                            overlay.update_info(
                                cursor_pos, target_pos, distance,
                                movement, detected_objects,
                                fps, perf_monitor.get_stats(),
                                speed, direction, cursor_controller
                            )
                        except Exception as e:
                            print(f"Error updating overlay: {str(e)}")
                            import traceback
                            traceback.print_exc()
                        finally:
                            perf_monitor.stop('overlay')
                            
                        # Обновляем время последней обработки
                        last_process_time = current_time
                        
                        # Обновление FPS
                        frame_count += 1
                        elapsed_time = current_time - start_time
                        if elapsed_time >= 1.0:
                            fps = frame_count / elapsed_time
                            frame_count = 0
                            start_time = current_time
                
                # Выводим статистику каждые 5 секунд
                if current_time - last_stats_time >= 5.0:
                    stats = perf_monitor.get_stats()
                    print("\nPerformance Statistics:")
                    for name, counter in stats.items():
                        print(f"{name}: {counter.current_time*1000:.1f}ms (avg: {counter.avg_time*1000:.1f}ms)")
                    last_stats_time = current_time
                
                # Запись кадра если идет запись
                if recorder.is_recording and frame is not None:
                    try:
                        recorder.write_frame(frame)
                    except Exception as e:
                        print(f"Error writing frame: {str(e)}")
                        recorder.stop_recording()
                
                # Обработка событий OpenCV
                key = cv2.waitKey(1) & 0xFF
                if key == 27:  # ESC
                    print("ESC pressed, exiting...")
                    break
                
                # Небольшая задержка для снижения нагрузки на CPU
                time.sleep(0.001)
                
            except Exception as e:
                print(f"Error in main loop iteration: {str(e)}")
                import traceback
                traceback.print_exc()
                time.sleep(1)
                
    except Exception as e:
        print(f"Error in main loop: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        print("Cleaning up resources...")
        if 'recorder' in locals():
            recorder.stop_recording()
        if 'overlay' in locals():
            try:
                overlay.__del__()
            except:
                pass
        cv2.destroyAllWindows()
        cv2.waitKey(1)
        print("Cleanup completed")
        return 0

if __name__ == "__main__":
    sys.exit(main()) 