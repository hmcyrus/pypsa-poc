### Our goal
Detect power infrastructure (substations, electrical towers, transformers) from satellite imagery, covering a large landscape, using open source tools and AI, within six months.

### Initial Assessment

**Feasibility**: Confirmed doable. Power infrastructure has *distinct visual signatures at 5–15 meter resolution*. Free imagery sources like Sentinel-2 will also work and worth expploring

**Problem Orientation**: Not GIS—it’s object detection. You need CNNs, YOLO/Faster RCNN, and *an understanding that satellite images carry embedded coordinates*. Traditional map knowledge is mostly unnecessary.

**The data problem**: Your main bottleneck. No pre-annotated datasets are available, and Google Maps is realistically your only accessible imagery source. 

## Further discussion about the Data Bottleneck

The core constraint: No pre-annotated satellite imagery datasets exist for your use case. Google Maps/Earth is realistically your only free imagery source, and you can’t programmatically scrape it at scale due to terms of service.

>> Why data matters most: The model architecture and pipeline are straightforward engineering problems you can solve. The quality and quantity of labeled training data is what determines whether the system actually works. This is your real bottleneck.

Five approaches we can consider given our current scenario:

*Semi-automatic labeling from Street View* -> Walk Street View along roads near known infrastructure, visually confirm what you see at ground level, then switch to satellite view and mark the location. Gives you reliable ground truth but is slow and manual.

*weak supervision with point labels* -> Skip precise bounding boxes—just drop point labels at the center of objects in satellite imagery. Train on these noisy labels, then use the model’s own predictions to iteratively refine your dataset. Faster to start, messier to clean up.

*Synthetic data generation* -> Composite geometric patterns resembling substations onto real satellite textures. Useful for bootstrapping but won’t capture real-world variation well on its own. Can be explored later, the most complicated path.

*Transfer learning from pretrained models / Finetuning models* -> Start from a model pre-trained on general aerial object detection (buildings, roads, vehicles) and fine-tune on your small labeled set. **Cuts your labeling needs from thousands down to maybe a hundred or so good examples**.

*Hybrid approach (most feasible direction)* -> Combine manual point labeling via Street View with transfer learning. Collect a few hundred ground-truth examples manually, fine-tune a pre-trained model, then use that model’s predictions to find more examples and refine labels iteratively. Balances effort, speed, and accuracy within your six-month window.

### The timeline consideration

Data collection realistically consumes month one entirely. The target we can start working toward was 500 labeled objects. This one month will start after the knowledge transfer required to enable data annotators
