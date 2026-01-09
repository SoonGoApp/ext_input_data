"""
Images utils. Useful for OCR and image processing.
"""
import base64
from io import BytesIO
from typing import Self

import numpy as np

from soongo_data.utils.imports import safe_import

pil = safe_import(
    module_name='PIL',
    min_major_version=10,
    min_minor_version=4,
)
cv2 = safe_import(
    module_name='cv2',
    min_major_version=4,
    min_minor_version=10,
)
deskew = safe_import(
    module_name='deskew',
    min_major_version=1,
    min_minor_version=5,
)


class ImageProcesser:
    """ Callable object to pre process images before OCR. """

    def __init__(
        self: Self,
        lower_threshold: int = 150,
        higher_threshold: int = 300,
        unskewing: bool = True,
        dilate: bool = True,
    ):
        self.lower_threshold = lower_threshold
        self.higher_threshold = higher_threshold
        self.unskewing = unskewing
        self.dilate = dilate

    def __call__(self, pil_image) -> np.ndarray:
        """ Call the image processing function
        :param pil_image: PIL image to process

        :return: processed image
        """

        # Convert to grayscale and apply binary thresholding
        array_image = np.array(pil_image.convert("RGB"))
        page = cv2.cvtColor(array_image, cv2.COLOR_BGR2GRAY)
        _, page = cv2.threshold(
            page,
            self.lower_threshold,
            self.higher_threshold,
            cv2.THRESH_BINARY,
        )

        if self.unskewing:
            page = unskew_image(page)

        if self.dilate:
            page = dilate_image(page)

        return page


def unskew_image(image: np.ndarray) -> np.ndarray:
    angle = deskew.determine_skew(image)

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    deskewed = cv2.warpAffine(
        image,
        M,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return deskewed


def dilate_image(image: np.ndarray) -> np.ndarray:
    """ Dilate the image to make the text more readable
    :param image: image to dilate
    :return: dilated image
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    dilated = cv2.dilate(image, kernel, iterations=1)
    return dilated


def base64_image_encode(
    image_array: np.ndarray,
) -> str:
    """ Encode an image to base64 string

    :param image: image to encode
    :param encoding: encoding to use for the base64 string

    :returns: base64 encoded string
    """
    image = pil.Image.fromarray(image_array)

    # Save the image to a BytesIO buffer in PNG format
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)  # Move to the beginning of the buffer

    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    return image_base64
