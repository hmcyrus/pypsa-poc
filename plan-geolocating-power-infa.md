Here’s where we’ve landed so far.

Your goal: Detect power infrastructure (substations, electrical towers, transformers) from satellite imagery, covering a large landscape, using open source tools and AI, within six months.

Feasibility: Confirmed doable. Power infrastructure has distinct visual signatures at 5–15 meter resolution. Free imagery sources like Sentinel-2 work, and your software engineering background maps directly onto the computer vision pipeline needed.

Core skill gap: Not GIS—it’s object detection. You need CNNs, YOLO/Faster RCNN, and an understanding that satellite images carry embedded coordinates. Traditional map knowledge is mostly unnecessary.

The data problem: Your main bottleneck. No pre-annotated datasets are available, and Google Maps is realistically your only accessible imagery source. We explored five approaches to bootstrap training data: semi-automatic labeling from Street View, weak supervision with point labels, synthetic data generation, transfer learning from pre-trained models, and a hybrid combining these.

Chosen direction: The hybrid approach—combine manual point-level labeling using Google Street View for ground truth, then leverage transfer learning on a pre-trained detection model fine-tuned on your small dataset, iteratively improving with model-assisted relabeling.

Where we stopped: You asked for the detailed step-by-step process of manually labeling 500 objects using Google Maps and Street View, starting from the very basics of how to search, navigate, and label.

Here’s the data discussion distilled.

The core constraint: No pre-annotated satellite imagery datasets exist for your use case. Google Maps/Earth is realistically your only free imagery source, and you can’t programmatically scrape it at scale due to terms of service.

Why data matters most: The model architecture and pipeline are straightforward engineering problems you can solve. The quality and quantity of labeled training data is what determines whether the system actually works. This is your real bottleneck.

Five approaches we explored:

Semi-automatic labeling from Street View. Walk Street View along roads near known infrastructure, visually confirm what you see at ground level, then switch to satellite view and mark the location. Gives you reliable ground truth but is slow and manual.

Weak supervision. Skip precise bounding boxes—just drop point labels at the center of objects in satellite imagery. Train on these noisy labels, then use the model’s own predictions to iteratively refine your dataset. Faster to start, messier to clean up.

Synthetic data. Composite geometric patterns resembling substations onto real satellite textures. Useful for bootstrapping but won’t capture real-world variation well on its own.

Transfer learning. Start from a model pre-trained on general aerial object detection (buildings, roads, vehicles) and fine-tune on your small labeled set. Cuts your labeling needs from thousands down to maybe a hundred or so good examples.

Hybrid approach (chosen direction). Combine manual point labeling via Street View with transfer learning. Collect a few hundred ground-truth examples manually, fine-tune a pre-trained model, then use that model’s predictions to find more examples and refine labels iteratively. Balances effort, speed, and accuracy within your six-month window.

The timeline impact: Data collection realistically consumes month one entirely. The target we were working toward was 500 labeled objects, and you asked for the detailed step-by-step process of how to actually do that labeling using Google Maps and Street View—which is where the conversation paused.