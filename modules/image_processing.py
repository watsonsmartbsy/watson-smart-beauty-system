import cv2
import numpy as np
import gc

# Load Haar Cascade only once
FACE_CASCADE = cv2.CascadeClassifier(
    "modules/cascades/haarcascade_frontalface_default.xml"
)


def analyze_skin(image_path):

    # =========================
    # LOAD IMAGE
    # =========================
    image = cv2.imread(image_path)

    if image is None:
        return {
            "error": "Unable to read image."
        }

    # =========================
    # RESIZE IMAGE
    # Reduce memory usage
    # =========================
    max_width = 640

    h, w = image.shape[:2]

    if w > max_width:
        scale = max_width / w
        new_width = int(w * scale)
        new_height = int(h * scale)

        image = cv2.resize(
            image,
            (new_width, new_height),
            interpolation=cv2.INTER_AREA
        )

    # =========================
    # CONVERT TO GRAYSCALE
    # =========================
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

    # =========================
    # FACE DETECTION
    # =========================
    faces = FACE_CASCADE.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80)
    )

    if len(faces) == 0:

        del image
        del gray
        gc.collect()

        return {
            "error": "No face detected"
        }

    # =========================
    # TAKE FIRST FACE
    # =========================
    (x, y, w, h) = faces[0]

    face_region = image[
        y:y+h,
        x:x+w
    ]

    # =========================
    # BRIGHTNESS
    # =========================
    brightness = np.mean(face_region)

    # =========================
    # REDNESS
    # =========================
    redness = np.mean(face_region[:, :, 2])

    # =========================
    # CLEAN MEMORY
    # =========================
    del image
    del gray
    del face_region
    gc.collect()

    # =========================
    # RETURN RESULT
    # =========================
    return {
        "brightness": round(brightness, 2),
        "redness": round(redness, 2),
        "texture": round(texture_score, 2)
    }
