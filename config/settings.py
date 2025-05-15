import win32con

# MediaPipe settings - optimized for skeleton detection only
MEDIAPIPE_CONFIG = {
    'static_image_mode': False,
    'model_complexity': 0,  # Минимальная сложность модели
    'enable_segmentation': False,
    'smooth_landmarks': False,  # Отключаем сглаживание для производительности
    'min_detection_confidence': 0.5,
    'min_tracking_confidence': 0.5,
}

# Overlay settings
OVERLAY_CONFIG = {
    'window_name': "Overlay",
    'crosshair_size': 20,
    'crosshair_thickness': 2,
    'crosshair_color': 0x00FF00,  # Green
    'crosshair_relative_color': 0x0000FF,  # Blue for relative mode
    'update_interval': 1.0 / 60.0,  # 60 FPS
    'transparency': 100  # 100 - более прозрачный (раньше было 128)
}

# Cursor settings
CURSOR_CONFIG = {
    'sensitivity': 1.0,
    'relative_mode_sensitivity': 0.5,
    'smoothing_factor': 0.3,
    'min_movement_threshold': 0.1
}

# Performance monitoring settings
PERFORMANCE_CONFIG = {
    'reset_interval': 1.0,
    'log_interval': 1.0,
    'log_dir': 'performance_logs',  # Directory for performance logs
    'log_metrics': True,  # Enable/disable performance logging
    'metrics_to_log': [  # List of metrics to log
        'capture',
        'process',
        'detection',
        'drawing',
        'overlay',
        'cursor'
    ]
}

# Video recording settings
VIDEO_CONFIG = {
    'fps': 30,
    'codec': 'XVID',
    'output_dir': 'recordings'
}

# Window settings
WINDOW_CONFIG = {
    'style': win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST,
    'class_name': "Static",
    'window_name': "Overlay",
    'flags': win32con.WS_POPUP | win32con.WS_VISIBLE
} 