import cv2
import numpy as np


def analyze_skin(image_path):

    # LOAD IMAGE
    image = cv2.imread(image_path)

    if image is None:
        return None

    # CONVERT TO GRAYSCALE
    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

     # =========================
    # TEXTURE ANALYSIS
    # =========================

    texture_score = cv2.Laplacian(
        gray,
        cv2.CV_64F
    ).var()

    # LOAD FACE CASCADE
    face_cascade = cv2.CascadeClassifier(
        'modules/cascades/haarcascade_frontalface_default.xml'
    )

    # DETECT FACE
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5
    )

    # NO FACE DETECTED
    if len(faces) == 0:

        return {
            "error": "No face detected"
        }

    # TAKE FIRST FACE
    (x, y, w, h) = faces[0]

    face_region = image[
        y:y+h,
        x:x+w
    ]

    # ANALYZE BRIGHTNESS
    brightness = np.mean(face_region)

    # ANALYZE REDNESS
    redness = np.mean(face_region[:, :, 2])

    return {

    "brightness": round(
        brightness,
        2
    ),

    "redness": round(
        redness,
        2
    ),

    "texture": round(
        texture_score,
        2
    )

}