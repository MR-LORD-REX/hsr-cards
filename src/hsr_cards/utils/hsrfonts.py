from PIL import ImageFont
from pathlib import Path
from typing import Dict , Literal

fontpath= Path(__file__).parent.parent / "assets" / "fonts"

class HSRFonts:
    FONTS: dict[str, str] = {
        "bold": str(fontpath / "DIN-Bold.ttf"),
        "light": str(fontpath / "DIN-Light.ttf"),
        "medium": str(fontpath / "DIN-Medium.ttf"),
        "regular": str(fontpath / "DIN-Regular.ttf"),
    }
    
    @staticmethod
    def get_font(size: int,type:Literal["bold","light","medium","regular"]) -> ImageFont.FreeTypeFont:
        font_path = HSRFonts.FONTS.get(type)
        if font_path is None:
            raise ValueError(f"Invalid font type: {type}")
        return ImageFont.truetype(font_path, size)