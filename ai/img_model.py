# img_model.py

import math

import cv2
import numpy as np
from PIL import Image, ImageEnhance
from PIL.ImageQt import ImageQt
from PySide6.QtGui import QPixmap


def sharpen_new(img):
    """
    Apply K-means clustering for color quantization to sharpen an image.

    Parameters:
    - img (np.ndarray): The input image.

    Returns:
    - np.ndarray: The sharpened image.
    """
    Z = img.reshape((-1, 3))
    Z = np.float32(Z)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    K = 2
    ret, label, center = cv2.kmeans(Z, K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    center = np.uint8(center)
    res = center[label.flatten()]
    res2 = res.reshape((img.shape))
    return res2


def sharpen_image(img):
    """
        Sharpen an image using a defined kernel.

        Parameters:
        - img (np.ndarray): The input image.

        Returns:
        - np.ndarray: The sharpened image.
        """

    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])
    return cv2.filter2D(src=img, ddepth=-1, kernel=kernel)


def brighten_image(img):
    """
     Brighten an image using ImageEnhance.

     Parameters:
     - img (Image.Image): The PIL image to brighten.

     Note: This function modifies the input image but does not return it.
     """
    enhancer = ImageEnhance.Brightness(img)
    factor = 2
    enhancer.enhance(factor)


def rotate_image(image, angle):
    """
    Rotate an image by a specific angle.

    Parameters:
    - image (np.ndarray): The input image.
    - angle (float): The rotation angle in degrees.

    Returns:
    - np.ndarray: The rotated image.
    """
    image_center = tuple(np.array(image.shape[1::-1]) / 2)
    rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
    return result


def compute_skew(src_img):
    """
       Compute the skew angle of an image.

       Parameters:
       - src_img (np.ndarray): The source image.

       Returns:
       - float: The skew angle in degrees.
       """
    if len(src_img.shape) == 3:
        h, w, _ = src_img.shape
    elif len(src_img.shape) == 2:
        h, w = src_img.shape
    else:
        print('upsupported image type')

    img = cv2.medianBlur(src_img, 3)

    edges = cv2.Canny(img, threshold1=30, threshold2=100, apertureSize=3, L2gradient=True)
    lines = cv2.HoughLinesP(edges, 1, math.pi / 180, 30, minLineLength=w / 4.0, maxLineGap=h / 4.0)
    angle = 0.0
    cnt = 0
    if lines is not None and lines.any():
        for x1, y1, x2, y2 in lines[0]:
            ang = np.arctan2(y2 - y1, x2 - x1)
            if math.fabs(ang) <= 30:  # excluding extreme rotations
                angle += ang
                cnt += 1

    if cnt == 0:
        return 0.0
    return (angle / cnt) * 180 / math.pi


def deskew(src_img):
    """
       Deskew an image based on the computed skew angle.

       Parameters:
       - src_img (np.ndarray): The source image.

       Returns:
       - np.ndarray: The deskewed image.
       """
    return rotate_image(src_img, compute_skew(src_img))


def grayscale(image):
    """
        Convert an image to grayscale and apply noise removal and thickening of fonts.

        Parameters:
        - image (np.ndarray): The input color image.

        Returns:
        - np.ndarray: The processed grayscale image.
        """
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh, im_bw = cv2.threshold(gray_image, 210, 230, cv2.THRESH_BINARY)
    no_noise = noise_removal(im_bw)
    dilated_image = thick_font(no_noise)
    return dilated_image


def noise_removal(image):
    """
        Apply morphological operations to remove noise from an image.

        Parameters:
        - image (np.ndarray): The input image.

        Returns:
        - np.ndarray: The noise-removed image.
        """
    import numpy as np
    kernel = np.ones((1, 1), np.uint8)
    image = cv2.dilate(image, kernel, iterations=1)
    kernel = np.ones((1, 1), np.uint8)
    image = cv2.erode(image, kernel, iterations=1)
    image = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
    image = cv2.medianBlur(image, 3)
    return (image)


def thin_font(image):
    """
       Apply erosion to make the font thinner in an image.

       Parameters:
       - image (np.ndarray): The input image.

       Returns:
       - np.ndarray: The image with a thinner font.
       """
    import numpy as np
    image = cv2.bitwise_not(image)
    kernel = np.ones((2, 2), np.uint8)
    image = cv2.erode(image, kernel, iterations=1)
    image = cv2.bitwise_not(image)
    return (image)


def thick_font(image):
    """
       Apply dilation to make the font thicker in an image.

       Parameters:
       - image (np.ndarray): The input image.

       Returns:
       - np.ndarray: The image with a thicker font.
       """
    import numpy as np
    image = cv2.bitwise_not(image)
    kernel = np.ones((2, 2), np.uint8)
    image = cv2.dilate(image, kernel, iterations=1)
    image = cv2.bitwise_not(image)
    return (image)


def opencv_resize(image, ratio):
    """
        Resize an image by a given ratio using OpenCV.

        Parameters:
        - image (np.ndarray): The input image.
        - ratio (float): The scaling ratio.

        Returns:
        - np.ndarray: The resized image.
        """

    width = int(image.shape[1] * ratio)
    height = int(image.shape[0] * ratio)
    dim = (width, height)
    return cv2.resize(image, dim, interpolation=cv2.INTER_AREA)


def approximate_contour(contour):
    """
       Approximate contours to a simpler shape.

       Parameters:
       - contour (np.ndarray): The contour to approximate.

       Returns:
       - np.ndarray: The approximated contour.
       """
    peri = cv2.arcLength(contour, True)
    return cv2.approxPolyDP(contour, 0.032 * peri, True)


def get_receipt_contour(contours):
    """
        Get the contour of a receipt from a list of contours.

        Parameters:
        - contours (list): The list of contours.

        Returns:
        - np.ndarray: The receipt contour, if found.
        """
    for c in contours:
        approx = approximate_contour(c)
        if len(approx) == 4:
            return approx


def wrap_perspective(img, rect):
    """
    Apply perspective wrapping to an image given a rectangle defining the ROI.

    Parameters:
    - img (np.ndarray): The source image.
    - rect (np.ndarray): The rectangle defining the ROI.

    Returns:
    - np.ndarray: The image after perspective wrapping.
    """
    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    maxHeight = max(int(heightA), int(heightB))
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, M, (maxWidth, maxHeight))


def to_img_opencv(imgPIL):
    """
    Convert a PIL image to an OpenCV image.

    Parameters:
    - imgPIL (Image.Image): The PIL image.

    Returns:
    - np.ndarray: The OpenCV image.
    """

    i = np.array(imgPIL)
    red = i[:, :, 0].copy()
    i[:, :, 0] = i[:, :, 2].copy()
    i[:, :, 2] = red
    return i


def to_img_pil(imgOpenCV):
    """
      Convert an OpenCV image to a PIL image.

      Parameters:
      - imgOpenCV (np.ndarray): The OpenCV image.

      Returns:
      - Image.Image: The PIL image.
      """
    return Image.fromarray(cv2.cvtColor(imgOpenCV, cv2.COLOR_BGR2RGB));


def convert_cv_image_to_qt_image(self, cv_img):
    """
      Convert an OpenCV image to a Qt image.

      Parameters:
      - cv_img (np.ndarray): The OpenCV image.

      Returns:
      - QPixmap: The Qt image.
      """
    rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    PIL_image = Image.fromarray(rgb_image).convert('RGB')
    return QPixmap.fromImage(ImageQt(PIL_image))


def controller(img, brightness=250, contrast=150):
    """
     Adjust the brightness and contrast of an image.

     Parameters:
     - img (np.ndarray): The input image.
     - brightness (int): The brightness value.
     - contrast (int): The contrast value.

     Returns:
     - np.ndarray: The image with adjusted brightness and contrast.
     """
    brightness = int((brightness - 0) * (255 - (-255)) / (510 - 0) + (-255))

    contrast = int((contrast - 0) * (127 - (-127)) / (254 - 0) + (-127))

    if brightness != 0:

        if brightness > 0:

            shadow = brightness

            max = 255

        else:

            shadow = 0
            max = 255 + brightness

        al_pha = (max - shadow) / 255
        ga_mma = shadow
        cal = cv2.addWeighted(img, al_pha,
                              img, 0, ga_mma)

    else:
        cal = img

    if contrast != 0:
        Alpha = float(131 * (contrast + 127)) / (127 * (131 - contrast))
        Gamma = 127 * (1 - Alpha)
        cal = cv2.addWeighted(cal, Alpha, cal, 0, Gamma)

    return cal


text_font = cv2.FONT_HERSHEY_DUPLEX
colorss = (0, 0, 255)
text_font_scale = 2


def draw_fps(videoFrame, fps):
    """
       Draw FPS information on a video frame.

       Parameters:
       - videoFrame (np.ndarray): The video frame on which to draw the FPS.
       - fps (float): The FPS value to draw.
       """
    text = 'fps: ' + str(int(fps))

    rectangle_bgr = (0, 0, 0)
    text_offset_x = 50
    text_offset_y = 75
    (text_width, text_height) = cv2.getTextSize(text, text_font, text_font_scale, thickness=5)[0]
    box_coords = (
        (text_offset_x + 20, text_offset_y), (text_offset_x + text_width + 20, text_offset_y - text_height - 20))

    cv2.rectangle(videoFrame, box_coords[0], box_coords[1], rectangle_bgr, cv2.FILLED)
    cv2.putText(videoFrame, text, box_coords[0], text_font, text_font_scale, color=(255, 0, 0), thickness=5)


def resize_image(image_matrix, nh, nw):
    """
        Resize an image to new height and width using basic interpolation.

        Parameters:
        - image_matrix (np.ndarray): The source image.
        - nh (int): The new height.
        - nw (int): The new width.

        Returns:
        - np.ndarray: The resized image.
        """
    image_size = image_matrix.shape
    oh = image_size[0]
    ow = image_size[1]

    re_image_matrix = np.array([
        np.array([image_matrix[(oh * h // nh)][(ow * w // nw)] for w in range(nw)])
        for h in range(nh)
    ])

    return re_image_matrix


def concat_images(image_set, how):
    """
       Concatenate multiple images together.

       Parameters:
       - image_set (list): The list of images to concatenate.
       - how (str): The direction of concatenation ('vertical' or 'horizontal').

       Returns:
       - np.ndarray: The concatenated image.
       """
    shape_vals = [imat.shape for imat in image_set]
    shape_lens = [len(ishp) for ishp in shape_vals]
    channel_flag = True if len(set(shape_lens)) == 1 else False

    if channel_flag:
        ideal_shape = max(shape_vals)
        images_resized = [
            resize_image(image_matrix=imat, nh=ideal_shape[0], nw=ideal_shape[1])
            if imat.shape != ideal_shape else imat for imat in image_set
        ]
    else:
        return False

    images_resized = tuple(images_resized)

    if (how == 'vertical') or (how == 0):
        axis_val = 0
    elif (how == 'horizontal') or (how == 1):
        axis_val = 1
    else:
        axis_val = 1
    concats = np.concatenate(images_resized, axis=axis_val)
    return concats
