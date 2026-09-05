from transformers import AutoModelForImageTextToText, AutoProcessor, DonutProcessor, VisionEncoderDecoderModel
from PIL import Image
import re
import json

# Question answer
processor_qa = AutoProcessor.from_pretrained("naver-clova-ix/donut-base-finetuned-docvqa")
model_qa = AutoModelForImageTextToText.from_pretrained(
    "naver-clova-ix/donut-base-finetuned-docvqa", device_map="auto"
)

# cord-v2 (JSON)
processor_cord = DonutProcessor.from_pretrained("naver-clova-ix/donut-base-finetuned-cord-v2")
model_cord = VisionEncoderDecoderModel.from_pretrained(
    "naver-clova-ix/donut-base-finetuned-cord-v2", device_map="auto"
)

# mychen76 receipt

# processor_cord = DonutProcessor.from_pretrained("mychen76/invoice-and-receipts_donut_v1")
# model_cord = VisionEncoderDecoderModel.from_pretrained(
#     "mychen76/invoice-and-receipts_donut_v1", device_map="auto"
# )

def get_configs(model):
    print(model.config)


def infer_question(image, prompt):
    print("\nInferring question to donut model...")
    task_prompt = f"<s_docvqa><s_question>{prompt}</s_question><s_answer>"
    inputs = processor_qa(image, task_prompt, return_tensors="pt").to(model_qa.device)

    outputs = model_qa.generate(
        input_ids=inputs.input_ids, pixel_values=inputs.pixel_values, max_length=512
    )
    answer = processor_qa.decode(outputs[0], skip_special_tokens=True)

    return answer


def infer_json(image):
    print("\nInferring donut model (JSON) ...")

    task_prompt = "<s_cord-v2>"
    decoder_input_ids = (
        processor_cord.tokenizer(task_prompt, add_special_tokens=False, return_tensors="pt")
        .to(model_cord.device)
        .input_ids
    )

    pixel_values = processor_cord(image, return_tensors="pt").to(model_cord.device).pixel_values

    outputs = model_cord.generate(
        pixel_values.to(model_cord.device),
        decoder_input_ids=decoder_input_ids.to(model_cord.device),
        max_length=model_cord.decoder.config.max_position_embeddings,
        pad_token_id=processor_cord.tokenizer.pad_token_id,
        eos_token_id=processor_cord.tokenizer.eos_token_id,
        use_cache=True,
        bad_words_ids=[[processor_cord.tokenizer.unk_token_id]],
        return_dict_in_generate=True,
    )

    sequence = processor_cord.batch_decode(outputs.sequences)[0]
    sequence = sequence.replace(processor_cord.tokenizer.eos_token, "").replace(processor_cord.tokenizer.pad_token, "")
    sequence = re.sub(r"<.*?>", "", sequence, count=1).strip()  # remove first task start token

    return processor_cord.token2json(sequence)


if __name__ == "__main__":
    # get_configs()
    img_name = "receipt2"
    image = Image.open(f"./data/inference/{img_name}.jpg")

    print("image successfully loaded")

    # prompt = input("Please enter a question prompt: ")
    # response = infer_question(image, prompt)

    response = infer_json(image)
    response = json.dumps(response, indent=2, ensure_ascii=False)

    print(response)
