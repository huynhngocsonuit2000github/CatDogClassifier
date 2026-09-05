# CatDogClassifier — Training Page Enhancement

## Goal

Redesign the Training page so it looks like a realistic MLOps training interface while keeping the current clean UI.

The existing Training page already supports:
- Architecture
- Dataset version
- Epochs
- Batch size
- Learning rate
- Start training
- Training runs
- Accuracy / Loss
- Run comparison

Keep all existing functionality working.

---

## 1. Training Configuration

Organize the configuration into clear sections.

### Model

#### Architecture
Example: `MobileNetV2`

Tooltip:
> Neural network architecture used for image classification.

#### Pretrained Model
Example: `Enabled`

Tooltip:
> Start from a model pretrained on ImageNet instead of training from scratch.

#### Image Size
Example: `224 × 224`

Tooltip:
> Image resolution used as input to the model.

---

### Training

#### Epochs
Example: `15`

Tooltip:
> Number of times the model goes through the entire training dataset.

#### Batch Size
Example: `32`

Tooltip:
> Number of images processed before updating the model weights.

#### Learning Rate
Example: `0.0005`

Tooltip:
> Controls how large each update to the model weights is during training.

#### Optimizer
Example: `Adam`

Options:
- Adam
- AdamW
- SGD

Tooltip:
> Algorithm used to update model weights during training.

#### Loss Function
Example: `Cross Entropy`

Tooltip:
> Measures how far the model predictions are from the correct labels.

#### Validation Split
Example: `20%`

Tooltip:
> Percentage of the dataset reserved for validation during training.

---

### Advanced

#### Weight Decay
Example: `0.0001`

Tooltip:
> Regularization technique that helps reduce overfitting.

#### Learning Rate Scheduler
Example: `Cosine`

Options:
- None
- Step
- Cosine
- ReduceLROnPlateau

Tooltip:
> Adjusts the learning rate during training to improve model convergence.

#### Early Stopping
Example: `Enabled`

Tooltip:
> Stops training when validation performance stops improving.

#### Random Seed
Example: `42`

Tooltip:
> Controls randomness so training results can be reproduced.

---

## 2. Data Augmentation

Add a separate section for image augmentation.

### Horizontal Flip
Default: Enabled

Tooltip:
> Randomly flips images horizontally to create additional training variations.

### Rotation
Default: `±15°`

Tooltip:
> Randomly rotates images to make the model more robust to image orientation.

### Color Jitter
Default: Enabled

Tooltip:
> Randomly changes image brightness, contrast, saturation, and related properties.

### Random Crop
Default: Enabled

Tooltip:
> Randomly crops images to improve robustness to object position and framing.

---

## 3. Recommended Layout

Keep the page visually clean and similar to the current design.

Suggested structure:

Training

[ Training Configuration ]

Model
- Architecture
- Pretrained Model
- Image Size

Training
- Epochs
- Batch Size
- Learning Rate
- Optimizer
- Loss Function
- Validation Split

Advanced
- Weight Decay
- Learning Rate Scheduler
- Early Stopping
- Random Seed

Data Augmentation
- Horizontal Flip
- Rotation
- Color Jitter
- Random Crop

[ Start Training ]

[ All Runs ]
- Run
- Architecture
- Dataset
- Accuracy
- Loss
- Status
- Started

---

## 4. Tooltip UX

Every configurable parameter should have a small `ⓘ` information icon beside its label.

On hover:
- Show a compact tooltip.
- Explain the parameter in simple language.
- Do not make the tooltip too large.
- Keep the UI uncluttered.

Example:

`Learning Rate  ⓘ`

Hover:

> Controls how large each update to the model weights is during training.

---

## 5. Important Implementation Rule

Do NOT create fake functionality.

The UI should only send parameters that the existing backend/training pipeline actually supports.

If a parameter is currently not supported by the backend:
- Keep the UI design ready for it, OR
- Implement the backend support if it is straightforward and consistent with the existing architecture.

Do not pretend a parameter affects training when it does not.

---

## 6. Training Run Metadata

When a training run is created, store/display the important configuration used for that run.

A run detail should eventually be able to show:

- Run ID
- Architecture
- Dataset version
- Image size
- Epochs
- Batch size
- Learning rate
- Optimizer
- Loss function
- Validation split
- Weight decay
- Scheduler
- Early stopping
- Augmentation settings
- Accuracy
- Loss
- Training duration
- Status
- Started time

This allows users to reproduce and compare experiments.

---

## 7. UX Principles

- Preserve the existing visual style.
- Keep the interface simple and professional.
- Group related parameters instead of putting everything into one long form.
- Use sensible defaults.
- Use dropdowns for parameters with predefined options.
- Use numeric validation for numeric parameters.
- Disable Start Training while a training job is running.
- Show clear training status and errors.
- Do not break the existing Training Runs table or comparison functionality.

---

## 8. Demo Target

The final page should make this workflow obvious:

Dataset Version
        ↓
Training Configuration
        ↓
Start Training
        ↓
Training Run
        ↓
Accuracy / Loss
        ↓
Compare Runs
        ↓
Register Model
        ↓
Model Registry
        ↓
Prediction

The goal is to make CatDogClassifier look like a small but realistic end-to-end MLOps platform, not just a simple ML training form.
