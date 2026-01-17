import re
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# ================= USER SETTINGS ============================
# ============================================================

# Path to G-code file
GCODE_FILE = """gcode_file.gcode"""

# Height range (for display)
TOTAL_HEIGHT_MM = None  # None = auto-detect from gcode

# Layer height (optional)
# If None, auto-detect from G-Code layer changes
LAYER_HEIGHT_MM = None

COLOURMAP = "copper_r"
# COLOURMAP = "bwr"

# ============================================================
# ==================== GCODE PARSING ============================
# ============================================================

def get_value(line, key):
    """Extract numeric value after a letter key in gcode."""
    if key not in line:
        return None
    match = re.search(rf"{key}([-+]?[0-9]*\.?[0-9]+)", line)
    if not match:
        return None
    return float(match.group(1))


def parse_gcode_layers(gcode_lines):
    """Parse gcode and return (layer_z, temp_per_layer)."""
    layer_zs = []
    temps = []

    current_temp = None
    current_z = None
    layer1_z = None  # <-- use layer 1 as zero

    for line in gcode_lines:
        line = line.strip()

        # detect temp command
        if line.startswith("M104") or line.startswith("M109"):
            temp = get_value(line, "S")
            if temp is not None:
                current_temp = temp

        # detect Z moves
        if line.startswith("G0") or line.startswith("G1"):
            z_val = get_value(line, "Z")
            if z_val is not None:
                current_z = z_val

        # detect layer change
        if line.startswith(";LAYER:"):
            # Capture layer 1 Z height using exact match
            if re.match(r"^;LAYER:1\b", line):
                layer1_z = current_z if current_z is not None else 0

            layer_zs.append(current_z if current_z is not None else 0)
            temps.append(current_temp if current_temp is not None else 0)

    # Normalize heights so layer 1 = 0
    if layer1_z is not None:
        layer_zs = np.array(layer_zs) - layer1_z
    else:
        layer_zs = np.array(layer_zs)

    return layer_zs, np.array(temps)


def load_gcode(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.readlines()


# ============================================================
# ======================= MAIN ===============================
# ============================================================

def main():
    lines = load_gcode(GCODE_FILE)

    layer_zs, temps = parse_gcode_layers(lines)

    # Auto-detect total height
    total_height = TOTAL_HEIGHT_MM if TOTAL_HEIGHT_MM is not None else max(layer_zs)

    # Auto-detect layer height if needed
    if LAYER_HEIGHT_MM is None:
        if len(layer_zs) > 1:
            layer_height = abs(layer_zs[1] - layer_zs[0])
        else:
            layer_height = 0.1
    else:
        layer_height = LAYER_HEIGHT_MM

    # Create grid for pcolormesh
    y = layer_zs
    x = np.array([0, 1])  # two columns for pcolormesh

    # Temperature matrix must be 2D
    temp_matrix = temps.reshape(-1, 1)
    temp_matrix = np.repeat(temp_matrix, 2, axis=1)

    # Build X/Y meshgrid matching Z's shape
    X, Y = np.meshgrid(x, y)

    plt.figure(figsize=(6, 8))
    mesh = plt.pcolormesh(
        X, Y, temp_matrix,
        shading="auto", cmap=COLOURMAP
    )

    cbar = plt.colorbar(mesh)
    cbar.set_label("Temperature (°C)")
    cbar.set_ticks(np.arange(np.min(temps), np.max(temps) + 2.5, 2.5))

    # Remove X axis labels/ticks
    plt.xticks([])
    plt.xlabel("")

    # Set Y-axis limits to match actual print height
    plt.ylim(np.min(y), np.max(y))

    plt.ylabel("Height (mm)")
    plt.title("G-code Layer Temperature Map")

    plt.show()


if __name__ == "__main__":
    main()
