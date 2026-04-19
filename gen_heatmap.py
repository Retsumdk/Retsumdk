#!/usr/bin/env python3
grid = [
    [0,0,8,0,0,0,0,0,0,0,0,0,0,3,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,2,0,5,0,0,0,0,0,3,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,2,0,5,0,0,0,0,0,1,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,2,0,4,0,0,0,0,0,1,0,3],
    [6,0,0,0,0,0,0,0,0,0,0,0,0,2,0,0,0,0,6,0,0,0,0,0],
    [0,23,0,0,0,0,0,0,5,15,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,3,0,0],
]
DAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
total = sum(sum(row) for row in grid)
max_val = max(max(row) for row in grid)

CELL = 18; GAP = 4; PAD_L = 52; PAD_T = 36; LABEL_GAP = 10
cols = 24; rows = 7
grid_w = cols*(CELL+GAP)
W = PAD_L + grid_w + 24
H = PAD_T + rows*(CELL+GAP) + LABEL_GAP + 24

def col(v):
    if v==0: return '#161b22'
    p = v/max_val
    if p<=0.25: return '#0e4429'
    if p<=0.5: return '#006d32'
    if p<=0.75: return '#26a641'
    return '#39d353'

F = '"-apple-system,BlinkMacSystemFont,&apos;Segoe UI&apos;,Helvetica,Arial,sans-serif"'

svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%">
<rect width="100%" height="100%" fill="#0d1117"/>
<text x="4" y="18" font-size="13" font-weight="600" fill="#c9d1d9" font-family={F}>Daily commits by hour</text>
<text x="4" y="32" font-size="10" fill="#6e7681" font-family={F}>{total} commits · last 7 days</text>
'''
for i,day in enumerate(DAYS):
    y = PAD_T + i*(CELL+GAP) + CELL//2 + 5
    svg += f'<text x="{PAD_L-LABEL_GAP}" y="{y}" font-size="11" text-anchor="end" fill="#8b949e" font-family={F}>{day}</text>\n'
for h in [0,6,12,18]:
    x = PAD_L + h*(CELL+GAP) + CELL//2
    svg += f'<text x="{x}" y="{PAD_T+rows*(CELL+GAP)+LABEL_GAP+14}" font-size="10" text-anchor="middle" fill="#6e7681" font-family={F}>{h}:00</text>\n'
for i in range(rows):
    for h in range(cols):
        v = grid[i][h]
        x = PAD_L + h*(CELL+GAP)
        y = PAD_T + i*(CELL+GAP)
        svg += f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="3" fill="{col(v)}"/>\n'
lx = PAD_L + grid_w - 60
ly = PAD_T + rows*(CELL+GAP) + LABEL_GAP + 12
svg += f'<text x="{lx-2}" y="{ly}" font-size="10" fill="#6e7681" font-family={F}>Less</text>\n'
COLS = ['#161b22','#0e4429','#006d32','#26a641','#39d353']
for k in range(5):
    svg += f'<rect x="{lx+28+k*14}" y="{ly-10}" width="11" height="11" rx="2" fill="{COLS[k]}"/>\n'
svg += f'<text x="{lx+100}" y="{ly}" font-size="10" fill="#6e7681" font-family={F}>More</text>\n'
svg += '</svg>'
with open('/tmp/heatmap.svg','w') as f: f.write(svg)
print(f'Done: {len(svg)} bytes, cells={svg.count("<rect")}, total={total}, max={max_val}')
