import re 
import random
import math
import datetime

# ----------------------------
# Global settings (user controls)
# ----------------------------
AVG_TEMP_DEFAULT = 210
TEMP_VARIATION_DEFAULT = 10
MAX_DELTA_DEFAULT = 2.5
RAFT_TEMP_DEFAULT = 210
WALL_SPEED_VARIATION_DEFAULT = 50.0
GRAIN_SIZE_DEFAULT = 1.0
SPIKINESS_POWER_DEFAULT = 1.0
SEED_DEFAULT = 42
SCAN_FOR_ZHOP_DEFAULT = 5


# -- Required for the Cura wrapper --
from ..Script import Script

from time import sleep
import threading

from UM.Logger import Logger
from UM.Message import Message
from PyQt6.QtCore import QCoreApplication
from UM.Qt.QtApplication import QtApplication


try:
    xrange
except NameError:
    xrange = range


class Woodgrain_Cura(Script):

    class Perlin:

        def __init__(self, tile_dimension=256, seed=0):
            self.tile_dimension = tile_dimension
            self.perm = [None] * 2 * tile_dimension

            permutation = []
            for value in xrange(tile_dimension):
                permutation.append(value)

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
            if h < 8:
                u = x
            else:
                u = y
            if h < 4:
                v = y
            else:
                if h == 12 or h == 14:
                    v = x
                else:
                    v = z
            if h & 1 == 0:
                first = u
            else:
                first = -u
            if h & 2 == 0:
                second = v
            else:
                second = -v
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
            for octave in xrange(octaves):
                n = self.noise(x * frequency, y * frequency, z * frequency)
                value += amplitude * n
                total_amplitude += amplitude
                amplitude *= persistence
                frequency *= 2
            return value / total_amplitude


    def getSettingDataString(self):
        return """{
            "name": "Woodgrain Effect",
            "key": "Woodgrain",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "avgTemp":
                {
                    "label": "Average temperature",
                    "description": "Average temperature around which the woodgrain varies",
                    "type": "int",
                    "value": "%i",
                    "unit": "C"
                },
                "tempVariation":
                {
                    "label": "Temperature variation ±",
                    "description": "Temperature varies between Average ± this value",
                    "type": "float",
                    "value": "%0.1f",
                    "unit": "C"
                },
                "maxDelta":
                {
                    "label": "Max temperature change per layer",
                    "description": "Limits how much the temperature can change from one layer to the next",
                    "type": "float",
                    "value": "%0.1f",
                    "unit": "C"
                },
                "raftTemp":
                {
                    "label": "Raft temperature",
                    "description": "Temperature to use for all temperatures before layer 0",
                    "type": "int",
                    "value": "%i",
                    "unit": "C"
                },
                "wallSpeedVariation":
                {
                    "label": "Percentage wall speed variation ±",
                    "description": "Maximum wall speed variation based on temperature (in percent)",
                    "type": "float",
                    "value": "%0.1f",
                    "minimum_value": "0"
                },
                "grainSize":
                {
                    "label": "Average wood grain size",
                    "description": "Make it larger for slower changes in temperature",
                    "type": "float",
                    "value": "%0.1f",
                    "unit": "mm"
                },
                "spikinessPower":
                {
                    "label": "Spikiness",
                    "description": "Higher values make dark bands sparser",
                    "type": "float",
                    "value": "%0.1f"
                },
                "seed":
                {
                    "label": "Woodgrain seed",
                    "description": "Change to get a different woodgrain pattern",
                    "type": "int",
                    "value": "%i"
                },
                "scanForZHop":
                {
                    "label": "Scan for z-hop",
                    "description": "Lines to scan ahead for Z-Hop",
                    "type": "int",
                    "value": "%i"
                }
            }
        }""" % (
            AVG_TEMP_DEFAULT,
            TEMP_VARIATION_DEFAULT,
            MAX_DELTA_DEFAULT,
            RAFT_TEMP_DEFAULT,
            WALL_SPEED_VARIATION_DEFAULT,
            GRAIN_SIZE_DEFAULT,
            SPIKINESS_POWER_DEFAULT,
            SEED_DEFAULT,
            SCAN_FOR_ZHOP_DEFAULT
        )


    def execute(self, data):
        Logger.log("d", "[Woodgrain Effect] Begin processing")

        self.progress_bar = Message(title="Applying Woodgrain Effect", text="This may take several minutes, please be patient.\n\n",
                                    lifetime=0, dismissable=False, progress=-1)
        self.progress_bar.show()

        self._locks = {}
        self._locks["metadata"] = threading.Lock()
        self._locks["output"] = threading.Lock()

        self.progress = (-1,0)
        self.output_gcode=[]

        self.apply_woodgrain_thread = threading.Thread(target=self.apply_woodgrain, args=(data,))
        self.apply_woodgrain_thread.start()

        GUI_UPDATE_FREQUENCY = 50
        PROGRESS_CHECK_INTERVAL = 1000

        update_period = 1 / GUI_UPDATE_FREQUENCY
        updates_per_check = int(GUI_UPDATE_FREQUENCY * (PROGRESS_CHECK_INTERVAL / 1000))

        while True:
            for i in range(0, updates_per_check):
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



    def apply_woodgrain(self, data):
        lines = []

        if "\r\n" in data[0]:
            eol = "\r\n"
        else:
            eol = "\n"

        for layer in data:
            gcode_line = layer.split(eol)
            for line in gcode_line:
                lines.append(line)

        avgTemp = int(self.getSettingValueByKey("avgTemp"))
        tempVariation = float(self.getSettingValueByKey("tempVariation"))
        minTemp = avgTemp - tempVariation
        maxTemp = avgTemp + tempVariation

        firstTemp = avgTemp
        raftTemp = int(self.getSettingValueByKey("raftTemp"))
        wallSpeedVariation = float(self.getSettingValueByKey("wallSpeedVariation"))
        grainSize = float(self.getSettingValueByKey("grainSize"))
        maxDelta = float(self.getSettingValueByKey("maxDelta"))
        spikinessPower = float(self.getSettingValueByKey("spikinessPower"))
        seed = int(self.getSettingValueByKey("seed"))
        scanForZHop = int(self.getSettingValueByKey("scanForZHop"))

        tempCommand = 'M104'
        skipStartZ = 0


        def get_value(gcode_line, key, default=None):
            if not key in gcode_line or (';' in gcode_line and gcode_line.find(key) > gcode_line.find(';')):
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
            if get_value(line, 'G') == 0 or get_value(line, 'G') == 1:
                return get_value(line, 'Z', default)
            else:
                return default


        minimumChangeZ = 0.1

        maxZ = 0
        thisZ = 0
        for line in lines:
            thisZ = get_z(line)
            if thisZ is not None:
                if maxZ < thisZ:
                    maxZ = thisZ


        perlin = self.Perlin(seed=seed)


        def perlin_to_normalized_wood(z):
            banding = 3
            octaves = 3
            persistence = 0.6

            # 3D sampling with gentle XY drift
            x = seed * 0.731 + z * 0.15
            y = seed * 0.193 + z * 0.15 * 0.7
            z_scaled = z / (grainSize * 2)

            noise = banding * perlin.fractal(
                octaves,
                persistence,
                x,
                y,
                z_scaled
            )

            noise = (noise - math.floor(noise))
            noise = math.pow(noise, spikinessPower)
            return noise


        noises = {}
        noises[0] = perlin_to_normalized_wood(0)
        pendingNoise = None
        formerZ = -1
        for line in lines:
            thisZ = get_z(line, formerZ)

            if thisZ > 2 + formerZ:
                formerZ = thisZ
            elif abs(thisZ - formerZ) > minimumChangeZ and thisZ > skipStartZ:
                formerZ = thisZ
                noises[thisZ] = perlin_to_normalized_wood(thisZ)

        noisesMax = noises[max(noises, key=noises.get)]
        noisesMin = noises[min(noises, key=noises.get)]
        for z, v in noises.items():
            noises[z] = (noises[z] - noisesMin) / (noisesMax - noisesMin)


        def noise_to_temp(noise):
            return minTemp + noise * (maxTemp - minTemp)


    

        def z_hop_scan_ahead(index, z):
            if scanForZHop == 0:
                return False
            for i in range(scanForZHop):
                checkZ = get_z(lines[index + i], z)
                if checkZ < z:
                    return True
            return False
        

        def temp_to_feedrate(temp, feedrate):
            wallSpeedVariation /= 100
            new_feedrate = feedrate*(1-wallSpeedVariation*(temp-avgTemp)/tempVariation)
            min_feedrate = max(0, feedrate*(1-wallSpeedVariation))
            max_feedrate = min(feedrate(1+wallSpeedVariation), 100*60)
            
            return max(min_feedrate, min(new_feedrate, max_feedrate))

        class write_to_list:
            def __init__(self):
                self.content = ""
            def write(self, chars):
                self.content += (chars + eol)
            def get_data(self):
                list_output = []
                for line in self.content.split(eol):
                    list_output.append(line + eol)
                return list_output
        f = write_to_list()


        f.write(";woodified gcode, see graph at the end - generated on " +
                datetime.datetime.now().strftime("%Y%m%d-%H%M") + eol)
        warmingTempCommands = "M230 S0" + eol
        t = firstTemp
        if t == 0:
            t = noise_to_temp(0)
        warmingTempCommands += ("%s S%i" + eol) % (tempCommand, t)
        warmingTempCommands += "M230 S1" + eol
        warmingTempCommands += "M116" + eol
        f.write(warmingTempCommands)

        graphStr = ";WoodGraph: Wood temperature graph (from " + str(minTemp) + "C to " + str(
            maxTemp) + "C, grain size " + str(grainSize) + "mm" + ", scanForZHop " + str(scanForZHop) + ")"
        if maxDelta:
            graphStr += ", maxDelta " + str(maxDelta)
        graphStr += ":"
        graphStr += eol

        thisZ = -1
        formerZ = -1
        warned = 0

        postponedTempDelta = 0
        postponedTempLast = None
        skip_lines = 0
        total_length = len(lines) - 1
        for index, line in enumerate(lines):

            self._locks["metadata"].acquire()
            self.progress = (index, total_length)
            self._locks["metadata"].release()

            # RAFT TEMPERATURE OVERRIDE BEFORE LAYER 0
            if ";LAYER:0" not in line and ("M104" in line or "M109" in line):
                if "M104" in line:
                    f.write("M104 S" + str(raftTemp) + eol)
                elif "M109" in line:
                    f.write("M109 S" + str(raftTemp) + eol)
                continue

            layer_temp = avgTemp
            if "; set extruder " in line.lower():
                f.write(line)
                f.write(warmingTempCommands)
                warmingTempCommands = ""
            elif "; M104_M109" in line:
                f.write(line)
            elif skip_lines > 0:
                skip_lines -= 1
            elif ";woodified" in line.lower():
                skip_lines = 4
            elif not ";woodgraph" in line.lower():
                if thisZ == maxZ:
                    f.write(line)
                elif not "m104" in line.lower():
                    thisZ = get_z(line, formerZ)
                    if thisZ != formerZ and thisZ in noises and not z_hop_scan_ahead(index, thisZ):

                        if firstTemp != 0 and thisZ <= 0.5:
                            temp = firstTemp
                        else:
                            temp = noise_to_temp(noises[thisZ])

                            temp += postponedTempDelta
                            postponedTempDelta = 0
                            if (postponedTempLast is not None) and (maxDelta > 0) and (temp > postponedTempLast + maxDelta):
                                postponedTempDelta = temp - (postponedTempLast + maxDelta)
                                temp = postponedTempLast + maxDelta
                            if (postponedTempLast is not None) and (maxDelta > 0) and (temp < postponedTempLast - maxDelta):
                                postponedTempDelta = postponedTempLast - maxDelta - temp
                                temp = postponedTempLast - maxDelta
                            if temp > maxTemp:
                                postponedTempDelta = 0
                                temp = maxTemp
                            postponedTempLast = temp
                            layer_temp = temp

                            f.write(("%s S%i" + eol) % (tempCommand, temp))

                        formerZ = thisZ

                        t = int(19 * (temp - minTemp) / (maxTemp - minTemp))
                        graphStr += ";WoodGraph: Z %03f " % thisZ
                        graphStr += "@%3iC | " % temp
                        graphStr += '#'*t + '.'*(20 - t)
                        graphStr += eol

                    f.write(line)

            if ";TYPE:WALL" in line:
                for j in range(index+1, len(lines)):
                    next_line = lines[j]

                    if ";TYPE:" in next_line:
                        break

                    if next_line.startswith("G1") and ("X" in next_line or "Y" in next_line) and "F" in next_line:
                        match = re.search(r'F(\d+(\.\d+)?)', next_line)
                        if match:
                            initial_feedrate = float(match.group(1))
                            new_feedrate = temp_to_feedrate(layer_temp, initial_feedrate)
                            lines[j] = next_line.replace(match.group(0), f"F{new_feedrate:.2f}")

        f.write(graphStr + eol)


        self._locks["output"].acquire()
        first_layer_done = False
        for line in f.get_data():
            if not first_layer_done:
                if ";LAYER:0" in line:
                    first_layer_done = True
                elif "M104" in line and not ("M104 S" + str(firstTemp)) in line:
                    continue

            self.output_gcode.append(line)

        self._locks["output"].release()
