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

## Project Structure

The project has been refactored to follow a modular architecture:

- `main15.py` - Main application entry point
- `utils/` - Utility modules:
  - `kalman.py` - Kalman filter implementation for smooth tracking
  - `detector.py` - Object detection using YOLO model
  - `cursor_control.py` - Cursor controller with multiple modes
  - `training.py` - Tools for collecting data and fine-tuning the model
  - `drawing.py` - Drawing utilities for visualization

## Version History

### Version 0.037
- Improved modularity: `CursorController` moved to a separate module
- Enhanced code maintainability and readability
- Simplified main file structure

### Version 0.036
- Optimized cursor movement to prevent duplicate movement calls
- Added `cursor_moved_this_frame` flag to track cursor state
- Fixed cursor jitter caused by redundant move_cursor calls
- Reduced CPU load in frame processing

### Version 0.035
- Fixed variable scope issue in handle_auto_movement method
- Improved variable scope management for BoxFilter integration
- Optimized target position update logic

### Version 0.034
- Moved object detector to a separate module
- Code refactoring for improved modularity
- Better code organization with module separation
- Simplified main file for better maintenance

### Version 0.033
- Moved Kalman filter to a separate module
- Optimized Kalman filter application for more efficient smoothing
- Improved object center calculation without redundant filtering

### Version 0.032
- Optimized screen capture: removed Win32API fallback method, kept only MSS
- Added proper resource cleanup when closing application using contextlib.suppress

### Version 0.031
- Added ability to hide/show object bounding boxes with F4 key
- Program now starts with hidden bounding boxes by default
- Added --show-boxes command line argument to start with visible boxes

### Version 0.030
- Improved MSS screen capture stability
- Suppressed common GetDIBits errors for cleaner logs
- Optimized GDI object creation error messages
- Improved GDI resource cleanup to prevent leaks
- Added error filtering for better console output readability

### Version 0.029
- Added GPU (CUDA) support for neural network inference acceleration
- Optimized screen capture to reduce system load
- Added detection result caching to decrease inference frequency
- Reduced full frame analysis frequency to 10 Hz to save resources
- Fixed issues causing overlay disappearance during extended operation
- Added periodic GDI object cleanup to prevent Windows resource leaks
- Fixed UpdateLayeredWindow method for correct transparent overlay
- Added periodic forced overlay updates for stable operation
- Replaced YOLOv8 with YOLO11 for improved object detection
- Replaced MediaPipe recognition system with YOLO for better detection range
- Optimized performance with frame scaling
- Improved handling of multiple people in frame by selecting the largest
- Added recognition for all object types (not just people)
- Configured nearest object targeting
- Added static list of ignored objects
- Added display of object type and distance information
- Improved UI element positioning
- Added "Reign of Bots" title and version in header
- Fixed GDI resource leaks and improved transparent window
- Optimized UI rendering performance

## Requirements

See requirements.txt for dependencies.

## Controls

- `-` to toggle between absolute and relative mouse movement modes
- `+` to toggle following mode
- `F5` to toggle cursor control mode
- `F4` to toggle bounding box visibility
- `Backspace` to toggle attack mode
- `\` to toggle ignoring people (class 0)
- `F1` to exit
- `F6` to start/stop training data collection for bags
- `F7` to start fine-tuning the model with collected data

## Usage

```
python main15.py
```

To run without cursor control:
```
python main15.py --no-cursor-control
```

To run with CUDA disabled:
```
python main15.py --no-cuda
```

To show bounding boxes at startup:
```
python main15.py --show-boxes
``` 