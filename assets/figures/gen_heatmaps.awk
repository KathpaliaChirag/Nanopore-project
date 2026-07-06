# Generates fig2_L_matrix.svg and fig4_raw_vs_softmax.svg from a fixed illustrative dataset.
# L[t,s] = c[t]*b[s]*(P[t]/P[s]) for s<=t (0 above diagonal). Values computed exactly.
function irgb(bR,bG,bB, pR,pG,pB, t,  r,g,b){
  r=int(bR+(pR-bR)*t+0.5); g=int(bG+(pG-bG)*t+0.5); b=int(bB+(pB-bB)*t+0.5)
  return sprintf("rgb(%d,%d,%d)",r,g,b) }
function divcolor(v,  t){ t=(v<0?-v:v)/M; if(t>1)t=1
  if(v>=0) return irgb(243,241,238,235,104,52,t); else return irgb(243,241,238,42,120,214,t) }
function seqcolor(u){ if(u<0)u=0; if(u>1)u=1; return irgb(233,240,251,13,54,107,u) }
function ink(t){ return (t>0.58?"#ffffff":"#0A2540") }
function header(f,title,subt){
  printf("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 %d %d\" font-family=\"system-ui,-apple-system,Segoe UI,sans-serif\">\n",CW,CH) > f
  printf("<rect x=\"0\" y=\"0\" width=\"%d\" height=\"%d\" rx=\"14\" fill=\"#fcfcfb\" stroke=\"#e1e0d9\"/>\n",CW,CH) > f
  printf("<text x=\"28\" y=\"40\" font-size=\"21\" font-weight=\"700\" fill=\"#0b0b0b\">%s</text>\n",title) > f
  printf("<text x=\"28\" y=\"66\" font-size=\"13.5\" fill=\"#52514e\">%s</text>\n",subt) > f }
BEGIN{
  n=8
  split("0.90 0.85 0.80 0.88 0.75 0.82 0.90 0.78",a," ")
  split("1.0 -0.5 0.8 0.3 -0.9 0.6 -0.4 0.7",b," ")
  split("0.5 0.9 -0.3 0.7 0.4 -0.6 0.8 0.2",c," ")
  for(t=0;t<n;t++){ av[t]=a[t+1]; bv[t]=b[t+1]; cv[t]=c[t+1] }
  P[0]=av[0]; for(t=1;t<n;t++) P[t]=P[t-1]*av[t]
  M=0
  for(t=0;t<n;t++) for(s=0;s<=t;s++){ L[t,s]=cv[t]*bv[s]*(P[t]/P[s]); m=(L[t,s]<0?-L[t,s]:L[t,s]); if(m>M)M=m }
  for(t=0;t<n;t++){ sum=0; for(s=0;s<=t;s++){ E=exp(L[t,s]); Es[t,s]=E; sum+=E } for(s=0;s<=t;s++) W[t,s]=Es[t,s]/sum
    rs=0; for(s=0;s<=t;s++) rs+=L[t,s]; rowsumL[t]=rs }

  # ---------- FIG 2 ----------
  cs=52; gx=96; gy=104; CW=gx+n*cs+150; CH=gy+n*cs+118; f2="assets/figures/fig2_L_matrix.svg"
  header(f2,"The matrix L  \xE2\x80\x94  y = L @ x in one picture","Each cell L[t,s] = c_t \xC2\xB7 b_s \xC2\xB7 (P_t / P_s). Blank = causal mask (no peeking at the future). Orange +, blue \xE2\x88\x92.")
  for(s=0;s<n;s++) printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"#898781\" text-anchor=\"middle\">s=%d</text>\n",gx+s*cs+cs/2,gy-10,s) > f2
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"#52514e\" text-anchor=\"middle\" font-weight=\"600\">input position s  \xE2\x86\x92</text>\n",gx+n*cs/2,gy-30) > f2
  for(t=0;t<n;t++) printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"#898781\" text-anchor=\"end\">t=%d</text>\n",gx-12,gy+t*cs+cs/2+4,t) > f2
  printf("<text transform=\"translate(30,%d) rotate(-90)\" font-size=\"12\" fill=\"#52514e\" text-anchor=\"middle\" font-weight=\"600\">output position t  \xE2\x86\x93</text>\n",gy+n*cs/2) > f2
  for(t=0;t<n;t++) for(s=0;s<n;s++){ x=gx+s*cs; y=gy+t*cs
    if(s<=t){ v=L[t,s]; tt=(v<0?-v:v)/M
      printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"%s\" stroke=\"#fcfcfb\" stroke-width=\"2\"/>\n",x,y,cs,cs,divcolor(v)) > f2
      printf("<text x=\"%d\" y=\"%d\" font-size=\"11.5\" fill=\"%s\" text-anchor=\"middle\">%.2f</text>\n",x+cs/2,y+cs/2+4,ink(tt),v) > f2 }
    else printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"#f7f6f3\" stroke=\"#fcfcfb\" stroke-width=\"2\"/>\n",x,y,cs,cs) > f2 }
  printf("<path d=\"M%d,%d L%d,%d\" stroke=\"#0A2540\" stroke-width=\"2.5\" fill=\"none\" opacity=\"0.5\"/>\n",gx,gy,gx+n*cs,gy+n*cs) > f2
  lx=gx+n*cs+40; ly=gy+16
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"#52514e\" font-weight=\"600\">weight</text>\n",lx,ly-10) > f2
  for(i=0;i<=20;i++){ vv=M*(1-i/10.0); printf("<rect x=\"%d\" y=\"%d\" width=\"22\" height=\"13\" fill=\"%s\"/>\n",lx,ly+i*13,divcolor(vv)) > f2 }
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"#52514e\">+%.2f</text>\n",lx+28,ly+8,M) > f2
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"#52514e\">0</text>\n",lx+28,ly+10*13+8) > f2
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"#52514e\">\xE2\x88\x92%.2f</text>\n",lx+28,ly+20*13+8,M) > f2
  printf("<text x=\"28\" y=\"%d\" font-size=\"12.5\" fill=\"#52514e\">Diagonal (s=t): input just written, weight c\xC2\xB7b, no decay yet. Fading up-left = older inputs, decayed by a longer chain of a's.</text>\n",CH-52) > f2
  printf("<text x=\"28\" y=\"%d\" font-size=\"12\" fill=\"#898781\">Illustrative fixed dataset; values computed exactly by awk and shared with the interactive companion.</text>\n",CH-30) > f2
  print "</svg>" > f2; close(f2)

  # ---------- FIG 4 ----------
  cs=42; gx=70; gy=150; gap=120; block=n*cs
  CW=gx+block+gap+block+90; CH=gy+block+120; f4="assets/figures/fig4_raw_vs_softmax.svg"
  header(f4,"Same grid, two rules: raw L vs. softmax attention","Left = Mamba's L (can be negative, rows sum to anything). Right = after causal softmax (all positive, every row sums to 1.00).")
  gx2=gx+block+gap
  printf("<text x=\"%d\" y=\"%d\" font-size=\"14\" font-weight=\"700\" fill=\"#0A2540\">Mamba's L (raw)</text>\n",gx,gy-40) > f4
  printf("<text x=\"%d\" y=\"%d\" font-size=\"14\" font-weight=\"700\" fill=\"#0A2540\">L after causal softmax</text>\n",gx2,gy-40) > f4
  # left grid (raw, diverging) + right grid (softmax, sequential)
  for(t=0;t<n;t++) for(s=0;s<n;s++){
    xL=gx+s*cs; xR=gx2+s*cs; y=gy+t*cs
    if(s<=t){ v=L[t,s]; tt=(v<0?-v:v)/M
      printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"%s\" stroke=\"#fcfcfb\" stroke-width=\"1.5\"/>\n",xL,y,cs,cs,divcolor(v)) > f4
      w=W[t,s]
      printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"%s\" stroke=\"#fcfcfb\" stroke-width=\"1.5\"/>\n",xR,y,cs,cs,seqcolor(w)) > f4
      printf("<text x=\"%d\" y=\"%d\" font-size=\"9\" fill=\"%s\" text-anchor=\"middle\">%.2f</text>\n",xR+cs/2,y+cs/2+3,(w>0.5?"#fff":"#0A2540"),w) > f4 }
    else { printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"#f7f6f3\" stroke=\"#fcfcfb\" stroke-width=\"1.5\"/>\n",xL,y,cs,cs) > f4
      printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"#f7f6f3\" stroke=\"#fcfcfb\" stroke-width=\"1.5\"/>\n",xR,y,cs,cs) > f4 } }
  # row-sum margins
  printf("<text x=\"%d\" y=\"%d\" font-size=\"10.5\" fill=\"#52514e\" text-anchor=\"middle\" font-weight=\"600\">row sum</text>\n",gx+block+34,gy-8) > f4
  printf("<text x=\"%d\" y=\"%d\" font-size=\"10.5\" fill=\"#52514e\" text-anchor=\"middle\" font-weight=\"600\">row sum</text>\n",gx2+block+34,gy-8) > f4
  for(t=0;t<n;t++){
    printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"#0A2540\" text-anchor=\"middle\">%.2f</text>\n",gx+block+34,gy+t*cs+cs/2+4,rowsumL[t]) > f4
    printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"#2a78d6\" text-anchor=\"middle\" font-weight=\"600\">1.00</text>\n",gx2+block+34,gy+t*cs+cs/2+4) > f4 }
  printf("<text x=\"28\" y=\"%d\" font-size=\"12.5\" fill=\"#52514e\">The row sums are the whole lesson: raw L's rows sum to anything (even negatives); softmax forces every row to 1.00. L is attention-SHAPED, not softmax attention.</text>\n",CH-30) > f4
  print "</svg>" > f4; close(f4)
  print "OK  max|L|=" M
}
