BEGIN{FS=","}
NR>1 && $13==0 {t[$1","$3]=$8; h1[$1","$3]=$10; h2[$1","$3]=$11; n[$1]=1}
END{
 printf "%-13s %12s %12s %12s | %8s %8s %8s | %7s\n","variant","t10_us","t25_us","t50_us","d10%","d25%","d50%","L1hit50";
 for(v in n){ printf "%-13s %12.3f %12.3f %12.3f | %+8.3f %+8.3f %+8.3f | %7s\n", v,t[v",10"]/1e9,t[v",25"]/1e9,t[v",50"]/1e9,(t[v",10"]/t["base,10"]-1)*100,(t[v",25"]/t["base,25"]-1)*100,(t[v",50"]/t["base,50"]-1)*100,h1[v",50"] }
 print ""; 
 for(v in n){ if(v=="base"||v ~ /^pf_/){ printf "%-13s saved-vs-base (us): 10r=%.3f 25r=%.3f 50r=%.3f\n", v,(t["base,10"]-t[v",10"])/1e9,(t["base,25"]-t[v",25"])/1e9,(t["base,50"]-t[v",50"])/1e9 } }
}
