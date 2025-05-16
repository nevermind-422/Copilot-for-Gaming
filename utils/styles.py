"""
Модуль с константами стилей для интерфейса.
Содержит настройки цветов, размеров и позиций элементов оверлея.
"""

# Цвета (в формате BGR для Win32 API: 0x00BBGGRR)
COLORS = {
    # Основные цвета
    'transparent': 0x00000000,
    'dark_gray': 0x202020,
    'medium_gray': 0x404040,
    'light_gray': 0x808080,
    'white': 0xFFFFFF,
    'red': 0x0000FF,
    'green': 0x00FF00,
    'blue': 0xFF0000,
    'yellow': 0x00FFFF,
    'cyan': 0xFFFF00,
    
    # Статусные цвета
    'active': 0x00FF00,     # Зеленый для активных состояний
    'inactive': 0xFF0000,   # Красный для неактивных состояний
    'warning': 0x0000FF,    # Красный для предупреждений
    'highlight': 0x00FFFF,  # Голубой для выделения
    'info': 0xFFFFFF,       # Белый для информации
}

# Размеры элементов
SIZES = {
    # Основные размеры
    'button': {
        'width': 140,
        'height': 30,
        'margin': 5,
        'padding': 5,
    },
    'block': {
        'width': 180,
        'height': 90,
        'margin': 5,
        'padding': 5,
    },
    'text': {
        'small': 14,
        'normal': 16,
        'large': 20,
        'header': 30,
        'title': 40,
    },
    'line_height': 18,
    'border': 2,
    'corner_radius': 5,
    
    # Элементы прицела
    'crosshair': {
        'size': 15,
        'thickness': 2,
        'dot_radius': 3,
    },
}

# Позиции элементов интерфейса
POSITIONS = {
    # Основные блоки
    'control_panel': {
        'x': 100,
        'y': 100,
        'width': 300, 
        'height': 400,
    },
    'stats_panel': {
        'x': 100,
        'y': 520,
        'width': 300,
        'height': 300,  # Увеличиваем высоту с 250 до 300 для размещения всего текста
    },
    'title': {
        'x_right': 200,
        'y_bottom': 60,
        'width': 180,
        'height': 50,
    },
}

# Шрифты
FONTS = {
    'normal': {
        'name': 'Consolas',
        'height': 16,
        'weight': 400,  # FW_NORMAL
    },
    'bold': {
        'name': 'Consolas',
        'height': 16,
        'weight': 700,  # FW_BOLD
    },
    'title': {
        'name': 'Arial',
        'height': 40,
        'weight': 700,  # FW_BOLD
        'italic': True,
    },
    'small': {
        'name': 'Consolas',
        'height': 14,
        'weight': 400,  # FW_NORMAL
    },
    'large': {
        'name': 'Consolas',
        'height': 20,
        'weight': 700,  # FW_BOLD
    },
}

# Расстояния между элементами
SPACING = {
    'padding': 5,
    'margin': 8,
    'block_spacing': 15,
    'button_spacing': 10,
} 