/* Bounded, UART controlled Wi-Fi experiments. No credentials persisted. */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <inttypes.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/socket.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "driver/uart.h"
#include "lwip/inet.h"

static volatile bool active=false, is_ap=false, connected=false;
static volatile int64_t load_until=0;
static volatile int load_mbps=0;
static volatile uint64_t tx_bytes=0, rx_bytes=0, echoes=0;
static volatile bool tcp_connected=false;
static volatile uint32_t network_generation=0;
static volatile int tx_socket=-1,rx_socket=-1;
static volatile bool tcp_peer_ready=false;
static volatile uint32_t tcp_nonce=0,tcp_challenge=0;
static volatile uint64_t send_attempts=0,send_eagain=0,handshake_failures=0;
static volatile int last_send_errno=0;
static volatile int udp_rate=0,udp_id=0;
static volatile int64_t udp_until=0,udp_seen=0;
static volatile uint64_t udp_bytes=0,udp_packets=0;
static struct sockaddr_in udp_peer;
static char target[32]="192.168.4.1";
static esp_netif_t *sta_if, *ap_if;

static void events(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (base==WIFI_EVENT && id==WIFI_EVENT_STA_START && active && !is_ap) esp_wifi_connect();
    if (base==WIFI_EVENT && id==WIFI_EVENT_STA_DISCONNECTED) {
        connected=false;
        if(active && !is_ap) esp_wifi_connect();
    }
    if(base==IP_EVENT && id==IP_EVENT_STA_GOT_IP) {
        connected=true;
        ip_event_got_ip_t *e=data;
        printf("IP " IPSTR "\n", IP2STR(&e->ip_info.ip));fflush(stdout);
    }
}

static void status(void) {
    uint8_t ch=0; wifi_second_chan_t second=0; int8_t power=0;
    wifi_bandwidth_t bw=0; wifi_ap_record_t ap={0};
    esp_wifi_get_channel(&ch,&second);esp_wifi_get_max_tx_power(&power);
    esp_wifi_get_bandwidth(is_ap?WIFI_IF_AP:WIFI_IF_STA,&bw);
    esp_wifi_sta_get_ap_info(&ap);wifi_sta_list_t clients={0};esp_wifi_ap_get_sta_list(&clients);
    wifi_ps_type_t ps=WIFI_PS_NONE;esp_wifi_get_ps(&ps);
    int64_t remaining=(load_until-esp_timer_get_time())/1000;if(remaining<0)remaining=0;
    printf("STATE {\"version\":7,\"udp_ready\":%d,\"udp_tx_bytes\":%"PRIu64",\"udp_tx_packets\":%"PRIu64",\"udp_run_id\":%d,\"tcp_connected\":%d,\"active\":%d,\"ap\":%d,\"connected\":%d,\"ap_clients\":%d,\"primary\":%u,\"secondary\":%d,\"configured_bw\":%d,\"ap_bw\":%d,\"rssi\":%d,\"tx_qdbm\":%d,\"tx_bytes\":%"PRIu64",\"rx_bytes\":%"PRIu64",\"echoes\":%"PRIu64",\"tcp_peer_ready\":%d,\"tcp_nonce\":%"PRIu32",\"tcp_challenge\":%"PRIu32",\"send_attempts\":%"PRIu64",\"send_eagain\":%"PRIu64",\"handshake_failures\":%"PRIu64",\"last_send_errno\":%d,\"load_rate_setting\":%d,\"load_remaining_ms\":%"PRId64",\"power_save\":%d,\"network_generation\":%"PRIu32"}\n",udp_seen>0 && esp_timer_get_time()-udp_seen<5000000,udp_bytes,udp_packets,udp_id,tcp_connected,active,is_ap,connected,clients.num,ch,second,bw,ap.bandwidth,ap.rssi,power,tx_bytes,rx_bytes,echoes,tcp_peer_ready,tcp_nonce,tcp_challenge,send_attempts,send_eagain,handshake_failures,last_send_errno,load_mbps,remaining,ps,network_generation);
    fflush(stdout);
}

static void echo_task(void *arg) {
    int s=socket(AF_INET,SOCK_DGRAM,0); struct sockaddr_in addr={.sin_family=AF_INET,.sin_port=htons(5140),.sin_addr.s_addr=INADDR_ANY};
    bind(s,(struct sockaddr*)&addr,sizeof(addr)); char b[1600];
    for(;;) {
        struct sockaddr_in peer; socklen_t n=sizeof(peer);
        int r=recvfrom(s,b,sizeof(b),0,(struct sockaddr*)&peer,&n);
        if(r>0){sendto(s,b,r,0,(struct sockaddr*)&peer,n);echoes++;}
    }
}

static bool transfer_exact(int s,void *buffer,size_t size,bool writing,uint32_t generation) {
    size_t used=0;int64_t deadline=esp_timer_get_time()+2000000;
    while(used<size && active && generation==network_generation && esp_timer_get_time()<deadline) {
        int n=writing?send(s,(char*)buffer+used,size-used,0):recv(s,(char*)buffer+used,size-used,0);
        if(n>0)used+=n;
        else if(n==0 || (errno!=EAGAIN && errno!=EWOULDBLOCK))return false;
        else vTaskDelay(1);
    }
    return used==size && active && generation==network_generation;
}

static void tx_task(void *arg) {
    int server=socket(AF_INET,SOCK_STREAM,0), one=1;
    setsockopt(server,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one));
    struct sockaddr_in a={.sin_family=AF_INET,.sin_port=htons(5002),.sin_addr.s_addr=INADDR_ANY};
    bind(server,(struct sockaddr*)&a,sizeof(a));listen(server,2);
    static char b[4096];for(int i=0;i<sizeof(b);i++)b[i]=(i*97+11)&255;
    for(;;) {
        int s=accept(server,NULL,NULL); if(s<0){vTaskDelay(100);continue;}
        uint32_t generation=network_generation;tx_socket=s;
        int keep=1,idle=2,interval=1,count=3;
        setsockopt(s,SOL_SOCKET,SO_KEEPALIVE,&keep,sizeof(keep));
        setsockopt(s,IPPROTO_TCP,TCP_KEEPIDLE,&idle,sizeof(idle));
        setsockopt(s,IPPROTO_TCP,TCP_KEEPINTVL,&interval,sizeof(interval));
        setsockopt(s,IPPROTO_TCP,TCP_KEEPCNT,&count,sizeof(count));
        struct timeval tv={.tv_sec=1};setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof(tv));
        struct timeval receive_tv={.tv_usec=200000};setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&receive_tv,sizeof(receive_tv));
        uint32_t hello[2],ack[3],confirm[2];
        uint32_t challenge=esp_random();if(!challenge)challenge=1;
        bool verified=transfer_exact(s,hello,sizeof(hello),false,generation) && ntohl(hello[0])==0x43354837 && ntohl(hello[1])!=0;
        if(verified) {
            ack[0]=htonl(0x43354137);ack[1]=hello[1];ack[2]=htonl(challenge);
            verified=transfer_exact(s,ack,sizeof(ack),true,generation) && transfer_exact(s,confirm,sizeof(confirm),false,generation) && ntohl(confirm[0])==0x43354337 && ntohl(confirm[1])==challenge;
        }
        if(!verified){handshake_failures++;tx_socket=-1;close(s);continue;}
        tcp_nonce=ntohl(hello[1]);tcp_challenge=challenge;tcp_peer_ready=true;
        tcp_connected=true;uint64_t session=0;int64_t start=esp_timer_get_time();
        while(active && is_ap && generation==network_generation) {
            int64_t now=esp_timer_get_time();
            char pending;int peek=recv(s,&pending,1,MSG_PEEK|MSG_DONTWAIT);
            if(peek==0 || (peek<0 && errno!=EAGAIN && errno!=EWOULDBLOCK))break;
            int rate=load_mbps; /* UART may change the shared rate during send(). */
            if(now>=load_until || rate<=0){start=now;session=0;vTaskDelay(10);continue;}
            send_attempts++;int n=send(s,b,sizeof(b),0);last_send_errno=n<0?errno:0;
            if(n<0 && (errno==EAGAIN || errno==EWOULDBLOCK)){send_eagain++;vTaskDelay(1);continue;}
            if(n<=0)break;
            tx_bytes+=n;session+=n;
            if(rate<1000) {
                int64_t due=start+(int64_t)(session*8/rate);
                int64_t wait=due-esp_timer_get_time();
                if(wait>1000)vTaskDelay(pdMS_TO_TICKS(wait/1000));
            }
        }
        tcp_connected=false;tcp_peer_ready=false;tcp_nonce=0;tcp_challenge=0;tx_socket=-1;close(s);
    }
}

static void rx_task(void *arg) {
    static char b[8192];
    for(;;) {
        if(!active || is_ap || !connected || !strcmp(target,"OFF")){vTaskDelay(100);continue;}
        int s=socket(AF_INET,SOCK_STREAM,0);
        uint32_t generation=network_generation;rx_socket=s;
        int keep=1,idle=2,interval=1,count=3;
        setsockopt(s,SOL_SOCKET,SO_KEEPALIVE,&keep,sizeof(keep));
        setsockopt(s,IPPROTO_TCP,TCP_KEEPIDLE,&idle,sizeof(idle));
        setsockopt(s,IPPROTO_TCP,TCP_KEEPINTVL,&interval,sizeof(interval));
        setsockopt(s,IPPROTO_TCP,TCP_KEEPCNT,&count,sizeof(count));
        struct sockaddr_in a={.sin_family=AF_INET,.sin_port=htons(5002)};inet_pton(AF_INET,target,&a.sin_addr);
        struct timeval tv={.tv_sec=2};setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof(tv));
        if(connect(s,(struct sockaddr*)&a,sizeof(a))==0) {
            uint32_t nonce=esp_random();if(!nonce)nonce=1;
            uint32_t hello[2]={htonl(0x43354837),htonl(nonce)},ack[3],confirm[2];
            bool verified=transfer_exact(s,hello,sizeof(hello),true,generation) && transfer_exact(s,ack,sizeof(ack),false,generation) && ntohl(ack[0])==0x43354137 && ntohl(ack[1])==nonce && ntohl(ack[2])!=0;
            if(verified){confirm[0]=htonl(0x43354337);confirm[1]=ack[2];verified=transfer_exact(s,confirm,sizeof(confirm),true,generation);}
            if(!verified){handshake_failures++;rx_socket=-1;close(s);vTaskDelay(250);continue;}
            tcp_peer_ready=true;tcp_nonce=nonce;tcp_challenge=ntohl(ack[2]);
            while(active && !is_ap && connected && generation==network_generation) {
                int n=recv(s,b,sizeof(b),0);
                if(n>0)rx_bytes+=n;
                else if(n==0 || (errno!=EAGAIN && errno!=EWOULDBLOCK))break;
            }
        }
        tcp_peer_ready=false;tcp_nonce=0;tcp_challenge=0;rx_socket=-1;close(s);vTaskDelay(250);
    }
}

static void udp_ready_task(void *arg) {
    int s=socket(AF_INET,SOCK_DGRAM,0);char b[32];
    struct sockaddr_in a={.sin_family=AF_INET,.sin_port=htons(5003),.sin_addr.s_addr=INADDR_ANY};bind(s,(struct sockaddr*)&a,sizeof(a));
    for(;;){struct sockaddr_in peer;socklen_t n=sizeof(peer);int k=recvfrom(s,b,sizeof(b),0,(struct sockaddr*)&peer,&n);if(k==7 && !memcmp(b,"C5READY",7) && active && is_ap){udp_peer=peer;udp_seen=esp_timer_get_time();}}
}
static void udp_tx_task(void *arg) {
    int s=socket(AF_INET,SOCK_DGRAM,0);static uint32_t b[350];
    for(int i=0;i<350;i++)b[i]=0x12345678+i;
    int previous=-1;uint32_t seq=0;uint64_t session=0;int64_t start=0;
    for(;;) {
        int rate=udp_rate,id=udp_id;int64_t now=esp_timer_get_time();
        if(!active || !is_ap || rate<=0 || now>=udp_until || !udp_seen || now-udp_seen>5000000){vTaskDelay(10);continue;}
        if(previous!=id){previous=id;seq=0;session=0;start=now;}
        b[0]=htonl(0x43355246);b[1]=htonl(id);b[2]=htonl(seq);b[3]=htonl((uint32_t)now);
        int n=sendto(s,b,sizeof(b),0,(struct sockaddr*)&udp_peer,sizeof(udp_peer));
        if(n>0){udp_bytes+=n;udp_packets++;session+=n;seq++;}else{vTaskDelay(1);continue;}
        int64_t due=start+(int64_t)(session*8/rate);
        if(due>esp_timer_get_time())vTaskDelay(1);
    }
}

static void command(char *line) {
    char op[16]={0}, ssid[33]={0}, pass[65]={0}; int ch=6,bw=20,power=76,seconds=0,rate=0;
    sscanf(line,"%15s",op);
    if(!strcmp(op,"STOP")){active=false;connected=false;load_until=0;network_generation++;if(tx_socket>=0)shutdown(tx_socket,SHUT_RDWR);if(rx_socket>=0)shutdown(rx_socket,SHUT_RDWR);esp_wifi_stop();puts("OK STOP");}
    else if(!strcmp(op,"STATUS"))status();
    else if(!strcmp(op,"LOAD")) {
        sscanf(line,"%*s %d %d",&rate,&seconds);load_mbps=rate;
        load_until=esp_timer_get_time()+(int64_t)seconds*1000000;
        printf("OK LOAD %d %d\n",rate,seconds);
    } else if(!strcmp(op,"UDPLOAD")) {
        int id=0;sscanf(line,"%*s %d %d %d",&rate,&seconds,&id);udp_id=id;udp_rate=rate;
        udp_until=esp_timer_get_time()+(int64_t)seconds*1000000;printf("OK UDPLOAD %d %d %d\n",rate,seconds,id);
    } else if(!strcmp(op,"PS")) {
        sscanf(line,"%*s %d",&rate);esp_wifi_set_ps(rate?WIFI_PS_MIN_MODEM:WIFI_PS_NONE);printf("OK PS %d\n",rate);
    } else if(!strcmp(op,"AP") || !strcmp(op,"STA")) {
        active=false;connected=false;load_until=0;udp_until=0;udp_seen=0;tcp_connected=false;network_generation++;if(tx_socket>=0)shutdown(tx_socket,SHUT_RDWR);if(rx_socket>=0)shutdown(rx_socket,SHUT_RDWR);esp_wifi_stop();vTaskDelay(150);
        is_ap=!strcmp(op,"AP");
        wifi_config_t conf={0};
        if(is_ap) {
            sscanf(line,"%*s %d %d %d",&ch,&bw,&power);
            strcpy((char*)conf.ap.ssid,"ESP-SDR-INTERFERER");strcpy((char*)conf.ap.password,"SdrLab2026TestOnly");
            conf.ap.ssid_len=strlen((char*)conf.ap.ssid);conf.ap.channel=ch;conf.ap.max_connection=2;
            conf.ap.authmode=WIFI_AUTH_WPA2_PSK;conf.ap.beacon_interval=100;
            ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP,&conf));
            ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_AP,bw==40?WIFI_BW40:WIFI_BW20));
        } else {
            sscanf(line,"%*s %32s %64s %31s %d",ssid,pass,target,&bw);
            strcpy((char*)conf.sta.ssid,ssid);strcpy((char*)conf.sta.password,pass);
            ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA,&conf));
            ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA,bw==40?WIFI_BW40:WIFI_BW20));
        }
        active=true;ESP_ERROR_CHECK(esp_wifi_start());esp_wifi_set_ps(WIFI_PS_NONE);
        if(is_ap)esp_wifi_set_max_tx_power(power);
        printf("OK %s\n",op);
    } else puts("ERR COMMAND");
    fflush(stdout);
}

void app_main(void) {
    esp_log_level_set("*",ESP_LOG_WARN);setvbuf(stdout,NULL,_IONBF,0);
    esp_err_t e=nvs_flash_init();if(e==ESP_ERR_NVS_NO_FREE_PAGES || e==ESP_ERR_NVS_NEW_VERSION_FOUND){nvs_flash_erase();e=nvs_flash_init();}ESP_ERROR_CHECK(e);
    ESP_ERROR_CHECK(esp_netif_init());ESP_ERROR_CHECK(esp_event_loop_create_default());
    sta_if=esp_netif_create_default_wifi_sta();ap_if=esp_netif_create_default_wifi_ap();
    wifi_init_config_t init=WIFI_INIT_CONFIG_DEFAULT();ESP_ERROR_CHECK(esp_wifi_init(&init));
    esp_wifi_set_storage(WIFI_STORAGE_RAM);
    wifi_country_t country={.cc="JP",.schan=1,.nchan=13,.policy=WIFI_COUNTRY_POLICY_MANUAL};esp_wifi_set_country(&country);
    esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,events,NULL);esp_event_handler_register(IP_EVENT,IP_EVENT_STA_GOT_IP,events,NULL);
    xTaskCreate(echo_task,"udp_echo",4096,NULL,8,NULL);xTaskCreate(tx_task,"tcp_tx",4096,NULL,4,NULL);xTaskCreate(rx_task,"tcp_rx",4096,NULL,4,NULL);
    xTaskCreate(udp_ready_task,"udp_ready",4096,NULL,4,NULL);xTaskCreate(udp_tx_task,"udp_tx",4096,NULL,4,NULL);
    uart_config_t u={.baud_rate=115200,.data_bits=UART_DATA_8_BITS,.parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,.flow_ctrl=UART_HW_FLOWCTRL_DISABLE,.source_clk=UART_SCLK_DEFAULT};
    uart_param_config(UART_NUM_0,&u);uart_driver_install(UART_NUM_0,2048,0,0,NULL,0);
    printf("READY OPERATIONAL_WIFI v7\n");
    char line[192];int n=0;
    for(;;) {uint8_t c;if(uart_read_bytes(UART_NUM_0,&c,1,pdMS_TO_TICKS(100))==1){if(c=='\n'||c=='\r'){if(n){line[n]=0;command(line);n=0;}}else if(n<sizeof(line)-1)line[n++]=c;}}
}
