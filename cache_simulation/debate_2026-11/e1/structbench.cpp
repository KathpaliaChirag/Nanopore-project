// E3 structbench: linear probing vs double hashing (kraken2's real second_hash) vs line-aligned linear,
// 4-byte cells, load 0.70, S16-style batched prefetch.
// usage: structbench <log2cap> <threads,comma> <miss_fracs,comma> <nq_per_thread>
#include <bits/stdc++.h>
#include <omp.h>
#include <sys/mman.h>
using namespace std; typedef uint64_t u64; typedef uint32_t u32;
static inline u64 mix(u64 x){ x+=0x9E3779B97F4A7C15ULL; x=(x^(x>>30))*0xBF58476D1CE4E5B9ULL; x=(x^(x>>27))*0x94D049BB133111EBULL; return x^(x>>31); }
static u64 CAP; static u32* T; static u64 failed_ins=0;
enum Scheme{LIN=0,DBL=1,ALN=2};
static inline u64 rng(u64 h,u64 n){ return (u64)(((unsigned __int128)h*n)>>64); }
static inline u64 start(Scheme s,u64 h){ return s==ALN ? rng(h,CAP/16)*16 : rng(h,CAP); }
static inline u64 stepf(Scheme s,u64 h){ return s==DBL ? ((h>>8)|1) : 1; }
static inline u32 fp(u64 h){ return (u32)(h)|1u; }  // low bits: independent of start index (top bits)
static void insert(Scheme s,u64 h){ u64 i0=start(s,h), i=i0, st=stepf(s,h); u32 f=fp(h);
  for(;;){ if(__sync_bool_compare_and_swap(&T[i],0u,f)) return; i+=st; if(i>=CAP) i%=CAP; if(i==i0){ __sync_fetch_and_add(&failed_ins,1); return; } } }
template<bool COUNT> static inline bool look(Scheme s,u64 h,u64 i0,int*lines){ u64 i=i0, st=stepf(s,h); u32 f=fp(h); u64 pl=~0ULL; int ln=0;
  for(;;){ if(COUNT && (i>>4)!=pl){ln++; pl=i>>4;} u32 c=T[i]; if(c==0){ if(COUNT)*lines=ln; return false;} if(c==f){ if(COUNT)*lines=ln; return true;} i+=st; if(i>=CAP) i%=CAP; if(i==i0){ if(COUNT)*lines=ln; return false;} } }
static vector<double> parse(const char*s){ vector<double> v; stringstream ss(s); string t; while(getline(ss,t,',')) v.push_back(atof(t.c_str())); return v; }
int main(int argc,char**argv){
  int lg=atoi(argv[1]); auto nts=parse(argv[2]); auto mfs=parse(argv[3]); u64 nq=strtoull(argv[4],0,10);
  CAP=(1ULL<<lg)-1;
  size_t bytes=(CAP+64)*4; T=(u32*)mmap(0,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0); madvise(T,bytes,MADV_HUGEPAGE);
  u64 M=(u64)(0.70*CAP); const char* nm[]={"linear","double","aligned"};
  printf("CAP=%llu gcd(CAP,3)=%d M=%llu\n",(unsigned long long)CAP,(int)(CAP%3==0?3:1),(unsigned long long)M);
  for(int si=0;si<3;si++){ Scheme s=(Scheme)si;
    double t0=omp_get_wtime();
    #pragma omp parallel for num_threads(32) schedule(static)
    for(u64 i=0;i<CAP;i++) T[i]=0;
    failed_ins=0;
    #pragma omp parallel for num_threads(32) schedule(static)
    for(u64 i=0;i<M;i++) insert(s,mix(i));
    double tb=omp_get_wtime()-t0; u64 fi=failed_ins;
    double lh=0,lm=0; { int l; u64 N=2000000; for(u64 q=0;q<N;q++){ u64 h=mix(mix(q+77)%M); look<true>(s,h,start(s,h),&l); lh+=l; } for(u64 q=0;q<N;q++){ u64 h=mix(M+mix(q+99)%M); look<true>(s,h,start(s,h),&l); lm+=l; } lh/=N; lm/=N; }
    printf("BUILD cap=2^%d scheme=%s build_s=%.1f failed_inserts=%llu (%.4f%% of keys) lines_hit=%.3f lines_miss=%.3f\n",lg,nm[si],tb,(unsigned long long)fi,100.0*fi/M,lh,lm); fflush(stdout);
    for(double ntd:nts) for(double mf:mfs) for(int pf2=0; pf2<(s==DBL?2:1); pf2++){ int nt=(int)ntd;
      double best=1e30; u64 found=0;
      for(int rep=0;rep<3;rep++){ found=0; double t1=omp_get_wtime();
        #pragma omp parallel num_threads(nt) reduction(+:found)
        { int tid=omp_get_thread_num(); u64 st8=mix(tid+12345+rep*1000); const int B=16; u64 hq[2][B], iq[2][B];
          auto fill=[&](int b){ for(int k=0;k<B;k++){ st8=mix(st8); u64 r=st8; bool miss=((r>>40)&0xFFFFFF)<(u64)(mf*16777216.0); u64 key=(r%M)+(miss?M:0); u64 h=mix(key); hq[b][k]=h; iq[b][k]=start(s,h); __builtin_prefetch(&T[iq[b][k]]); if(pf2) __builtin_prefetch(&T[(iq[b][k]+stepf(s,h))%CAP]); } };
          fill(0); int cur=0; for(u64 n=0;n<nq;n+=B){ fill(cur^1); for(int k=0;k<B;k++) found+=look<false>(s,hq[cur][k],iq[cur][k],0); cur^=1; } }
        best=min(best,omp_get_wtime()-t1); }
      printf("RESULT cap=2^%d T=%d miss=%.2f scheme=%s%s ns_per_lookup_per_thread=%.1f agg_Mlookups_s=%.1f found_frac=%.3f (best of 3)\n",lg,nt,mf,nm[si],pf2?"+pf2":"",best*1e9/nq,(double)nt*nq/best/1e6,(double)found/((double)nt*nq)); fflush(stdout);
    } }
}
