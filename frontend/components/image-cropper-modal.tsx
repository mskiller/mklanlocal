"use client";

import Cropper from "cropperjs";
import { useEffect, useMemo, useRef, useState } from "react";

import { CropSpec } from "@/lib/types";

export interface CropModalResult {
  crop: CropSpec;
  previewBlob: Blob | null;
}

function normalizeQuadrants(value: number) {
  return ((value % 4) + 4) % 4;
}

function cropSignature(crop: CropSpec | null | undefined) {
  if (!crop) {
    return "empty";
  }
  return `${crop.rotation_quadrants}:${crop.crop_x}:${crop.crop_y}:${crop.crop_width}:${crop.crop_height}`;
}

function canvasToBlob(canvas: HTMLCanvasElement | null): Promise<Blob | null> {
  if (!canvas) {
    return Promise.resolve(null);
  }
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), "image/png");
  });
}

export function ImageCropperModal({
  open,
  title,
  imageSrc,
  initialCrop,
  naturalWidth,
  naturalHeight,
  confirmLabel = "Create Crop",
  busyLabel = "Saving...",
  onClose,
  onConfirm,
}: {
  open: boolean;
  title: string;
  imageSrc: string | null | undefined;
  initialCrop?: CropSpec | null;
  naturalWidth?: number | null;
  naturalHeight?: number | null;
  confirmLabel?: string;
  busyLabel?: string;
  onClose: () => void;
  onConfirm: (result: CropModalResult) => Promise<void> | void;
}) {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const cropperRef = useRef<Cropper | null>(null);
  const [rotationQuadrants, setRotationQuadrants] = useState(initialCrop?.rotation_quadrants ?? 0);
  const [submitting, setSubmitting] = useState(false);
  const [ready, setReady] = useState(false);
  const initialKey = useMemo(() => cropSignature(initialCrop), [initialCrop]);

  useEffect(() => {
    setRotationQuadrants(initialCrop?.rotation_quadrants ?? 0);
  }, [initialKey, initialCrop]);

  useEffect(() => {
    if (!open || !imageSrc || !imageRef.current) {
      return;
    }

    setReady(false);
    const image = imageRef.current;
    const cropper = new Cropper(image, {
      viewMode: 1,
      background: false,
      autoCropArea: 1,
      dragMode: "move",
      responsive: true,
      checkOrientation: false,
      ready() {
        const imageData = cropper.getImageData();
        const fullWidth = naturalWidth ?? imageData.naturalWidth;
        const fullHeight = naturalHeight ?? imageData.naturalHeight;
        cropper.setData(
          initialCrop
            ? {
                x: initialCrop.crop_x,
                y: initialCrop.crop_y,
                width: initialCrop.crop_width,
                height: initialCrop.crop_height,
                rotate: initialCrop.rotation_quadrants * 90,
              }
            : {
                x: 0,
                y: 0,
                width: fullWidth,
                height: fullHeight,
                rotate: 0,
              }
        );
        setRotationQuadrants(initialCrop?.rotation_quadrants ?? 0);
        setReady(true);
      },
    });

    cropperRef.current = cropper;
    return () => {
      cropper.destroy();
      cropperRef.current = null;
      setReady(false);
      setSubmitting(false);
    };
  }, [open, imageSrc, initialKey, initialCrop, naturalWidth, naturalHeight]);

  if (!open || !imageSrc) {
    return null;
  }

  const handleRotate = (delta: number) => {
    const cropper = cropperRef.current;
    if (!cropper) {
      return;
    }
    cropper.rotate(delta * 90);
    setRotationQuadrants((current) => normalizeQuadrants(current + delta));
  };

  const handleReset = () => {
    const cropper = cropperRef.current;
    if (!cropper) {
      return;
    }
    const imageData = cropper.getImageData();
    cropper.reset();
    cropper.setData({
      x: 0,
      y: 0,
      width: naturalWidth ?? imageData.naturalWidth,
      height: naturalHeight ?? imageData.naturalHeight,
      rotate: 0,
    });
    setRotationQuadrants(0);
  };

  const handleConfirm = async () => {
    const cropper = cropperRef.current;
    if (!cropper) {
      return;
    }
    const data = cropper.getData(true);
    const previewBlob = await canvasToBlob(cropper.getCroppedCanvas());
    const crop: CropSpec = {
      rotation_quadrants: normalizeQuadrants(
        Number.isFinite(data.rotate) ? Math.round((data.rotate ?? 0) / 90) : rotationQuadrants
      ),
      crop_x: Math.max(0, Math.round(data.x ?? 0)),
      crop_y: Math.max(0, Math.round(data.y ?? 0)),
      crop_width: Math.max(1, Math.round(data.width ?? 1)),
      crop_height: Math.max(1, Math.round(data.height ?? 1)),
    };
    setSubmitting(true);
    try {
      await onConfirm({ crop, previewBlob });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button type="button" aria-label="Close crop editor" className="modal-scrim" onClick={onClose} disabled={submitting} />
      <section className="modal-panel panel stack cropper-modal-panel">
        <div className="row-between">
          <div>
            <p className="eyebrow">Crop Draft</p>
            <h2>{title}</h2>
          </div>
          <button className="button ghost-button small-button" type="button" onClick={onClose} disabled={submitting}>
            Close
          </button>
        </div>
        <div className="cropper-stage">
          <img ref={imageRef} src={imageSrc} alt={title} />
        </div>
        <div className="card-actions cropper-toolbar">
          <button className="button ghost-button small-button" type="button" onClick={() => handleRotate(-1)} disabled={!ready || submitting}>
            Rotate Left
          </button>
          <button className="button ghost-button small-button" type="button" onClick={() => handleRotate(1)} disabled={!ready || submitting}>
            Rotate Right
          </button>
          <button className="button subtle-button small-button" type="button" onClick={handleReset} disabled={!ready || submitting}>
            Reset
          </button>
          <button className="button small-button" type="button" onClick={() => void handleConfirm()} disabled={!ready || submitting}>
            {submitting ? busyLabel : confirmLabel}
          </button>
        </div>
      </section>
    </>
  );
}
