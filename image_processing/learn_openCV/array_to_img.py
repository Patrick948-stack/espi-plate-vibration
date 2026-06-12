# Code logic adapted from the official OpenCV and NumPy documentation.
# For reference on how OpenCV uses NumPy arrays, see:
# https://docs.opencv.org/ and https://numpy.org

# ─── IMPORTS ──────────────────────────────────────────────────────────────────

# cv2 is the OpenCV library. OpenCV (Open Source Computer Vision) is a library
# built for real-time image processing. It can read, write, transform, and
# display images and videos. We import it as "cv2" — that's just its module name.
import cv2

# NumPy is the foundational library for numerical computing in Python.
# It gives us the "array" data structure, which is a grid of numbers stored
# efficiently in memory. Images ARE arrays — a 300x300 pixel image is just a
# 300x300 grid of numbers. We import it as "np" — a universal convention.
import numpy as np


# ─── STEP 1: CREATE A BLANK IMAGE AS A NUMPY ARRAY ───────────────────────────

# np.zeros(...) creates an array filled entirely with 0s (zero = black).
# Think of it as allocating a blank canvas in memory.
#
# The first argument (300, 300, 3) is the SHAPE of the array — its dimensions:
#   - 300  → height: 300 rows of pixels (top to bottom)
#   - 300  → width:  300 columns of pixels (left to right)
#   - 3    → channels: each pixel has 3 values (Blue, Green, Red in OpenCV)
#
# So img_array[row, col] gives you one pixel, and img_array[row, col, channel]
# gives you one colour component of that pixel.
#
# dtype=np.uint8 sets the data type of every number in the array.
# uint8 = "unsigned 8-bit integer", which means values from 0 to 255.
# This is the standard range for pixel colour values:
#   0   → no intensity (black / off)
#   255 → full intensity (brightest)
# Using uint8 also saves memory — each value takes exactly 1 byte.
img_array = np.zeros((300, 300, 3), dtype=np.uint8)

# img_array[:] = [255, 255, 0] fills EVERY pixel with the colour [255, 255, 0].
#
# The colon [:] is NumPy "slice" syntax — it means "all rows".
# So img_array[:] means "every row in the array", which is every pixel.
#
# [255, 255, 0] is a BGR colour value (OpenCV uses Blue-Green-Red, NOT RGB):
#   Blue  = 255 (full)
#   Green = 255 (full)
#   Red   = 0   (none)
# Blue + Green with no Red = CYAN. So this paints the whole canvas cyan.
#
# Why BGR instead of RGB? OpenCV was originally built on Windows, where the
# native image format stored colours in BGR order. That convention stuck.
img_array[:] = [255, 255, 0] #cyan canvas/background


# ─── STEP 2: DRAW A PATTERN BY DIRECTLY MODIFYING ARRAY VALUES ───────────────

# img_array[135:165, :] selects a horizontal SLICE of the array.
# NumPy slice syntax is  array[row_start:row_stop, col_start:col_stop]
#
# 135:165  → rows 135 through 164 (the stop index is exclusive — 165 is not included)
#   This is a 30-pixel-tall band across the vertical middle of the 300px image.
# :        → ALL columns (left edge to right edge, full width)
#
# Assigning [0, 0, 255] sets every pixel in that band to:
#   Blue=0, Green=0, Red=255 → pure RED
# This paints a horizontal red bar across the middle.
img_array[135:165, :] = [0, 0, 255]  # Horizontal red bar

# img_array[:, 135:165] selects a vertical SLICE.
# :        → ALL rows (full height)
# 135:165  → columns 135 through 164 (30-pixel-wide band down the middle)
#
# Assigning [0, 0, 255] paints a vertical red bar down the middle.
#
# Together with the horizontal bar above, this creates a RED CROSS ("+") shape
# centred on the cyan background. Where the two bars overlap, red wins because
# we write the vertical bar second — it overwrites whatever was there.
img_array[:, 135:165] = [0, 0, 255]  # Vertical red bar


# ─── STEP 3: SAVE THE ARRAY AS AN IMAGE FILE ─────────────────────────────────

# cv2.imwrite(filename, array) converts the NumPy array into an image file
# and writes it to disk. OpenCV figures out the file format from the extension:
#   .png  → lossless compression (no quality loss — great for generated images)
#   .jpg  → lossy compression (smaller file, but some detail is lost)
#
# The file will be saved in the CURRENT WORKING DIRECTORY — wherever you run
# the script from. You can also give a full path like "/Users/you/Desktop/img.png".
#
# Returns True if saving succeeded, False if it failed (e.g. bad path).
cv2.imwrite("generated_image.png", img_array)


# ─── STEP 4: DISPLAY THE ARRAY IN A LIVE WINDOW ──────────────────────────────

# cv2.imshow(window_name, array) opens a GUI window and renders the array as
# a visible image. The first argument is just the title bar text.
# OpenCV handles all the pixel-drawing work — you just hand it the array.
cv2.imshow("Array converted to Image", img_array)

# cv2.waitKey(delay_ms) pauses the program and listens for a keyboard event.
# The argument is how long to wait in milliseconds:
#   0  → wait FOREVER until the user presses any key
#   n  → wait n milliseconds, then continue automatically
#
# Without this call, the window would appear and vanish instantly because
# Python would reach the end of the script and exit before you see anything.
# This line is what keeps the window open.
cv2.waitKey(0)

# cv2.destroyAllWindows() closes every OpenCV window that is currently open.
# Always call this at the end — it cleanly releases the GUI resources.
# On some systems, skipping this can leave ghost windows or cause crashes.
cv2.destroyAllWindows()
