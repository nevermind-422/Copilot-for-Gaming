"""
Модуль для работы с детектором объектов на основе YOLO.
Предоставляет класс для обнаружения людей и других объектов на изображении.
"""

import cv2
import numpy as np
import math
import time
import torch
from ultralytics import YOLO

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

# Список игнорируемых типов объектов по умолчанию
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

class YOLOPersonDetector:
    """Класс для обнаружения людей и других объектов с помощью YOLOv8"""
    
    def __init__(self, model=None, conf=0.5, device="auto", debug=False):
        """
        Инициализирует детектор объектов.
        
        Args:
            model: Предварительно загруженная модель YOLO
            conf: Порог достоверности для детекции (от 0 до 1)
            device: Устройство для инференса ('cuda', 'cpu' или 'auto')
            debug: Флаг для вывода отладочных сообщений
        """
        self.model = model
        self.conf = conf
        self.last_frame = None
        self.last_results = None
        self.debug = debug
        
        # Определяем устройство для инференса
        self.cuda_available = torch.cuda.is_available()
        if device == "auto":
            self.device = "cuda:0" if self.cuda_available else "cpu"
        else:
            self.device = device
            
        print(f"YOLOPersonDetector initialized on {self.device}")
        
        # Добавляем поддержку пользовательских классов (вне COCO)
        self.custom_classes = {
            80: 'bag',  # Мешок
        }
        
        # Убедимся, что модель работает на правильном устройстве
        if self.model:
            try:
                self.model.to(self.device)
                print(f"Model moved to {self.device}")
                
                # Добавляем пользовательские классы в модель, если их там еще нет
                if hasattr(self.model, 'names'):
                    for class_id, class_name in self.custom_classes.items():
                        if class_id not in self.model.names:
                            print(f"Adding custom class '{class_name}' with ID {class_id} to model names")
                            self.model.names[class_id] = class_name
            except Exception as e:
                print(f"Warning: Could not set device to {self.device}: {str(e)}")
    
    def detect(self, frame):
        """
        Обнаружение людей на кадре.
        
        Args:
            frame: Входное изображение для обработки
            
        Returns:
            Результаты детекции или None в случае ошибки
        """
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
            start_time = time.time()
            
            # Используем CUDA, если доступно
            device = self.device if self.cuda_available else "cpu"
            
            try:
                # Пробуем использовать CUDA
                results = self.model(resized_frame, conf=self.conf, classes=0, device=device)  # class 0 = person
            except Exception as cuda_error:
                print(f"Error using {device} for detection, falling back to CPU: {str(cuda_error)}")
                # Если произошла ошибка с CUDA, используем CPU
                results = self.model(resized_frame, conf=self.conf, classes=0, device="cpu")
            
            # Рассчитываем время работы
            inference_time = (time.time() - start_time) * 1000  # в мс
            if self.debug:
                print(f"Detection time: {inference_time:.2f}ms on {device}")
            
            self.last_results = results
            self.last_frame = frame
                
            return results
        except Exception as e:
            print(f"Error in YOLO detection: {str(e)}")
            return None
            
    def detect_all_objects(self, frame):
        """
        Обнаружение всех объектов на кадре.
        
        Args:
            frame: Входное изображение для обработки
            
        Returns:
            Результаты детекции или None в случае ошибки
        """
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
            start_time = time.time()
            
            # Используем CUDA, если доступно
            device = self.device if self.cuda_available else "cpu"
            
            try:
                # Пробуем использовать CUDA
                results = self.model(resized_frame, conf=self.conf, device=device, verbose=False)
            except Exception as cuda_error:
                print(f"Error using {device} for detection, falling back to CPU: {str(cuda_error)}")
                # Если произошла ошибка с CUDA, используем CPU
                results = self.model(resized_frame, conf=self.conf, device="cpu", verbose=False)
            
            # Рассчитываем время работы
            inference_time = (time.time() - start_time) * 1000  # в мс
            if self.debug:
                print(f"All objects detection time: {inference_time:.2f}ms on {device}")
            
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
        Получает рамки всех обнаруженных объектов.
        
        Args:
            results: Результаты детекции из detect_all_objects()
        
        Returns:
            list: список объектов с информацией о типе, местоположении и размере
        """
        if results is None:
            results = self.last_results
            
        if results is None or len(results) == 0:
            return []
            
        # Используем глобальный словарь классов COCO + пользовательские классы
        coco_classes = COCO_CLASSES.copy()
        coco_classes.update(self.custom_classes)
            
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
        Получает рамку самого большого человека на кадре.
        
        Args:
            results: Результаты детекции
        
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
        на основе размера рамки с учетом законов перспективы.
        
        Args:
            box: Координаты ограничивающей рамки (x_min, y_min, x_max, y_max)
            screen_width: Ширина экрана
            screen_height: Высота экрана
            
        Returns:
            tuple: (target_x, target_y, distance, speed, direction)
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


def detect_objects(frame, perf_monitor, detector, screen_width, screen_height):
    """
    Обнаруживает объекты на заданном кадре используя YOLO.
    
    Args:
        frame: Входной кадр для обработки
        perf_monitor: Объект для мониторинга производительности
        detector: Экземпляр YOLOPersonDetector
        screen_width: Ширина экрана
        screen_height: Высота экрана
        
    Returns:
        Кортеж из (all_objects, results) где all_objects - список обнаруженных объектов,
        а results - необработанные результаты обнаружения от YOLO
    """
    try:
        if frame is None or frame.size == 0:
            print("Error: Invalid frame")
            return [], None
            
        # Детекция с помощью YOLO
        perf_monitor.start('detection')
        
        # Хранение времени последнего полного анализа
        if not hasattr(detect_objects, "last_full_detection_time"):
            detect_objects.last_full_detection_time = 0
            detect_objects.detection_interval = 0.1  # 10 раз в секунду
            detect_objects.cached_results = None
            detect_objects.debug_log_counter = 0
            detect_objects.debug_log_interval = 20  # Логировать каждый 20-й цикл детекции
        
        current_time = time.time()
        
        # Уменьшаем частоту инференса для снижения нагрузки
        # Делаем полный анализ только раз в 100 мс (10 Гц), а в остальное время используем кеш
        if current_time - detect_objects.last_full_detection_time >= detect_objects.detection_interval:
            # Запускаем детекцию всех объектов
            results = detector.detect_all_objects(frame)
            detect_objects.cached_results = results
            detect_objects.last_full_detection_time = current_time
        else:
            # Используем кешированные результаты
            results = detect_objects.cached_results
        
        # Получаем все объекты
        all_objects = detector.get_all_objects(results)
        
        perf_monitor.stop('detection')
        
        # Список для хранения всех найденных объектов
        detected_objects = []
        
        # Если найдены объекты, обработаем их
        if all_objects:
            # Выводим информацию о количестве найденных объектов только каждый N-ый раз
            detect_objects.debug_log_counter += 1
            if detect_objects.debug_log_counter >= detect_objects.debug_log_interval:
                detect_objects.debug_log_counter = 0
                print(f"Detected {len(all_objects)} objects")
            
            # Добавляем все объекты в список объектов для отображения
            for obj in all_objects:
                try:
                    obj_box = obj['box']
                    obj_class = obj['class_name']
                    
                    # Вычисляем 3D позицию объекта
                    obj_x, obj_y, obj_distance, obj_speed, obj_direction = detector.calculate_3d_position(
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
                        'bag': (0, 255, 255),   # Желтый для мешков
                    }
                    color = color_map.get(obj_class.lower(), (255, 255, 255))  # Белый для остальных
                    
                    # Сохраняем информацию об объекте
                    detected_objects.append({
                        'type': 'object',
                        'class': obj_class,
                        'color': color,
                        'box': obj_box,
                        'distance': obj_distance,
                        'position': (obj_x, obj_y),
                        'speed': obj_speed,
                        'direction': obj_direction
                    })
                except Exception as e:
                    # Подавляем распространенные ошибки обработки объектов
                    if not any(err in str(e) for err in ["invalid handle", "GetDIBits", "index out of range"]):
                        print(f"Error processing object: {e}")
        
        return detected_objects, results
        
    except Exception as e:
        print(f"Error in detect_objects: {str(e)}")
        import traceback
        traceback.print_exc()
        return [], None


def select_target(detected_objects, cursor_controller, training_active=False):
    """
    Выбирает целевой объект из списка обнаруженных объектов.
    
    Args:
        detected_objects: Список обнаруженных объектов
        cursor_controller: Объект контроллера курсора с настройками таргетинга
        training_active: Флаг активности режима обучения
        
    Returns:
        Кортеж из (target_box, target_x, target_y, target_distance, target_speed, target_direction)
        или (None, None, None, None, 0.0, 0.0), если цель не найдена
    """
    try:
        if not detected_objects or training_active:
            return None, None, None, None, 0.0, 0.0
        
        target_box = None
        target_x = None
        target_y = None
        target_distance = None
        target_speed = 0.0
        target_direction = 0.0
        
        # Фильтруем объекты, исключая те, которые находятся в списке игнорируемых
        valid_objects = [obj for obj in detected_objects 
                       if obj['class'].lower() not in [cls.lower() for cls in cursor_controller.ignored_classes]]
        
        if not valid_objects:
            return None, None, None, None, 0.0, 0.0
        
        # Определяем целевой объект в зависимости от режима
        if cursor_controller.following_enabled:
            # Режим следования за ближайшим объектом
            nearest_object = min(valid_objects, key=lambda obj: obj['distance'])
            target_box = nearest_object['box']
            target_x, target_y = nearest_object['position']
            target_distance = nearest_object['distance']
            target_speed = nearest_object.get('speed', 0.0)
            target_direction = nearest_object.get('direction', 0.0)
            
            # Отмечаем ближайший объект как целевой
            for obj in detected_objects:
                obj['is_target'] = (obj['box'] == target_box)
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
                target_speed = largest_person.get('speed', 0.0)
                target_direction = largest_person.get('direction', 0.0)
                
                # Отмечаем самого большого человека как целевой
                for obj in detected_objects:
                    obj['is_target'] = (obj['box'] == target_box)
            elif valid_objects:
                # Если людей нет, берем самый большой допустимый объект
                largest_object = max(valid_objects, key=lambda obj: 
                    (obj['box'][2] - obj['box'][0]) * (obj['box'][3] - obj['box'][1]))
                
                target_box = largest_object['box']
                target_x, target_y = largest_object['position']
                target_distance = largest_object['distance']
                target_speed = largest_object.get('speed', 0.0)
                target_direction = largest_object.get('direction', 0.0)
                
                # Отмечаем самый большой объект как целевой
                for obj in detected_objects:
                    obj['is_target'] = (obj['box'] == target_box)
        
        return target_box, target_x, target_y, target_distance, target_speed, target_direction
        
    except Exception as e:
        print(f"Error in select_target: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None, None, 0.0, 0.0 