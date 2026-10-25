"""
Image improvements to try in order to find text
"""
# Try image improvements, adds about 5% extra
IMPROVEMENTS = (
    ("NONE",),
    ("ENHANCE",),
    ("GRAY",),
    ("OTSU",),
    ("ROTATE",),
    (
        "ROTATE",
        "ROTATE",
    ),
    (
        "ROTATE",
        "ROTATE",
        "ROTATE",
    ),
)

# Don't try to improve images, works on 90+% of images
IMPROVEMENTS = (("NONE",),)
