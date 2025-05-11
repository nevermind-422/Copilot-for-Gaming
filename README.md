# Reign of Bots

A computer vision application for cursor control using YOLO11 object detection.

## Features

- Real-time object detection using YOLO11 model
- Automatic cursor movement to track objects
- Transparent overlay with detailed information
- Auto movement with W key when target is far
- Multiple tracking modes (absolute/relative cursor movement)
- Attack mode with automatic clicking
- Support for ignoring specific object types

## Version 0.026 Changes

- Replaced YOLOv8 with YOLO11 for improved object detection
- Optimized performance through frame scaling
- Improved handling of multiple people in frame
- Added detection for all object types (not just people)
- Added nearest object targeting
- Added static list of ignored objects
- Improved UI element positioning
- Added "Reign of Bots" title and version in header
- Fixed GDI resource leaks and improved transparent window
- Optimized UI rendering performance

## Requirements

See requirements.txt for dependencies.

## Controls

- `-` to toggle between absolute and relative mouse movement modes
- `+` to toggle following mode
- `Backspace` to toggle attack mode
- `\` to toggle ignoring people (class 0)
- `F1` to exit
- `.` to start/stop recording

## Usage

```
python main15.py
```

To run without cursor control:
```
python main15.py --no-cursor-control
``` 