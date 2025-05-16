"""
Модуль для управления курсором мыши.
Предоставляет класс для отслеживания и управления курсором в различных режимах.
"""

import win32api
import win32con
import time
import math
import random
import keyboard
from collections import deque
from threading import Thread

from utils.kalman import KalmanFilter, BoxFilter
from utils.detector import DEFAULT_IGNORED_CLASSES, COCO_CLASSES

class CursorController:
    """
    Класс для управления курсором мыши с поддержкой различных режимов работы:
    - Абсолютный/относительный режим перемещения
    - Автоматическое следование за целью
    - Автоматическая атака (кликание)
    - Фильтрация движений для плавного перемещения
    """
    
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
        self.smoothing_factor = 0.1  # Коэффициент экспоненциального сглаживания движений курсора - чем меньше, тем плавнее движения
        self.sensitivity = 1.0
        self.min_distance = 0.5  # Уменьшаем минимальное расстояние для большей точности
        self.max_speed = 100
        self.move_history = deque(maxlen=5)
        
        # Флаг для отслеживания перемещения курсора в текущем кадре
        self.cursor_moved_this_frame = False
        
        # Параметры высокочастотного обновления
        self.update_interval = 1/500  # 500 Hz
        self.running = True
        self.update_thread = Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        # Параметры состояния
        self.following_enabled = False  # По умолчанию режим следования выключен
        self.cursor_control_enabled = False  # По умолчанию управление мышью выключено
        self.attack_enabled = False
        self.last_attack_time = 0
        self.attack_interval = random.uniform(0.1, 0.3)  # Случайный интервал между кликами
        self.last_position = None
        self.last_box = None
        
        # Список игнорируемых типов объектов (не будут выбираться в качестве цели)
        self.ignored_classes = DEFAULT_IGNORED_CLASSES.copy()
        
        # Используем единый BoxFilter вместо множества фильтров Калмана для координат
        self.box_filter = BoxFilter(process_variance=0.00001, measurement_variance=0.3)
        self.filtered_box = None
        
        # Фильтр для расстояния
        self.distance_filter = KalmanFilter(process_variance=0.003, measurement_variance=0.05)
        self.last_distance_check_time = 0
        self.distance_check_interval = 0.05  # Уменьшаем интервал проверки до 50 мс для более быстрой реакции
        self.distance_threshold_press = 1.9  # Порог в метрах для нажатия W
        self.distance_threshold_release = 1.8  # Порог в метрах для отпускания W
        self.target_lost_timeout = 0.3  # Уменьшаем время до признания цели потерянной
        
        # Параметры движения вперед
        self.w_key_pressed = False
        self.manual_key_pressed = False  # Флаг для отслеживания ручного нажатия клавиши W
        
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
        
        # Переменные для экспоненциального сглаживания координат объекта
        self.smoothed_min_x = None
        self.smoothed_min_y = None
        self.smoothed_max_x = None
        self.smoothed_max_y = None

    def toggle_following(self):
        """Переключает режим следования за целью"""
        self.following_enabled = not self.following_enabled
        return True
        
    def toggle_mode(self):
        """Переключает режим управления мышью (абсолютный/относительный)"""
        self.relative_mode = not self.relative_mode
        return True
        
    def toggle_cursor_control(self):
        """Переключает режим управления курсором мыши (включено/выключено)"""
        self.cursor_control_enabled = not self.cursor_control_enabled
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
        
        # Применяем BoxFilter к координатам рамки
        # Фильтруем только самые необходимые координаты (x_min, y_min)
        # Остальные вычисляются из исходной ширины и высоты
        filtered_box = self.box_filter.update(box)
        
        # Сохраняем отфильтрованные данные
        self.filtered_box = filtered_box
        self.last_box = self.filtered_box
        
        # Вычисляем центр цели после фильтрации
        center = self.box_filter.get_center()
        
        # Создаем локальные переменные для центра цели
        if center:
            tgt_x, tgt_y = center
        else:
            # Если фильтр не вернул центр, вычисляем из исходной рамки
            min_x, min_y, max_x, max_y = box
            tgt_x = int((min_x + max_x) / 2)
            tgt_y = int((min_y + max_y) / 2)
        
        # Применяем фильтр к расстоянию
        filtered_distance = self.distance_filter.update(distance)
        self.last_distance = filtered_distance
        
        # Обновляем глобальные target_x и target_y для использования в других методах
        self.target_x = tgt_x
        self.target_y = tgt_y
        
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
        
        # Устанавливаем целевую позицию курсора только если включено управление курсором
        if self.cursor_control_enabled:
            self.move_cursor(self.target_x, self.target_y)
            # Отмечаем, что курсор уже был перемещен в этом кадре
            self.cursor_moved_this_frame = True
    
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
        if not self.cursor_control_enabled:
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
        if not self.cursor_control_enabled:
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
        """Move cursor to target position"""
        # Если курсор уже перемещен в этом кадре, просто обновляем целевые координаты
        if self.cursor_moved_this_frame:
            self.target_x = target_x
            self.target_y = target_y
            return win32api.GetCursorPos()
        
        # Если управление курсором отключено, только обновляем целевую позицию без перемещения
        if not self.cursor_control_enabled:
            self.target_x = target_x
            self.target_y = target_y
            return win32api.GetCursorPos()
            
        # Применяем абсолютный или относительный режим
        if self.relative_mode:
            # В относительном режиме только устанавливаем цель
            self.target_x = target_x
            self.target_y = target_y
            return win32api.GetCursorPos()
        else:
            # Абсолютный режим - перемещаем курсор напрямую
            current_pos = win32api.GetCursorPos()
            dx = target_x - current_pos[0]
            dy = target_y - current_pos[1]
            
            # Применяем сглаживание к dx и dy
            dx *= self.sensitivity
            dy *= self.sensitivity
            
            # Перемещаем курсор, если разница достаточно большая
            if abs(dx) > 0.5 or abs(dy) > 0.5:
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
            
            # Возвращаем обновленную позицию
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