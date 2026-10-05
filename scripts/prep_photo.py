import sys, numpy as np, cv2
from PIL import Image
from rembg import remove, new_session
src = sys.argv[1]
im = Image.open(src).convert("RGB")
# crop around head + shoulders
im = im.crop((820, 220, 1800, 1500))
sess = new_session("u2net_human_seg")
rgba = remove(im, session=sess)
a = np.array(rgba)[:, :, 3]
# keep only the largest connected blob (drops neighbours)
n, lab, stats, _ = cv2.connectedComponentsWithStats((a > 128).astype(np.uint8))
if n > 1:
    big = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    a = np.where(lab == big, a, 0)
# drop the person behind-right (curly hair + glasses) with a soft mask
h, w = a.shape
yy, xx = np.mgrid[0:h, 0:w]
cut = (yy > 560) & (xx > 790 - (yy - 560) * 0.25)
a = np.where(cut, 0, a)
a = cv2.GaussianBlur(a, (0, 0), 3)
g = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2GRAY)
g = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(g)
alpha = a.astype(float) / 255
out = (g * alpha + 255 * (1 - alpha)).astype(np.uint8)
Image.fromarray(out).save("source-prepped.png")
print(out.shape)
