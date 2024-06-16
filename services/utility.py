from PySide6.QtCore import QBuffer
from PySide6.QtGui import QImage


def convert_image_to_byte(image: QImage) -> bytes:
    """
    Converts a QImage to a byte array in PNG format.

    Args:
        image (QImage): The image to be converted.

    Returns:
        bytes: The byte array representing the image in PNG format.
    """
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
    image.save(buffer, 'PNG')  # Save QImage to buffer as PNG format
    image_data = bytes(buffer.data())  # Get the binary data from the buffer
    buffer.close()
    return image_data


# --------------------------------------------------------------------------------------------------------------------
fa_to_en_digits = {
    '۰': '0',
    '۱': '1',
    '۲': '2',
    '۳': '3',
    '۴': '4',
    '۵': '5',
    '۶': '6',
    '۷': '7',
    '۸': '8',
    '۹': '9'
}


def convert_fa_digits_to_en(plate_number: str) -> str:
    """
    Converts Persian digits in a string to English digits.

    Args:
        plate_number (str): The string containing Persian digits.

    Returns:
        str: The string with Persian digits converted to English digits.
    """
    result = []
    for char in plate_number:
        if char in fa_to_en_digits:
            result.append(fa_to_en_digits[char])
        else:
            result.append(char)
    return ''.join(result)
