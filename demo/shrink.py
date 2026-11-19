"""Shrinks the README screenshots (256-color PNGs, about 85% smaller). Needs Pillow."""
import glob, sys
from PIL import Image
for f in glob.glob(sys.argv[1] + "/*.png"):
    Image.open(f).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(f, optimize=True)
