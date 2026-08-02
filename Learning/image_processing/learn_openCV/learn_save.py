import cv2

rose1 = cv2.imread('sammy.png', 1)
cv2.imshow('colored', rose1)
rose0 = cv2.imread('sammy.png', 0)
cv2.imshow('black&white', rose0)
rose_1 = cv2.imread('sammy.png', -1)
cv2.imshow('original', rose_1)

cv2.waitKey(0)
cv2.destroyAllWindows()
