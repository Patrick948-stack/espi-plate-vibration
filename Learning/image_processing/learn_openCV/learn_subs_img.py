# Importing OpenCV, a powerful library for image processing and computer vision tasks
import cv2

# Importing NumPy, which lets us work with images as arrays of numbers (pixels)
import numpy as np

# Importing Pillow (PIL), a library that makes it easy to open and manipulate images
from PIL import Image

# Importing pillow-heif so Pillow can understand HEIC files (iPhone photo format)
import pillow_heif

# Registering pillow-heif with Pillow — this is required so that Image.open()
# knows how to decode .HEIC files. Without this line, opening a HEIC would fail.
pillow_heif.register_heif_opener()


def get_image_path(prompt):
    # Asking the user to type a file path, stripping accidental whitespace.
    path = input(prompt).strip()
    return path


def load_grayscale(path):
    # Opening the image file and converting it to grayscale ("L" mode = luminance, 0–255).
    # Working in grayscale simplifies the difference calculation — only one brightness
    # channel is compared instead of three (R, G, B).
    image = Image.open(path)
    gray = image.convert("L")
    # Converting the Pillow grayscale image into a NumPy array.
    # OpenCV works with arrays, not Pillow objects.
    # Each value in the array is a pixel brightness from 0 (black) to 255 (white).
    return np.array(gray)


def compute_and_show_difference(img1, img2):
    # Making sure both images loaded correctly before proceeding.
    assert img1 is not None, "img1 could not be read, check file path"
    assert img2 is not None, "img2 could not be read, check file path"

    # Also checking that both images are the same size.
    # cv2.absdiff() requires matching dimensions — mismatched sizes would cause an error.
    assert img1.shape == img2.shape, f"Images must be the same size: {img1.shape} vs {img2.shape}"

    # Computing the absolute difference between the two images pixel by pixel.
    # For each pixel: diff = |img1_pixel - img2_pixel|
    # Bright spots in the result = areas that changed a lot between the two images.
    # Dark spots = areas that stayed the same.
    diff = cv2.absdiff(img1, img2)

    # Wraps automatically for uint8 (0-255)

    modulo_diff = img2 - img1

    # normalize: NORM_MINMAX stretches the least bright pixel to 0 and the brightest to 255,
    # making the interference pattern clearly visible and human-readable.
    diff_amplified = cv2.normalize(
        src=diff,
        dst=None,
        alpha=0,
        beta=255,
        norm_type=cv2.NORM_MINMAX,
        dtype=cv2.CV_8U
    )
    # I use Otsu's binarization to find the threshold value, it's an automatic technique in opencv that finds the optimal treshold
    optimal_tresh, binary_output = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    print(f"The calculated optimal threshold value is: {optimal_tresh}")

    # Displaying the amplified difference image in a window.
    # Bright regions are where the two photos differ most.
    cv2.imshow("Difference", diff)

    cv2.imshow("Difference Amplified", diff_amplified)

    cv2.imshow("Binary Mask", binary_output)

    cv2.imshow("Modulo Difference", modulo_diff)

    # Keeping the window open until any key is pressed.
    # Without this, the window would flash and disappear immediately.
    cv2.waitKey(0)

    # Closing all OpenCV windows and freeing memory once done.
    cv2.destroyAllWindows()


path1 = get_image_path("Enter path to first image: ")
path2 = get_image_path("Enter path to second image: ")

img1 = load_grayscale(path1)
img2 = load_grayscale(path2)

compute_and_show_difference(img1, img2)
