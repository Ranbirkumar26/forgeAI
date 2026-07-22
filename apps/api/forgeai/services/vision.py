from pathlib import Path

import cv2
import numpy as np


def create_demo_visual_diff(output_path: Path) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    before = np.full((260, 420, 3), 245, dtype=np.uint8)
    after = before.copy()
    cv2.rectangle(before, (30, 40), (390, 95), (20, 20, 20), -1)
    cv2.rectangle(before, (30, 130), (250, 165), (180, 40, 40), -1)
    cv2.rectangle(after, (30, 40), (390, 95), (20, 20, 20), -1)
    cv2.rectangle(after, (30, 130), (390, 165), (35, 120, 70), -1)
    diff = cv2.absdiff(before, after)
    heatmap = cv2.applyColorMap(cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY), cv2.COLORMAP_TURBO)
    composed = np.hstack([before, after, heatmap])
    cv2.imwrite(str(output_path), composed)
    changed_pixels = int(np.count_nonzero(diff))
    total_pixels = int(diff.size)
    return {
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "change_ratio": round(changed_pixels / total_pixels, 4),
        "message": "Visual diff generated from before/after UI fixture.",
    }
