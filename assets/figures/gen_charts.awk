function log10(x){ return log(x)/log(10) }
function card(f,w,h,title,subt){
  printf("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 %d %d\" font-family=\"system-ui,-apple-system,Segoe UI,sans-serif\">\n",w,h) > f
  printf("<rect x=\"0\" y=\"0\" width=\"%d\" height=\"%d\" rx=\"14\" fill=\"#fcfcfb\" stroke=\"#e1e0d9\"/>\n",w,h) > f
  printf("<text x=\"28\" y=\"38\" font-size=\"20\" font-weight=\"700\" fill=\"#0b0b0b\">%s</text>\n",title) > f
  printf("<text x=\"28\" y=\"62\" font-size=\"13\" fill=\"#52514e\">%s</text>\n",subt) > f
}
BEGIN{
  BLUE="#2a78d6"; ORANGE="#eb6834"; INK="#0A2540"; MUT="#898781"; GRID="#e8e7e0"; RED="#d03b3b"
  L2=log(2)

  # ===== FIG 1: work vs depth =====
  f="assets/figures/fig1_work_vs_depth.svg"; W=760; H=430
  card(f,W,H,"The paradox: fewer operations can still lose","A chip runs DEPTH (steps that must wait), not total work.")
  pah=250; pay=100
  ax=70; aw=280
  printf("<text x=\"%d\" y=\"%d\" font-size=\"13\" font-weight=\"700\" fill=\"%s\">Total arithmetic (log scale)</text>\n",ax,pay-14,INK) > f
  printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"none\" stroke=\"%s\"/>\n",ax,pay,aw,pah,GRID) > f
  ymaxA=7
  for(g=0;g<=6;g+=2){ yy=pay+pah*(1-g/ymaxA); printf("<line x1=\"%d\" y1=\"%.1f\" x2=\"%d\" y2=\"%.1f\" stroke=\"%s\"/>\n",ax,yy,ax+aw,yy,GRID) > f
    printf("<text x=\"%d\" y=\"%.1f\" font-size=\"10\" fill=\"%s\" text-anchor=\"end\">10^%d</text>\n",ax-6,yy+3,MUT,g) > f }
  N=11; sR=""; sA=""
  for(i=0;i<=N;i++){ x=ax+aw*(i/N)
    yR=pay+pah*(1-(i*log10(2))/ymaxA); yA=pay+pah*(1-(2*i*log10(2))/ymaxA)
    sR=sR sprintf("%s%.1f,%.1f",(i==0?"M":"L"),x,yR); sA=sA sprintf("%s%.1f,%.1f",(i==0?"M":"L"),x,yA) }
  printf("<path d=\"%s\" fill=\"none\" stroke=\"%s\" stroke-width=\"3\"/>\n",sA,ORANGE) > f
  printf("<path d=\"%s\" fill=\"none\" stroke=\"%s\" stroke-width=\"3\"/>\n",sR,BLUE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\" font-weight=\"700\">attention  T\xC2\xB2</text>\n",ax+aw-96,pay+18,ORANGE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\" font-weight=\"700\">RNN  T</text>\n",ax+aw-70,pay+pah-40,BLUE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"%s\" text-anchor=\"middle\">sequence length T (1 to 2048)</text>\n",ax+aw/2,pay+pah+22,MUT) > f
  bx=460; bw=280
  printf("<text x=\"%d\" y=\"%d\" font-size=\"13\" font-weight=\"700\" fill=\"%s\">Steps that must happen in order</text>\n",bx,pay-14,INK) > f
  printf("<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"none\" stroke=\"%s\"/>\n",bx,pay,bw,pah,GRID) > f
  printf("<line x1=\"%d\" y1=\"%d\" x2=\"%d\" y2=\"%d\" stroke=\"%s\" stroke-width=\"3\"/>\n",bx,pay+pah,bx+bw,pay,BLUE) > f
  printf("<line x1=\"%d\" y1=\"%.1f\" x2=\"%d\" y2=\"%.1f\" stroke=\"%s\" stroke-width=\"3\"/>\n",bx,pay+pah-2,bx+bw,pay+pah-2,ORANGE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\" font-weight=\"700\">RNN depth = T</text>\n",bx+40,pay+30,BLUE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"12\" fill=\"%s\" font-weight=\"700\">attention depth = 1 (flat)</text>\n",bx+70,pay+pah-10,ORANGE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"%s\" text-anchor=\"middle\">sequence length T</text>\n",bx+bw/2,pay+pah+22,MUT) > f
  printf("<text x=\"28\" y=\"%d\" font-size=\"12.5\" fill=\"#52514e\">Left: the RNN does LESS total arithmetic. Right: but every step waits for the last, so its depth grows with T while attention's stays 1.</text>\n",H-38) > f
  printf("<text x=\"28\" y=\"%d\" font-size=\"12.5\" fill=\"%s\" font-weight=\"600\">On a chip full of parallel workers, flat depth wins \xE2\x80\x94 even while doing far more arithmetic.</text>\n",H-18,INK) > f
  print "</svg>" > f; close(f)

  # ===== FIG 3: cumulative product underflow cliff =====
  f="assets/figures/fig3_underflow.svg"; W=760; H=420
  card(f,W,H,"The odometer P_t dives toward zero, then off a cliff","P_t = 0.8^t is a product of numbers below 1. Past the float floor the machine rounds it to exactly 0, and b*x/P explodes.")
  px=80; py=100; pw=620; ph=250; tmax=420
  ymin=-45; ymax=1
  for(g=0;g>=-40;g-=10){ yy=py+ph*(1-(g-ymin)/(ymax-ymin)); printf("<line x1=\"%d\" y1=\"%.1f\" x2=\"%d\" y2=\"%.1f\" stroke=\"%s\"/>\n",px,yy,px+pw,yy,GRID) > f
    printf("<text x=\"%d\" y=\"%.1f\" font-size=\"10\" fill=\"%s\" text-anchor=\"end\">10^%d</text>\n",px-6,yy+3,MUT,g) > f }
  s=""; for(t=0;t<=tmax;t+=4){ lp=t*log10(0.8); if(lp<ymin)lp=ymin; x=px+pw*(t/tmax); y=py+ph*(1-(lp-ymin)/(ymax-ymin)); s=s sprintf("%s%.1f,%.1f",(t==0?"M":"L"),x,y) }
  printf("<path d=\"%s\" fill=\"none\" stroke=\"%s\" stroke-width=\"3\"/>\n",s,BLUE) > f
  ff=-37.93; yff=py+ph*(1-(ff-ymin)/(ymax-ymin))
  printf("<line x1=\"%d\" y1=\"%.1f\" x2=\"%d\" y2=\"%.1f\" stroke=\"%s\" stroke-width=\"2\" stroke-dasharray=\"6 4\"/>\n",px,yff,px+pw,yff,RED) > f
  printf("<text x=\"%d\" y=\"%.1f\" font-size=\"11\" fill=\"%s\" font-weight=\"600\">float32 underflow floor (1.18e-38)</text>\n",px+8,yff-6,RED) > f
  tstar=391; xstar=px+pw*(tstar/tmax)
  printf("<line x1=\"%.1f\" y1=\"%d\" x2=\"%.1f\" y2=\"%d\" stroke=\"%s\" stroke-width=\"1.5\" stroke-dasharray=\"3 3\"/>\n",xstar,py,xstar,py+ph,RED) > f
  printf("<text x=\"%.1f\" y=\"%d\" font-size=\"11\" fill=\"%s\" text-anchor=\"middle\">t=391: P is 0 in the machine</text>\n",xstar-4,py+ph+34,RED) > f
  for(cb=64;cb<tmax;cb+=64){ xc=px+pw*(cb/tmax); printf("<line x1=\"%.1f\" y1=\"%d\" x2=\"%.1f\" y2=\"%d\" stroke=\"%s\" stroke-width=\"1\"/>\n",xc,py+ph-8,xc,py+ph,MUT) > f }
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"%s\">ticks = chunk boundaries (every 64): resetting P here keeps it far above the cliff</text>\n",px+60,py+ph+16,MUT) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"%s\" text-anchor=\"middle\">step t</text>\n",px+pw/2,py+ph+52,MUT) > f
  printf("<text x=\"28\" y=\"%d\" font-size=\"12.5\" fill=\"#52514e\">The real fix isn't chunking, it's working in log-space (add log a's, subtract) so you never divide tiny numbers. Chunking is extra safety.</text>\n",H-20) > f
  print "</svg>" > f; close(f)

  # ===== FIG 9: compute vs bandwidth gap =====
  f="assets/figures/fig9_compute_bandwidth.svg"; W=760; H=320
  card(f,W,H,"Why a chip is almost never limited by 'how much math'","On Luna's L40S: it does far more arithmetic per second than it can fetch bytes per second. That gap decides everything.")
  bx=70; by=120; bw=650; bh=44
  lo=11.4; hi=14.7
  v1=362e12; v2=0.864e12
  fr1=(log10(v1)-lo)/(hi-lo); fr2=(log10(v2)-lo)/(hi-lo)
  printf("<text x=\"%d\" y=\"%d\" font-size=\"13\" fill=\"%s\" font-weight=\"600\">math the cores can do</text>\n",bx,by-8,INK) > f
  printf("<rect x=\"%d\" y=\"%d\" width=\"%.1f\" height=\"%d\" rx=\"5\" fill=\"%s\"/>\n",bx,by,bw*fr1,bh,ORANGE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"13\" fill=\"#ffffff\" font-weight=\"700\">= 362 trillion FLOPs / sec</text>\n",bx+10,by+27) > f
  by2=by+90
  printf("<text x=\"%d\" y=\"%d\" font-size=\"13\" fill=\"%s\" font-weight=\"600\">bytes it can fetch from memory</text>\n",bx,by2-8,INK) > f
  printf("<rect x=\"%d\" y=\"%d\" width=\"%.1f\" height=\"%d\" rx=\"5\" fill=\"%s\"/>\n",bx,by2,bw*fr2,bh,BLUE) > f
  printf("<text x=\"%.1f\" y=\"%d\" font-size=\"13\" fill=\"%s\" font-weight=\"700\">= 0.86 trillion bytes / sec</text>\n",bx+bw*fr2+10,by2+27,BLUE) > f
  printf("<text x=\"%d\" y=\"%d\" font-size=\"15\" fill=\"%s\" font-weight=\"700\" text-anchor=\"middle\">about 400 FLOPs for every single byte it fetches</text>\n",bx+bw/2,by2+95,INK) > f
  printf("<text x=\"28\" y=\"%d\" font-size=\"12.5\" fill=\"#52514e\">So the winner is whoever keeps the cores FED (high arithmetic intensity), not whoever does the least math. Log scale; L40S FP16 tensor + bandwidth.</text>\n",H-18) > f
  print "</svg>" > f; close(f)
  print "charts OK"
}
