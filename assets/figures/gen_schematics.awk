function card(f,w,h,title,subt){
  printf("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 %d %d\" font-family=\"system-ui,-apple-system,Segoe UI,sans-serif\">\n",w,h) > f
  printf("<rect x=\"0\" y=\"0\" width=\"%d\" height=\"%d\" rx=\"14\" fill=\"#fcfcfb\" stroke=\"#e1e0d9\"/>\n",w,h) > f
  printf("<text x=\"28\" y=\"38\" font-size=\"20\" font-weight=\"700\" fill=\"#0b0b0b\">%s</text>\n",title) > f
  printf("<text x=\"28\" y=\"62\" font-size=\"13\" fill=\"#52514e\">%s</text>\n",subt) > f
}
BEGIN{
  BLUE="#2a78d6"; ORANGE="#eb6834"; INK="#0A2540"; MUT="#898781"; GRID="#e8e7e0"; PALE="#f0efec"

  # ===== FIG 6: recipe machine =====
  f="assets/figures/fig6_recipe_machine.svg"; W=760; H=340
  card(f,W,H,"What x @ W actually does: a stack of recipes","One output number is a custom weighted blend of ALL the inputs. One column of the matrix = one recipe.")
  ix=70; iy=140; bs=46
  split("2 4 1", xv, " ")
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\" font-weight=\"600\">input x</text>\n",ix,iy-12,INK) > f
  for(i=0;i<3;i++){ printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" rx=\"6\" fill=\"#eaf1fb\" stroke=\"%s\"/>\n",ix,iy+i*bs,bs,bs,BLUE) > f
    printf("<text x=\"%d\" y=\"%d\" font-size=\"16\" fill=\"%s\" text-anchor=\"middle\" font-weight=\"700\">%s</text>\n",ix+bs/2,iy+i*bs+bs/2+6,INK,xv[i+1]) > f }
  # matrix W 3x3, first column tinted orange (the active recipe)
  wx=260; wy=iy
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\" font-weight=\"600\">matrix W (each column is a recipe)</text>\n",wx,wy-12,INK) > f
  split("0.5 0.2 -0.1", col1, " ")
  for(r=0;r<3;r++) for(cc=0;cc<3;cc++){ fillc=(cc==0?"#fd e":"#fff"); fc=(cc==0?"#fcece3":"#ffffff")
    printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"%s\" stroke=\"%s\"/>\n",wx+cc*bs,wy+r*bs,bs,bs,fc,(cc==0?ORANGE:GRID)) > f
    if(cc==0) printf("<text x=\"%d\" y=\"%d\" font-size=\"13\" fill=\"%s\" text-anchor=\"middle\" font-weight=\"700\">%s</text>\n",wx+cc*bs+bs/2,wy+r*bs+bs/2+5,ORANGE,col1[r+1]) > f
    else printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\" text-anchor=\"middle\">.</text>\n",wx+cc*bs+bs/2,wy+r*bs+bs/2+5,MUT) > f }
  # arrows from inputs to output y1
  ox=560; oy=iy
  for(i=0;i<3;i++) printf("<line x1=\"%d\" y1=\"%d\" x2=\"%d\" y2=\"%d\" stroke=\"%s\" stroke-width=\"1.5\" opacity=\"0.7\"/>\n",ix+bs,iy+i*bs+bs/2,ox,oy+bs/2,ORANGE) > f
  printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" rx=\"6\" fill=\"#fcece3\" stroke=\"%s\" stroke-width=\"2\"/>\n",ox,oy,bs+8,bs,ORANGE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"16\" fill=\"%s\" text-anchor=\"middle\" font-weight=\"700\">1.7</text>\n",ox+(bs+8)/2,oy+bs/2+6,ORANGE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\" font-weight=\"600\">output y1</text>\n",ox,oy-12,INK) > f
  printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" rx=\"6\" fill=\"#f7f6f3\" stroke=\"%s\"/>\n",ox,oy+bs+10,bs+8,bs,GRID) > f
  printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" rx=\"6\" fill=\"#f7f6f3\" stroke=\"%s\"/>\n",ox,oy+2*bs+20,bs+8,bs,GRID) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"15\" fill=\"%s\" text-anchor=\"middle\">y1 = 0.5*2 + 0.2*4 - 0.1*1 = 1.7</text>\n",W/2,H-58,INK) > f
  printf("<text x=\"28\" y=\"%d\" font-size=\"12.5\" fill=\"#52514e\">Stack the recipes, get the whole output. This one operation is the thing chips run fastest, and the whole document rides on it.</text>\n",H-24) > f
  print "</svg>" > f; close(f)

  # ===== FIG 8: scan vs GEMM utilization =====
  f="assets/figures/fig8_utilization.svg"; W=760; H=360
  card(f,W,H,"Same chip, very different occupancy (intuition, not a benchmark)","A bespoke scan keeps a moving front busy while the rest idles; GEMM lights up the whole stadium at once.")
  n=8; cell=30; gap=6
  # left grid: scan wavefront
  gx=90; gy=110
  printf("<text x=\"%d\" y=\"%d\" font-size=\"13\" font-weight=\"700\" fill=\"%s\">Mamba scan kernel</text>\n",gx,gy-14,BLUE) > f
  for(r=0;r<n;r++) for(cc=0;cc<n;cc++){ lit=(r+cc==7); col=(lit?ORANGE:"#e6e5df")
    printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" rx=\"3\" fill=\"%s\"/>\n",gx+cc*(cell),gy+r*(cell),cell-gap,cell-gap,col) > f }
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11.5\" fill=\"%s\">a moving front works; the stadium mostly waits</text>\n",gx,gy+n*cell+22,MUT) > f
  # right grid: GEMM full
  gx2=440
  printf("<text x=\"%d\" y=\"%d\" font-size=\"13\" font-weight=\"700\" fill=\"%s\">GEMM / attention</text>\n",gx2,gy-14,ORANGE) > f
  for(r=0;r<n;r++) for(cc=0;cc<n;cc++){ printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" rx=\"3\" fill=\"%s\"/>\n",gx2+cc*(cell),gy+r*(cell),cell-gap,cell-gap,ORANGE) > f }
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11.5\" fill=\"%s\">every seat rehearsed this one move: all busy</text>\n",gx2,gy+n*cell+22,MUT) > f
  printf("<text x=\"28\" y=\"%d\" font-size=\"12.5\" fill=\"#52514e\">This is why we want Mamba's math in GEMM form: the scan's low arithmetic intensity starves the cores; the matmul saturates them.</text>\n",H-22) > f
  print "</svg>" > f; close(f)

  # ===== FIG 5: chunking as tiling of L =====
  f="assets/figures/fig5_chunking.svg"; W=680; H=560
  card(f,W,H,"Chunking is just tiling the matrix L","Fill each orange diagonal block with a fast parallel matmul; stitch blocks with one cheap blue thread of carried state.")
  n=8; cs=52; gx=90; gy=110
  # base grid (lower triangle faint)
  for(t=0;t<n;t++) for(s=0;s<n;s++){ x=gx+s*cs; y=gy+t*cs
    fc=(s<=t?"#eef1f5":"#f7f6f3")
    printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"%s\" stroke=\"#fcfcfb\" stroke-width=\"2\"/>\n",x,y,cs,cs,fc) > f }
  # chunk size 3 -> blocks {0-2},{3-5},{6-7}
  nb=split("0 3 6 8", bnd, " ")  # boundaries
  for(k=1;k<nb;k++){ lo=bnd[k]; hi=bnd[k+1]-1; sz=hi-lo+1
    # diagonal block outline (orange)
    printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"#fbe9df\" stroke=\"%s\" stroke-width=\"3\"/>\n",gx+lo*cs,gy+lo*cs,sz*cs,sz*cs,ORANGE) > f
    printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"%s\" text-anchor=\"middle\" font-weight=\"700\">matmul</text>\n",gx+lo*cs+sz*cs/2,gy+lo*cs+sz*cs/2+4,ORANGE) > f
    # below-diagonal region for this block's rows vs earlier cols (blue)
    if(lo>0) printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"#dbe8fb\" stroke=\"%s\" stroke-width=\"1.5\" opacity=\"0.75\"/>\n",gx,gy+lo*cs,lo*cs,sz*cs,BLUE) > f
    # carried-state arrow to next block
    if(k<nb-1) printf("<path d=\"M%d,%d L%d,%d\" stroke=\"%s\" stroke-width=\"2.5\" fill=\"none\" marker-end=\"url(#ar)\"/>\n",gx+lo*cs+sz*cs/2,gy+(hi+1)*cs-4,gx+(hi+1)*cs-4,gy+(hi+1)*cs+2,BLUE) > f }
  printf("<defs><marker id=\"ar\" markerWidth=\"8\" markerHeight=\"8\" refX=\"6\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L6,3 L0,6 Z\" fill=\"%s\"/></marker></defs>\n",BLUE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\"><tspan fill=\"%s\" font-weight=\"700\">orange blocks</tspan> = parallel matmul (GEMM, tensor cores)</text>\n",gx,gy+n*cs+30,INK,ORANGE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\"><tspan fill=\"%s\" font-weight=\"700\">blue region + arrow</tspan> = small summary state carried chunk to chunk (cheap recurrence)</text>\n",gx,gy+n*cs+52,INK,BLUE) > f
  printf("<text x=\"28\" y=\"%d\" font-size=\"12.5\" fill=\"#52514e\">Attention inside each chunk, a thin recurrence between: reading the novel chapter by chapter.</text>\n",H-22) > f
  print "</svg>" > f; close(f)

  # ===== FIG 10: nanopore squiggle -> k-mer -> base =====
  f="assets/figures/fig10_squiggle.svg"; W=760; H=420
  card(f,W,H,"What the nanopore signal actually is","The current is a fingerprint of a WINDOW of bases in the pore at once, and the signal is ~10x longer than the DNA it encodes.")
  # squiggle: plateaus
  sx=70; sy=110; sw=620; sh=120
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"%s\">current (pA)</text>\n",sx,sy-4,MUT) > f
  n=8; split("60 45 72 72 72 38 55 66", lvl, " ")
  s=""; xx=sx; step=sw/(n)
  for(i=0;i<n;i++){ y=sy+sh*(1-(lvl[i+1]-30)/60); x0=sx+i*step; x1=sx+(i+1)*step
    s=s sprintf("%sM%.1f,%.1f L%.1f,%.1f",(i==0?"":" "),x0,y,x1,y)
    if(i<n-1){ y2=sy+sh*(1-(lvl[i+2]-30)/60); s=s sprintf(" L%.1f,%.1f",x1,y2) } }
  printf("<path d=\"%s\" fill=\"none\" stroke=\"%s\" stroke-width=\"2.5\"/>\n",s,BLUE) > f
  # highlight window over plateau 3-4-5 (the flat 72s)
  printf("<rect x=\"%.1f\" y=\"%d\" width=\"%.1f\" height=\"%d\" fill=\"%s\" opacity=\"0.18\" stroke=\"%s\" stroke-dasharray=\"5 3\"/>\n",sx+2*step,sy-6,3*step,sh+12,ORANGE,ORANGE) > f
  printf("<text x=\"%.1f\" y=\"%d\" font-size=\"11\" fill=\"%s\" text-anchor=\"middle\" font-weight=\"600\">sensing region: ~5-9 bases in the pore at once</text>\n",sx+3.5*step,sy-14,ORANGE) > f
  # DNA strand
  dy=sy+sh+50
  split("G A C T G C A A G T", bases, " ")
  nb2=10
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"%s\">DNA strand threading the pore</text>\n",sx,dy-16,MUT) > f
  for(i=0;i<nb2;i++){ bx=sx+i*(sw/nb2); inwin=(i>=3&&i<=7)
    printf("<rect x=\"%.1f\" y=\"%d\" width=\"%.1f\" height=\"26\" rx=\"4\" fill=\"%s\" stroke=\"%s\"/>\n",bx,dy,sw/nb2-6,(inwin?"#fcece3":"#eef1f5"),(inwin?ORANGE:GRID)) > f
    printf("<text x=\"%.1f\" y=\"%d\" font-size=\"14\" fill=\"%s\" text-anchor=\"middle\" font-family=\"monospace\" font-weight=\"700\">%s</text>\n",bx+(sw/nb2-6)/2,dy+18,INK,bases[i+1]) > f }
  # output bases (shorter)
  oy2=dy+70
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"%s\">basecaller output (shorter than the signal)</text>\n",sx,oy2-8,MUT) > f
  split("T G C A A", ob, " ")
  for(i=0;i<5;i++){ bx=sx+i*40; printf("<rect x=\"%d\" y=\"%d\" width=\"34\" height=\"26\" rx=\"4\" fill=\"#eafaf0\" stroke=\"#3a9d6a\"/>\n",bx,oy2) > f
    printf("<text x=\"%d\" y=\"%d\" font-size=\"14\" fill=\"%s\" text-anchor=\"middle\" font-family=\"monospace\" font-weight=\"700\">%s</text>\n",bx+17,oy2+18,INK,ob[i+1]) > f }
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\">~10 signal samples per base, so input T is ~10x longer than output. One read = hundreds of thousands of samples.</text>\n",sx+230,oy2+18,INK) > f
  print "</svg>" > f; close(f)
  print "schematics OK"
}
