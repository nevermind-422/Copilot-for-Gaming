"""
Модуль для отрисовки графики на кадрах.
"""

import cv2
import numpy as np
import math

class DrawingUtils:
    """
    Утилиты для отрисовки элементов интерфейса и визуализации результатов.
    """
    
    @staticmethod
    def draw_bounding_box(frame, box, color, padding=10, thickness=2):
        """
        Рисует рамку вокруг обнаруженного объекта
        
        Args:
            frame: Кадр для рисования
            box: Координаты рамки (x1, y1, x2, y2)
            color: Цвет рамки в формате BGR
            padding: Отступ от границ объекта
            thickness: Толщина линии
            
        Returns:
            Кадр с нарисованной рамкой
        """
        min_x, min_y, max_x, max_y = box
        
        # Добавляем отступ
        min_x = max(0, min_x - padding)
        min_y = max(0, min_y - padding)
        max_x = min(frame.shape[1], max_x + padding)
        max_y = min(frame.shape[0], max_y + padding)
        
        # Рисуем прямоугольник
        cv2.rectangle(frame, (min_x, min_y), (max_x, max_y), color, thickness)
        
        return frame
    
    @staticmethod
    def draw_debug_info(frame, target_x, target_y, distance, speed, direction, fps):
        """
        Отображает отладочную информацию на кадре
        
        Args:
            frame: Кадр для рисования
            target_x, target_y: Координаты цели
            distance: Расстояние до цели
            speed: Скорость движения
            direction: Направление движения
            fps: Количество кадров в секунду
            
        Returns:
            Кадр с отладочной информацией
        """
        # Рисуем белое полупрозрачное поле для текста
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (300, 120), (255, 255, 255), -1)
        alpha = 0.7
        cv2.addWeighted(overlay, alpha, frame, 1-alpha, 0, frame)
        
        # Рисуем текст
        y = 30
        cv2.putText(frame, f"Target: {target_x}, {target_y}", (20, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        y += 20
        cv2.putText(frame, f"Distance: {distance:.2f} m", (20, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        y += 20
        cv2.putText(frame, f"Speed: {speed:.2f}", (20, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        y += 20
        cv2.putText(frame, f"Direction: {direction:.2f}", (20, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        y += 20
        cv2.putText(frame, f"FPS: {fps:.1f}", (20, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        return frame
    
    @staticmethod
    def draw_movement_vector(frame, start_point, end_point, color, thickness=2):
        """
        Рисует вектор движения с градиентом и стрелкой
        
        Args:
            frame: Кадр для рисования
            start_point: Начальная точка (x, y)
            end_point: Конечная точка (x, y)
            color: Цвет линии в формате BGR
            thickness: Толщина линии
            
        Returns:
            Кадр с нарисованным вектором
        """
        # Рисуем саму линию
        cv2.line(frame, start_point, end_point, color, thickness)
        
        # Рисуем наконечник стрелки
        # Вычисляем угол линии
        angle = math.atan2(end_point[1] - start_point[1], 
                          end_point[0] - start_point[0])
        
        # Вычисляем координаты для наконечника стрелки
        arrow_length = 15
        arrow1_x = end_point[0] - arrow_length * math.cos(angle + math.pi/6)
        arrow1_y = end_point[1] - arrow_length * math.sin(angle + math.pi/6)
        arrow2_x = end_point[0] - arrow_length * math.cos(angle - math.pi/6)
        arrow2_y = end_point[1] - arrow_length * math.sin(angle - math.pi/6)
        
        # Рисуем наконечник стрелки
        cv2.line(frame, end_point, (int(arrow1_x), int(arrow1_y)), color, thickness)
        cv2.line(frame, end_point, (int(arrow2_x), int(arrow2_y)), color, thickness)
        
        return frame 