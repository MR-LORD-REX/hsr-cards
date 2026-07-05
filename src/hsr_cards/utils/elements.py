from PIL import Image
from pathlib import Path
from typing import Dict , Literal

img_path = Path(__file__).parent.parent / "assets" / "elements"

class Elements:
    ELEMENTS: Dict[str, Image.Image] = {
        "fire": Image.open(img_path / "fire.png"),
        "ice": Image.open(img_path / "ice.png"),
        "wind": Image.open(img_path / "wind.png"),
        "lightning": Image.open(img_path / "lightning.png"),
        "physical": Image.open(img_path / "physical.png"),
        "quantum": Image.open(img_path / "quantum.png"),
        "imaginary": Image.open(img_path / "imaginary.png"),
    }

    @staticmethod
    def get_element(element: Literal["fire", "ice", "wind", "lightning", "physical","imaginary","quantum"]) -> Image.Image:
        img= Elements.ELEMENTS.get(element)
        if img is None:
            raise ValueError(f"Invalid element: {element}")
        return img