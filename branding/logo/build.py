import os, numpy as np, vtracer, subprocess
from PIL import Image, ImageDraw, ImageFilter
B=os.path.dirname(os.path.abspath(__file__)); S=B+"/source/komboe-padlock-k-original.png"
for d in ["master","variants","favicon","extension","desktop","mobile/ios","mobile/android"]: os.makedirs(f"{B}/{d}",exist_ok=True)
g=np.asarray(Image.open(S).convert("L")).astype(float)
a=np.clip((236-g)/(236-8),0,1); a[a<0.06]=0
ys,xs=np.where(a>0.5); y0,y1,x0,x1=ys.min(),ys.max(),xs.min(),xs.max()
h=y1-y0+1; w=x1-x0+1; side=int(max(h,w)*1.2); side+=side%2
cy=(y0+y1)//2; cx=(x0+x1)//2
A=np.zeros((side,side)); 
sy=cy-side//2; sx=cx-side//2
A=np.pad(a,side)[sy+side:sy+2*side, sx+side:sx+2*side]
mask=Image.fromarray((A*255).round().astype(np.uint8))
mask.save(f"{B}/master/komboe-mask.png")
def glyph(color,size=None,m=mask):
    mm=m if size is None else m.resize((size,size),Image.LANCZOS)
    im=Image.new("RGBA",mm.size,color+(0,)); im.putalpha(mm); return im
INK=(7,7,2); CREAM=(240,236,231); PURPLE=(109,74,255); LAV=(196,183,255); DARK=(25,23,36)
glyph(INK).save(f"{B}/master/komboe-logo-master-transparent.png")
V={"original":(INK,CREAM),"light":(PURPLE,(255,255,255)),"dark":(LAV,DARK)}
for k,(fg,bg) in V.items():
    glyph(fg).save(f"{B}/variants/komboe-{k}-transparent.png")
    t=Image.new("RGBA",mask.size,bg+(255,)); t.alpha_composite(glyph(fg)); t.convert("RGB").save(f"{B}/variants/komboe-{k}-on-bg.png")
# SVG trace
bw=Image.new("L",mask.size,255); bw.paste(0,mask=mask.point(lambda v:255 if v>127 else 0))
up=bw.resize((side*4,side*4),Image.LANCZOS).point(lambda v:0 if v<128 else 255); up.save("/workspace/kb/bw.png")
vtracer.convert_image_to_svg_py("/workspace/kb/bw.png",f"{B}/master/komboe-logo.svg",colormode="binary",mode="spline",filter_speckle=4,corner_threshold=60,path_precision=3)
# App tile: dark-purple gradient rounded square, white glyph, ~62% glyph
def tile(n,radius=0.225,alpha=True,scale=0.66):
    t=Image.new("RGBA",(n,n),(0,0,0,0)); grad=Image.new("RGBA",(n,n))
    top=np.array([124,92,255]); bot=np.array([62,36,180]); yy=np.linspace(0,1,n)[:,None,None]
    arr=(top*(1-yy)+bot*yy).repeat(n,1); grad=Image.fromarray(np.dstack([arr,np.full((n,n,1),255)]).astype(np.uint8),"RGBA")
    m=Image.new("L",(n,n),0 if radius else 255)
    if radius: ImageDraw.Draw(m).rounded_rectangle([0,0,n-1,n-1],int(n*radius),fill=255)
    t.paste(grad,mask=m); gs=int(n*scale)
    if gs>=2: t.alpha_composite(glyph((255,255,255),gs),((n-gs)//2,(n-gs)//2))
    return t if alpha else t.convert("RGB")
# small sizes: glyph only gets lost; use tile
for n in (16,32,48): tile(n,0.2,scale=0.8).save(f"{B}/favicon/favicon-{n}.png")
tile(256,0.2,scale=0.8).save(f"{B}/favicon/favicon.ico",sizes=[(16,16),(32,32),(48,48)])
tile(180,0,False).save(f"{B}/favicon/apple-touch-icon-180.png")
for n in (192,512): tile(n).save(f"{B}/favicon/pwa-{n}.png")
for n in (16,32,48,128): tile(n,0.2,scale=0.8 if n<48 else 0.7).save(f"{B}/extension/icon-{n}.png")
tile(256).save(f"{B}/desktop/komboe.ico",sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
tile(1024).save(f"{B}/desktop/komboe.icns")
for n in (256,512): tile(n).save(f"{B}/desktop/komboe-{n}.png")
tile(1024,0,False).save(f"{B}/mobile/ios/AppIcon-1024.png")
fg=Image.new("RGBA",(432,432),(0,0,0,0)); gs=int(432*0.42); fg.alpha_composite(glyph((255,255,255),gs),((432-gs)//2,(432-gs)//2)); fg.save(f"{B}/mobile/android/ic_launcher_foreground.png")
tile(432,0,False,0.0001).save(f"{B}/mobile/android/ic_launcher_background.png")
tile(512,0,False).save(f"{B}/mobile/android/play-store-512.png")
