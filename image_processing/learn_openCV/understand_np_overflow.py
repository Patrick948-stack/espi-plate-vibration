import numpy as np

# numpy arrays are like Python lists, but faster and built for math.
# When you create one, you can specify a "dtype" (data type) — this controls
# what kind of numbers the array can hold and how much memory it uses.

# uint8 = "unsigned 8-bit integer"
#   - "unsigned" means NO negative numbers (0 and above only)
#   - "8-bit" means each number is stored in 8 binary digits
#   - This gives a range of 0 to 255 (2^8 - 1 = 255)
#   - uint8 is the standard dtype for image pixel values in OpenCV
a = np.array([10], dtype=np.uint8)
b = np.array([20], dtype=np.uint8)

# What happens when you subtract a larger uint8 from a smaller one?
# Mathematically: 10 - 20 = -10, but uint8 can't store negative numbers!
#
# Instead of raising an error, numpy "wraps around" — this is called OVERFLOW.
# It wraps around the 0 boundary like a clock wrapping around midnight:
#
#   0, 1, 2, ... 255, 0, 1, 2 ...  (going up)
#   255, 254, ... 1, 0, 255, 254 ...(going down past 0)
#
# So: 10 - 20 = -10 → wraps to 256 - 10 = 246
# You will see 246 printed below, NOT -10 or an error.
print(a - b)
# THE FIX: temporarily convert (cast) both arrays to regular Python int before subtracting.
# .astype(int) changes the dtype from uint8 to int64, which CAN hold negative numbers.
# np.abs() then takes the absolute value so we get the true distance between the two numbers.
# Result: |10 - 20| = |-10| = 10  ← the correct answer, no overflow.
print(np.abs(a.astype(int) - b.astype(int)))

# WHY THIS MATTERS FOR IMAGE PROCESSING:
# If you subtract pixel values naively (e.g. to find differences between images),
# overflow will give you completely wrong pixel values silently.
# Fix: use cv2.subtract() which "clips" at 0 instead of wrapping,
# or cast to a signed int before doing math: a.astype(np.int16) - b.astype(np.int16)
