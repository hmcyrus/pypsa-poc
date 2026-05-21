Here’s where we’ve landed so far.

Your goal: Detect power infrastructure (substations, electrical towers, transformers) from satellite imagery, covering a large landscape, using open source tools and AI, within six months.

Feasibility: Confirmed doable. Power infrastructure has distinct visual signatures at 5–15 meter resolution. Free imagery sources like Sentinel-2 work, and your software engineering background maps directly onto the computer vision pipeline needed.

Core skill gap: Not GIS—it’s object detection. You need CNNs, YOLO/Faster RCNN, and an understanding that satellite images carry embedded coordinates. Traditional map knowledge is mostly unnecessary.

The data problem: Your main bottleneck. No pre-annotated datasets are available, and Google Maps is realistically your only accessible imagery source. We explored five approaches to bootstrap training data: semi-automatic labeling from Street View, weak supervision with point labels, synthetic data generation, transfer learning from pre-trained models, and a hybrid combining these.

Chosen direction: The hybrid approach—combine manual point-level labeling using Google Street View for ground truth, then leverage transfer learning on a pre-trained detection model fine-tuned on your small dataset, iteratively improving with model-assisted relabeling.

Where we stopped: You asked for the detailed step-by-step process of manually labeling 500 objects using Google Maps and Street View, starting from the very basics of how to search, navigate, and label.