/* UDP control probe + TCP bulk receiver, both forwarded by the experiment AP. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <errno.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_rom_crc.h"
#include "driver/uart.h"
#include "lwip/sockets.h"
#include "lwip/inet.h"
#define COUNT 3000
static uint32_t rows[COUNT][3];
static volatile bool connected=false,tcp_connected=false,running=false,done=false;
static volatile uint64_t rx_bytes=0,bench_rx=0;
static volatile int requested=0,run_id=0;
static int64_t base_us=0;
static void events(void*a,esp_event_base_t b,int32_t id,void*d){if(id==WIFI_EVENT_STA_START)esp_wifi_connect();else if(id==WIFI_EVENT_STA_DISCONNECTED){connected=false;tcp_connected=false;esp_wifi_connect();}else if(id==WIFI_EVENT_STA_CONNECTED)connected=true;}
static void receiver(void*unused){static char buf[8192];for(;;){if(!connected){vTaskDelay(100);continue;}int s=socket(AF_INET,SOCK_STREAM,0);struct sockaddr_in a={.sin_family=AF_INET,.sin_port=htons(5003)};inet_pton(AF_INET,"192.168.8.20",&a.sin_addr);struct timeval tv={.tv_sec=1};setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));if(connect(s,(struct sockaddr*)&a,sizeof(a))==0){tcp_connected=true;while(connected){int n=recv(s,buf,sizeof(buf),0);if(n>0){rx_bytes+=n;if(running && esp_timer_get_time()-base_us<(int64_t)requested*10000)bench_rx+=n;}else if(n==0 || (errno!=EAGAIN && errno!=EWOULDBLOCK))break;}}tcp_connected=false;close(s);vTaskDelay(250);}}
static void probe(void*unused){for(;;){if(!running){vTaskDelay(1);continue;}int n=requested;int s=socket(AF_INET,SOCK_DGRAM,0);struct sockaddr_in a={.sin_family=AF_INET,.sin_port=htons(5140)};inet_pton(AF_INET,"192.168.8.20",&a.sin_addr);connect(s,(struct sockaddr*)&a,sizeof(a));struct timeval tv={.tv_usec=1000};setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));int seq=0;uint32_t packet[16]={0},reply[16];base_us=esp_timer_get_time();bench_rx=0;
 while(running && (seq<n || esp_timer_get_time()-base_us<(int64_t)n*10000+1000000)){int64_t now=esp_timer_get_time()-base_us;if(seq<n && now>=(int64_t)seq*10000){rows[seq][0]=seq*10000;rows[seq][1]=now;packet[0]=htonl(run_id);packet[1]=htonl(seq);packet[2]=htonl(now);send(s,packet,sizeof(packet),0);seq++;}int r=recv(s,reply,sizeof(reply),0);if(r==sizeof(reply)&&ntohl(reply[0])==run_id){uint32_t q=ntohl(reply[1]);if(q<(unsigned)n&&ntohl(reply[2])==rows[q][1]&&!rows[q][2])rows[q][2]=esp_timer_get_time()-base_us;}}
 close(s);running=false;done=true;}}
static void state(void){wifi_ap_record_t ap={0};esp_wifi_sta_get_ap_info(&ap);printf("STATE {\"version\":1,\"connected\":%d,\"tcp_connected\":%d,\"running\":%d,\"done\":%d,\"run_id\":%d,\"rx_bytes\":%"PRIu64",\"bench_rx_bytes\":%"PRIu64",\"primary\":%u,\"secondary\":%d,\"ap_bw\":%d,\"rssi\":%d}\n",connected,tcp_connected,running,done,run_id,rx_bytes,bench_rx,ap.primary,ap.second,ap.bandwidth,ap.rssi);}
static void command(char*line){if(!strcmp(line,"STATUS"))state();else if(!strcmp(line,"STOP")){running=false;esp_wifi_stop();puts("OK STOP");}else if(!strncmp(line,"BENCH ",6)){int id=0,n=3000;sscanf(line,"BENCH %d %d",&id,&n);if(!connected||running||n<1||n>COUNT){puts("ERR BENCH");return;}memset(rows,0,sizeof(rows));requested=n;run_id=id;done=false;running=true;puts("OK BENCH");}else if(!strcmp(line,"DUMP")){if(!done){puts("ERR NOT_DONE");return;}size_t n=requested*sizeof(rows[0]);uint32_t crc=esp_rom_crc32_le(0,(uint8_t*)rows,n);printf("BIN %u %08"PRIx32"\n",(unsigned)n,crc);fflush(stdout);uart_write_bytes(UART_NUM_0,rows,n);uart_wait_tx_done(UART_NUM_0,pdMS_TO_TICKS(3000));}else puts("ERR COMMAND");fflush(stdout);}
void app_main(void){esp_log_level_set("*",ESP_LOG_WARN);setvbuf(stdout,NULL,_IONBF,0);esp_err_t e=nvs_flash_init();if(e==ESP_ERR_NVS_NO_FREE_PAGES||e==ESP_ERR_NVS_NEW_VERSION_FOUND){nvs_flash_erase();e=nvs_flash_init();}ESP_ERROR_CHECK(e);ESP_ERROR_CHECK(esp_netif_init());ESP_ERROR_CHECK(esp_event_loop_create_default());esp_netif_t*sta=esp_netif_create_default_wifi_sta();esp_netif_dhcpc_stop(sta);esp_netif_ip_info_t ip={0};IP4_ADDR(&ip.ip,192,168,8,10);IP4_ADDR(&ip.gw,192,168,8,1);IP4_ADDR(&ip.netmask,255,255,255,0);ESP_ERROR_CHECK(esp_netif_set_ip_info(sta,&ip));wifi_init_config_t config=WIFI_INIT_CONFIG_DEFAULT();ESP_ERROR_CHECK(esp_wifi_init(&config));esp_wifi_set_storage(WIFI_STORAGE_RAM);esp_wifi_set_mode(WIFI_MODE_STA);wifi_config_t conf={0};strcpy((char*)conf.sta.ssid,"ESP-SDR-TEAM-A");strcpy((char*)conf.sta.password,"SdrLab2026TestOnly");ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA,&conf));esp_wifi_set_bandwidth(WIFI_IF_STA,WIFI_BW20);esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,events,NULL);ESP_ERROR_CHECK(esp_wifi_start());esp_wifi_set_ps(WIFI_PS_NONE);xTaskCreate(receiver,"tcp_rx",8192,NULL,4,NULL);xTaskCreate(probe,"udp_probe",8192,NULL,8,NULL);uart_config_t u={.baud_rate=460800,.data_bits=UART_DATA_8_BITS,.parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,.flow_ctrl=UART_HW_FLOWCTRL_DISABLE,.source_clk=UART_SCLK_DEFAULT};uart_param_config(UART_NUM_0,&u);uart_driver_install(UART_NUM_0,2048,0,0,NULL,0);puts("READY TEAM_CONTROLLER v1");char line[128];int n=0;for(;;){uint8_t x;if(uart_read_bytes(UART_NUM_0,&x,1,pdMS_TO_TICKS(100))==1){if(x=='\r'||x=='\n'){if(n){line[n]=0;command(line);n=0;}}else if(n<sizeof(line)-1)line[n++]=x;}}}
