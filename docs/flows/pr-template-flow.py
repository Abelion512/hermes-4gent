# Regenerates docs/assets/pr-template-flow.png. Run from the repo root: python3 docs/flows/pr-template-flow.py
from PIL import Image, ImageDraw, ImageFont
W,H=1500,520
im=Image.new("RGB",(W,H),"#0f1420"); d=ImageDraw.Draw(im)
F="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FB="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
t=ImageFont.truetype(FB,34); b=ImageFont.truetype(FB,22); s=ImageFont.truetype(F,19)
G="#9fb0cc"
d.text((40,26),"How it works: the pull request template",font=t,fill="#ffffff")
d.text((40,74),"The template fills the PR description for you. The image helps the reviewer see the change.",font=s,fill=G)
def box(x,y,w,h,title,lines,col):
    d.rounded_rectangle((x,y,x+w,y+h),radius=16,fill="#18202f",outline=col,width=3)
    d.text((x+18,y+14),title,font=b,fill=col)
    for i,l in enumerate(lines): d.text((x+18,y+50+i*27),l,font=s,fill="#dbe4f5")
def arrow(x1,y,x2):
    d.line((x1,y,x2,y),fill=G,width=4); d.polygon([(x2,y),(x2-14,y-9),(x2-14,y+9)],fill=G)
box(40,140,300,150,"1. Open a PR",["GitHub pre-fills the","description from","the template"],"#6ea8ff")
box(400,140,330,150,"2. Fill it in",["What changed","How it works (image)","Verification, Trade-off"],"#7ee0a1")
box(790,140,300,150,"3. Add the image",["Screenshot or small","diagram of the change.","Source stays in repo."],"#ffd36e")
box(1150,140,310,150,"4. Review",["Review the picture","and the checks."],"#c3a6ff")
for a,b2 in ((340,400),(730,790),(1090,1150)): arrow(a,215,b2)
d.text((40,340),"The template is applied to new PRs only after it is merged to the default branch.",font=s,fill=G)
d.text((40,374),"Nothing here runs in CI, merges, or deploys.",font=s,fill=G)
im.save("docs/assets/pr-template-flow.png")
