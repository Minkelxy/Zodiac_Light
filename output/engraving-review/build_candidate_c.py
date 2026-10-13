import json, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path(__file__).parent
out.mkdir(parents=True, exist_ok=True)
paths = []
def p(role, *points):
    paths.append({'points':[list(q) for q in points], 'role':role})
O='outline'
D='detail'

# The upper outline and belly are interrupted at limb attachments.
p(O,(93,203),(126,193),(165,192),(199,195),(226,193))
p(O,(247,206),(258,226),(247,244))
p(O,(220,251),(188,253),(145,255))
p(O,(112,250),(96,242),(88,225),(93,203))

# Near foreleg reaches forward; the far foreleg supports the stride.
p(O,(247,244),(273,281),(294,311),(313,326),(318,326),(319,337),(300,337),(280,313),(250,278),(220,251))
p(O,(222,250),(208,284),(212,328),(226,338),(227,350),(207,350),(197,338),(191,289),(198,254))

# Two anatomically distinct hind legs, with reverse-bending hocks.
p(O,(112,250),(101,273),(88,287),(88,321),(66,351),(48,351),(42,342),(52,335),(58,335),(72,315),(68,275),(96,242))
p(O,(145,255),(130,278),(112,312),(118,337),(131,342),(130,355),(108,355),(99,340),(95,310),(109,278),(112,250))
p(O,(92,205),(70,203),(49,213),(32,245),(45,235),(53,222),(73,215),(91,220))

# Human torso blends into the horse shoulder without a separate pedestal.
p(O,(226,193),(222,183),(216,157),(216,125),(228,113))
p(O,(252,116),(241,126),(249,146),(257,169),(257,193),(247,206),(226,193))
p(O,(231,99),(228,113))
p(O,(255,103),(252,116))

# A recognisable head profile: angular hair, brow, nose, lips, chin.
p(O,(231,99),(225,90),(223,76),(228,61),(239,51),(254,54),(267,67),(263,78),(272,83),(265,89),(266,97),(255,103),(241,103),(231,99))

# Bow arm extends forward; the drawing arm pulls back to the chin.
p(O,(239,119),(273,124),(309,136),(339,137),(346,139),(348,144),(346,151),(338,154),(302,150),(279,143),(248,143))
p(O,(223,119),(201,140),(202,153),(215,158),(249,147),(254,141),(249,136),(217,145),(219,140),(234,126))

# Bow, string, arrow, and the arrowhead consist entirely of straight cuts.
p(O,(332,90),(340,108),(345,126),(346,151),(342,185),(332,216))
p(O,(332,90),(254,144),(332,216))
p(O,(254,144),(375,144))
p(O,(362,135),(375,144),(362,153))
p(O,(340,136),(347,137),(347,152),(340,153))

# Broad head facets leave room to guide the knife around the face.
p(D,(228,61),(239,68),(254,64),(263,69))
p(D,(239,51),(239,68),(227,78))
p(D,(242,77),(252,75),(261,79))
p(D,(245,83),(253,90),(266,90))
p(D,(231,89),(244,96),(255,103))
p(D,(244,96),(251,91))

# Chest and abdominal planes are deliberately large.
p(D,(227,111),(240,124),(234,148),(241,173),(247,195))
p(D,(216,125),(231,129),(248,143))
p(D,(217,159),(234,148),(252,160))
p(D,(222,183),(241,173),(257,179))
p(D,(226,193),(247,195),(257,193))
p(D,(231,129),(228,144))
p(D,(234,148),(235,159),(241,173))
p(D,(231,99),(240,112),(242,121))

# Muscle planes in the arms communicate the archery gesture.
p(D,(247,130),(274,133),(301,144))
p(D,(274,124),(274,141))
p(D,(289,130),(285,144))
p(D,(304,138),(302,150))
p(D,(222,132),(209,144),(216,152),(244,141))
p(D,(205,140),(217,145))
p(D,(223,119),(229,128))
p(D,(226,143),(228,154))

# Horse facets follow rump, ribcage and shoulder rather than a dense mesh.
p(D,(93,203),(112,220),(96,242))
p(D,(126,193),(112,220),(143,222),(165,192))
p(D,(112,220),(126,243),(145,255))
p(D,(143,222),(163,240),(188,253))
p(D,(165,192),(179,213),(202,216),(226,193))
p(D,(143,222),(179,213))
p(D,(179,213),(174,241),(145,255))
p(D,(202,216),(217,233),(220,251))
p(D,(202,216),(231,214),(247,206))
p(D,(231,214),(242,233),(247,244))
p(D,(217,233),(242,233))
p(D,(174,241),(198,241),(217,233))

# Leg and hoof panels remain long enough for hand engraving.
p(D,(237,226),(254,256),(271,286),(284,310),(307,331))
p(D,(258,266),(276,287))
p(D,(280,313),(294,311))
p(D,(300,337),(307,331),(319,337))
p(D,(211,253),(201,285),(202,327),(215,340))
p(D,(197,282),(208,284))
p(D,(194,302),(211,307))
p(D,(197,338),(212,328))
p(D,(99,252),(80,276),(79,316),(57,343))
p(D,(69,280),(88,287))
p(D,(69,314),(87,314))
p(D,(52,335),(64,341),(66,351))
p(D,(122,256),(120,278),(104,310),(108,336),(119,348))
p(D,(109,278),(130,278))
p(D,(95,310),(112,312))
p(D,(99,340),(118,337))
p(D,(108,355),(119,348),(130,355))
p(D,(91,212),(71,208),(55,217),(41,235))

obj={'id':'C','title':'人马射手几何细节','subtitle':'四腿人马 · 拉弓侧影 · 大分面直线刻纹','polylines':paths}
(out/'candidate-c.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

scale=3
im=Image.new('RGB',(400*scale,400*scale),'#fbfaf6')
draw=ImageDraw.Draw(im)
draw.rectangle((7*scale,7*scale,393*scale,393*scale),outline='#d5d3ca',width=2)
for role,color,width in [('detail','#879eaa',2),('outline','#143040',4)]:
    for path in paths:
        if path['role']==role:
            draw.line([(int(x*scale),int(y*scale)) for x,y in path['points']],fill=color,width=width,joint='curve')
im.save(out/'candidate-c-preview.png')

lengths=[math.dist(a,b) for path in paths for a,b in zip(path['points'],path['points'][1:])]
details=[math.dist(a,b) for path in paths if path['role']=='detail' for a,b in zip(path['points'],path['points'][1:])]
print(json.dumps({'segments':len(lengths),'detail_segments':len(details),'shortest_mm':round(min(lengths),3),'under_8mm':sum(x<8 for x in lengths),'total_length_mm':round(sum(lengths))}))
