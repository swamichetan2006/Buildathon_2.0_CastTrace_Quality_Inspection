"""Shared deterministic image preprocessing for training, validation, and inference."""

import io
from typing import Tuple, Union
import torch
from torchvision import transforms
from PIL import Image

# Standard ImageNet normalization parameters
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
DEFAULT_INPUT_SIZE: Tuple[int, int] = (224, 224)


def get_inference_transform(input_size: Tuple[int, int] = DEFAULT_INPUT_SIZE) -> transforms.Compose:
    """Deterministic preprocessing transform for live inference (e.g. FastAPI / background worker)."""
    return transforms.Compose([
        transforms.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        transforms.Resize(input_size, interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def get_eval_transform(input_size: Tuple[int, int] = DEFAULT_INPUT_SIZE) -> transforms.Compose:
    """Deterministic preprocessing transform for validation and test dataset evaluation.
    
    Must remain strictly identical to get_inference_transform.
    """
    return transforms.Compose([
        transforms.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        transforms.Resize(input_size, interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def get_train_transform(input_size: Tuple[int, int] = DEFAULT_INPUT_SIZE) -> transforms.Compose:
    """Stochastic preprocessing transform with domain-appropriate casting augmentations."""
    return transforms.Compose([
        transforms.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        transforms.Resize(input_size, interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.1, contrast=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def preprocess_pil(
    image: Image.Image,
    input_size: Tuple[int, int] = DEFAULT_INPUT_SIZE,
) -> torch.Tensor:
    """Preprocess a PIL image into a 4D batch tensor [1, 3, H, W] for model execution."""
    transform = get_inference_transform(input_size)
    tensor = transform(image)
    return tensor.unsqueeze(0)


def preprocess_image_bytes(
    image_bytes: bytes,
    input_size: Tuple[int, int] = DEFAULT_INPUT_SIZE,
) -> torch.Tensor:
    """Preprocess raw image bytes into a 4D batch tensor [1, 3, H, W] for model execution."""
    image = Image.open(io.BytesIO(image_bytes))
    return preprocess_pil(image, input_size)
