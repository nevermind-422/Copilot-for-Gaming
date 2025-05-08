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
    model_complexity=1,       # Уменьшаем сложность для производительности
    enable_segmentation=False,  # Отключаем сегментацию для производительности
    smooth_landmarks=True,    # Включаем сглаживание
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
                cursor_controller.handle_attack()  # Обработка атак
            
            if detected_objects:
                for obj in detected_objects:
                    if obj['type'] == 'body':
                        if self.draw_skeleton_enabled:
                            self.draw_skeleton(obj['landmarks'], obj['color'])
                        if 'box' in obj:
                            self.draw_bounding_box(obj['box'], obj['color'])
            
            if cursor_pos and target_pos and movement:
                self.draw_movement_vector(cursor_pos, target_pos, speed, direction)
            
            self.save_dc.SelectObject(self.font)
            
            # Серый фон для всей отладочной информации
            self.save_dc.FillSolidRect((100, 60, 450, 520), 0x404040)  # Увеличена высота на 30 пикселей
            
            # FPS, Distance, Speed, Movement Angle
            fps_str = f"FPS: {fps:.1f}"
            distance_str = f"Distance: {distance:.2f}m" if distance is not None else "Distance: ---"
            speed_str = f"Speed: {speed:.2f} m/s" if speed is not None else "Speed: ---"
            angle_str = f"Movement Angle: {math.degrees(direction):.1f}°" if direction is not None and speed >= 0.1 else "Movement Angle: ---"
            
            self.save_dc.SetTextColor(0x00FF00)
            self.save_dc.TextOut(110, 70, fps_str)
            self.save_dc.TextOut(110, 90, distance_str)
            self.save_dc.TextOut(110, 110, speed_str)
            self.save_dc.TextOut(110, 130, angle_str)
            
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
                    (110, 170, 460, 490),
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

class CursorController:
    def __init__(self):
        self.relative_mode = False
        self.sensitivity = 0.075  # Уменьшена чувствительность в два раза (было 0.15)
        self.center_x = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN) // 2
        self.center_y = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN) // 2
        self.last_mode_switch_time = 0
        self.last_position = None
        
        # Параметры для абсолютного режима
        self.smoothing_factor = 0.3
        self.min_distance = 5
        self.max_speed = 20
        
        # Параметры для сглаживания в относительном режиме
        self.move_history = deque(maxlen=3)  # История последних движений
        self.max_move = 15  # Уменьшено максимальное смещение за один кадр (было 30)
        
        # Параметры для автоматического движения
        self.is_moving = False
        self.target_distance = 2.0  # Целевая дистанция в метрах
        self.movement_threshold = 0.1  # Порог для начала движения
        self.following_enabled = True  # Состояние следования за целью
        
        # Параметры для режима атаки
        self.attack_enabled = False
        self.last_key1_time = 0
        self.last_mouse1_time = 0
        self.key1_interval = random.uniform(2.0, 4.0)  # Интервал для клавиши 1
        self.mouse1_interval = random.uniform(0.5, 0.7)  # Интервал для Mouse1
        self.last_box = None  # Последняя известная рамка
        self.last_distance = None  # Последнее известное расстояние
        
        # История позиций запястий для проверки стабильности
        self.wrist_positions = deque(maxlen=10)  # Храним последние 10 позиций
        self.stability_threshold = 0.02  # Порог стабильности (можно настроить)

    def check_stability(self, left_wrist, right_wrist):
        """Проверяет стабильность положения запястий"""
        if not left_wrist or not right_wrist:
            return True  # Если нет данных, считаем стабильным
            
        # Вычисляем среднюю позицию запястий
        current_pos = (
            (left_wrist.x + right_wrist.x) / 2,
            (left_wrist.y + right_wrist.y) / 2,
            (left_wrist.z + right_wrist.z) / 2
        )
        
        # Добавляем текущую позицию в историю
        self.wrist_positions.append(current_pos)
        
        # Если у нас недостаточно истории, считаем стабильным
        if len(self.wrist_positions) < 3:
            return True
            
        # Вычисляем среднее отклонение от среднего положения
        avg_x = sum(p[0] for p in self.wrist_positions) / len(self.wrist_positions)
        avg_y = sum(p[1] for p in self.wrist_positions) / len(self.wrist_positions)
        avg_z = sum(p[2] for p in self.wrist_positions) / len(self.wrist_positions)
        
        # Вычисляем среднее отклонение
        deviations = []
        for pos in self.wrist_positions:
            dx = abs(pos[0] - avg_x)
            dy = abs(pos[1] - avg_y)
            dz = abs(pos[2] - avg_z)
            deviation = (dx + dy + dz) / 3  # Среднее отклонение по всем координатам
            deviations.append(deviation)
            
        avg_deviation = sum(deviations) / len(deviations)
        
        # Если среднее отклонение меньше порога, считаем положение стабильным
        return avg_deviation < self.stability_threshold

    def is_crosshair_in_box(self, box):
        """Проверяет, находится ли прицел внутри рамки"""
        if not box:
            return False
        min_x, min_y, max_x, max_y = box
        return (min_x <= self.center_x <= max_x and 
                min_y <= self.center_y <= max_y)

    def handle_auto_movement(self, distance, box):
        """Управляет автоматическим движением к цели"""
        if not box or not self.following_enabled:
            if self.is_moving:
                keyboard.release('w')
                self.is_moving = False
            return

        # Проверяем, находится ли прицел в рамке
        if self.is_crosshair_in_box(box):
            if distance > self.target_distance + self.movement_threshold:
                # Если дистанция больше целевой, начинаем движение
                if not self.is_moving:
                    keyboard.press('w')
                    self.is_moving = True
            elif distance < self.target_distance - self.movement_threshold:
                # Если дистанция меньше целевой, останавливаемся
                if self.is_moving:
                    keyboard.release('w')
                    self.is_moving = False
        else:
            # Если прицел не в рамке, останавливаемся
            if self.is_moving:
                keyboard.release('w')
                self.is_moving = False

    def toggle_mode(self):
        """Toggle between absolute and relative mouse movement modes"""
        current_time = time.time()
        if current_time - self.last_mode_switch_time >= 0.5:  # Предотвращаем частое переключение
            self.relative_mode = not self.relative_mode
            self.last_mode_switch_time = current_time
            print(f"Switched to {'RELATIVE' if self.relative_mode else 'ABSOLUTE'} mode")
            
            if self.relative_mode:
                # Центрируем курсор при переходе в относительный режим
                win32api.SetCursorPos((self.center_x, self.center_y))
                self.last_position = (self.center_x, self.center_y)
            return True
        return False

    def toggle_following(self):
        """Переключает состояние следования за целью"""
        current_time = time.time()
        if current_time - self.last_mode_switch_time >= 0.5:  # Предотвращаем частое переключение
            self.following_enabled = not self.following_enabled
            self.last_mode_switch_time = current_time
            print(f"Following {'ENABLED' if self.following_enabled else 'DISABLED'}")
            return True
        return False

    def toggle_attack(self):
        """Переключает режим атаки"""
        current_time = time.time()
        if current_time - self.last_mode_switch_time >= 0.5:  # Предотвращаем частое переключение
            self.attack_enabled = not self.attack_enabled
            self.last_mode_switch_time = current_time
            if self.attack_enabled:
                self.last_key1_time = current_time
                self.key1_interval = random.uniform(2.0, 4.0)  # Новый случайный интервал
            print(f"Attack mode {'ENABLED' if self.attack_enabled else 'DISABLED'}")
            return True
        return False

    def handle_attack(self):
        """Управляет комбинированной атакой"""
        if not self.attack_enabled:
            return

        current_time = time.time()
        
        # Обработка нажатия клавиши 1
        if current_time - self.last_key1_time >= self.key1_interval:
            try:
                keyboard.press('1')
                time.sleep(0.1)  # Короткая задержка для надежности
                keyboard.release('1')
                self.last_key1_time = current_time
                self.key1_interval = random.uniform(2.0, 4.0)  # Новый случайный интервал
            except Exception as e:
                print(f"Error in key1 press: {str(e)}")
        
        # Обработка нажатия Mouse1 только если прицел в рамке и расстояние подходящее
        if current_time - self.last_mouse1_time >= self.mouse1_interval:
            try:
                # Проверяем, находится ли прицел в рамке и расстояние
                if hasattr(self, 'last_box') and self.last_box and self.last_distance is not None:
                    if self.is_crosshair_in_box(self.last_box) and self.last_distance <= 20.0:
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        time.sleep(0.05)  # Короткая задержка
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        self.last_mouse1_time = current_time
                        self.mouse1_interval = random.uniform(0.5, 0.7)  # Новый случайный интервал
            except Exception as e:
                print(f"Error in mouse1 click: {str(e)}")

    def move_cursor(self, target_x, target_y):
        try:
            if self.relative_mode:
                # Вычисляем смещение относительно центра экрана
                dx = target_x - self.center_x
                dy = target_y - self.center_y
                
                # Применяем чувствительность
                move_x = dx * self.sensitivity
                move_y = dy * self.sensitivity
                
                # Ограничиваем максимальное смещение за кадр
                move_x = max(min(move_x, self.max_move), -self.max_move)
                move_y = max(min(move_y, self.max_move), -self.max_move)
                
                # Добавляем текущее движение в историю
                self.move_history.append((move_x, move_y))
                
                # Вычисляем сглаженное движение как среднее по истории
                if len(self.move_history) > 0:
                    smooth_x = sum(x for x, _ in self.move_history) / len(self.move_history)
                    smooth_y = sum(y for _, y in self.move_history) / len(self.move_history)
                    
                    # Применяем сглаженное движение только если оно достаточно большое
                    if abs(smooth_x) > 0.1 or abs(smooth_y) > 0.1:
                        win32api.mouse_event(
                            win32con.MOUSEEVENTF_MOVE,
                            int(smooth_x),
                            int(smooth_y),
                            0, 0
                        )
                
                return self.center_x, self.center_y
            else:
                # Стандартный режим абсолютного позиционирования
                current_x, current_y = win32api.GetCursorPos()
                dx = target_x - current_x
                dy = target_y - current_y
                distance = (dx**2 + dy**2)**0.5
                
                if distance < self.min_distance:
                    return current_x, current_y
                    
                if distance > self.max_speed:
                    scale = self.max_speed / distance
                    dx *= scale
                    dy *= scale
                    
                move_x = int(dx * self.smoothing_factor)
                move_y = int(dy * self.smoothing_factor)
                
                screen_width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
                screen_height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
                new_x = max(0, min(current_x + move_x, screen_width - 1))
                new_y = max(0, min(current_y + move_y, screen_height - 1))
                
                win32api.SetCursorPos((new_x, new_y))
                return new_x, new_y
                
        except Exception as e:
            print(f"Error in move_cursor: {str(e)}")
            current_x, current_y = win32api.GetCursorPos()
            return current_x, current_y

    def calculate_3d_position(self, landmarks, frame_width, frame_height):
        """Вычисляет позицию цели на основе ключевых точек"""
        if not landmarks:
            return None, None, None, 0.0, 0.0
            
        try:
            # Получаем координаты центра тела (между плечами)
            left_shoulder = landmarks.landmark[mp_holistic.PoseLandmark.LEFT_SHOULDER]
            right_shoulder = landmarks.landmark[mp_holistic.PoseLandmark.RIGHT_SHOULDER]
            
            # Вычисляем центр между плечами
            center_x = (left_shoulder.x + right_shoulder.x) / 2
            center_y = (left_shoulder.y + right_shoulder.y) / 2
            
            # Конвертируем в пиксели
            pixel_x = int(center_x * frame_width)
            pixel_y = int(center_y * frame_height)
            
            # Простой расчет расстояния на основе размера скелета
            min_y = float('inf')
            max_y = float('-inf')
            for landmark in landmarks.landmark:
                y = landmark.y * frame_height
                min_y = min(min_y, y)
                max_y = max(max_y, y)
            
            height_pixels = max_y - min_y
            # Нормализуем расстояние: 1 метр при высоте 1/3 экрана, умножаем на 2 для соответствия реальной дистанции
            distance = 2 * (frame_height / 3) / height_pixels if height_pixels > 0 else 0
            
            # Сохраняем последнее расстояние для проверки в handle_attack
            self.last_distance = distance
            
            # Простой расчет скорости
            if self.last_position:
                dx = pixel_x - self.last_position[0]
                dy = pixel_y - self.last_position[1]
                # Нормализуем скорость: 1 м/с при движении на 1/10 экрана в секунду
                speed = (dx * dx + dy * dy) ** 0.5 / (frame_width / 10)
                direction = math.atan2(dy, dx)
            else:
                speed = 0.0
                direction = 0.0
            
            self.last_position = (pixel_x, pixel_y)
            
            return pixel_x, pixel_y, distance, speed, direction
            
        except Exception as e:
            print(f"Error in calculate_3d_position: {str(e)}")
            return None, None, None, 0.0, 0.0

    def __del__(self):
        """Очистка при завершении работы"""
        if self.is_moving:
            keyboard.release('w')

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
        if frame is None or frame.size == 0:
            print("Error: Invalid frame")
            return None, None, None, 0.0, 0.0, []
            
        perf_monitor.start('process')
        
        # Получаем размеры экрана
        screen_width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        screen_height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        
        # Проверяем размеры кадра
        if frame.shape[0] != screen_height or frame.shape[1] != screen_width:
            frame = cv2.resize(frame, (screen_width, screen_height))
        
        # Конвертируем в RGB для MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Получаем результаты от MediaPipe
        perf_monitor.start('detection')
        results = holistic.process(rgb_frame)
        perf_monitor.stop('detection')
        
        # Список для хранения всех найденных объектов
        detected_objects = []
        target_x, target_y, target_distance, speed, direction = None, None, None, 0.0, 0.0
        
        # Обрабатываем результаты распознавания
        if results.pose_landmarks:
            try:
                # Создаем временную рамку для проверки размера
                temp_box = DrawingUtils.draw_bounding_box(
                    frame,
                    results.pose_landmarks,
                    (0, 255, 0),
                    20,
                    2
                )
                
                if temp_box:
                    # Проверяем размер области
                    min_x, min_y, max_x, max_y = temp_box
                    width = max_x - min_x
                    height = max_y - min_y
                    area = width * height
                    
                    # Проверяем положение области
                    center_y = (min_y + max_y) / 2
                    center_x = (min_x + max_x) / 2
                    
                    # Проверяем, находится ли центр области в нижней трети экрана
                    is_in_lower_third = center_y > (screen_height * 2/3)
                    
                    # Проверяем, находится ли центр области в центральной трети по горизонтали
                    is_in_center_third = (screen_width/3) <= center_x <= (screen_width * 2/3)
                    
                    # Проверяем глубину (z-координату) ключевых точек
                    left_wrist = results.pose_landmarks.landmark[mp_holistic.PoseLandmark.LEFT_WRIST]
                    right_wrist = results.pose_landmarks.landmark[mp_holistic.PoseLandmark.RIGHT_WRIST]
                    left_shoulder = results.pose_landmarks.landmark[mp_holistic.PoseLandmark.LEFT_SHOULDER]
                    right_shoulder = results.pose_landmarks.landmark[mp_holistic.PoseLandmark.RIGHT_SHOULDER]
                    
                    # Вычисляем среднюю z-координату запястий и плеч
                    wrist_z = (left_wrist.z + right_wrist.z) / 2
                    shoulder_z = (left_shoulder.z + right_shoulder.z) / 2
                    
                    # Если запястья находятся ближе к камере, чем плечи, это могут быть руки
                    # z-координата в MediaPipe: меньше = ближе к камере
                    is_hands_closer = wrist_z < shoulder_z - 0.1  # Порог 0.1 можно настроить
                    
                    # Проверяем стабильность положения
                    is_stable = cursor_controller.check_stability(left_wrist, right_wrist)
                    
                    # Игнорируем обнаружение, если:
                    # 1. Область находится в нижней трети экрана И
                    # 2. Область находится в центральной трети по горизонтали И
                    # 3. (Запястья находятся ближе к камере, чем плечи ИЛИ положение нестабильно)
                    should_ignore = is_in_lower_third and is_in_center_third and (is_hands_closer or not is_stable)
                    
                    # Минимальный размер области для детекции
                    MIN_DETECTION_AREA = 50000
                    
                    if not should_ignore and area >= MIN_DETECTION_AREA:
                        # Получаем 3D позицию цели
                        target_x, target_y, target_distance, speed, direction = cursor_controller.calculate_3d_position(
                            results.pose_landmarks,
                            screen_width,
                            screen_height
                        )
                        
                        # Сохраняем рамку в контроллере
                        cursor_controller.last_box = temp_box
                        
                        # Добавляем тело в список объектов
                        detected_objects.append({
                            'type': 'body',
                            'landmarks': results.pose_landmarks,
                            'color': (0, 255, 0),
                            'box': temp_box
                        })
                        
                        # Управляем автоматическим движением
                        cursor_controller.handle_auto_movement(target_distance, temp_box)
                    else:
                        # Если область должна быть проигнорирована, сбрасываем рамку
                        cursor_controller.last_box = None
                
                # Перемещаем курсор к цели
                if target_x is not None and target_y is not None:
                    perf_monitor.start('cursor')
                    cursor_x, cursor_y = cursor_controller.move_cursor(target_x, target_y)
                    perf_monitor.stop('cursor')
                    
            except Exception as e:
                print(f"Error processing pose landmarks: {str(e)}")
        else:
            # Если объект не обнаружен, сбрасываем рамку
            cursor_controller.last_box = None
        
        perf_monitor.stop('process')
        return target_x, target_y, target_distance, speed, direction, detected_objects
        
    except Exception as e:
        print(f"Error in process_frame: {str(e)}")
        import traceback
        traceback.print_exc()
        perf_monitor.stop('process')
        return None, None, None, 0.0, 0.0, []

def main():
    try:
        # Отключаем защиту PyAutoGUI
        pyautogui.FAILSAFE = False
        
        # Инициализация компонентов
        cursor_controller = CursorController()
        overlay = OverlayWindow()
        recorder = VideoRecorder()
        perf_monitor = PerformanceMonitor()
        
        # Создаем окно для отладки
        cv2.namedWindow('Debug View', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Debug View', 1280, 720)
        
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
        
        print("Starting main loop...")
        print("Press '-' to toggle between absolute and relative mouse movement modes")
        print("Press '+' to toggle following mode")
        print("Press 'Backspace' to toggle attack mode")
        print("Press 'F1' to exit")
        print("Press '.' to start/stop recording")
        
        while True:
            try:
                # Проверяем нажатие клавиш перед обработкой кадра
                if keyboard.is_pressed('F1'):
                    print("F1 pressed, exiting...")
                    break
                elif keyboard.is_pressed('.'):
                    if not recorder.is_recording:
                        recorder.start_recording(frame)
                    else:
                        recorder.stop_recording()
                elif keyboard.is_pressed('-'):
                    if cursor_controller.toggle_mode():
                        time.sleep(0.1)  # Короткая задержка только при успешном переключении
                elif keyboard.is_pressed('+'):
                    if cursor_controller.toggle_following():
                        time.sleep(0.1)  # Короткая задержка только при успешном переключении
                elif keyboard.is_pressed('backspace'):
                    if cursor_controller.toggle_attack():
                        time.sleep(0.1)  # Короткая задержка только при успешном переключении
                
                perf_monitor.start('capture')
                # Захват экрана
                frame = capture_screen()
                perf_monitor.stop('capture')
                
                if frame is None:
                    print("Error: Failed to capture screen")
                    time.sleep(0.1)  # Пауза перед следующей попыткой
                    continue
                
                # Обработка кадра
                target_x, target_y, target_distance, speed, direction, detected_objects = process_frame(
                    frame, cursor_controller, overlay, fps, perf_monitor
                )
                
                if target_x is not None and target_y is not None:
                    # Обновляем позиции
                    target_pos = (target_x, target_y)
                    distance = target_distance
                    
                    # Сглаживание движения курсора
                    cursor_pos = cursor_controller.move_cursor(
                        target_pos[0], target_pos[1]
                    )
                    
                    # Вычисляем движение как целые числа
                    movement = (
                        int(target_pos[0] - cursor_pos[0]),
                        int(target_pos[1] - cursor_pos[1])
                    )
                else:
                    movement = (0, 0)
                
                # Обновление FPS
                frame_count += 1
                elapsed_time = time.time() - start_time
                if elapsed_time >= 1.0:
                    fps = frame_count / elapsed_time
                    frame_count = 0
                    start_time = time.time()
                
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
                finally:
                    perf_monitor.stop('overlay')
                
                # Выводим статистику каждые 5 секунд
                current_time = time.time()
                if current_time - last_stats_time >= 5.0:
                    stats = perf_monitor.get_stats()
                    print("\nPerformance Statistics:")
                    for name, counter in stats.items():
                        print(f"{name}: {counter.current_time*1000:.1f}ms (avg: {counter.avg_time*1000:.1f}ms)")
                    last_stats_time = current_time
                
                # Запись кадра если идет запись
                if recorder.is_recording:
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
                time.sleep(1)  # Пауза перед следующей итерацией
                
    except Exception as e:
        print(f"Error in main loop: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Очистка ресурсов
        if 'recorder' in locals():
            recorder.stop_recording()
        if 'overlay' in locals():
            try:
                overlay.__del__()
            except:
                pass
        cv2.destroyAllWindows()
        cv2.waitKey(1)  # Даем время на закрытие окон
        print("Cleanup completed")
        return 0

if __name__ == "__main__":
    sys.exit(main()) 