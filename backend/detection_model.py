import io
import os
from pathlib import Path

import albumentations as A
import numpy as np
import torch
import torchvision
from albumentations import Compose
from albumentations.pytorch import ToTensorV2
from PIL import Image, ImageDraw
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

inference_transform = Compose([
    A.Resize(height=1400, width=3600),
    A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ToTensorV2(),
])


def resolve_model_path(model_path=None):
    candidates = [
        model_path,
        os.getenv("MODEL_PATH"),
        "./model/vein_detector.pt",
        "./model/vein_detector_old.pt",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    raise FileNotFoundError(
        "No compatible torchvision model file found. Expected one of: "
        "./model/vein_detector.pt, ./model/vein_detector_old.pt"
    )


def load_model(model_path=None):
    model_path = resolve_model_path(model_path)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(
        weights=None,
        weights_backbone=None,
    )
    num_classes = 3
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()
    return model, device


def get_model():
    global model, device
    if model is None:
        model, device = load_model()
    return model, device


model = None
device = None

SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.25"))
MAX_DETECTIONS = int(os.getenv("MAX_DETECTIONS", "20"))


def detect_objects(image_bytes, score_threshold=SCORE_THRESHOLD):
    model, device = get_model()
    orig_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    orig_np = np.array(orig_img)
    orig_h, orig_w = orig_np.shape[:2]

    transformed = inference_transform(image=orig_np)
    image_tensor = transformed["image"].unsqueeze(0).to(device)

    with torch.no_grad():
        preds = model(image_tensor)[0]

    keep = preds["scores"] > score_threshold
    boxes = preds["boxes"][keep][:MAX_DETECTIONS].cpu().numpy()
    labels = preds["labels"][keep][:MAX_DETECTIONS].cpu().numpy()
    scores = preds["scores"][keep][:MAX_DETECTIONS].cpu().numpy()

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
            "confidence": float(score),
        })

    draw = ImageDraw.Draw(orig_img)
    for box, label, score in zip(scaled_boxes, labels, scores):
        xmin, ymin, xmax, ymax = box
        draw.rectangle(((xmin, ymin), (xmax, ymax)), outline="red", width=2)
        draw.text((xmin, ymin - 10), f"Class: {label}, Score: {score:.2f}", fill="red")

    return bboxes, orig_img
