"""Generate a professional OG image for AI Blog Daily."""
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630

img = Image.new("RGB", (WIDTH, HEIGHT))
draw = ImageDraw.Draw(img)

# Dark gradient background
for y in range(HEIGHT):
    r = int(12 + (y / HEIGHT) * 12)
    g = int(12 + (y / HEIGHT) * 18)
    b = int(30 + (y / HEIGHT) * 25)
    draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

# Convert to RGBA for transparency support
img = img.convert("RGBA")

# Subtle dot grid pattern
grid = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
grid_draw = ImageDraw.Draw(grid)
for x in range(40, WIDTH, 50):
    for y in range(40, HEIGHT, 50):
        grid_draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255, 12))
img = Image.alpha_composite(img, grid)

# Accent glow circles (soft, decorative)
overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
overlay_draw = ImageDraw.Draw(overlay)

# Top-right glow - purple
for radius in range(350, 0, -2):
    alpha = int(18 * (1 - radius / 350))
    overlay_draw.ellipse(
        [950 - radius, -200 - radius, 950 + radius, -200 + radius],
        fill=(120, 70, 220, alpha),
    )

# Bottom-left glow - blue
for radius in range(320, 0, -2):
    alpha = int(14 * (1 - radius / 320))
    overlay_draw.ellipse(
        [150 - radius, 700 - radius, 150 + radius, 700 + radius],
        fill=(50, 120, 240, alpha),
    )

img = Image.alpha_composite(img, overlay)
draw = ImageDraw.Draw(img)

# Top accent line with gradient effect
for x in range(WIDTH):
    # Purple to blue gradient
    t = x / WIDTH
    r = int(120 * (1 - t) + 50 * t)
    g = int(70 * (1 - t) + 120 * t)
    b = int(220 * (1 - t) + 240 * t)
    draw.line([(x, 0), (x, 4)], fill=(r, g, b, 255))

# Load fonts
try:
    font_title = ImageFont.truetype("segoeuib.ttf", 78)
    font_subtitle = ImageFont.truetype("segoeui.ttf", 28)
    font_tags = ImageFont.truetype("segoeuib.ttf", 21)
    font_url = ImageFont.truetype("segoeui.ttf", 18)
except:
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 78)
        font_subtitle = ImageFont.truetype("arial.ttf", 28)
        font_tags = ImageFont.truetype("arialbd.ttf", 21)
        font_url = ImageFont.truetype("arial.ttf", 18)
    except:
        font_title = ImageFont.load_default()
        font_subtitle = font_title
        font_tags = font_title
        font_url = font_title

# Small "robot" icon above title - simple geometric bot face
icon_cx, icon_cy = WIDTH // 2, 145
# Bot head (rounded rect)
draw.rounded_rectangle(
    [icon_cx - 28, icon_cy - 28, icon_cx + 28, icon_cy + 28],
    radius=8,
    fill=(120, 70, 220, 180),
    outline=(160, 120, 255, 200),
    width=2,
)
# Bot eyes
draw.rounded_rectangle([icon_cx - 15, icon_cy - 12, icon_cx - 5, icon_cy - 2], radius=2, fill=(255, 255, 255, 220))
draw.rounded_rectangle([icon_cx + 5, icon_cy - 12, icon_cx + 15, icon_cy - 2], radius=2, fill=(255, 255, 255, 220))
# Bot mouth
draw.rounded_rectangle([icon_cx - 12, icon_cy + 6, icon_cx + 12, icon_cy + 12], radius=2, fill=(255, 255, 255, 160))
# Bot antenna
draw.line([(icon_cx, icon_cy - 28), (icon_cx, icon_cy - 42)], fill=(160, 120, 255, 200), width=2)
draw.ellipse([icon_cx - 4, icon_cy - 48, icon_cx + 4, icon_cy - 40], fill=(120, 70, 220, 220))

# Title
title = "AI Blog Daily"
bbox = draw.textbbox((0, 0), title, font=font_title)
tw = bbox[2] - bbox[0]
x_title = (WIDTH - tw) // 2
y_title = 195

draw.text((x_title + 2, y_title + 3), title, fill=(0, 0, 0, 120), font=font_title)
draw.text((x_title, y_title), title, fill=(255, 255, 255, 255), font=font_title)

# Subtitle
subtitle = "AI-Generated Content from the Best AI Tools"
bbox = draw.textbbox((0, 0), subtitle, font=font_subtitle)
sw = bbox[2] - bbox[0]
x_sub = (WIDTH - sw) // 2
y_sub = y_title + 100
draw.text((x_sub, y_sub), subtitle, fill=(160, 165, 185, 255), font=font_subtitle)

# Decorative accent line
line_y = y_sub + 55
# Gradient line
for x in range(WIDTH // 2 - 80, WIDTH // 2 + 80):
    t = abs(x - WIDTH // 2) / 80
    alpha = int(255 * (1 - t))
    draw.point((x, line_y), fill=(120, 70, 220, alpha))
    draw.point((x, line_y + 1), fill=(120, 70, 220, alpha))

# AI tool tags as pills
tools = ["ChatGPT", "Claude", "Gemini", "Grok"]
colors = [(16, 163, 127), (217, 158, 66), (66, 133, 244), (200, 200, 210)]
pill_y = line_y + 25
pill_data = []

for i, tool in enumerate(tools):
    bbox = draw.textbbox((0, 0), tool, font=font_tags)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pill_w = text_w + 44
    pill_data.append((tool, pill_w, text_w, text_h, colors[i]))

spacing = 16
total_with_spacing = sum(p[1] for p in pill_data) + spacing * (len(tools) - 1)
start_x = (WIDTH - total_with_spacing) // 2

for tool, pill_w, text_w, text_h, color in pill_data:
    pill_h = 36
    # Pill background
    bg_color = (color[0] // 8, color[1] // 8, color[2] // 8, 180)
    draw.rounded_rectangle(
        [start_x, pill_y, start_x + pill_w, pill_y + pill_h],
        radius=18,
        fill=bg_color,
        outline=(*color, 80),
        width=1,
    )
    # Centered text
    tx = start_x + (pill_w - text_w) // 2
    ty = pill_y + (pill_h - text_h) // 2 - 1
    draw.text((tx, ty), tool, fill=(*color, 255), font=font_tags)
    start_x += pill_w + spacing

# URL at bottom
url_text = "aiblogdaily.com"
bbox = draw.textbbox((0, 0), url_text, font=font_url)
uw = bbox[2] - bbox[0]
draw.text(((WIDTH - uw) // 2, HEIGHT - 50), url_text, fill=(90, 95, 120, 200), font=font_url)

# Save as RGB PNG
img = img.convert("RGB")
output_path = "static/img/og-default.png"
img.save(output_path, "PNG")
print(f"OG image saved to {output_path}")
