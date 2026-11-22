// E1 offline analysis of a slot-index trace (uint64: idx | hit<<63)
#include <bits/stdc++.h>
using namespace std;
typedef uint64_t u64;
int main(int argc,char**argv){
  FILE*f=fopen(argv[1],"rb"); vector<u64> raw; u64 b[1<<16]; size_t k;
  while((k=fread(b,8,1<<16,f))>0) raw.insert(raw.end(),b,b+k);
  size_t n=raw.size(); vector<u64> key(n); size_t hits=0;
  for(size_t i=0;i<n;i++){ key[i]=raw[i]&~(1ULL<<63); hits+=raw[i]>>63; }
  printf("lookups %zu  hit_share %.4f\n",n,(double)hits/n);
  // unique keys, unique 64B lines (4B cells -> 16 per line)
  unordered_map<u64,uint32_t> cnt; cnt.reserve(n);
  for(auto x:key) cnt[x]++;
  unordered_set<u64> lines; for(auto x:key) lines.insert(x>>4);
  printf("unique slots %zu (%.4f of lookups)  unique 64B lines %zu (%.4f)\n",cnt.size(),(double)cnt.size()/n,lines.size(),(double)lines.size()/n);
  printf("global repeat rate %.4f\n",1.0-(double)cnt.size()/n);
  // coverage curve: top-K slots by frequency
  vector<uint32_t> fr; for(auto&p:cnt) fr.push_back(p.second); sort(fr.rbegin(),fr.rend());
  size_t Ks[]={1024,16384,65536,262144,1048576}; 
  for(size_t K:Ks){ if(K>fr.size()) K=fr.size(); u64 s=0; for(size_t i=0;i<K;i++) s+=fr[i]; printf("top-%zu slots cover %.4f of lookups\n",K,(double)s/n);}
  // exact stack distance via Fenwick tree
  vector<int> bit(n+2,0); auto upd=[&](size_t i,int v){for(i++;i<=n+1;i+=i&-i)bit[i]+=v;}; auto qry=[&](size_t i){int s=0;for(i++;i>0;i-=i&-i)s+=bit[i];return s;};
  unordered_map<u64,size_t> last; last.reserve(cnt.size()*2);
  vector<u64> hist(40,0); u64 cold=0; vector<uint32_t> sd(n,UINT32_MAX);
  for(size_t i=0;i<n;i++){
    auto it=last.find(key[i]);
    if(it==last.end()){cold++;}
    else{ size_t p=it->second; int d=qry(i)-qry(p); sd[i]=d; int bkt=d<=0?0:(int)floor(log2((double)d))+1; hist[min(bkt,39)]++; upd(p,-1);}    
    upd(i,1); last[key[i]]=i;
  }
  printf("cold(first-touch) %llu\nreuse-distance histogram (distinct slots between reuses), bucket 2^b:\n",(unsigned long long)cold);
  u64 rep=n-cold; u64 cum=0; for(int b2=0;b2<40;b2++) if(hist[b2]){cum+=hist[b2]; printf("  <2^%-2d : %9llu  (%.4f of repeats, cum %.4f)\n",b2,(unsigned long long)hist[b2],(double)hist[b2]/rep,(double)cum/rep);}
  // fully-assoc LRU hit rate at N entries == fraction with stack distance < N
  size_t Ns[]={4096,16384,65536,262144,1048576,4194304};
  printf("LRU fully-assoc hit rate (stack distance<N):\n");
  for(size_t N:Ns){ u64 h=0; for(size_t i=0;i<n;i++) if(sd[i]!=UINT32_MAX && sd[i]<N) h++; printf("  N=%-8zu %.4f\n",N,(double)h/n);}  
  // windowed dedup: fraction of lookups whose slot already appeared earlier in the same window
  size_t Ws[]={10000,100000,1000000,10000000};
  printf("windowed dedup (lookups removable inside non-overlapping windows):\n");
  for(size_t W:Ws){ u64 rem=0; unordered_set<u64> seen; for(size_t i=0;i<n;i++){ if(i%W==0) seen.clear(); if(!seen.insert(key[i]).second) rem++; } printf("  W=%-9zu %.4f\n",W,(double)rem/n);}  
  // Belady (OPT) fully associative
  vector<size_t> nxt(n); { unordered_map<u64,size_t> nu; nu.reserve(cnt.size()*2); for(size_t i=n;i-->0;){ auto it=nu.find(key[i]); nxt[i]= it==nu.end()? SIZE_MAX: it->second; nu[key[i]]=i; } }
  printf("Belady (OPT) fully-assoc hit rate:\n");
  for(size_t N:Ns){ set<pair<size_t,u64>> byNext; unordered_map<u64,size_t> inC; u64 h=0; inC.reserve(N*2);
    for(size_t i=0;i<n;i++){ auto it=inC.find(key[i]);
      if(it!=inC.end()){ h++; byNext.erase({it->second,key[i]}); byNext.insert({nxt[i],key[i]}); it->second=nxt[i]; }
      else{ if(nxt[i]==SIZE_MAX) continue; /* bypass never-reused */ if(inC.size()>=N){ auto v=prev(byNext.end()); if(v->first<=nxt[i]) continue; inC.erase(v->second); byNext.erase(v);} inC[key[i]]=nxt[i]; byNext.insert({nxt[i],key[i]}); } }
    printf("  N=%-8zu %.4f\n",N,(double)h/n); }
  // 4-way set-assoc LRU (sets=N/4, index = slot hash mix) for comparison
  printf("4-way set-assoc LRU hit rate (murmur-mixed set index):\n");
  for(size_t N:Ns){ size_t S=N/4; vector<array<u64,4>> sets(S); for(auto&s:sets) s.fill(~0ULL); u64 h=0;
    for(size_t i=0;i<n;i++){ u64 x=key[i]*0x9E3779B97F4A7C15ULL; x^=x>>29; size_t si=(x>>7)%S; auto&s=sets[si]; int w=-1; for(int j=0;j<4;j++) if(s[j]==key[i]){w=j;break;} if(w>=0){h++; for(int j=w;j>0;j--) s[j]=s[j-1]; s[0]=key[i];} else{ for(int j=3;j>0;j--) s[j]=s[j-1]; s[0]=key[i]; } }
    printf("  N=%-8zu %.4f\n",N,(double)h/n);}
}
