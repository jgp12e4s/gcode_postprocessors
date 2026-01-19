import re
import random
import math
import datetime
from time import sleep
import threading
from ..Script import Script
from UM.Logger import Logger
from UM.Message import Message
from PyQt6.QtCore import QCoreApplication
from UM.Qt.QtApplication import QtApplication

try:
    xrange
except NameError:
    xrange = range

# ----------------------------
# Global defaults
# ----------------------------
AVG_TEMP_DEFAULT = 210
TEMP_VARIATION_DEFAULT = 20.0
MAX_DELTA_DEFAULT = 2.5
RAFT_TEMP_DEFAULT = 210
GRAIN_SIZE_DEFAULT = 2.0
SPIKINESS_POWER_DEFAULT = 1.0
SEED_DEFAULT = 42
SCAN_FOR_ZHOP_DEFAULT = 5
WALL_SPEED_DEFAULT = 60.0           # mm/s
WALL_SPEED_VARIATION_DEFAULT = 20.0 # mm/s

class Woodgrain_Cura(Script):

    class Perlin:
        def __init__(self, tile_dimension=256, seed=0):
            self.tile_dimension = tile_dimension
            self.perm = [None] * 2 * tile_dimension
            permutation = list(range(tile_dimension))
            random.seed(seed)
            random.shuffle(permutation)
            for i in xrange(tile_dimension):
                self.perm[i] = permutation[i]
                self.perm[tile_dimension + i] = self.perm[i]

        @staticmethod
        def fade(t):
            return t * t * t * (t * (t * 6 - 15) + 10)

        @staticmethod
        def lerp(t, a, b):
            return a + t * (b - a)

        @staticmethod
        def grad(hash_code, x, y, z):
            h = hash_code & 15
            u = x if h < 8 else y
            v = y if h < 4 else (x if h in [12, 14] else z)
            first = u if h & 1 == 0 else -u
            second = v if h & 2 == 0 else -v
            return first + second

        def noise(self, x, y, z):
            X = int(x) & (self.tile_dimension - 1)
            Y = int(y) & (self.tile_dimension - 1)
            Z = int(z) & (self.tile_dimension - 1)
            x -= int(x)
            y -= int(y)
            z -= int(z)
            u = self.fade(x)
            v = self.fade(y)
            w = self.fade(z)
            A = self.perm[X] + Y
            AA = self.perm[A] + Z
            AB = self.perm[A + 1] + Z
            B = self.perm[X + 1] + Y
            BA = self.perm[B] + Z
            BB = self.perm[B + 1] + Z
            return self.lerp(w, self.lerp(v,
                    self.lerp(u, self.grad(self.perm[AA], x, y, z), self.grad(self.perm[BA], x - 1, y, z)),
                    self.lerp(u, self.grad(self.perm[AB], x, y - 1, z), self.grad(self.perm[BB], x - 1, y - 1, z))),
                    self.lerp(v,
                        self.lerp(u, self.grad(self.perm[AA + 1], x, y, z - 1), self.grad(self.perm[BA + 1], x - 1, y, z - 1)),
                        self.lerp(u, self.grad(self.perm[AB + 1], x, y - 1, z - 1), self.grad(self.perm[BB + 1], x - 1, y - 1, z - 1))))

        def fractal(self, octaves, persistence, x, y, z, frequency=1):
            value = 0.0
            amplitude = 1.0
            total_amplitude = 0.0
            for _ in xrange(octaves):
                n = self.noise(x * frequency, y * frequency, z * frequency)
                value += amplitude * n
                total_amplitude += amplitude
                amplitude *= persistence
                frequency *= 2
            return value / total_amplitude

    # ----------------------------
    # Cura plugin settings
    # ----------------------------
    def getSettingDataString(self):
        return """{
            "name": "Woodgrain Effect",
            "key": "Woodgrain",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "avgTemp": {"label": "Average temperature","description":"Average temp","type":"int","value":"%i"},
                "tempVariation":{"label":"Temperature variation ±","type":"float","value":"%0.1f"},
                "maxDelta":{"label":"Max temp change per layer","type":"float","value":"%0.1f"},
                "raftTemp":{"label":"Raft temperature","type":"int","value":"%i"},
                "grainSize":{"label":"Average wood grain size","type":"float","value":"%0.1f"},
                "spikinessPower":{"label":"Spikiness","type":"float","value":"%0.1f"},
                "seed":{"label":"Woodgrain seed","type":"int","value":"%i"},
                "scanForZHop":{"label":"Scan for z-hop","type":"int","value":"%i"},
                "wallSpeed":{"label":"Average print speed of walls","type":"float","value":"%0.1f"},
                "wallSpeedVariation":{"label":"Print speed variation","type":"float","value":"%0.1f"}
            }
        }""" % (
            AVG_TEMP_DEFAULT, TEMP_VARIATION_DEFAULT, MAX_DELTA_DEFAULT, RAFT_TEMP_DEFAULT,
            GRAIN_SIZE_DEFAULT, SPIKINESS_POWER_DEFAULT, SEED_DEFAULT, SCAN_FOR_ZHOP_DEFAULT,
            WALL_SPEED_DEFAULT, WALL_SPEED_VARIATION_DEFAULT
        )

    # ----------------------------
    # Main execution
    # ----------------------------
    def execute(self, data):
        Logger.log("d", "[Woodgrain Effect] Begin processing")

        self.progress_bar = Message(title="Applying Woodgrain Effect",
                                    text="This may take several minutes, please be patient.\n\n",
                                    lifetime=0, dismissable=False, progress=-1)
        self.progress_bar.show()
        self._locks = {"metadata": threading.Lock(), "output": threading.Lock()}
        self.progress = (-1, 0)
        self.output_gcode = []

        self.apply_woodgrain_thread = threading.Thread(target=self.apply_woodgrain, args=(data,))
        self.apply_woodgrain_thread.start()

        GUI_UPDATE_FREQUENCY = 50
        PROGRESS_CHECK_INTERVAL = 1000
        update_period = 1 / GUI_UPDATE_FREQUENCY
        updates_per_check = int(GUI_UPDATE_FREQUENCY * (PROGRESS_CHECK_INTERVAL / 1000))

        while True:
            for _ in range(updates_per_check):
                QCoreApplication.processEvents()
                sleep(update_period)

            self._locks["metadata"].acquire()
            progress = self.progress
            self._locks["metadata"].release()
            self.progress_bar.setProgress((progress[0] / progress[1]) * 100)

            main_window = QtApplication.getInstance().getMainWindow()
            if main_window is None:
                return None

            if progress[0] >= progress[1]:
                self.apply_woodgrain_thread.join()
                break

        Logger.log("d", "[Woodgrain Effect] End processing. " + str(progress[1]) + " iterations performed")
        self.progress_bar.hide()
        return self.output_gcode

    # ----------------------------
    # Core woodgrain processing
    # ----------------------------
    def apply_woodgrain(self, data):
        lines = []
        eol = "\r\n" if "\r\n" in data[0] else "\n"
        for layer in data:
            lines.extend(layer.split(eol))

        avgTemp = int(self.getSettingValueByKey("avgTemp"))
        tempVariation = float(self.getSettingValueByKey("tempVariation"))
        minTemp = avgTemp - tempVariation
        maxTemp = avgTemp + tempVariation
        raftTemp = int(self.getSettingValueByKey("raftTemp"))
        grainSize = float(self.getSettingValueByKey("grainSize"))
        maxDelta = float(self.getSettingValueByKey("maxDelta"))
        spikinessPower = float(self.getSettingValueByKey("spikinessPower"))
        seed = int(self.getSettingValueByKey("seed"))
        scanForZHop = int(self.getSettingValueByKey("scanForZHop"))
        avg_wall_speed = float(self.getSettingValueByKey("wallSpeed"))
        wall_speed_variation = float(self.getSettingValueByKey("wallSpeedVariation"))

        avg_wall_feed = avg_wall_speed * 60
        wall_feed_variation = wall_speed_variation * 60
        minimum_feedrate = 100

        tempCommand = 'M104'
        perlin = self.Perlin(seed=seed)
        noises = {}

        def perlin_to_normalized_wood(z):
            banding = 3
            octaves = 3
            persistence = 0.6
            x = seed * 0.731 + z * 0.15
            y = seed * 0.193 + z * 0.15 * 0.7
            z_scaled = z / (grainSize * 2)
            noise = banding * perlin.fractal(octaves, persistence, x, y, z_scaled)
            noise = (noise - math.floor(noise))
            noise = math.pow(noise, spikinessPower)
            return noise

        def get_value(gcode_line, key, default=None):
            if key not in gcode_line or (';' in gcode_line and gcode_line.find(key) > gcode_line.find(';')):
                return default
            sub_part = gcode_line[gcode_line.find(key) + 1:]
            m = re.search('^[0-9]+\.?[0-9]*', sub_part)
            if m is None:
                return default
            try:
                return float(m.group(0))
            except:
                return default

        def get_z(line, default=None):
            if line.startswith(";WoodGraph:"):
                return default
            if get_value(line, 'G') in [0,1]:
                return get_value(line, 'Z', default)
            return default

        # Precompute noises per Z
        maxZ = 0
        formerZ = -1
        for line in lines:
            z = get_z(line)
            if z is not None:
                if z > maxZ:
                    maxZ = z
                if abs(z - formerZ) > 0.1:
                    noises[z] = perlin_to_normalized_wood(z)
                    formerZ = z

        # Normalize noises
        noisesMax = max(noises.values())
        noisesMin = min(noises.values())
        for z in noises:
            noises[z] = (noises[z] - noisesMin) / (noisesMax - noisesMin)

        def noise_to_temp(noise):
            return minTemp + noise * (maxTemp - minTemp)

        # Precompute wall feedrates per layer
        layer_feedrates = {}
        for z, noise in noises.items():
            temp = noise_to_temp(noise)
            feed = avg_wall_feed - wall_feed_variation * (temp - avgTemp) / tempVariation
            layer_feedrates[z] = max(minimum_feedrate, int(feed))

        # --- Write output ---
        class write_to_list:
            def __init__(self):
                self.content = ""
            def write(self, chars):
                self.content += (chars + eol)
            def get_data(self):
                return [line + eol for line in self.content.split(eol)]

        f = write_to_list()
        f.write(";woodified gcode, generated on " + datetime.datetime.now().strftime("%Y%m%d-%H%M") + eol)
        f.write(f"M104 S{raftTemp}{eol}M116{eol}")

        in_wall_block = False
        pending_wall_feed = None
        formerZ = -1

        graphStr = ";WoodGraph:" + eol
        for index, line in enumerate(lines):
            thisZ = get_z(line, formerZ)
            if thisZ != formerZ and thisZ in noises:
                temp = noise_to_temp(noises[thisZ])
                formerZ = thisZ
                pending_wall_feed = layer_feedrates.get(thisZ)

                # Write temp command per layer
                f.write(f"{tempCommand} S{int(temp)}{eol}")

                # Update graph
                t = int(19 * (temp - minTemp) / (maxTemp - minTemp))
                graphStr += ";WoodGraph: Z%.3f @%iC | %s%s%s" % (
                    thisZ, int(temp), '#' * t, '.' * (20 - t), eol
                )

            # Wall speed injection
            if line.startswith(";TYPE:WALL-") and thisZ > 0:
                in_wall_block = True
                f.write(line)
                continue

            if in_wall_block and pending_wall_feed is not None:
                if line.startswith("G1") and "F" in line:
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p.startswith("F"):
                            parts[i] = f"F{pending_wall_feed}"
                            break
                    line = " ".join(parts)
                    f.write(line)
                    pending_wall_feed = None
                    continue
                if line.startswith("G1") and "E" in line and "F" not in line:
                    f.write(f"G1 F{pending_wall_feed}")
                    pending_wall_feed = None
                    f.write(line)
                    continue

            if line.startswith(";TYPE:") and not line.startswith(";TYPE:WALL-"):
                in_wall_block = False

            f.write(line)

        f.write(graphStr)
        self.output_gcode = f.get_data()
