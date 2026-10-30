#define _GNU_SOURCE
#include <sys/mman.h>
#include <sys/resource.h>
#include <unistd.h>
#include <stdio.h>
int main(void) {
    long page=sysconf(_SC_PAGESIZE);if(page<=0)return 1;
    size_t n=(size_t)page*16;
    volatile unsigned char *p=mmap(NULL,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if(p==MAP_FAILED)return 2;
    struct rusage a,b;if(getrusage(RUSAGE_SELF,&a))return 3;
    for(int i=0;i<16;i++)p[(size_t)i*(size_t)page]=(unsigned char)i;
    if(getrusage(RUSAGE_SELF,&b))return 4;
    printf("page_size=%ld pages=16 minor_fault_delta=%ld major_fault_delta=%ld\n",page,b.ru_minflt-a.ru_minflt,b.ru_majflt-a.ru_majflt);
    if(munmap((void *)p,n))return 5;
    return 0;
}
