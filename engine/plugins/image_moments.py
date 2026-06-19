from registry import vision_node, NodeProcessor
import cv2
import numpy as np


@vision_node(
    type_id='image_moments',
    label='Image Moments',
    category='measure',
    icon='Target',
    description="Compute spatial image moments and the 7 invariant Hu moments "
                "(scale/rotation/translation invariant shape descriptors). "
                "Reports the centroid, area and log-scaled Hu moments. "
                "Source can be a binary mask (if connected) or the Otsu-thresholded "
                "grayscale image. Optionally draws the centroid on the output frame.",
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
        {'id': 'mask', 'label': 'Mask', 'color': 'mask'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Overlay', 'color': 'image'},
        {'id': 'data', 'label': 'Moments', 'color': 'dict'},
    ],
    params=[
        {'id': 'source', 'label': 'Source', 'type': 'enum',
         'options': ['Largest Contour', 'Whole Mask'], 'default': 'Largest Contour'},
        {'id': 'draw_overlay', 'label': 'Draw Overlay', 'type': 'bool', 'default': True},
    ]
)
class ImageMomentsNode(NodeProcessor):

    @staticmethod
    def _to_binary(mask, image):
        """Return a single-channel uint8 binary image (0/255)."""
        if mask is not None:
            if mask.ndim == 3:
                mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
            return binary.astype(np.uint8)
        # Otsu on grayscale of the input image
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary.astype(np.uint8)

    @staticmethod
    def _hu_log(hu):
        """Sign-preserving log10 scaling of the 7 Hu moments."""
        out = []
        for v in hu.flatten():
            v = float(v)
            if v == 0.0:
                out.append(0.0)
            else:
                out.append(float(-np.sign(v) * np.log10(abs(v))))
        return out

    def process(self, inputs, params):
        image = inputs.get('image')
        mask = inputs.get('mask')
        if image is None:
            return {'main': None, 'data': None}

        source = params.get('source', 'Largest Contour')
        draw_overlay = bool(params.get('draw_overlay', True))

        binary = self._to_binary(mask, image)

        moments = None
        contour = None
        if source == 'Largest Contour':
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                contour = max(contours, key=cv2.contourArea)
                moments = cv2.moments(contour)
        if moments is None:
            # Whole-mask path, or fallback when no contour was found
            moments = cv2.moments(binary, binaryImage=True)

        m00 = moments['m00']
        if m00 != 0:
            cx = moments['m10'] / m00
            cy = moments['m01'] / m00
        else:
            cx = cy = 0.0
        area = float(m00)

        hu = cv2.HuMoments(moments)
        hu_moments = self._hu_log(hu)

        # Build BGR overlay output
        if image.ndim == 2:
            overlay = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            overlay = image.copy()

        if draw_overlay and m00 != 0:
            cxi, cyi = int(round(cx)), int(round(cy))
            if contour is not None:
                cv2.drawContours(overlay, [contour], -1, (0, 255, 255), 2)
            cv2.circle(overlay, (cxi, cyi), 6, (0, 0, 255), -1)
            cv2.line(overlay, (cxi - 14, cyi), (cxi + 14, cyi), (0, 0, 255), 2)
            cv2.line(overlay, (cxi, cyi - 14), (cxi, cyi + 14), (0, 0, 255), 2)
            cv2.putText(overlay, f"area={area:.0f}", (cxi + 10, cyi - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

        return {
            'main': overlay,
            'data': {
                'centroid': [float(cx), float(cy)],
                'area': area,
                'hu_moments': hu_moments,
                'raw_moments': {k: float(v) for k, v in moments.items()},
            }
        }
