import torch
import torchvision
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from albumentations import Compose
from albumentations.pytorch import ToTensorV2
import albumentations as A
import numpy as np
from PIL import Image, ImageDraw
import io
import os

inference_transform = Compose([
    A.Resize(height=1400, width=3600),
    A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ToTensorV2()
])

# Load the trained model (assume saved as 'vein_detector.pt' after running notebook)
def load_model(model_path="./model/vein_detector_val_loss.pt"):
    print(f'model path:{model_path}')
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=False)
    num_classes = 3  # From notebook
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    
    # Загружаем с указанием устройства
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()
    print('model loaded')
    return model, device

def get_model():
    """Ленивая загрузка модели"""
    global model, device
    if model is None:
        print('🔄 Initializing model (first call)...')
        model, device = load_model()
    return model, device

model = None
device = None

SCORE_THRESHOLD = 0.5

def detect_objects(image_bytes, score_threshold=SCORE_THRESHOLD):
    model, device = get_model()
    print('detect_objects 1.0')
    orig_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    orig_np = np.array(orig_img)
    orig_h, orig_w = orig_np.shape[:2]  # Original dimensions
    print('detect_objects 1')
    transformed = inference_transform(image=orig_np)
    image_tensor = transformed['image'].unsqueeze(0).to(device)  
    with torch.no_grad():
        preds = model(image_tensor)[0]  # Predictions
    print('detect_objects 2')
    # Filter by score
    keep = preds['scores'] > score_threshold
    boxes = preds['boxes'][keep].cpu().numpy()  # xyxy format
    labels = preds['labels'][keep].cpu().numpy()
    scores = preds['scores'][keep].cpu().numpy()

    # Scale boxes back to original image size
    scale_x = orig_w / 3600
    scale_y = orig_h / 1400
    scaled_boxes = boxes * np.array([scale_x, scale_y, scale_x, scale_y])

    bboxes = []
    for box, label, score in zip(scaled_boxes, labels, scores):
        xmin, ymin, xmax, ymax = box
        bboxes.append({
            "x": float(xmin),
            "y": float(ymin),
            "w": float(xmax - xmin),
            "h": float(ymax - ymin),
            "class": f"vein_{int(label)}",
            "confidence": float(score)
        })

    # Draw bounding boxes on image
    draw = ImageDraw.Draw(orig_img)
    for box, label, score in zip(scaled_boxes, labels, scores):
        xmin, ymin, xmax, ymax = box
        draw.rectangle(((xmin, ymin), (xmax, ymax)), outline="red", width=2)
        draw.text((xmin, ymin - 10), f"Class: {label}, Score: {score:.2f}", fill="red")

    return bboxes, orig_img