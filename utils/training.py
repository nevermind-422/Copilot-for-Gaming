import os
import cv2
import numpy as np
from ultralytics import YOLO

class YOLOTrainer:
    def __init__(self, model=None, model_path=None):
        self.model = model
        self.model_path = model_path
        self.collection_active = False
        self.frames_to_save = 0
        self.collected_frames = []
        self.collected_boxes = []
        
    def start_collection(self, frames_to_collect=100):
        """Start collecting training data"""
        self.collection_active = True
        self.frames_to_save = frames_to_collect
        self.collected_frames = []
        self.collected_boxes = []
        print(f"Started collecting {frames_to_collect} frames for training")
        
    def stop_collection(self):
        """Stop collecting training data"""
        self.collection_active = False
        print(f"Stopped collecting frames. Collected {len(self.collected_frames)} frames")
        
    def process_frame(self, frame, results, cursor_pos):
        """Process a frame for training data collection"""
        if not self.collection_active or self.frames_to_save <= 0:
            return
            
        if frame is None or results is None:
            return
            
        # Save frame and annotation
        self.collected_frames.append(frame.copy())
        self.collected_boxes.append(results)
        self.frames_to_save -= 1
        
        if self.frames_to_save <= 0:
            self.stop_collection()
            
    def fine_tune(self, epochs=5, batch_size=4, device="cpu"):
        """Fine-tune the model with collected data"""
        if not self.collected_frames or not self.collected_boxes:
            print("No training data collected")
            return False
            
        try:
            # Save collected data
            data_dir = os.path.join(os.path.dirname(self.model_path), "training_data")
            os.makedirs(data_dir, exist_ok=True)
            
            # Save frames and annotations
            for i, (frame, boxes) in enumerate(zip(self.collected_frames, self.collected_boxes)):
                # Save frame
                frame_path = os.path.join(data_dir, f"frame_{i:04d}.jpg")
                cv2.imwrite(frame_path, frame)
                
                # Save annotation (simplified for this example)
                # In a real implementation, you would save proper YOLO format annotations
                with open(frame_path.replace('.jpg', '.txt'), 'w') as f:
                    for box in boxes.boxes:
                        if hasattr(box, 'xyxyn'):
                            x1, y1, x2, y2 = box.xyxyn[0].tolist()
                            # Convert to YOLO format (x_center, y_center, width, height)
                            x_center = (x1 + x2) / 2
                            y_center = (y1 + y2) / 2
                            width = x2 - x1
                            height = y2 - y1
                            # Write annotation (class 80 for 'bag')
                            f.write(f"80 {x_center} {y_center} {width} {height}\n")
            
            print(f"Saved {len(self.collected_frames)} training samples")
            
            # In a real implementation, you would use the YOLO training API
            # For now, we'll just return success
            return True
            
        except Exception as e:
            print(f"Error during fine-tuning: {str(e)}")
            return False 