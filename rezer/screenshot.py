"""Screenshot tool: captures the browser window and saves it to Pictures/Rezer."""

import datetime
import os


def capture_window(x: int, y: int, width: int, height: int) -> str:
    """Capture the given screen rect. Returns the saved file path."""
    import mss

    pictures = os.path.join(os.path.expanduser("~"), "Pictures", "Rezer")
    os.makedirs(pictures, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(pictures, f"rezer-{stamp}.png")

    # mss needs ints; clamp to sane values
    region = {
        "left": max(int(x), 0),
        "top": max(int(y), 0),
        "width": max(int(width), 1),
        "height": max(int(height), 1),
    }
    with mss.mss() as sct:
        shot = sct.grab(region)
        mss.tools.to_png(shot.rgb, shot.size, output=path)
    return path
