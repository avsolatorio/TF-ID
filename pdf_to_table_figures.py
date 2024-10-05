from pdf2image import convert_from_path, convert_from_bytes
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError
)
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM 

import os
import json
import time

import torch


def pdf_to_image(pdf_path):
	images = convert_from_path(pdf_path)
	return images

def tf_id_detection(image, model, processor):
	prompt = "<OD>"
	inputs = processor(text=prompt, images=image, return_tensors="pt")
	inputs.to(model.device)

	generated_ids = model.generate(
		input_ids=inputs["input_ids"],
		pixel_values=inputs["pixel_values"],
		max_new_tokens=1024,
		do_sample=False,
		num_beams=3
	)
	generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
	annotation = processor.post_process_generation(generated_text, task="<OD>", image_size=(image.width, image.height))
	return annotation["<OD>"]

def save_image_from_bbox(image, annotation, page, output_dir):
	# the name should be page + label + index
	for i in range(len(annotation['bboxes'])):
		bbox = annotation['bboxes'][i]
		label = annotation['labels'][i]
		x1, y1, x2, y2 = bbox
		cropped_image = image.crop((x1, y1, x2, y2))
		cropped_image.save(os.path.join(output_dir, f"page_{page}_{label}_{i}.png"))

def pdf_to_table_figures(pdf_path, model_id, output_dir, device: str | None = None):
	if device is None:
		if torch.cuda.device_count() > 0:
			device = "cuda:0"
		else:
			device = "cpu"

	timestr = time.strftime("%Y%m%d-%H%M%S")
	output_dir = os.path.join(output_dir, timestr)

	os.makedirs(output_dir, exist_ok=True)

	images = pdf_to_image(pdf_path)
	print(f"PDF loaded. Number of pages: {len(images)}")
	model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, device_map=device)
	processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True, device_map=device)
	print("Model loaded: ", model_id)
	
	print("=====================================")
	print("start saving cropped images")
	for i, image in enumerate(images):
		annotation = tf_id_detection(image, model, processor)
		save_image_from_bbox(image, annotation, i, output_dir)
		print(f"Page {i} saved. Number of objects: {len(annotation['bboxes'])}")
	
	print("=====================================")
	print("All images saved to: ", output_dir)


def main(pdf_path: str, model_id: str = "yifeihu/TF-ID-large", output_dir: str = "./sample_output", device: str = None):
    pdf_to_table_figures(pdf_path, model_id, output_dir, device=device)


if __name__ == "__main__":
    import fire

    fire.Fire(main)

