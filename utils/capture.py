"""
Модуль для захвата изображения с экрана.
"""
import cv2
import numpy as np
import time
import contextlib
import mss

class ScreenCapture:
    """
    Класс для захвата экрана с использованием MSS.
    Обеспечивает высокопроизводительный захват изображения с экрана и его обработку.
    """
    def __init__(self, monitor_number=0):
        """
        Инициализирует захват экрана.
        
        Args:
            monitor_number: Номер монитора для захвата (0 - основной экран)
        """
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[monitor_number]
        self.error_count = 0
        self.last_reinit_time = time.time()
        self.reinit_interval = 60.0  # Реинициализация каждые 60 секунд
        print("MSS screen capture initialized")
    
    def capture(self):
        """
        Захватывает изображение экрана с высокой производительностью.
        
        Returns:
            np.ndarray: Изображение экрана в формате BGR для OpenCV или None в случае ошибки
        """
        try:
            # Проверяем, не слишком ли много ошибок или не пора ли реинициализировать
            current_time = time.time()
            if (self.error_count > 10 or 
                current_time - self.last_reinit_time > self.reinit_interval):
                print(f"Reinitializing MSS after {self.error_count} errors or time interval")
                # Высвобождаем ресурсы и пересоздаем MSS
                with contextlib.suppress(Exception):
                    self.sct.close()
                    self.sct = mss.mss()
                    self.monitor = self.sct.monitors[0]
                self.error_count = 0
                self.last_reinit_time = current_time
                print("MSS screen capture reinitialized")
            
            # Захватываем изображение с экрана с помощью MSS
            img = np.asarray(self.sct.grab(self.monitor))
            
            # Сбрасываем счетчик ошибок при успешном выполнении
            self.error_count = 0
            
            # Конвертируем из BGR в RGB для OpenCV
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            # Увеличиваем счетчик ошибок
            self.error_count += 1
            # Подавляем вывод стандартных ошибок GetDIBits
            if "GetDIBits" not in str(e):
                print(f"Error in MSS screen capture: {str(e)} (count: {self.error_count})")
            
            return None
    
    def cleanup(self):
        """
        Очищает ресурсы захвата экрана.
        """
        try:
            if hasattr(self, 'sct'):
                print("Cleaning MSS screen capture resources...")
                self.sct.close()
        except Exception as e:
            print(f"Error cleaning MSS screen capture resources: {str(e)}")

# Функция-обертка для обратной совместимости
def capture_screen(monitor_number=0):
    """
    Функция-обертка для захвата экрана.
    Создает и использует экземпляр ScreenCapture для захвата экрана.
    
    Args:
        monitor_number: Номер монитора для захвата (0 - основной экран)
        
    Returns:
        np.ndarray: Изображение экрана в формате BGR для OpenCV или None в случае ошибки
    """
    if not hasattr(capture_screen, "screen_capturer"):
        capture_screen.screen_capturer = ScreenCapture(monitor_number)
    
    return capture_screen.screen_capturer.capture() 