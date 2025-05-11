import argparse
import cv2
import numpy as np
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
from ultralytics import YOLO

# Версия 0.026
# - Заменена модель детекции YOLOv8 на YOLO11 для улучшения обнаружения объектов
# - Заменена система распознавания с MediaPipe на YOLOv8 для улучшения дальности детекции
# - Оптимизирована производительность за счет масштабирования входного кадра
# - Улучшена обработка нескольких людей в кадре с выбором самого большого
# - Добавлено распознавание всех типов объектов (не только людей)
# - Настроена выборка ближайшего объекта в качестве цели
# - Добавлен статический список игнорируемых объектов
# - Добавлено отображение информации о типе объекта и расстоянии
# - Улучшено расположение элементов на экране
# - Добавлено название "Reign of Bots" и версия в заголовке
# - Исправлены утечки ресурсов GDI, улучшена работа прозрачного окна
# - Оптимизирована производительность отрисовки интерфейса

# Словарь имен классов COCO для YOLO11
COCO_CLASSES = {
    0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 4: 'airplane', 5: 'bus', 
    6: 'train', 7: 'truck', 8: 'boat', 9: 'traffic light', 10: 'fire hydrant', 
    11: 'stop sign', 12: 'parking meter', 13: 'bench', 14: 'bird', 15: 'cat', 
    16: 'dog', 17: 'horse', 18: 'sheep', 19: 'cow', 20: 'elephant', 21: 'bear', 
    22: 'zebra', 23: 'giraffe', 24: 'backpack', 25: 'umbrella', 26: 'handbag', 
    27: 'tie', 28: 'suitcase', 29: 'frisbee', 30: 'skis', 31: 'snowboard', 
    32: 'sports ball', 33: 'kite', 34: 'baseball bat', 35: 'baseball glove', 
    36: 'skateboard', 37: 'surfboard', 38: 'tennis racket', 39: 'bottle', 
    40: 'wine glass', 41: 'cup', 42: 'fork', 43: 'knife', 44: 'spoon', 
    45: 'bowl', 46: 'banana', 47: 'apple', 48: 'sandwich', 49: 'orange', 
    50: 'broccoli', 51: 'carrot', 52: 'hot dog', 53: 'pizza', 54: 'donut', 
    55: 'cake', 56: 'chair', 57: 'couch', 58: 'potted plant', 59: 'bed', 
    60: 'dining table', 61: 'toilet', 62: 'tv', 63: 'laptop', 64: 'mouse', 
    65: 'remote', 66: 'keyboard', 67: 'cell phone', 68: 'microwave', 
    69: 'oven', 70: 'toaster', 71: 'sink', 72: 'refrigerator', 73: 'book', 
    74: 'clock', 75: 'vase', 76: 'scissors', 77: 'teddy bear', 78: 'hair drier', 
    79: 'toothbrush'
}

# Список игнорируемых типов объектов по умолчанию (не будут выбираться в качестве цели)
# Включаем в игнорирование все, кроме: person(0), dog(16), cat(15), bird(14), 
# horse(17), sheep(18), cow(19), elephant(20), bear(21), zebra(22), giraffe(23)
DEFAULT_IGNORED_CLASSES = [
    'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 
    'backpack', 'umbrella', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 
    'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 
    'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 
    'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange', 
    'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 
    'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 
    'laptop', 'mouse', 'remote', 'keyboard', 'cell phone', 'microwave', 
    'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase', 
    'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]

# Парсим аргументы командной строки
parser = argparse.ArgumentParser(description='Reign of Bots - Screen Detection')
parser.add_argument('--no-cursor-control', action='store_true', 
                    help='Disable cursor control features to avoid errors')
args = parser.parse_args()

# Отключение управления курсором
DISABLE_CURSOR_CONTROL = args.no_cursor_control
if DISABLE_CURSOR_CONTROL:
    print("Cursor control is disabled. The program will not move the cursor.")

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
absl_logging.use_absl_handler()
absl_logging.set_verbosity(absl_logging.INFO)

# Отключаем CUDA в случае проблем с совместимостью
os.environ["CUDA_VISIBLE_DEVICES"] = ""

# Загружаем YOLO модель
print("Initializing YOLO11...")
yolo_model = None
try:
    # Проверяем наличие папки models
    models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(models_dir, exist_ok=True)
    
    # Путь к модели yolo11n
    model_path = os.path.join(models_dir, "yolo11n.pt")
    
    # Явно используем CPU
    device = "cpu"
    print(f"Using device: {device} (CUDA disabled)")
    
    # Загружаем модель если она есть
    if os.path.exists(model_path):
        yolo_model = YOLO(model_path)
        # Явно указываем устройство
        yolo_model.to(device)
    else:
        # Если модели нет, сообщаем об ошибке
        print("YOLO11n model not found. Please make sure yolo11n.pt is in the models directory.")
        sys.exit(1)
        
    print(f"YOLO11 initialized successfully on {device}")
    
except Exception as e:
    print(f"Error initializing YOLO11: {str(e)}")
    print("Falling back to direct initialization")
    try:
        yolo_model = YOLO("yolo11n.pt")
        yolo_model.to("cpu")
        print("YOLO11 initialized using fallback method on CPU")
    except Exception as e2:
        print(f"Critical error initializing YOLO11: {str(e2)}")
        yolo_model = None

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
        
        # Устанавливаем размеры экрана
        self.screen_width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        self.screen_height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        
        # Создаем DC для окна
        self.hdc = win32gui.GetDC(self.hwnd)
        self.mfc_dc = win32ui.CreateDCFromHandle(self.hdc)
        
        # Создаем совместимый DC для рисования
        self.save_dc = self.mfc_dc.CreateCompatibleDC()
        
        # Создаем 32-битный битмап с альфа-каналом
        self.bitmap = win32ui.CreateBitmap()
        self.bitmap.CreateCompatibleBitmap(self.mfc_dc, self.screen_width, self.screen_height)
        self.save_dc.SelectObject(self.bitmap)
        
        # Настраиваем правильные цвета и прозрачность для DC
        self.save_dc.SetBkMode(win32con.TRANSPARENT)  # Устанавливаем прозрачный фон для текста
        
        # GDI объекты для очистки
        self.gdi_objects = []
        
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
        self.update_interval = 1.0 / 30.0  # 30 FPS
        
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
        """Не используется в YOLO, оставлено для совместимости"""
        pass

    def draw_movement_vector(self, cursor_pos, target_pos, speed, direction):
        """Рисует вектор движения с градиентом скорости"""
        try:
            if not cursor_pos or not target_pos or speed <= 0:
                return
            
            # Создаем список для отслеживания GDI объектов
            gdi_objects = []
                
            # Создаем перо для рисования
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0x0000FF)  # Красный цвет, толщина 2
            gdi_objects.append(pen)
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
                
                # Очищаем ресурсы
                for obj in gdi_objects:
                    try:
                        obj.DeleteObject()
                    except:
                        pass  # Игнорируем ошибку удаления пера
                
        except Exception as e:
            print(f"Error in draw_movement_vector: {str(e)}")

    def draw_bounding_box(self, box, color, class_name=None, distance=None):
        if not box:
            return
        try:
            # Создаем список для отслеживания GDI объектов
            gdi_objects = []
            
            min_x, min_y, max_x, max_y = box
            
            # Валидация координат
            if not all(isinstance(x, (int, float)) for x in [min_x, min_y, max_x, max_y]):
                print(f"Invalid box coordinates: {box}")
                return
                
            # Преобразуем в целые числа
            min_x, min_y, max_x, max_y = int(min_x), int(min_y), int(max_x), int(max_y)
            
            # Проверяем, что координаты имеют правильный порядок
            if min_x >= max_x or min_y >= max_y:
                print(f"Invalid box dimensions: {box}")
                return
                
            # Валидация цвета
            if not isinstance(color, (list, tuple)) or len(color) != 3:
                print(f"Invalid color format: {color}")
                color = (255, 255, 255)  # Белый цвет по умолчанию
                
            # Убедимся, что цвет - это кортеж из трех целых чисел от 0 до 255
            color = tuple(max(0, min(255, int(c))) for c in color)
            
            # Только перо, без кисти (заливки)
            color_value = color[2] << 16 | color[1] << 8 | color[0]
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, color_value)
            gdi_objects.append(pen)
            self.save_dc.SelectObject(pen)
            
            # Убираем заливку: не выбираем кисть вообще
            self.save_dc.Rectangle((min_x, min_y, max_x, max_y))
            
            # Центр
            center_x = (min_x + max_x) // 2
            center_y = (min_y + max_y) // 2
            yellow_pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0x00FFFF)
            gdi_objects.append(yellow_pen)
            self.save_dc.SelectObject(yellow_pen)
            cross = 10
            self.save_dc.MoveTo((center_x - cross, center_y)); self.save_dc.LineTo((center_x + cross, center_y))
            self.save_dc.MoveTo((center_x, center_y - cross)); self.save_dc.LineTo((center_x, center_y + cross))
            self.save_dc.Ellipse((center_x - cross, center_y - cross, center_x + cross, center_y + cross))
            
            # Добавляем информацию о классе и расстоянии, если они предоставлены
            if class_name or distance:
                info_text = ""
                if class_name:
                    info_text += f"{class_name}"
                if distance:
                    if info_text:
                        info_text += f": {distance:.2f}m"
                    else:
                        info_text += f"{distance:.2f}m"
                    
                if info_text:
                    # Рисуем фон для текста
                    text_width = self.save_dc.GetTextExtent(info_text)[0]
                    bg_color = 0x404040  # Серый фон
                    brush = win32ui.CreateBrush(win32con.BS_SOLID, bg_color, 0)
                    gdi_objects.append(brush)
                    self.save_dc.SelectObject(brush)
                    self.save_dc.Rectangle((min_x, min_y - 30, min_x + text_width + 10, min_y - 5))
                    
                    # Рисуем текст
                    self.save_dc.SetTextColor(0xFFFFFF)  # Белый текст
                    self.save_dc.TextOut(min_x + 5, min_y - 25, info_text)
            
            # Очищаем ресурсы
            for obj in gdi_objects:
                try:
                    obj.DeleteObject()
                except:
                    pass
                    
        except Exception as e:
            print(f"Error in draw_bounding_box: {e}")
            import traceback
            traceback.print_exc()

    def draw_landmark_labels(self, landmarks):
        """Не используется в YOLO, оставлено для совместимости"""
        pass

    def draw_crosshair(self, cursor_controller):
        """Рисует прицел в зависимости от режима"""
        try:
            # Создаем список для отслеживания GDI объектов
            gdi_objects = []
            
            # Получаем цвет прицела в зависимости от режима
            color = self.crosshair_relative_color if cursor_controller.relative_mode else self.crosshair_color
            
            # Рисуем прицел в центре экрана
            center_x = cursor_controller.center_x
            center_y = cursor_controller.center_y
            
            # Создаем перо для линий прицела
            pen = win32ui.CreatePen(win32con.PS_SOLID, self.crosshair_thickness, color)
            gdi_objects.append(pen)
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
            
            # Очищаем ресурсы
            for obj in gdi_objects:
                try:
                    obj.DeleteObject()
                except:
                    pass
                    
        except Exception as e:
            print(f"Error drawing crosshair: {str(e)}")

    def draw_following_status(self, cursor_controller):
        try:
            # Создаем список для отслеживания GDI объектов
            gdi_objects = []
            
            # Позиция и размеры кнопки
            button_width = 240
            button_height = 80
            button_x = 460  # Смещаем левее с 600 до 460
            button_y = 50  # Располагаем рядом с отладочной информацией
            
            # Цвета для кнопки
            button_bg_color = 0x404040  # Серый фон
            button_border_active = cursor_controller.following_enabled and self.following_color or self.following_disabled_color
            button_text_color = 0xFFFFFF  # Белый текст
            
            # Рисуем фон кнопки
            brush = win32ui.CreateBrush(win32con.BS_SOLID, button_bg_color, 0)
            gdi_objects.append(brush)
            self.save_dc.SelectObject(brush)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем рамку кнопки
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, button_border_active)
            gdi_objects.append(pen)
            self.save_dc.SelectObject(pen)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем название режима
            self.save_dc.SetTextColor(button_text_color)
            self.save_dc.TextOut(button_x + 10, button_y + 10, "FOLLOWING MODE")
            
            # Рисуем статус режима
            self.save_dc.SetTextColor(button_border_active)
            following_status = "ON" if cursor_controller.following_enabled else "OFF"
            self.save_dc.TextOut(button_x + 10, button_y + 30, following_status)
            
            # Добавляем подсказку по клавише справа от кнопки
            hotkey_text = ": +"
            self.save_dc.SetTextColor(0x00FF00)  # Зеленый цвет для подсказки
            hotkey_x = button_x + button_width + 10
            self.save_dc.TextOut(hotkey_x, button_y + 30, hotkey_text)
            
            # Рисуем отдельный индикатор для режима выбора цели
            self.draw_target_mode(cursor_controller, button_x, button_y + 50)
            
            # Очищаем ресурсы
            for obj in gdi_objects:
                try:
                    obj.DeleteObject()
                except:
                    pass
            
        except Exception as e:
            print(f"Error drawing following status: {str(e)}")

    def draw_target_mode(self, cursor_controller, x, y):
        """Рисует индикатор режима выбора цели"""
        try:
            # Создаем список для отслеживания GDI объектов
            gdi_objects = []
            
            # Позиция и размеры кнопки
            button_width = 240
            button_height = 30
            
            # Цвета для кнопки
            button_bg_color = 0x404040  # Серый фон
            button_border = 0xFFFFFF  # Белая рамка
            button_text_color = 0xFFFFFF  # Белый текст
            
            # Рисуем фон кнопки
            brush = win32ui.CreateBrush(win32con.BS_SOLID, button_bg_color, 0)
            gdi_objects.append(brush)
            self.save_dc.SelectObject(brush)
            self.save_dc.Rectangle((x, y, x + button_width, y + button_height))
            
            # Рисуем рамку кнопки
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, button_border)
            gdi_objects.append(pen)
            self.save_dc.SelectObject(pen)
            self.save_dc.Rectangle((x, y, x + button_width, y + button_height))
            
            # Рисуем текст режима выбора цели
            if cursor_controller.following_enabled:
                target_mode = "TARGET MODE: NEAREST"
            else:
                target_mode = "TARGET MODE: LARGEST"
                
            self.save_dc.SetTextColor(button_text_color)
            self.save_dc.TextOut(x + 10, y + 5, target_mode)
            
            # Очищаем ресурсы
            for obj in gdi_objects:
                try:
                    obj.DeleteObject()
                except:
                    pass
            
        except Exception as e:
            print(f"Error drawing target mode: {str(e)}")

    def draw_mode_status(self, cursor_controller):
        """Рисует индикатор режима мыши в виде кнопки"""
        try:
            # Создаем список для отслеживания GDI объектов
            gdi_objects = []
            
            # Позиция и размеры кнопки
            button_width = 120
            button_height = 40
            button_x = 460  # Смещаем левее с 600 до 460
            button_y = 140  # Размещаем под кнопкой following
            
            # Цвета
            bg_color = 0x00FFFF if cursor_controller.relative_mode else 0x00FF00  # Голубой для относительного, зеленый для абсолютного
            text_color = 0xFFFFFF  # Белый текст
            
            # Рисуем фон кнопки
            brush = win32ui.CreateBrush(win32con.BS_SOLID, bg_color, 0)
            gdi_objects.append(brush)
            self.save_dc.SelectObject(brush)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем рамку кнопки
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0xFFFFFF)  # Белая рамка
            gdi_objects.append(pen)
            self.save_dc.SelectObject(pen)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем текст
            self.save_dc.SetTextColor(text_color)
            status = "MS: RELATIVE" if cursor_controller.relative_mode else "MS: ABSOLUTE"
            
            # Центрируем текст
            text_width = self.save_dc.GetTextExtent(status)[0]
            text_x = button_x + (button_width - text_width) // 2
            text_y = button_y + (button_height - 20) // 2
            
            self.save_dc.TextOut(text_x, text_y, status)
            
            # Добавляем подсказку с хоткеем справа от кнопки
            hotkey_text = ": -"
            self.save_dc.SetTextColor(0x00FF00)  # Зеленый цвет для подсказки
            hotkey_x = button_x + button_width + 10
            self.save_dc.TextOut(hotkey_x, button_y + (button_height - 20) // 2, hotkey_text)
            
            # Очищаем ресурсы
            for obj in gdi_objects:
                try:
                    obj.DeleteObject()
                except:
                    pass
            
        except Exception as e:
            print(f"Error drawing mode status: {str(e)}")

    def draw_attack_status(self, cursor_controller):
        """Рисует индикатор режима атаки в виде кнопки"""
        try:
            # Создаем список для отслеживания GDI объектов
            gdi_objects = []
            
            # Позиция и размеры кнопки
            button_width = 120
            button_height = 40
            button_x = 460  # Смещаем левее с 600 до 460
            button_y = 190  # Располагаем под кнопкой режима
            
            # Цвета
            bg_color = 0xFF0000 if cursor_controller.attack_enabled else 0x404040  # Красный для активного, серый для неактивного
            text_color = 0xFFFFFF  # Белый текст
            
            # Рисуем фон кнопки
            brush = win32ui.CreateBrush(win32con.BS_SOLID, bg_color, 0)
            gdi_objects.append(('brush', brush))
            self.save_dc.SelectObject(brush)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем рамку кнопки
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0xFFFFFF)  # Белая рамка
            gdi_objects.append(('pen', pen))
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
            
            # Добавляем подсказку с хоткеем справа от кнопки
            hotkey_text = ": BS"
            self.save_dc.SetTextColor(0x00FF00)  # Зеленый цвет для подсказки
            hotkey_x = button_x + button_width + 10
            self.save_dc.TextOut(hotkey_x, button_y + (button_height - 20) // 2, hotkey_text)
            
            # Очищаем ресурсы
            for obj_type, obj in gdi_objects:
                try:
                    if obj_type == 'brush':
                        if hasattr(obj, 'DeleteObject'):
                            obj.DeleteObject()
                        elif hasattr(obj, 'delete'):
                            obj.delete()
                    elif obj_type == 'pen':
                        if hasattr(obj, 'DeleteObject'):
                            obj.DeleteObject()
                        elif hasattr(obj, 'delete'):
                            obj.delete()
                except Exception as e:
                    print(f"Error cleaning up GDI object ({obj_type}): {str(e)}")
            
        except Exception as e:
            print(f"Error drawing attack status: {str(e)}")

    def draw_person_ignore_status(self, cursor_controller):
        """Рисует индикатор режима игнорирования людей в виде кнопки"""
        try:
            # Создаем список для отслеживания GDI объектов
            gdi_objects = []
            
            # Позиция и размеры кнопки - та же ширина, что и у других кнопок
            button_width = 120
            button_height = 40
            button_x = 460  # Смещаем левее с 600 до 460
            button_y = 240  # Располагаем под кнопкой атаки
            
            # Проверяем, игнорируются ли люди (person)
            person_ignored = 'person' in [cls.lower() for cls in cursor_controller.ignored_classes]
            
            # Цвета
            bg_color = 0xFF0000 if person_ignored else 0x404040  # Красный для активного, серый для неактивного
            text_color = 0xFFFFFF  # Белый текст
            
            # Рисуем фон кнопки
            brush = win32ui.CreateBrush(win32con.BS_SOLID, bg_color, 0)
            gdi_objects.append(('brush', brush))
            self.save_dc.SelectObject(brush)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем рамку кнопки
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0xFFFFFF)  # Белая рамка
            gdi_objects.append(('pen', pen))
            self.save_dc.SelectObject(pen)
            self.save_dc.Rectangle((button_x, button_y, button_x + button_width, button_y + button_height))
            
            # Рисуем текст
            self.save_dc.SetTextColor(text_color)
            status = "IGNORE PERSON" if person_ignored else "TRACK PERSON"
            
            # Центрируем текст
            text_width = self.save_dc.GetTextExtent(status)[0]
            text_x = button_x + (button_width - text_width) // 2
            text_y = button_y + (button_height - 20) // 2
            
            self.save_dc.TextOut(text_x, text_y, status)
            
            # Добавляем подсказку с хоткеем справа от кнопки
            hotkey_text = ": \\"
            self.save_dc.SetTextColor(0x00FF00)  # Зеленый цвет для подсказки
            hotkey_x = button_x + button_width + 10
            self.save_dc.TextOut(hotkey_x, button_y + (button_height - 20) // 2, hotkey_text)
            
            # Очищаем ресурсы
            for obj_type, obj in gdi_objects:
                try:
                    if obj_type == 'brush':
                        if hasattr(obj, 'DeleteObject'):
                            obj.DeleteObject()
                        elif hasattr(obj, 'delete'):
                            obj.delete()
                    elif obj_type == 'pen':
                        if hasattr(obj, 'DeleteObject'):
                            obj.DeleteObject()
                        elif hasattr(obj, 'delete'):
                            obj.delete()
                except Exception as e:
                    print(f"Error cleaning up GDI object ({obj_type}): {str(e)}")
            
        except Exception as e:
            print(f"Error drawing person ignore status: {str(e)}")

    def draw_ignored_classes(self, cursor_controller):
        try:
            # Создаем список для отслеживания GDI объектов
            gdi_objects = []
            
            # Параметры блока
            block_width = 200
            line_height = 20
            max_lines = 10  # Максимальное количество строк
            block_height = line_height * (max_lines + 1)  # +1 для заголовка
            block_x = 10
            block_y = 400  # Оригинальная позиция блока
            
            # Цвета
            bg_color = 0x404040  # Серый фон
            title_color = 0xFFFFFF  # Белый для заголовка
            text_color = 0x0000FF  # Красный для игнорируемых классов
            
            # Рисуем фон блока
            brush = win32ui.CreateBrush(win32con.BS_SOLID, bg_color, 0)
            gdi_objects.append(brush)
            self.save_dc.SelectObject(brush)
            self.save_dc.Rectangle((block_x, block_y, block_x + block_width, block_y + block_height))
            
            # Рисуем рамку блока
            pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0xFFFFFF)  # Белая рамка
            gdi_objects.append(pen)
            self.save_dc.SelectObject(pen)
            self.save_dc.Rectangle((block_x, block_y, block_x + block_width, block_y + block_height))
            
            # Рисуем заголовок
            self.save_dc.SetTextColor(title_color)
            self.save_dc.TextOut(block_x + 10, block_y + 10, "IGNORED OBJECTS:")
            
            # Рисуем список игнорируемых классов
            y_offset = block_y + 10 + line_height
            
            if hasattr(cursor_controller, 'ignored_classes') and cursor_controller.ignored_classes:
                self.save_dc.SetTextColor(text_color)
                for i, class_name in enumerate(cursor_controller.ignored_classes):
                    if i >= max_lines - 1:  # -1 для заголовка
                        # Если список слишком длинный, показываем многоточие
                        self.save_dc.TextOut(block_x + 10, y_offset, "...")
                        break
                        
                    self.save_dc.TextOut(block_x + 10, y_offset, class_name)
                    y_offset += line_height
            else:
                self.save_dc.SetTextColor(text_color)
                self.save_dc.TextOut(block_x + 10, y_offset, "None")
                
            # Очищаем ресурсы
            for obj in gdi_objects:
                try:
                    obj.DeleteObject()
                except:
                    pass
                
        except Exception as e:
            print(f"Error drawing ignored classes: {str(e)}")

    def update_info(self, cursor_pos, target_pos, distance, movement, detected_objects=None, fps=0, perf_stats=None, speed=0, direction=0, cursor_controller=None):
        current_time = time.time()
        if current_time - self.last_update_time < self.update_interval:
            return
        self.last_update_time = current_time
        
        # Список для отслеживания созданных GDI объектов
        gdi_objects = []
        
        try:
            # Заполняем фон с прозрачностью - используем RGBA формат
            # Создаем полупрозрачный темно-серый цвет
            # (R, G, B, A) где A - это уровень прозрачности (0-255)
            self.save_dc.FillSolidRect((0, 0, self.screen_width, self.screen_height), 0x00000000)  # Полностью прозрачный фон
            
            # Затем поверх рисуем полупрозрачную темно-серую подложку для элементов интерфейса
            brush = win32ui.CreateBrush(win32con.BS_SOLID, 0x202020, 0)
            gdi_objects.append(('brush', brush))
            alpha_pen = win32ui.CreatePen(win32con.PS_SOLID, 1, 0x202020)
            gdi_objects.append(('pen', alpha_pen))
            
            self.save_dc.SelectObject(brush)
            self.save_dc.SelectObject(alpha_pen)
            
            # Рисуем полупрозрачные области для интерфейса
            # Область заголовка
            self.save_dc.Rectangle((0, 0, self.screen_width, 300))
            
            # Области для элементов управления и информации
            self.save_dc.Rectangle((460, 50, 460 + 240, 50 + 240))  # Зона кнопок
            self.save_dc.Rectangle((100, 60, 450, 520))  # Зона статистики
            
            # Добавляем название программы и версию в центре верхней части экрана
            title_text = "Reign of Bots"
            version_text = "v0.026"
            
            # Используем Arial italic для заголовка, красный цвет, увеличиваем размер шрифта
            title_font = win32ui.CreateFont({
                'name': 'Arial',
                'height': 80,  # Значительно увеличиваем размер шрифта для лучшей видимости
                'weight': win32con.FW_BOLD,
                'italic': True,
                'charset': win32con.ANSI_CHARSET
            })
            gdi_objects.append(('font', title_font))
            
            # Сначала выбираем шрифт
            self.save_dc.SelectObject(title_font)
            
            # Затем устанавливаем цвет
            self.save_dc.SetTextColor(0x0000FF)  # Ярко-красный цвет
            
            # Теперь можем получить размеры текста
            title_width = self.save_dc.GetTextExtent(title_text)[0]
            title_height = 80  # Соответствует размеру шрифта
            center_x = (self.screen_width - title_width) // 2
            title_y = 100 - title_height // 2  # Смещаем заголовок на 100 пикселей выше
            
            # Рисуем заголовок ярко-красным цветом
            self.save_dc.SelectObject(title_font)
            self.save_dc.SetTextColor(0x0000FF)  # Ярко-красный цвет
            self.save_dc.TextOut(center_x, title_y, title_text)
            
            # Добавляем версию под заголовком маленьким текстом
            version_font = win32ui.CreateFont({
                'name': 'Consolas',
                'height': 14,  # Маленький размер текста
                'weight': win32con.FW_NORMAL,
                'charset': win32con.ANSI_CHARSET
            })
            gdi_objects.append(('font', version_font))
            
            self.save_dc.SelectObject(version_font)
            version_width = self.save_dc.GetTextExtent(version_text)[0]
            self.save_dc.SetTextColor(0xFFFFFF)  # Белый текст для версии
            self.save_dc.TextOut((self.screen_width - version_width) // 2, title_y + 70, version_text)
            
            # Возвращаемся к основному шрифту для остального интерфейса
            self.save_dc.SelectObject(self.font)
            
            if cursor_controller:
                self.draw_crosshair(cursor_controller)
                self.draw_following_status(cursor_controller)
                self.draw_mode_status(cursor_controller)
                self.draw_attack_status(cursor_controller)
                self.draw_person_ignore_status(cursor_controller)  # Добавляем индикатор игнорирования Persons
                
                # Добавляем статус информации про клавишу W и расстояние
                try:
                    # Позиция и размеры блока информации
                    info_width = 300
                    info_height = 120
                    info_x = 460  # Смещаем левее с 600 до 460
                    info_y = 290  # Располагаем под кнопкой игнорирования Person (было 240)
                    
                    # Цвета для блока
                    bg_color = 0x404040  # Серый фон
                    text_color = 0xFFFFFF  # Белый текст
                    highlight_color = 0x00FF00  # Зеленый для выделения
                    warning_color = 0x0000FF  # Красный для предупреждений
                    
                    # Рисуем фон блока
                    brush = win32ui.CreateBrush(win32con.BS_SOLID, bg_color, 0)
                    gdi_objects.append(('brush', brush))
                    self.save_dc.SelectObject(brush)
                    self.save_dc.Rectangle((info_x, info_y, info_x + info_width, info_y + info_height))
                    
                    # Рисуем рамку блока
                    pen = win32ui.CreatePen(win32con.PS_SOLID, 2, 0xFFFFFF)  # Белая рамка
                    gdi_objects.append(('pen', pen))
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
                    try:
                        if obj['type'] == 'body':
                            if self.draw_skeleton_enabled:
                                self.draw_skeleton(obj['landmarks'], obj['color'])
                            if 'box' in obj:
                                self.draw_bounding_box(obj['box'], obj['color'], obj.get('class', None), obj.get('distance', None))
                        elif obj['type'] == 'object':
                            if 'box' in obj:
                                # Добавляем метку над боксом с информацией о классе и расстоянии
                                box = obj['box']
                                color = obj['color']
                                
                                # Проверяем, что box содержит 4 элемента
                                if len(box) != 4:
                                    print(f"Invalid box format: {box}")
                                    continue
                                    
                                # Проверяем, что color содержит 3 элемента
                                if len(color) != 3:
                                    print(f"Invalid color format: {color}")
                                    color = (255, 255, 255)  # Устанавливаем белый цвет по умолчанию
                                
                                # Рисуем бокс
                                self.draw_bounding_box(box, color, obj.get('class', None), obj.get('distance', None))
                                
                                # Если объект является целевым, рисуем дополнительно подсветку
                                if obj.get('is_target', False):
                                    # Рисуем дополнительную рамку для выделения цели
                                    min_x, min_y, max_x, max_y = box
                                    pen = win32ui.CreatePen(win32con.PS_SOLID, 3, 0x00FFFF)  # Голубая рамка
                                    gdi_objects.append(('pen', pen))
                                    self.save_dc.SelectObject(pen)
                                    self.save_dc.Rectangle((min_x-5, min_y-5, max_x+5, max_y+5))
                                    
                                    # Добавляем текст "TARGET"
                                    self.save_dc.SetTextColor(0x00FFFF)  # Голубой текст
                                    self.save_dc.TextOut(min_x, max_y + 10, "[TARGET]")
                    except Exception as e:
                        print(f"Error drawing object: {e}")
                        import traceback
                        traceback.print_exc()
            
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
                threshold_text = f"Thresholds: Press>{1.9}m, Release<{1.8}m"
                self.save_dc.TextOut(110, 190, threshold_text)
            
            # Счетчики производительности
            if perf_stats:
                self.save_dc.SetTextColor(0x00FF00)
                text = "Performance (ms):\n"
                text += "Component        Current    Avg\n"
                text += "----------------------------\n"
                
                try:
                    for name, counter in perf_stats.items():
                        short_name = {
                            'capture': 'Capture',
                            'process': 'Process',
                            'detection': 'Detect',
                            'drawing': 'Draw',
                            'overlay': 'Overlay',
                            'cursor': 'Cursor'
                        }.get(name, name)
                            
                        try:
                            current_ms = round(counter.current_time * 1000, 1)
                            avg_ms = round(counter.avg_time * 1000, 1)
                            current_ms = min(max(current_ms, 0), 9999.9)
                            avg_ms = min(max(avg_ms, 0), 9999.9)
                            text += f"{short_name:<12} {current_ms:>8.1f} {avg_ms:>8.1f}\n"
                        except Exception as e:
                            print(f"Error formatting perf stat for {name}: {str(e)}")
                            text += f"{short_name:<12} {"error":>8} {"error":>8}\n"
                    
                    self.save_dc.DrawText(
                        text,
                        (110, 210, 460, 490),
                        win32con.DT_LEFT | win32con.DT_TOP
                    )
                except Exception as e:
                    print(f"Error drawing performance stats: {str(e)}")
                    
            self.mfc_dc.BitBlt(
                (0, 0), (self.screen_width, self.screen_height),
                self.save_dc,
                (0, 0),
                win32con.SRCCOPY
            )
            
            # Используем UpdateLayeredWindow вместо SetLayeredWindowAttributes
            try:
                # Создаем источник DC
                srcdc = self.save_dc.GetSafeHdc()
                
                # Параметры смешивания - используем 150 для общей прозрачности (было 255) 
                # и AC_SRC_ALPHA, чтобы учитывать альфа-канал пикселей
                blend_function = (win32con.AC_SRC_OVER, 0, 150, win32con.AC_SRC_ALPHA)
                
                # Координаты
                pt_src = (0, 0)
                pt_dst = (0, 0)
                
                # Размер
                size = (self.screen_width, self.screen_height)
                
                # Вызываем UpdateLayeredWindow
                win32gui.UpdateLayeredWindow(
                    self.hwnd,
                    win32gui.GetDC(0),  # Используем DC экрана
                    pt_dst,
                    size,
                    srcdc,
                    pt_src,
                    0,
                    blend_function,
                    win32con.ULW_ALPHA
                )
            except Exception as e:
                print(f"Error in UpdateLayeredWindow: {e}")
            
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
        finally:
            # Освобождаем все созданные GDI объекты
            for obj_type, obj in gdi_objects:
                try:
                    if obj_type == 'brush':
                        if hasattr(obj, 'DeleteObject'):
                            obj.DeleteObject()
                        elif hasattr(obj, 'delete'):
                            obj.delete()
                    elif obj_type == 'pen':
                        if hasattr(obj, 'DeleteObject'):
                            obj.DeleteObject()
                        elif hasattr(obj, 'delete'):
                            obj.delete()
                    elif obj_type == 'font':
                        # Для шрифтов нет явного метода удаления, они освобождаются автоматически
                        pass
                except Exception as e:
                    print(f"Error cleaning up GDI object ({obj_type}): {str(e)}")

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
    def __init__(self, process_variance=0.0001, measurement_variance=0.1):  # Уменьшаем process_variance для более сильного сглаживания
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
        
        # Список игнорируемых типов объектов (не будут выбираться в качестве цели)
        self.ignored_classes = DEFAULT_IGNORED_CLASSES.copy()
        
        # Фильтры Калмана для координат рамки с более сильным сглаживанием
        self.kalman_x_min = KalmanFilter(process_variance=0.00001, measurement_variance=0.3)  # Уменьшаем process_variance для более сильного сглаживания
        self.kalman_y_min = KalmanFilter(process_variance=0.00001, measurement_variance=0.3)
        self.kalman_x_max = KalmanFilter(process_variance=0.00001, measurement_variance=0.3)
        self.kalman_y_max = KalmanFilter(process_variance=0.00001, measurement_variance=0.3)
        self.filtered_box = None
        
        # Добавляем фильтры для размеров рамки
        self.kalman_width = KalmanFilter(process_variance=0.00001, measurement_variance=0.3)
        self.kalman_height = KalmanFilter(process_variance=0.00001, measurement_variance=0.3)
        
        # Добавляем фильтры для центра рамки
        self.kalman_center_x = KalmanFilter(process_variance=0.00001, measurement_variance=0.3)
        self.kalman_center_y = KalmanFilter(process_variance=0.00001, measurement_variance=0.3)
        
        # Добавляем историю размеров для дополнительного сглаживания
        self.width_history = deque(maxlen=5)
        self.height_history = deque(maxlen=5)
        
        # Параметры движения вперед
        self.w_key_pressed = False
        self.manual_key_pressed = False  # Флаг для отслеживания ручного нажатия клавиши W
        self.distance_filter = KalmanFilter(process_variance=0.003, measurement_variance=0.05)  # Увеличиваем process_variance и уменьшаем measurement_variance для более быстрой реакции
        self.last_distance_check_time = 0
        self.distance_check_interval = 0.05  # Уменьшаем интервал проверки до 50 мс для более быстрой реакции
        self.distance_threshold_press = 1.9  # Порог в метрах для нажатия W
        self.distance_threshold_release = 1.8  # Порог в метрах для отпускания W
        self.target_lost_timeout = 0.3  # Уменьшаем время до признания цели потерянной
        
        # Добавляем атрибут для отслеживания последнего расстояния
        self.last_distance = 0.0
        
        # Добавляем константы для оптимизации
        self.STOP_THRESHOLD = 2  # Порог остановки для абсолютного режима
        self.RELATIVE_STOP_THRESHOLD = 80  # Порог остановки для относительного режима
        self.SLOW_FACTOR = 100  # Фактор замедления для абсолютного режима
        self.RELATIVE_SLOW_FACTOR = 500  # Фактор замедления для относительного режима
        self.VIRTUAL_TARGET_SHIFT = 5  # Шаг смещения виртуальной цели
        self.MIN_MOVE = 0.01  # Минимальное движение для абсолютного режима
        self.RELATIVE_MIN_MOVE = 0.1  # Минимальное движение для относительного режима
        
        # Параметры для сглаживания движения
        self.movement_history = deque(maxlen=5)  # История движений для сглаживания
        self.last_move_time = time.time()
        self.move_interval = 1/500  # 500 Hz для более плавного движения
        self.velocity_x = 0
        self.velocity_y = 0
        self.velocity_smoothing = 0.3  # Фактор сглаживания скорости
        
        # Параметры для относительного режима
        self.RELATIVE_STOP_THRESHOLD = 80
        self.RELATIVE_SLOW_FACTOR = 500
        self.RELATIVE_MIN_MOVE = 0.1
        self.RELATIVE_MAX_VELOCITY = 50  # Максимальная скорость движения
        self.RELATIVE_ACCELERATION = 0.5  # Ускорение/замедление
        
        # Параметры для экспоненциального сглаживания
        self.smoothing_factor = 0.1  # Чем меньше, тем сильнее сглаживание
        self.smoothed_min_x = None
        self.smoothed_min_y = None
        self.smoothed_max_x = None
        self.smoothed_max_y = None
    
    def calculate_3d_position(self, landmarks, screen_width, screen_height):
        """
        УСТАРЕВШИЙ МЕТОД. Используйте YOLOPersonDetector.calculate_3d_position вместо него.
        Оставлен для обратной совместимости.
        """
        print("Warning: Calling deprecated method CursorController.calculate_3d_position")
        # Возвращаем пустые значения
        return None, None, None, 0.0, 0.0

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
        
    def toggle_class_ignore(self, class_name):
        """Переключает игнорирование определенного типа объекта"""
        # Проверяем, является ли class_name числом (ID класса)
        try:
            class_id = int(class_name)
            # Если это ID класса, получаем его название
            if class_id in COCO_CLASSES:
                class_name = COCO_CLASSES[class_id]
            else:
                print(f"Unknown class ID: {class_id}")
                return False
        except ValueError:
            # Если это не число, то считаем, что это название класса
            pass
            
        # Проверяем, есть ли класс в списке игнорируемых
        if class_name.lower() in [cls.lower() for cls in self.ignored_classes]:
            # Удаляем класс из списка игнорируемых (с сохранением регистра)
            for i, cls in enumerate(self.ignored_classes):
                if cls.lower() == class_name.lower():
                    self.ignored_classes.pop(i)
                    print(f"Now tracking '{class_name}' objects")
                    break
            return False  # Класс теперь не игнорируется
        else:
            # Добавляем класс в список игнорируемых
            self.ignored_classes.append(class_name)
            print(f"Now ignoring '{class_name}' objects")
            return True  # Класс теперь игнорируется
        
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
        
        # Сохраняем расстояние для отображения в любом случае
        if distance is not None and distance > 0:
            self.last_distance = distance
        
        # Проверка на потерю цели
        if not box:
            if self.w_key_pressed and self.following_enabled and not self.manual_key_pressed:
                try:
                    keyboard.release('w')
                    self.w_key_pressed = False
                    time.sleep(0.01)
                except Exception as e:
                    print(f"Error releasing W key: {e}")
            return
        
        # Проверка валидности расстояния
        if distance is None or distance <= 0:
            return
        
        # Применяем экспоненциальное сглаживание к координатам рамки
        min_x, min_y, max_x, max_y = box
        
        if self.smoothed_min_x is None:
            self.smoothed_min_x = min_x
            self.smoothed_min_y = min_y
            self.smoothed_max_x = max_x
            self.smoothed_max_y = max_y
        else:
            self.smoothed_min_x = (1 - self.smoothing_factor) * self.smoothed_min_x + self.smoothing_factor * min_x
            self.smoothed_min_y = (1 - self.smoothing_factor) * self.smoothed_min_y + self.smoothing_factor * min_y
            self.smoothed_max_x = (1 - self.smoothing_factor) * self.smoothed_max_x + self.smoothing_factor * max_x
            self.smoothed_max_y = (1 - self.smoothing_factor) * self.smoothed_max_y + self.smoothing_factor * max_y
        
        # Обновляем box с использованием сглаженных значений
        box = (self.smoothed_min_x, self.smoothed_min_y, self.smoothed_max_x, self.smoothed_max_y)
        
        # Применяем фильтр Калмана к координатам рамки
        filtered_min_x = self.kalman_x_min.update(min_x)
        filtered_min_y = self.kalman_y_min.update(min_y)
        filtered_max_x = self.kalman_x_max.update(max_x)
        filtered_max_y = self.kalman_y_max.update(max_y)
        
        # Сохраняем отфильтрованные данные
        self.filtered_box = (filtered_min_x, filtered_min_y, filtered_max_x, filtered_max_y)
        self.last_box = self.filtered_box
        
        # Вычисляем центр цели
        target_x = int((filtered_min_x + filtered_max_x) / 2)
        target_y = int((filtered_min_y + filtered_max_y) / 2)
        
        # Применяем фильтр к расстоянию
        filtered_distance = self.distance_filter.update(distance)
        self.last_distance = filtered_distance
        
        # Управление клавишей W
        if self.following_enabled:
            try:
                manual_w_pressed = keyboard.is_pressed('w')
                if manual_w_pressed and not self.w_key_pressed:
                    self.manual_key_pressed = True
                    return
                if not manual_w_pressed and self.manual_key_pressed:
                    self.manual_key_pressed = False
                
                # Если пользователь не нажимает W вручную и следование включено
                if not self.manual_key_pressed:
                    # Используем фильтрованное расстояние для более стабильного поведения
                    # Если расстояние больше 1.9м и клавиша W не нажата - нажимаем W
                    if filtered_distance > 1.9 and not self.w_key_pressed:
                        keyboard.press('w')
                        self.w_key_pressed = True
                        time.sleep(0.01)  # Небольшая пауза после нажатия
                    # Если расстояние меньше 1.8м и клавиша W нажата - отпускаем W
                    elif filtered_distance < 1.8 and self.w_key_pressed:
                        keyboard.release('w')
                        self.w_key_pressed = False
                        time.sleep(0.01)  # Небольшая пауза после отпускания
            except Exception as e:
                print(f"Error in auto W key handling: {str(e)}")
        else:
            if self.w_key_pressed and not self.manual_key_pressed:
                try:
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
        """Обновление в относительном режиме с оптимизированными вычислениями"""
        if not self.last_box:
            return
            
        # Если управление курсором отключено, просто выходим
        if DISABLE_CURSOR_CONTROL:
            return
        
        # Получаем разницу между целью и центром экрана
        dx = self.target_x - self.center_x
        dy = self.target_y - self.center_y
        
        # Вычисляем расстояние до цели
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Если близко к цели - останавливаемся
        if distance <= self.RELATIVE_STOP_THRESHOLD:
            return
        
        # Нормализуем направление
        if distance > 0:
            norm_dx = dx / distance
            norm_dy = dy / distance
        else:
            return
        
        # Вычисляем шаг движения
        move_x = norm_dx * 100 / self.RELATIVE_SLOW_FACTOR
        move_y = norm_dy * 100 / self.RELATIVE_SLOW_FACTOR
        
        # Обеспечиваем минимальное движение
        if abs(move_x) < self.RELATIVE_MIN_MOVE and norm_dx != 0:
            move_x = self.RELATIVE_MIN_MOVE if norm_dx > 0 else -self.RELATIVE_MIN_MOVE
        
        if abs(move_y) < self.RELATIVE_MIN_MOVE and norm_dy != 0:
            move_y = self.RELATIVE_MIN_MOVE if norm_dy > 0 else -self.RELATIVE_MIN_MOVE
        
        # Округляем для mouse_event
        move_amount_x = int(move_x * 10)
        move_amount_y = int(move_y * 10)
        
        # Гарантируем минимальное движение
        if move_amount_x == 0 and norm_dx != 0:
            move_amount_x = 1 if norm_dx > 0 else -1
        if move_amount_y == 0 and norm_dy != 0:
            move_amount_y = 1 if norm_dy > 0 else -1
        
        # Сдвигаем виртуальную цель навстречу движению
        self.target_x -= move_amount_x * self.VIRTUAL_TARGET_SHIFT
        self.target_y -= move_amount_y * self.VIRTUAL_TARGET_SHIFT
        
        # Перемещаем курсор
        win32api.mouse_event(
            win32con.MOUSEEVENTF_MOVE, 
            move_amount_x, move_amount_y, 
            0, 0
        )
        
        # Возвращаем курсор в центр
        win32api.SetCursorPos((self.center_x, self.center_y))
    
    def _update_absolute_mode(self):
        """Обновление в абсолютном режиме с оптимизированными вычислениями"""
        # Если управление курсором отключено, просто выходим
        if DISABLE_CURSOR_CONTROL:
            return
            
        current_x, current_y = win32api.GetCursorPos()
        
        # Вычисляем разницу до цели
        dx = self.target_x - current_x
        dy = self.target_y - current_y
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Если достигли цели - останавливаемся
        if distance <= self.STOP_THRESHOLD:
            return
        
        # Нормализуем направление
        if distance > 0:
            norm_dx = dx / distance
            norm_dy = dy / distance
        else:
            return
        
        # Основной расчет движения
        move_x = dx * self.smoothing_factor / self.SLOW_FACTOR
        move_y = dy * self.smoothing_factor / self.SLOW_FACTOR
        
        # Гарантируем минимальное движение
        if abs(move_x) < self.MIN_MOVE and norm_dx != 0:
            move_x = self.MIN_MOVE if norm_dx > 0 else -self.MIN_MOVE
        
        if abs(move_y) < self.MIN_MOVE and norm_dy != 0:
            move_y = self.MIN_MOVE if norm_dy > 0 else -self.MIN_MOVE
        
        # Вычисляем новую позицию
        new_x = int(current_x + move_x)
        new_y = int(current_y + move_y)
        
        # Предотвращаем "прилипание"
        if new_x == current_x and dx != 0:
            new_x += 1 if dx > 0 else -1
        if new_y == current_y and dy != 0:
            new_y += 1 if dy > 0 else -1
        
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
    # Словарь с названиями частей тела (не используется с YOLO)
    BODY_PARTS = {}

    @staticmethod
    def draw_landmarks(frame, landmarks, connections, color, thickness=2, circle_radius=4):
        """Эта функция не используется с YOLO, оставлена для совместимости"""
        pass

    @staticmethod
    def draw_bounding_box(frame, box, color, padding=10, thickness=2):
        """Рисует улучшенную рамку вокруг набора точек"""
        if not box:
            return None
            
        min_x, min_y, max_x, max_y = box

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
    hwindc = None
    srcdc = None
    memdc = None
    bmp = None
    
    try:
        # Пробуем получить DC с несколькими попытками
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                hwindc = win32gui.GetWindowDC(win32gui.GetDesktopWindow())
                if hwindc:
                    srcdc = win32ui.CreateDCFromHandle(hwindc)
                    if srcdc:
                        memdc = srcdc.CreateCompatibleDC()
                        bmp = win32ui.CreateBitmap()
                        bmp.CreateCompatibleBitmap(srcdc, screen_width, screen_height)
                        memdc.SelectObject(bmp)
                        break
            except Exception as e:
                if attempt < max_attempts - 1:
                    print(f"Attempt {attempt+1} failed: {str(e)}. Retrying...")
                    time.sleep(0.1)  # Небольшая пауза перед следующей попыткой
                else:
                    print(f"All {max_attempts} attempts to create DC failed: {str(e)}")
                    raise
        
        if not hwindc or not srcdc or not memdc or not bmp:
            print("Failed to initialize screen capture resources")
            return None
        
        # Копируем изображение с экрана
        memdc.BitBlt((0, 0), (screen_width, screen_height), srcdc, (0, 0), win32con.SRCCOPY)
        
        # Конвертируем в numpy array
        signedIntsArray = bmp.GetBitmapBits(True)
        img = np.frombuffer(signedIntsArray, dtype='uint8')
        img.shape = (screen_height, screen_width, 4)
        
        # Конвертируем в BGR для OpenCV
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except Exception as e:
        print(f"Error in screen capture: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Освобождаем ресурсы
        try:
            if srcdc:
                srcdc.DeleteDC()
            if memdc:
                memdc.DeleteDC()
            if hwindc:
                win32gui.ReleaseDC(win32gui.GetDesktopWindow(), hwindc)
            if bmp:
                win32gui.DeleteObject(bmp.GetHandle())
        except Exception as e:
            print(f"Error cleaning up screen capture resources: {str(e)}")

class YOLOPersonDetector:
    """Класс для обнаружения людей с помощью YOLOv8"""
    def __init__(self, model=None, conf=0.5):
        self.model = model
        self.conf = conf
        self.last_frame = None
        self.last_results = None
        self.lock = Thread()
        
        # Принудительно используем CPU
        self.cuda_available = False
        self.device = "cpu"
        print(f"YOLOPersonDetector initialized on {self.device} (CUDA disabled)")
        
        # Убедимся, что модель работает на правильном устройстве
        if self.model:
            try:
                self.model.to(self.device)
                print(f"Model moved to {self.device}")
            except Exception as e:
                print(f"Warning: Could not set device to {self.device}: {str(e)}")
                
        print(f"YOLOPersonDetector initialized on {self.device}")
        
    def detect(self, frame):
        """Обнаружение людей на кадре"""
        if frame is None or self.model is None:
            return None
            
        # Запускаем детекцию
        try:
            # Масштабируем кадр до меньшего размера для ускорения
            original_height, original_width = frame.shape[:2]
            target_width = 640
            target_height = int(original_height * (target_width / original_width))
            resized_frame = cv2.resize(frame, (target_width, target_height))
            
            # Замеряем время инференса
            import time
            start_time = time.time()
            
            # Используем выбранное устройство
            results = self.model(resized_frame, conf=self.conf, classes=0, device=self.device)  # class 0 = person
            
            # Рассчитываем время работы
            inference_time = (time.time() - start_time) * 1000  # в мс
            print(f"Detection time: {inference_time:.2f}ms on {self.device}")
            
            self.last_results = results
            self.last_frame = frame
            
            # Отладочная информация о размере и времени
            #for r in results:
            #    print(f"Detection time: {r.speed['inference']:.1f}ms, shape: {resized_frame.shape}")
                
            return results
        except Exception as e:
            print(f"Error in YOLO detection: {str(e)}")
            return None
            
    def detect_all_objects(self, frame):
        """Обнаружение всех объектов на кадре"""
        if frame is None or self.model is None:
            return None
            
        # Запускаем детекцию
        try:
            # Масштабируем кадр до меньшего размера для ускорения
            original_height, original_width = frame.shape[:2]
            target_width = 640
            target_height = int(original_height * (target_width / original_width))
            resized_frame = cv2.resize(frame, (target_width, target_height))
            
            # Замеряем время инференса
            import time
            start_time = time.time()
            
            # Принудительно используем CPU режим
            results = self.model(resized_frame, conf=self.conf, device="cpu", verbose=False)
            
            # Рассчитываем время работы
            inference_time = (time.time() - start_time) * 1000  # в мс
            print(f"All objects detection time: {inference_time:.2f}ms on CPU")
            
            self.last_results = results
            self.last_frame = frame
            
            return results
        except Exception as e:
            print(f"Error in YOLO all-objects detection: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
            
    def get_all_objects(self, results=None):
        """
        Получает рамки всех обнаруженных объектов
        
        Returns:
            list: список объектов с информацией о типе, местоположении и размере
        """
        if results is None:
            results = self.last_results
            
        if results is None or len(results) == 0:
            return []
            
        # Используем глобальный словарь классов COCO
        coco_classes = COCO_CLASSES
            
        # Находим все объекты
        objects = []
        for r in results:
            if hasattr(r, 'boxes'):
                for box in r.boxes:
                    class_id = int(box.cls[0])
                    class_name = coco_classes.get(class_id, f'Unknown ({class_id})')
                    
                    # Получаем координаты в процентах от размера кадра (0-1)
                    # Это позволяет масштабировать их обратно к оригинальному размеру
                    xyxy_normalized = box.xyxyn[0].tolist() 
                    
                    # Если у нас есть оригинальный кадр, масштабируем координаты
                    if self.last_frame is not None:
                        height, width = self.last_frame.shape[:2]
                        x1 = int(xyxy_normalized[0] * width)
                        y1 = int(xyxy_normalized[1] * height)
                        x2 = int(xyxy_normalized[2] * width)
                        y2 = int(xyxy_normalized[3] * height)
                    else:
                        # Используем абсолютные координаты, если нет оригинального кадра
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        
                    conf = float(box.conf[0])
                    area = (x2 - x1) * (y2 - y1)
                    
                    # Создаем объект с информацией
                    objects.append({
                        'box': (x1, y1, x2, y2),
                        'area': area,
                        'confidence': conf,
                        'class_id': class_id,
                        'class_name': class_name
                    })
        
        # Сортируем по площади (от большего к меньшему)
        objects.sort(key=lambda x: x['area'], reverse=True)
        return objects
            
    def get_person_box(self, results=None):
        """
        Получает рамку самого большого человека на кадре
        
        Returns:
            tuple: (min_x, min_y, max_x, max_y) или None если люди не обнаружены
        """
        if results is None:
            results = self.last_results
            
        if results is None or len(results) == 0:
            return None
            
        # Находим все боксы людей
        boxes = []
        for r in results:
            if hasattr(r, 'boxes'):
                for box in r.boxes:
                    if box.cls[0] == 0:  # класс 0 - человек
                        # Получаем координаты в процентах от размера кадра (0-1)
                        # Это позволяет масштабировать их обратно к оригинальному размеру
                        xyxy_normalized = box.xyxyn[0].tolist() 
                        
                        # Если у нас есть оригинальный кадр, масштабируем координаты
                        if self.last_frame is not None:
                            height, width = self.last_frame.shape[:2]
                            x1 = int(xyxy_normalized[0] * width)
                            y1 = int(xyxy_normalized[1] * height)
                            x2 = int(xyxy_normalized[2] * width)
                            y2 = int(xyxy_normalized[3] * height)
                        else:
                            # Используем абсолютные координаты, если нет оригинального кадра
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            
                        conf = float(box.conf[0])
                        area = (x2 - x1) * (y2 - y1)
                        boxes.append((x1, y1, x2, y2, area, conf))
        
        if not boxes:
            return None
            
        # Выбираем бокс с наибольшей площадью
        boxes.sort(key=lambda x: x[4], reverse=True)
        x1, y1, x2, y2, _, _ = boxes[0]
        
        return (x1, y1, x2, y2)
    
    def calculate_3d_position(self, box, screen_width, screen_height):
        """
        Вычисляет экранную позицию цели и примерное расстояние в метрах
        на основе размера рамки с учетом законов перспективы
        """
        if box is None:
            return None, None, None, 0.0, 0.0
            
        min_x, min_y, max_x, max_y = box
        
        # Центр цели
        target_x = (min_x + max_x) // 2
        target_y = (min_y + max_y) // 2
        
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
        
        # Расчет скорости и направления не имеет сильного смысла
        # для отдельного кадра, поэтому возвращаем нули
        speed = 0.0
        direction = 0.0
        
        return target_x, target_y, distance, speed, direction

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
        
        # Детекция с помощью YOLO
        perf_monitor.start('detection')
        
        # Инициализируем детектор при первом вызове
        if not hasattr(process_frame, "detector"):
            process_frame.detector = YOLOPersonDetector(model=yolo_model, conf=0.4)
        
        # Запускаем детекцию всех объектов, а не только людей
        results = process_frame.detector.detect_all_objects(frame)
        
        # Получаем все объекты
        all_objects = process_frame.detector.get_all_objects(results)
        
        perf_monitor.stop('detection')
        
        # Список для хранения всех найденных объектов
        detected_objects = []
        target_x, target_y, target_distance, speed, direction = None, None, None, 0.0, 0.0
        target_box = None
        
        # Если найдены объекты, обработаем их
        if all_objects:
            # Сначала выведем информацию о количестве найденных объектов
            print(f"Detected {len(all_objects)} objects")
            
            # Добавляем все объекты в список объектов для отображения
            for obj in all_objects:
                try:
                    obj_box = obj['box']
                    obj_class = obj['class_name']
                    
                    # Вычисляем 3D позицию объекта
                    obj_x, obj_y, obj_distance, obj_speed, obj_direction = process_frame.detector.calculate_3d_position(
                        obj_box, 
                        screen_width, 
                        screen_height
                    )
                    
                    # Определяем цвет в зависимости от класса
                    color_map = {
                        'person': (0, 255, 0),  # Зеленый для людей
                        'car': (0, 0, 255),     # Красный для машин
                        'dog': (255, 255, 0),   # Голубой для собак
                        'cat': (255, 0, 255),   # Розовый для кошек
                    }
                    color = color_map.get(obj_class.lower(), (255, 255, 255))  # Белый для остальных
                    
                    # Сохраняем информацию об объекте
                    detected_objects.append({
                        'type': 'object',
                        'class': obj_class,
                        'color': color,
                        'box': obj_box,
                        'distance': obj_distance,
                        'position': (obj_x, obj_y)
                    })
                except Exception as e:
                    print(f"Error processing object: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Определяем целевой объект в зависимости от режима
            if cursor_controller.following_enabled:
                # Режим следования за ближайшим объектом
                # Фильтруем объекты, исключая те, которые находятся в списке игнорируемых
                valid_objects = [obj for obj in detected_objects 
                               if obj['class'].lower() not in [cls.lower() for cls in cursor_controller.ignored_classes]]
                
                if valid_objects:
                    # Выбираем ближайший из допустимых объектов
                    nearest_object = min(valid_objects, key=lambda obj: obj['distance'])
                    target_box = nearest_object['box']
                    target_x, target_y = nearest_object['position']
                    target_distance = nearest_object['distance']
                    target_class = nearest_object['class']
                    
                    # Отмечаем ближайший объект как целевой
                    for obj in detected_objects:
                        if obj['box'] == target_box:
                            obj['is_target'] = True
                        else:
                            obj['is_target'] = False
                else:
                    # Нет допустимых объектов
                    target_box = None
                    target_x, target_y, target_distance = None, None, None
            else:
                # Фильтруем объекты, исключая те, которые находятся в списке игнорируемых
                valid_objects = [obj for obj in detected_objects 
                               if obj['class'].lower() not in [cls.lower() for cls in cursor_controller.ignored_classes]]
                
                if not valid_objects:
                    # Нет допустимых объектов
                    target_box = None
                    target_x, target_y, target_distance = None, None, None
                else:
                    # Если следование отключено, смотрим на самый большой объект (человека, если есть)
                    people = [obj for obj in valid_objects if obj['class'].lower() == 'person']
                    if people:
                        # Находим самого большого человека по площади бокса
                        largest_person = max(people, key=lambda obj: 
                            (obj['box'][2] - obj['box'][0]) * (obj['box'][3] - obj['box'][1]))
                        
                        target_box = largest_person['box']
                        target_x, target_y = largest_person['position']
                        target_distance = largest_person['distance']
                        target_class = largest_person['class']
                        
                        # Отмечаем самого большого человека как целевой
                        for obj in detected_objects:
                            if obj['box'] == target_box:
                                obj['is_target'] = True
                            else:
                                obj['is_target'] = False
                    elif valid_objects:
                        # Если людей нет, берем самый большой допустимый объект
                        largest_object = max(valid_objects, key=lambda obj: 
                            (obj['box'][2] - obj['box'][0]) * (obj['box'][3] - obj['box'][1]))
                        
                        target_box = largest_object['box']
                        target_x, target_y = largest_object['position']
                        target_distance = largest_object['distance']
                        target_class = largest_object['class']
                        
                        # Отмечаем самый большой объект как целевой
                        for obj in detected_objects:
                            if obj['box'] == target_box:
                                obj['is_target'] = True
                            else:
                                obj['is_target'] = False
        else:
            # Нет объектов
            cursor_controller.last_box = None
            target_box = None
        
        # Важно: всегда вызываем handle_auto_movement, передавая текущее расстояние и box (или None)
        cursor_controller.handle_auto_movement(target_distance, target_box)
        
        # Отрисовка результатов и перемещение курсора
        if target_box and target_x is not None and target_y is not None:
            perf_monitor.start('cursor')
            cursor_x, cursor_y = cursor_controller.move_cursor(target_x, target_y)
            perf_monitor.stop('cursor')
            
            # Рисуем рамки объектов в окне отладки
            perf_monitor.start('drawing')
            
            # Рисуем все обнаруженные объекты
            for obj in detected_objects:
                box = obj['box']
                color = obj['color']
                
                # Преобразуем цвет из BGR в RGB
                display_color = (color[2], color[1], color[0])
                
                # Рисуем рамку
                cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), display_color, 2)
                
                # Рисуем информацию о классе и расстоянии
                class_name = obj['class']
                distance = obj['distance']
                text = f"{class_name}: {distance:.2f}m"
                
                # Добавляем текст о выбранной цели
                if obj.get('is_target', False):
                    text += " [TARGET]"
                    # Рисуем более толстую рамку для целевого объекта
                    cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), display_color, 4)
                
                # Размещаем текст над рамкой
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                text_x = box[0]
                text_y = box[1] - 10 if box[1] > 30 else box[1] + 30
                cv2.rectangle(frame, (text_x, text_y - text_size[1] - 10), 
                              (text_x + text_size[0] + 10, text_y), display_color, -1)
                cv2.putText(frame, text, (text_x + 5, text_y - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
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
        
        # Убираем вывод в отдельное окно отладки
        """
        try:
            cv2.imshow('Debug View', frame)
            cv2.waitKey(1)
        except Exception as e:
            print(f"Error showing debug window: {str(e)}")
        """
        
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
        print("Press '\\' to toggle ignoring people (class 0)")
        print("Press 'F1' to exit")
        print("Press '.' to start/stop recording")
        
        # Сообщаем об игнорируемых классах
        if cursor_controller.ignored_classes:
            print("Currently ignoring: " + ', '.join(cursor_controller.ignored_classes))
        
        # Выводим подсказку о том, как игнорировать классы по ID
        print("\nYou can ignore objects by class name or ID. Examples of common classes:")
        print("0: person, 56: chair, 58: potted plant, 62: tv, 57: couch, 74: clock, 73: book")
        print("Use '\\' key to toggle ignoring people (class 0)")
        
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
                elif keyboard.is_pressed('\\'):
                    # Добавляем или удаляем "person" из списка игнорируемых объектов
                    if cursor_controller.toggle_class_ignore("person"):
                        print("Now ignoring people")
                    else:
                        print("Now tracking people")
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