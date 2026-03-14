from pathlib import Path
from PIL import Image , ImageDraw

star_normal=Path(__file__).parent.parent / "assets"/"backgrounds"/"ANO"/"star_normal.png"
star_gold=Path(__file__).parent.parent / "assets"/"backgrounds"/"ANO"/"star_gold.png"


async def render_stars(gold_count:int):
    new=Image.new("RGBA",(124,36),color=(0,0,0,0))
    norm=Image.open(star_normal).convert("RGBA").resize((36,36))
    gold=Image.open(star_gold).convert("RGBA").resize((36,36))
    for i in range(3):
        if i<gold_count:
            new.paste(gold,(i*36,0),mask=gold)
        else:
            new.paste(norm,(i*36,0),mask=norm)    
    return new