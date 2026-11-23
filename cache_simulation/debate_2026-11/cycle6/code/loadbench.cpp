// loadbench: time different ways of loading a big file into 2MB-aligned hugepage-backed anon memory
// usage: loadbench <file> <method> <threads> <chunk_mb>
// methods: pread | mmapcpy | mmapcpy_pop | pread_prepop | mmapcpy_prepop
#include <bits/stdc++.h>
#include <omp.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
using namespace std;
#ifndef MADV_POPULATE_WRITE
#define MADV_POPULATE_WRITE 23
#endif
#ifndef MADV_POPULATE_READ
#define MADV_POPULATE_READ 22
#endif
int main(int argc,char**argv){
  const char*file=argv[1]; string m=argv[2]; int nt=atoi(argv[3]); size_t CH=(size_t)atoll(argv[4])<<20;
  int fd=open(file,O_RDONLY); struct stat st; fstat(fd,&st); size_t sz=st.st_size;
  void*dst=nullptr; if(posix_memalign(&dst,2<<20,sz+(2<<20))) {puts("alloc fail");return 1;}
  madvise(dst,sz,MADV_HUGEPAGE);
  size_t nch=(sz+CH-1)/CH; double t0=omp_get_wtime(); double tpre=0;
  if(m=="pread_prepop"||m=="mmapcpy_prepop"){
    #pragma omp parallel for schedule(dynamic,1) num_threads(nt)
    for(size_t c=0;c<nch;c++){ size_t off=c*CH,len=min(CH,sz-off); madvise((char*)dst+off,len,MADV_POPULATE_WRITE); }
    tpre=omp_get_wtime()-t0; }
  double t1=omp_get_wtime();
  char*mp=nullptr;
  if(m.rfind("mmapcpy",0)==0){ mp=(char*)mmap(0,sz,PROT_READ,MAP_PRIVATE,fd,0); madvise(mp,sz,MADV_SEQUENTIAL); }
  #pragma omp parallel for schedule(dynamic,1) num_threads(nt)
  for(size_t c=0;c<nch;c++){
    size_t off=c*CH,len=min(CH,sz-off); char*d=(char*)dst+off;
    if(m.rfind("pread",0)==0){ size_t done=0; while(done<len){ ssize_t r=pread(fd,d+done,len-done,off+done); if(r<=0)break; done+=r; } }
    else { if(m=="mmapcpy_pop") madvise(mp+off,len,MADV_POPULATE_READ); memcpy(d,mp+off,len); }
  }
  double t2=omp_get_wtime();
  // checksum a few bytes to make sure data is there
  unsigned long long cs=0; for(size_t i=0;i<sz;i+=sz/1024+1) cs+=((unsigned char*)dst)[i];
  printf("RESULT method=%s threads=%d chunk=%zuMB prepop_s=%.2f copy_s=%.2f total_s=%.2f GBps=%.1f cs=%llu\n",m.c_str(),nt,CH>>20,tpre,t2-t1,t2-t0,sz/1e9/(t2-t0),cs);
  return 0; }
