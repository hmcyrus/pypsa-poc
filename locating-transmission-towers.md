We need to have the exact tower locations (as precisely possible) to constructing the transmission lines. 
For eaxmple, the 400KV line from aminbazar to gopalganj crosses padma beside the bride with some towers within the rivers around 500m - ~1km apart.

But we dont' have these tower location data in open-source. 
We are considering to extract tower location using the google map satellite images using following algo

-> start from a substation, which are usually marked in google map.
-> then search wihtin a circle of 1km radius for any transmission/distribution towers in the satellite image
-> then do the same thing from the last set of towers located untill we reach BD borders.

we can use object detection models like https://huggingface.co/facebook/sam3 or yolo for the image processing part.
