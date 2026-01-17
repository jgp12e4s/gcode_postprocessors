# **Woodgrain_Cura.py**

Adapted from (https://github.com/MoonCactus/gcode_postprocessors/tree/master/wood) the Woodgrain plugin for Cura post processes the gcode to change the temperature profile (and therefore) colour of each layer to give horizontal texturing so that it looks like wood. I have added extra functionality to the original, including more advanced smoothing prevent bad "seed" woodgrains, a fixed raft temperature (for negative layer numbers) and a few other extra/simplified controls.

## **To use as a plugin for Cura**
(Working on Cura 5.11.0)

* Open your config folder (*Help > Show Configuration Folder*), and place *"Woodgrain_Cura.py"* into the scripts directory

* Restart Cura

* Open the Post Processing window (*Extensions > Post Processing > Modify G-Code*), select "Add a Script", and select "Woodgrain Effect"

* Adjust any parameterrs to your specific print

* Save and print

The parameters and their defaults are:

* ```Average temperature``` - Baseline print temperature (default: 210 degree C)
* ```Temperature variation``` - Variation above and below average (default: 5 degree C)
* ```Max temperature change per layer``` - The maximum temperature change between two layers (default: 2 degree C)
* ```Raft temperature``` - The temperature of any negative layers (default: 210 degree C)
* ```Average wood grain size``` - The size of the wood grain, worth playing around with (default: 2 mm)
* ```Spikiness``` - Relates to the frequency of high temperature bands (default: 1)
* ```Woodgrain seed``` - The seed value of the Perlin noise, change for different woodgrain (default: 42)
* ```Scan for z-hop``` - How many gcode lines ahead to see if there is a jump in height (default: 5)  

# **Woodgrain_Visualiser.py**
My own visualisiton program to see what ```Woodgrain_Visualiser.py``` has done to the layers. Run the python code and input the name of the gcode file after you've used the Woodgrain Effect plugin. It will create a colourmap which shows the temperature of each layer, by default the colourmap used is ```"copper_r"``` which is the best representation I've found of what the print should come out as in terms of wood colour, if you want to see it as temperature variation swap to ```COLOURMAP="bwr"```


### Ascii art curve

MoonCactus added a vertical ascii-art "curve" at the end of the file, such as the excerpt show below.
It shows the variations of temperature according to the Z height, so you can get an idea of the effect of the parameters without having to print the object.

```
(...)
;WoodGraph: Z 3.000000 @190C | ...................
;WoodGraph: Z 3.200000 @239C | ##################.
;WoodGraph: Z 3.400000 @225C | #############......
;WoodGraph: Z 3.600000 @231C | ###############....
;WoodGraph: Z 3.800000 @190C | ...................
;WoodGraph: Z 4.000000 @197C | ##.................
;WoodGraph: Z 4.200000 @200C | ####...............
;WoodGraph: Z 4.400000 @191C | ...................
;WoodGraph: Z 4.600000 @236C | #################..
;WoodGraph: Z 4.800000 @222C | ############.......
;WoodGraph: Z 5.000000 @219C | ###########........
(...)
```
