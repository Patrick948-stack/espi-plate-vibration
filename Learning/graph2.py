import cv2
import matplotlib.pyplot as plt
import mplcursors


def plot_intensity_histogram(image_path):
    """Reads an image as grayscale and plots a histogram of how many
    pixels have each intensity value (0-255).

    Parameters:
    image_path (str): Path to the input image.
    """
    # 1. Load image and convert to grayscale
    pixels = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    if pixels is None:
        raise FileNotFoundError(
            f"Could not load image. Check the path: {image_path}"
        )

    pixel_counts = {}
    # Flatten the array and iterate through each pixel
    for p in pixels.flatten():
        i = int(p)
        if i in pixel_counts:
            pixel_counts[i] += 1
        else:
            pixel_counts[i] = 1

    keys = list(pixel_counts.keys())
    values = list(pixel_counts.values())

    # Define the scaling factors
    width_per_item = 0.5  # Allocation room for each bar + spacing
    min_width = 6.0       # Minimum window size so titles/labels fit
    max_width = 14.0      # Cap width since intensity is bounded to 0-255
    fixed_height = 5.0    # Keep the vertical height consistent

    # Calculate dynamic width based on data length, capped so a nearly-full
    # 0-255 histogram doesn't stretch into a huge, squashed strip
    dynamic_width = min(max_width, max(min_width, len(values) * width_per_item))

    # Apply the responsive size to the figure window
    fig, ax = plt.subplots(figsize=(dynamic_width, fixed_height))

    # Plot intensity (x-axis) vs number of pixels (y-axis)
    bars = ax.bar(keys, values, width=1, color='skyblue', edgecolor='black')

    # Enable the interactive hover tooltip
    # Transient mode ensures the tooltip vanishes when your mouse leaves the bar
    cursor = mplcursors.cursor(bars, hover=mplcursors.HoverMode.Transient)

    # Custom format the text inside the pop-up box
    @cursor.connect("add")
    def on_add(sel):
        # Extract the exact coordinates of the hovered bar
        x_val = int(sel.target[0])
        y_val = int(sel.target[1])
        sel.annotation.set(text=f"Intensity (X): {x_val}\nPixels (Y): {y_val:,}")
        sel.annotation.get_bbox_patch().set(fc="white", alpha=0.9) # Custom box styling

    # Prevent overflow of labels on the edges
    ax.set_xlabel("Intensity")
    ax.set_ylabel("Number of pixels")
    ax.set_title(f"Intensity Histogram")

    # Ensure elements don't get cut off at the margins
    plt.tight_layout() 
    plt.show()


# --- Test with the vignette image ---
plot_intensity_histogram("vignette_test.png")

