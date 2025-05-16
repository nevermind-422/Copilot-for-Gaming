"""
Модуль для мониторинга производительности и замера времени выполнения операций.
"""

import time

class PerformanceCounter:
    """
    Счетчик производительности для отдельной операции.
    Отслеживает время выполнения и вычисляет среднее значение.
    """
    def __init__(self, name):
        self.name = name
        self.total_time = 0.0
        self.count = 0
        self.last_time = 0.0
        self.current_time = 0.0
        self.avg_time = 0.0
        self.last_reset_time = time.time()
        
    def start(self):
        """Начать замер времени операции"""
        self.last_time = time.time()
        
    def stop(self):
        """Остановить замер времени и обновить статистику"""
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
    """
    Монитор производительности, содержащий несколько счетчиков для разных операций.
    Позволяет отслеживать производительность различных частей программы.
    """
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
        """Начать замер времени для указанной операции"""
        if counter_name in self.counters:
            self.counters[counter_name].start()
        
    def stop(self, counter_name):
        """Остановить замер времени для указанной операции"""
        if counter_name in self.counters:
            self.counters[counter_name].stop()
        
    def get_stats(self):
        """Получить статистику по всем счетчикам"""
        current_time = time.time()
        if current_time - self.last_reset >= self.reset_interval:
            self.last_reset = current_time
        return {name: counter for name, counter in self.counters.items()} 