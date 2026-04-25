import cv2
import numpy as np
import torch
from torchvision import transforms
from model import gaze_network
import mediapipe as mp
import os
import csv
import collections
from tqdm import tqdm
from scipy import interpolate
from scipy.signal import savgol_filter

# Constants
VIDEO_FILE_NAME = '/Users/nikos/Desktop/human/Jerome/Jerome.mp4'
SAVE_OUTPUT_VIDEO = False
VISUALIZE_GAZE = False

base_dir = os.path.dirname(VIDEO_FILE_NAME)
base_name = os.path.splitext(os.path.basename(VIDEO_FILE_NAME))[0]
OUTPUT_FILE_NAME = os.path.join(base_dir, f"{base_name}_gaze.mp4")
HEATMAP_OUTPUT = os.path.join(base_dir, f"{base_name}_gaze_heatmap.png")
csv_output = os.path.join(base_dir, "data", f"{base_name}_gaze.csv")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CAMERA_CALIBRATION = './red_epic_50mm_fullhd_calibration.xml'
MODEL_PATH = os.path.join(_SCRIPT_DIR, 'epoch_24_ckpt.pth.tar')

# Define a deque to store recent gaze vectors
SMOOTH_WINDOW = 3
gaze_history = collections.deque(maxlen=SMOOTH_WINDOW)


# Constants for blink detection
EYE_AR_THRESH = 0.2
EYE_AR_CONSEC_FRAMES = 3

trans = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# Initialize MediaPipe Face Mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(static_image_mode=False, refine_landmarks=True, max_num_faces=1,
                                  min_detection_confidence=0.9, min_tracking_confidence=0.9)


def calculate_eye_movement_speed(gaze_vectors, frame_indices, fps):
    speeds = []
    if len(gaze_vectors) < 2:
        print(f"Warning: Not enough gaze vectors to calculate speed. Got {len(gaze_vectors)}")
        return [0] * len(gaze_vectors)

    for i in range(len(gaze_vectors) - 1):
        start_vector = gaze_vectors[i]
        end_vector = gaze_vectors[i + 1]
        start_frame = frame_indices[i]
        end_frame = frame_indices[i + 1]

        # Normalize the vectors
        start_vector = start_vector / np.linalg.norm(start_vector)
        end_vector = end_vector / np.linalg.norm(end_vector)

        dot_product = np.dot(start_vector, end_vector)
        angle = np.arccos(np.clip(dot_product, -1.0, 1.0))
        angle_deg = np.degrees(angle)

        time_diff = (end_frame - start_frame) / fps
        if time_diff > 0:
            speed = angle_deg / time_diff
        else:
            speed = 0 if i == 0 else speeds[-1]  # Use previous speed if time_diff is 0

        speeds.append(speed)

    # Add the last speed for the last gaze vector
    speeds.append(speeds[-1] if speeds else 0)

    return speeds



def smooth_speeds(speeds, window_length=11, polyorder=3):
    """
    Apply Savitzky-Golay filter to smooth the speed data.
    """
    return savgol_filter(speeds, window_length, polyorder)


import numpy as np
from scipy.signal import savgol_filter

def interpolate_blink_speeds(speeds, blinks, fps, window_size=5):
    """
    Interpolate speeds during blinks using values before and after the blink.
    Handle all edge cases and ensure no out-of-bounds access.

    :param speeds: List of calculated speeds
    :param blinks: List of blink events (dictionaries with 'start' and 'end' keys)
    :param fps: Frames per second of the video
    :param window_size: Number of frames to consider before and after the blink
    :return: List of interpolated speeds
    """
    interpolated_speeds = speeds.copy()
    speed_length = len(speeds)

    for blink in blinks:
        start = max(0, blink['start'] - window_size)
        end = min(speed_length - 1, blink['end'] + window_size)

        if start >= end:
            continue  # Skip this blink if it's invalid

        pre_blink_speeds = speeds[start:blink['start']]
        post_blink_speeds = speeds[blink['end']:end + 1]

        if len(pre_blink_speeds) == 0:
            pre_blink_speed = np.mean(post_blink_speeds) if len(post_blink_speeds) > 0 else speeds[start]
        else:
            pre_blink_speed = np.mean(pre_blink_speeds)

        if len(post_blink_speeds) == 0:
            post_blink_speed = np.mean(pre_blink_speeds) if len(pre_blink_speeds) > 0 else speeds[end]
        else:
            post_blink_speed = np.mean(post_blink_speeds)

        blink_duration = min(blink['end'], speed_length - 1) - blink['start'] + 1
        total_duration = end - start + 1

        # Create a smooth transition
        transition = np.linspace(pre_blink_speed, post_blink_speed, total_duration)
        if len(transition) > 3:  # Only apply filter if we have enough points
            transition = savgol_filter(transition, window_length=min(len(transition), 11), polyorder=3)

        # Apply the interpolated speeds
        interpolated_speeds[start:end + 1] = transition[:end - start + 1]

    return interpolated_speeds


def eye_aspect_ratio(eye_landmarks):
    """Calculate the eye aspect ratio."""
    A = np.linalg.norm(eye_landmarks[1] - eye_landmarks[5])
    B = np.linalg.norm(eye_landmarks[2] - eye_landmarks[4])
    C = np.linalg.norm(eye_landmarks[0] - eye_landmarks[3])
    ear = (A + B) / (2.0 * C)
    return ear


def detect_blink(face_landmarks):
    """Detect if the person is blinking."""
    left_eye = np.array([[face_landmarks[i].x, face_landmarks[i].y] for i in [33, 160, 158, 133, 153, 144]])
    right_eye = np.array([[face_landmarks[i].x, face_landmarks[i].y] for i in [362, 385, 387, 263, 373, 380]])

    left_ear = eye_aspect_ratio(left_eye)
    right_ear = eye_aspect_ratio(right_eye)

    avg_ear = (left_ear + right_ear) / 2.0

    return avg_ear < EYE_AR_THRESH


def interpolate_gaze_and_speed(gaze_points, speeds, blink_events, frame_indices):
    """
    Interpolate gaze points and speeds during blinks.

    :param gaze_points: List of gaze points (x, y)
    :param speeds: List of gaze speeds
    :param blink_events: List of blink events (dict with 'start' and 'end' keys)
    :param frame_indices: List of frame indices
    :return: Tuple of interpolated gaze points and speeds
    """
    interpolated_gaze = gaze_points.copy()
    interpolated_speeds = speeds.copy()

    for blink in blink_events:
        start_idx = next((i for i, frame in enumerate(frame_indices) if frame >= blink['start']), None)
        end_idx = next((i for i, frame in enumerate(frame_indices) if frame > blink['end']), None)

        if start_idx is not None and end_idx is not None and start_idx > 0 and end_idx < len(gaze_points):
            # Interpolate gaze points
            pre_blink_point = gaze_points[start_idx - 1]
            post_blink_point = gaze_points[end_idx]

            # Interpolate speeds
            pre_blink_speed = speeds[start_idx - 1]
            post_blink_speed = speeds[end_idx]

            num_frames = end_idx - start_idx + 1

            # Create interpolation functions for x, y coordinates and speed
            t = np.linspace(0, 1, num_frames + 2)
            interp_x = interpolate.interp1d([0, 1], [pre_blink_point[0], post_blink_point[0]])
            interp_y = interpolate.interp1d([0, 1], [pre_blink_point[1], post_blink_point[1]])
            interp_speed = interpolate.interp1d([0, 1], [pre_blink_speed, post_blink_speed])

            # Apply interpolation
            for i, frame in enumerate(range(start_idx, end_idx + 1)):
                interpolated_gaze[frame] = (interp_x(t[i + 1]), interp_y(t[i + 1]))
                interpolated_speeds[frame] = interp_speed(t[i + 1])

    return interpolated_gaze, interpolated_speeds


def normalize_points(points, frame_shape):
    """Normalise les points pour qu'ils occupent tout l'espace de la heatmap."""
    x_min, y_min = np.min(points, axis=0)
    x_max, y_max = np.max(points, axis=0)

    normalized_points = []
    for point in points:
        x = (point[0] - x_min) / (x_max - x_min) * (frame_shape[1] - 1)
        y = (point[1] - y_min) / (y_max - y_min) * (frame_shape[0] - 1)
        normalized_points.append([x, y])

    return normalized_points

def smooth_gaze(gaze_point):
    """
    Lisse le point de regard en utilisant une moyenne mobile sur les derniers points.
    """
    gaze_history.append(gaze_point)
    if len(gaze_history) == SMOOTH_WINDOW:
        return np.mean(gaze_history, axis=0)
    return gaze_point


def adjust_gaze_angle(gaze_angles, vertical_adjustment=-200):
    """
    Ajuste l'angle vertical du regard.

    :param gaze_angles: Tuple (angle_horizontal, angle_vertical) en radians
    :param vertical_adjustment: Ajustement de l'angle vertical en degrés
    :return: Tuple ajusté (angle_horizontal, angle_vertical) en radians
    """
    horizontal, vertical = gaze_angles
    vertical += np.radians(vertical_adjustment)
    return (horizontal, vertical)


def estimateHeadPose(landmarks, face_model, camera, distortion, iterate=True):
    ret, rvec, tvec = cv2.solvePnP(face_model, landmarks, camera, distortion, flags=cv2.SOLVEPNP_EPNP)
    if iterate:
        ret, rvec, tvec = cv2.solvePnP(face_model, landmarks, camera, distortion, rvec, tvec, True)
    return rvec, tvec


def calculate_gaze_point(face_center, gaze_vector, frame_shape):
    # Calculer le point de regard en tenant compte de la position de la tête
    frame_center = np.array([frame_shape[1] / 2, frame_shape[0] / 2])

    # Calculer le point de regard sans ajustement
    gaze_point = face_center + gaze_vector

    # Calculer le vecteur du centre de l'image au point de regard
    gaze_direction = gaze_point - frame_center

    # Normaliser le vecteur de direction du regard
    gaze_direction_norm = gaze_direction / np.linalg.norm(gaze_direction)

    # Ajuster la longueur du vecteur en fonction de la distance entre le visage et le centre de l'image
    head_offset = np.linalg.norm(face_center - frame_center)
    adjusted_length = np.linalg.norm(gaze_vector) + head_offset

    # Calculer le point de regard ajusté
    adjusted_gaze_point = frame_center + gaze_direction_norm * adjusted_length

    return adjusted_gaze_point


def normalizeData_face(img, face_model, landmarks, hr, ht, cam):
    focal_norm = 960
    distance_norm = 600
    roiSize = (224, 224)

    ht = ht.reshape((3, 1))
    hR = cv2.Rodrigues(hr)[0]
    Fc = np.dot(hR, face_model.T) + ht
    two_eye_center = np.mean(Fc[:, 0:4], axis=1).reshape((3, 1))
    nose_center = np.mean(Fc[:, 4:6], axis=1).reshape((3, 1))
    face_center = np.mean(np.concatenate((two_eye_center, nose_center), axis=1), axis=1).reshape((3, 1))

    distance = np.linalg.norm(face_center)
    z_scale = distance_norm / distance
    cam_norm = np.array([
        [focal_norm, 0, roiSize[0] / 2],
        [0, focal_norm, roiSize[1] / 2],
        [0, 0, 1.0],
    ])
    S = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, z_scale],
    ])

    hRx = hR[:, 0]
    forward = (face_center / distance).reshape(3)
    down = np.cross(forward, hRx)
    down /= np.linalg.norm(down)
    right = np.cross(down, forward)
    right /= np.linalg.norm(right)
    R = np.c_[right, down, forward].T

    W = np.dot(np.dot(cam_norm, S), np.dot(R, np.linalg.inv(cam)))
    img_warped = cv2.warpPerspective(img, W, roiSize)

    landmarks_warped = cv2.perspectiveTransform(landmarks.reshape(1, -1, 2), W).reshape(-1, 2)

    return img_warped, landmarks_warped


def process_frame(frame, face_model, camera_matrix, camera_distortion, gaze_model, trans):
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_frame)
    gaze_point = None
    gaze_vector = None
    is_blinking = False

    if results.multi_face_landmarks:
        face_landmarks = results.multi_face_landmarks[0].landmark

        # Detect blink
        is_blinking = detect_blink(face_landmarks)
        if is_blinking:
            cv2.putText(frame, "BLINK", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        landmarks_sub = np.array([
            [face_landmarks[33].x, face_landmarks[33].y],
            [face_landmarks[133].x, face_landmarks[133].y],
            [face_landmarks[362].x, face_landmarks[362].y],
            [face_landmarks[263].x, face_landmarks[263].y],
            [face_landmarks[4].x, face_landmarks[4].y],
            [face_landmarks[152].x, face_landmarks[152].y]
        ])

        landmarks_sub[:, 0] *= frame.shape[1]
        landmarks_sub[:, 1] *= frame.shape[0]
        landmarks_sub = landmarks_sub.astype(float).reshape(6, 1, 2)

        hr, ht = estimateHeadPose(landmarks_sub, face_model, camera_matrix, camera_distortion)

        img_normalized, landmarks_warped = normalizeData_face(frame, face_model, landmarks_sub, hr, ht, camera_matrix)

        if not is_blinking:
            input_var = img_normalized[:, :, [2, 1, 0]]  # Convert BGR to RGB
            input_var = trans(input_var)
            input_var = input_var.unsqueeze(0)

            with torch.no_grad():
                pred_gaze = gaze_model(input_var)[0]
            pred_gaze_np = pred_gaze.cpu().numpy()

            # Calculate 3D gaze vector
            gaze_vector = np.array([
                -np.cos(pred_gaze_np[1]) * np.sin(pred_gaze_np[0]),
                -np.sin(pred_gaze_np[1]),
                -np.cos(pred_gaze_np[1]) * np.cos(pred_gaze_np[0])
            ])

            face_center = np.mean(landmarks_sub, axis=0).flatten().astype(int)
            gaze_length = 300
            gaze_point_vector = gaze_length * np.array(
                [-np.sin(pred_gaze_np[1]) * np.cos(pred_gaze_np[0]), -np.sin(pred_gaze_np[0])])

            # Calculate gaze point for visualization
            gaze_point = calculate_gaze_point(face_center, gaze_point_vector, frame.shape)

            # Apply smoothing
            gaze_point = smooth_gaze(gaze_point)
            cv2.arrowedLine(frame, tuple(face_center), tuple(gaze_point.astype(int)), (0, 0, 255), 2)

        for i, (x, y) in enumerate(landmarks_sub.reshape(-1, 2)):
            cv2.circle(frame, (int(x), int(y)), 3, (0, 255, 0), -1)
            cv2.putText(frame, str(i), (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)

    return frame, gaze_vector, gaze_point, is_blinking


def create_heatmap(gaze_points, shape=(1080, 1920), point_size=3, blur_size=25, opacity=0.7):
    """
    Crée une heatmap à partir des points de regard normalisés.

    :param gaze_points: Liste de points de regard [x, y]
    :param shape: Tuple (height, width) de la heatmap
    :param point_size: Taille des points sur la heatmap
    :param blur_size: Taille du flou gaussien appliqué
    :param opacity: Opacité de la heatmap (0-1)
    :return: Image de la heatmap
    """
    heatmap = np.zeros(shape, dtype=np.float32)

    for point in gaze_points:
        x, y = int(point[0]), int(point[1])
        if 0 <= x < shape[1] and 0 <= y < shape[0]:
            cv2.circle(heatmap, (x, y), point_size, (1, 1, 1), -1)

    # Normaliser la heatmap
    heatmap = heatmap / np.max(heatmap)

    # Appliquer un flou gaussien
    heatmap = cv2.GaussianBlur(heatmap, (blur_size, blur_size), 0)

    # Convertir en une image en couleur
    heatmap_color = cv2.applyColorMap((heatmap * 255).astype(np.uint8), cv2.COLORMAP_JET)

    # Créer un masque alpha pour la transparence
    alpha = (heatmap * 255 * opacity).astype(np.uint8)

    return heatmap_color, alpha


def overlay_heatmap(frame, heatmap_color, alpha):
    """
    Superpose la heatmap sur l'image d'origine.

    :param frame: Image d'origine
    :param heatmap_color: Heatmap en couleur
    :param alpha: Masque alpha pour la transparence
    :return: Image avec la heatmap superposée
    """
    # Redimensionner la heatmap si nécessaire
    if frame.shape[:2] != heatmap_color.shape[:2]:
        heatmap_color = cv2.resize(heatmap_color, (frame.shape[1], frame.shape[0]))
        alpha = cv2.resize(alpha, (frame.shape[1], frame.shape[0]))

    # Créer un masque 3 canaux
    alpha = cv2.merge([alpha, alpha, alpha])

    # Superposer la heatmap sur l'image d'origine
    return cv2.addWeighted(frame, 1, cv2.bitwise_and(heatmap_color, alpha), 1, 0)


def main():
    cap = cv2.VideoCapture(VIDEO_FILE_NAME)
    if not cap.isOpened():
        print(f"Error: Unable to open video file {VIDEO_FILE_NAME}")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    out = None
    if SAVE_OUTPUT_VIDEO:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(OUTPUT_FILE_NAME, fourcc, fps, (frame_width, frame_height))

    fs = cv2.FileStorage(CAMERA_CALIBRATION, cv2.FILE_STORAGE_READ)
    camera_matrix = fs.getNode('Camera_Matrix').mat()
    camera_distortion = fs.getNode('Distortion_Coefficients').mat()

    # Scale camera matrix
    scale_x = frame_width / 6000
    scale_y = frame_height / 4000
    camera_matrix[0, 0] *= scale_x
    camera_matrix[0, 2] *= scale_x
    camera_matrix[1, 1] *= scale_y
    camera_matrix[1, 2] *= scale_y

    face_model_load = np.loadtxt(os.path.join(_SCRIPT_DIR, 'face_model.txt'))
    landmark_use = [20, 23, 26, 29, 15, 19]
    face_model = face_model_load[landmark_use, :]

    gaze_model = gaze_network()
    try:
        ckpt = torch.load(MODEL_PATH, map_location=torch.device('cpu'), weights_only=True)
        if isinstance(ckpt, dict) and 'model_state' in ckpt:
            gaze_model.load_state_dict(ckpt['model_state'])
        else:
            gaze_model.load_state_dict(ckpt)
    except Exception as e:
        print(f"Error loading model: {e}")
        return
    gaze_model.eval()

    gaze_vectors = []
    gaze_points = []
    blink_events = []
    current_blink = None
    frame_100 = None

    pbar = tqdm(total=total_frames, desc="Processing frames", unit="frame")

    for frame_count in range(total_frames):
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count == 99:  # Save frame 100 (0-indexed)
            frame_100 = frame.copy()

        processed_frame, gaze_vector, gaze_point, is_blinking = process_frame(frame, face_model, camera_matrix, camera_distortion,
                                                                              gaze_model, trans)

        # Handle blink events
        if is_blinking and current_blink is None:
            current_blink = {'start': frame_count}
        elif not is_blinking and current_blink is not None:
            current_blink['end'] = frame_count - 1
            blink_events.append(current_blink)
            current_blink = None

        # Record gaze vector and point
        if gaze_vector is not None and gaze_point is not None:
            gaze_vectors.append((frame_count, gaze_vector))
            gaze_points.append((frame_count, gaze_point))

        if SAVE_OUTPUT_VIDEO:
            out.write(processed_frame)

        if VISUALIZE_GAZE:
            cv2.imshow('Gaze Estimation', processed_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        pbar.update(1)

    pbar.close()

    # Finalize any ongoing blink
    if current_blink is not None:
        current_blink['end'] = total_frames - 1
        blink_events.append(current_blink)

    cap.release()
    if out:
        out.release()
    cv2.destroyAllWindows()

    # Post-processing
    final_gaze_vectors = []
    final_gaze_points = []
    final_blink_data = []
    frame_indices = []

    gaze_index = 0
    for frame in range(total_frames):
        is_blinking = any(blink['start'] <= frame <= blink['end'] for blink in blink_events)
        final_blink_data.append(1 if is_blinking else 0)

        if gaze_index < len(gaze_vectors) and frame == gaze_vectors[gaze_index][0]:
            final_gaze_vectors.append(gaze_vectors[gaze_index][1])
            final_gaze_points.append(gaze_points[gaze_index][1])
            frame_indices.append(frame)
            gaze_index += 1
        else:
            final_gaze_vectors.append(None)
            final_gaze_points.append(None)

    # Filter out None values
    valid_gaze_vectors = [gv for gv in final_gaze_vectors if gv is not None]
    valid_frame_indices = [fi for fi, gv in zip(frame_indices, final_gaze_vectors) if gv is not None]

    # Calculate initial speeds using non-interpolated gaze vectors
    if len(valid_gaze_vectors) > 1:
        if len(valid_gaze_vectors) != len(valid_frame_indices):
            print(
                f"Warning: Mismatch between valid_gaze_vectors ({len(valid_gaze_vectors)}) and valid_frame_indices ({len(valid_frame_indices)})")
            # Use the shorter length to avoid index errors
            min_length = min(len(valid_gaze_vectors), len(valid_frame_indices))
            valid_gaze_vectors = valid_gaze_vectors[:min_length]
            valid_frame_indices = valid_frame_indices[:min_length]

        initial_speeds = calculate_eye_movement_speed(valid_gaze_vectors, valid_frame_indices, fps)

        if len(valid_frame_indices) != len(initial_speeds):
            print(
                f"Warning: Mismatch between valid_frame_indices ({len(valid_frame_indices)}) and initial_speeds ({len(initial_speeds)})")
            # Adjust lengths to match
            min_length = min(len(valid_frame_indices), len(initial_speeds))
            valid_frame_indices = valid_frame_indices[:min_length]
            initial_speeds = initial_speeds[:min_length]

        if len(valid_frame_indices) > 1:
            # Interpolate speeds to match the length of final_gaze_vectors
            speed_interpolator = interpolate.interp1d(valid_frame_indices, initial_speeds, kind='linear',
                                                      bounds_error=False,
                                                      fill_value=(initial_speeds[0], initial_speeds[-1]))
            interpolated_speeds = speed_interpolator(range(total_frames))
        else:
            print("Not enough valid frames to interpolate speeds. Using constant speed.")
            interpolated_speeds = [initial_speeds[0] if initial_speeds else 0] * total_frames
    else:
        print("Not enough valid gaze vectors to calculate speed. Using zero speed.")
        interpolated_speeds = [0] * total_frames

    # Interpolate gaze points and speeds during blinks
    interpolated_gaze_points, interpolated_speeds = interpolate_gaze_and_speed(
        final_gaze_points, interpolated_speeds, blink_events, range(total_frames)
    )

    # Apply smoothing to interpolated speeds
    smoothed_speeds = smooth_speeds(interpolated_speeds, window_length=11, polyorder=3)
    smoothed_speeds = smooth_speeds(smoothed_speeds, window_length=21, polyorder=3)

    # Normalize gaze points for heatmap
    valid_points = [p for p in interpolated_gaze_points if p is not None]
    normalized_points = normalize_points(valid_points, (frame_height, frame_width))

    # Create and save heatmap
    heatmap_color, alpha = create_heatmap(normalized_points, shape=(frame_height, frame_width),
                                          point_size=2, blur_size=15, opacity=0.7)
    cv2.imwrite(HEATMAP_OUTPUT, heatmap_color)

    # Overlay heatmap on frame 100
    if frame_100 is not None:
        result = overlay_heatmap(frame_100, heatmap_color, alpha)
        cv2.imwrite(os.path.join(base_dir, f"{base_name}_heatmap_overlay_frame100.png"), result)
    else:
        print("Unable to overlay heatmap on frame 100: frame not available.")

    # Save data to CSV
    with open(csv_output, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['frame', 'x', 'y', 'blink', 'speed'])
        for frame, (point, blink, speed) in enumerate(zip(interpolated_gaze_points, final_blink_data, smoothed_speeds)):
            if point is not None:
                csv_writer.writerow([frame, point[0], point[1], blink, speed])
            else:
                csv_writer.writerow([frame, '', '', '', ''])

    if SAVE_OUTPUT_VIDEO:
        print(f'Processed video saved to: {OUTPUT_FILE_NAME}')
    print(f'Heatmap saved to: {HEATMAP_OUTPUT}')
    print(f'Heatmap overlay saved to: {os.path.join(base_dir, f"{base_name}_heatmap_overlay_frame100.png")}')
    print(f'Gaze points, blink data, and speed data saved to: {csv_output}')

if __name__ == '__main__':
    main()