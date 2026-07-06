import cv2
import matplotlib.pyplot as plt
import numpy as np


def plot_3d_intensity_map(image_path, downsample_factor=5):
    """Reads an image file, converts it to grascale image, 
    downsamples the image array to protect the program from crashing
    due to a potentially overwhelming amount of data, then it plots the data

    Parameters:
    image_path (str): Path to the input image.
    downsample_factor (int): Factor to downsample the image.
    """
    # 1. Load image and convert to grayscale
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    if img is None:
        raise FileNotFoundError(
            f"Could not load image. Check the path: {image_path}"
        )

    # 2. Numpy slicing. This is used to downsample the image array. 
    # Run through every rown and every column of the img array, and 
    # make a new array called img where each row element is each 
    # downsample_factor-th row element and ditto for the column elements.
    if downsample_factor > 1:
        img = img[::downsample_factor, ::downsample_factor]

    # 3. Create coordinate matrices (X and Y axes)
    height, width = img.shape
    x = np.arange(0, width)
    y = np.arange(0, height)
    X, Y = np.meshgrid(x, y) #combine the two arrays we just created into a 2D array

    # Z-axis is the pixel intensity
    Z = img

    # 4. Set up the 3D plot
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")

    # 5. Plot the surface
    # 'viridis' or 'plasma' are great for showing light falloff/vignetting
    surface = ax.plot_surface(
        X, Y, Z, cmap="viridis", edgecolor="none", linewidth=0, antialiased=False
    )

    # 6. Customize labels and appearance
    ax.set_title("3D Surface Plot (Intensity Profile Map)", fontsize=14, pad=20)
    ax.set_xlabel("X Pixel Coordinate", fontsize=10)
    ax.set_ylabel("Y Pixel Coordinate", fontsize=10)
    ax.set_zlabel("Pixel Intensity (0-255)", fontsize=10)

    # Add a color bar map to read intensities easily
    fig.colorbar(
        surface, ax=ax, shrink=0.5, aspect=10, label="Intensity Value"
    )

    # Invert Y-axis so the 3D plot orientation matches standard image coordinates (top-left origin)
    ax.invert_yaxis()

    # Display the interactive plot
    plt.show()

width, height = 500, 500

# Create a smooth gradient that is bright in the center and dark at the corners
# (vignetting), computed for every pixel at once instead of one pixel at a time.
y_coords, x_coords = np.mgrid[0:height, 0:width]
distance = np.sqrt((x_coords - width / 2) ** 2 + (y_coords - height / 2) ** 2)
test_img = np.clip(255 - distance * 0.8, 0, 255).astype(np.uint8)

# Save this synthetic image to your computer
cv2.imwrite("vignette_test.png", test_img)

# --- 2. RUN THE FUNCTION ---
# Call the function we built earlier using the test image.
# downsample_factor=10 keeps the surface plot to a ~50x50 grid (2,500 quads)
# instead of 250x250 (62,500 quads) -- matplotlib's 3D renderer draws and
# depth-sorts every quad in pure Python, so fewer quads means a much faster render.
try:
    plot_3d_intensity_map("vignette_test.png", downsample_factor=10)
except NameError:
    print(
        "Make sure to paste the original 'plot_3d_intensity_profile' function above this test code!"
    )