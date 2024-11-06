import base64
from PIL import Image
import io

def replace_uuid_with_base64(passage, image_dict):
    """
    Takes in a passage object from an opensearch document 
    and returns the passage with the base64 included within <image_base64> tags.
    """
    for uuid, base64_str in image_dict.items():
        if uuid in passage:
            passage = passage.replace(f"({uuid})", f"<image_base64>{image_dict[uuid]}</image_base64>")
    return passage

def decode_base64_to_image(base64_str):
    image_data = base64.b64decode(base64_str)
    return Image.open(io.BytesIO(image_data))
