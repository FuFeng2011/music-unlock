# -*- coding: utf-8 -*-
"""生成应用图标：深色渐变圆角底 + 白色音符。"""
from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

grad = Image.new("RGBA", (SIZE, SIZE))
gd = ImageDraw.Draw(grad)
for y in range(SIZE):
    t = y / SIZE
    r = int(61 + (139 - 61) * t)
    g = int(215 + (92 - 215) * t)
    b = int(255 + (246 - 255) * t)
    gd.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))

mask = Image.new("L", (SIZE, SIZE), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=58, fill=255)
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)
white = (255, 255, 255, 255)
d.rounded_rectangle([96, 62, 100, 198], radius=2, fill=white)
d.rounded_rectangle([158, 62, 162, 198], radius=2, fill=white)
d.rounded_rectangle([96, 58, 162, 72], radius=7, fill=white)
d.ellipse([64, 170, 106, 212], fill=white)
d.ellipse([126, 170, 168, 212], fill=white)

img.save("D:/Tool-MusicUnlock/build/icon.ico",
         sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("icon.ico written")
