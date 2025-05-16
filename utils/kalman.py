"""
Модуль для работы с фильтром Калмана.
Предоставляет класс для сглаживания координат объектов.
"""

class KalmanFilter:
    """Реализация простого фильтра Калмана для сглаживания координат"""
    
    def __init__(self, process_variance=0.0001, measurement_variance=0.1):
        """
        Инициализирует новый фильтр Калмана.
        
        Args:
            process_variance (float): Дисперсия процесса (меньше = сильнее сглаживание)
            measurement_variance (float): Дисперсия измерения
        """
        self.process_variance = process_variance  # малое значение = сильное сглаживание
        self.measurement_variance = measurement_variance
        self.kalman_gain = 0
        self.estimated_value = None
        self.estimate_error = 1.0
        
    def update(self, measurement):
        """
        Обновляет оценку с новым измерением.
        
        Args:
            measurement: Новое измеренное значение
            
        Returns:
            float: Сглаженное (отфильтрованное) значение
        """
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
        
    def reset(self):
        """Сбрасывает состояние фильтра"""
        self.estimated_value = None
        self.estimate_error = 1.0
        self.kalman_gain = 0


class BoxFilter:
    """
    Фильтр для сглаживания координат ограничивающей рамки.
    Применяет фильтр Калмана только к координатам рамки.
    """
    
    def __init__(self, process_variance=0.00001, measurement_variance=0.3):
        """
        Инициализирует фильтр для рамки.
        
        Args:
            process_variance (float): Дисперсия процесса для фильтра Калмана
            measurement_variance (float): Дисперсия измерения для фильтра Калмана
        """
        # Создаем единственный фильтр для координат рамки
        self.kalman_box = KalmanFilter(process_variance, measurement_variance)
        self.last_box = None
    
    def update(self, box):
        """
        Применяет фильтр к координатам рамки.
        
        Args:
            box (tuple): Координаты рамки (x_min, y_min, x_max, y_max)
            
        Returns:
            tuple: Отфильтрованные координаты рамки
        """
        if box is None:
            return None
            
        x_min, y_min, x_max, y_max = box
        
        # Вычисляем ширину и высоту рамки
        width = x_max - x_min
        height = y_max - y_min
        
        # Применяем фильтр Калмана к ОДНОЙ координате - x_min
        # Остальные координаты будут рассчитаны относительно неё
        filtered_x_min = self.kalman_box.update(x_min)
        
        # Применяем фильтр Калмана к ОДНОЙ координате - y_min
        filtered_y_min = self.kalman_box.update(y_min)
        
        # Вычисляем остальные координаты на основе отфильтрованных x_min, y_min
        # и оригинальной ширины и высоты
        filtered_x_max = filtered_x_min + width
        filtered_y_max = filtered_y_min + height
        
        # Сохраняем отфильтрованную рамку
        self.last_box = (filtered_x_min, filtered_y_min, filtered_x_max, filtered_y_max)
        
        return self.last_box
        
    def get_center(self):
        """
        Вычисляет центр отфильтрованной рамки.
        
        Returns:
            tuple: Координаты центра (x, y) или None, если рамка не определена
        """
        if self.last_box is None:
            return None
            
        x_min, y_min, x_max, y_max = self.last_box
        center_x = (x_min + x_max) // 2
        center_y = (y_min + y_max) // 2
        
        return center_x, center_y 