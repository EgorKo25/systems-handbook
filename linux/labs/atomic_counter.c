#define _POSIX_C_SOURCE 200809L
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
static atomic_long counter=0;
static void *worker(void *arg) {
    (void)arg;
    for (int i=0;i<20000;i++) atomic_fetch_add_explicit(&counter,1,memory_order_relaxed);
    return NULL;
}
int main(void) {
    pthread_t a,b;
    if (pthread_create(&a,NULL,worker,NULL)) return 1;
    if (pthread_create(&b,NULL,worker,NULL)) {pthread_join(a,NULL);return 2;}
    if (pthread_join(a,NULL)||pthread_join(b,NULL)) return 3;
    printf("counter=%ld expected=40000\n",atomic_load(&counter));
    return atomic_load(&counter)==40000?0:4;
}
