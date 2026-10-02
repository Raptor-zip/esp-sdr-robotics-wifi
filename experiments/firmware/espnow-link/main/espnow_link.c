/* Owned peer-to-peer ESP-NOW application echo; no AP association. */
#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_wifi.h"
#include "esp_now.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_rom_crc.h"
#include "nvs_flash.h"
#include "driver/uart.h"
#define COUNT 3000
#define REQUEST 0xc5e51001u
#define RESPONSE 0xc5e51002u
static uint32_t rows[COUNT][3];
static uint8_t mac[6],peer[6];static bool paired=false;
static volatile int role=0,requested=0,run_id=0;
static volatile bool running=false,done=false;
static int64_t base_us=0;
static volatile uint32_t tx_success=0,tx_fail=0,tx_api_errors=0,rx_messages=0,queue_drops=0;
static volatile int rssi=-127,rx_rate=-1,rx_sig_mode=-1;
static QueueHandle_t echo_queue;
static void sent_cb(const esp_now_send_info_t*info,esp_now_send_status_t status){if(status==ESP_NOW_SEND_SUCCESS)tx_success++;else tx_fail++;}
static void recv_cb(const esp_now_recv_info_t*info,const uint8_t*data,int len){
 if(!paired||memcmp(info->src_addr,peer,6)||len!=64)return;
 uint32_t packet[16];memcpy(packet,data,64);rx_messages++;rssi=info->rx_ctrl->rssi;rx_rate=info->rx_ctrl->rate;rx_sig_mode=info->rx_ctrl->sig_mode;
 if(role==1 && packet[0]==REQUEST){packet[0]=RESPONSE;if(xQueueSend(echo_queue,packet,0)!=pdTRUE)queue_drops++;}
 else if(role==2 && running && packet[0]==RESPONSE && packet[1]==run_id && packet[2]<(unsigned)requested){unsigned i=packet[2];if(packet[3]==rows[i][1]&&!rows[i][2])rows[i][2]=esp_timer_get_time()-base_us;}
}
static void echo_task(void*unused){uint32_t packet[16];for(;;){if(xQueueReceive(echo_queue,packet,portMAX_DELAY)==pdTRUE && role==1){if(esp_now_send(peer,(uint8_t*)packet,64)!=ESP_OK)tx_api_errors++;}}}
static void probe(void*unused){for(;;){if(!running){vTaskDelay(1);continue;}int n=requested;uint32_t packet[16]={0};base_us=esp_timer_get_time();int seq=0;
 while(running && (seq<n||esp_timer_get_time()-base_us<(int64_t)n*10000+1000000)){
  int64_t now=esp_timer_get_time()-base_us;
  if(seq<n && now>=(int64_t)seq*10000){rows[seq][0]=seq*10000;rows[seq][1]=now;packet[0]=REQUEST;packet[1]=run_id;packet[2]=seq;packet[3]=now;if(esp_now_send(peer,(uint8_t*)packet,64)!=ESP_OK)tx_api_errors++;seq++;}
  vTaskDelay(1);
 }
 running=false;done=true;}}
static void state(void){uint8_t ch=0;wifi_second_chan_t second=0;esp_wifi_get_channel(&ch,&second);int8_t power=0;esp_wifi_get_max_tx_power(&power);
 printf("STATE {\"version\":1,\"role\":%d,\"paired\":%d,\"running\":%d,\"done\":%d,\"run_id\":%d,\"primary\":%u,\"tx_qdbm\":%d,\"rssi\":%d,\"rx_rate\":%d,\"rx_sig_mode\":%d,\"tx_success\":%u,\"tx_fail\":%u,\"tx_api_errors\":%u,\"rx_messages\":%u,\"queue_drops\":%u,\"mac\":\"%02x:%02x:%02x:%02x:%02x:%02x\"}\n",role,paired,running,done,run_id,ch,power,rssi,rx_rate,rx_sig_mode,(unsigned)tx_success,(unsigned)tx_fail,(unsigned)tx_api_errors,(unsigned)rx_messages,(unsigned)queue_drops,mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
}
static void command(char*line){
 if(!strcmp(line,"STATUS"))state();
 else if(!strncmp(line,"PEER ",5)){unsigned p[6];if(sscanf(line,"PEER %x:%x:%x:%x:%x:%x",p,p+1,p+2,p+3,p+4,p+5)!=6){puts("ERR PEER");return;}if(paired)esp_now_del_peer(peer);for(int i=0;i<6;i++)peer[i]=p[i];esp_now_peer_info_t conf={0};memcpy(conf.peer_addr,peer,6);conf.ifidx=WIFI_IF_STA;conf.channel=0;conf.encrypt=false;ESP_ERROR_CHECK(esp_now_add_peer(&conf));esp_now_rate_config_t rate={.phymode=WIFI_PHY_MODE_11B,.rate=WIFI_PHY_RATE_1M_L};ESP_ERROR_CHECK(esp_now_set_peer_rate_config(peer,&rate));paired=true;puts("OK PEER");}
 else if(!strncmp(line,"CHANNEL ",8)){int ch=0;sscanf(line,"CHANNEL %d",&ch);if(ch!=6&&ch!=7&&ch!=11){puts("ERR CHANNEL");return;}running=false;ESP_ERROR_CHECK(esp_wifi_set_channel(ch,WIFI_SECOND_CHAN_NONE));puts("OK CHANNEL");}
 else if(!strncmp(line,"ROLE ",5)){sscanf(line,"ROLE %d",&role);running=false;puts("OK ROLE");}
 else if(!strncmp(line,"BENCH ",6)){int id,n;sscanf(line,"BENCH %d %d",&id,&n);if(!paired||role!=2||running||n<1||n>COUNT){puts("ERR BENCH");return;}memset(rows,0,sizeof(rows));run_id=id;requested=n;done=false;running=true;puts("OK BENCH");}
 else if(!strcmp(line,"DUMP")){if(!done){puts("ERR NOT_DONE");return;}size_t n=requested*sizeof(rows[0]);printf("BIN %u %08"PRIx32"\n",(unsigned)n,esp_rom_crc32_le(0,(uint8_t*)rows,n));uart_write_bytes(UART_NUM_0,rows,n);uart_wait_tx_done(UART_NUM_0,pdMS_TO_TICKS(5000));}
 else if(!strcmp(line,"STOP")){role=0;running=false;puts("OK STOP");}
 else puts("ERR COMMAND");
}
void app_main(void){
 esp_log_level_set("*",ESP_LOG_WARN);setvbuf(stdout,NULL,_IONBF,0);esp_err_t e=nvs_flash_init();if(e==ESP_ERR_NVS_NO_FREE_PAGES||e==ESP_ERR_NVS_NEW_VERSION_FOUND){nvs_flash_erase();e=nvs_flash_init();}ESP_ERROR_CHECK(e);ESP_ERROR_CHECK(esp_netif_init());ESP_ERROR_CHECK(esp_event_loop_create_default());wifi_init_config_t conf=WIFI_INIT_CONFIG_DEFAULT();ESP_ERROR_CHECK(esp_wifi_init(&conf));ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA,WIFI_BW20));ESP_ERROR_CHECK(esp_wifi_start());ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));ESP_ERROR_CHECK(esp_wifi_set_channel(6,WIFI_SECOND_CHAN_NONE));ESP_ERROR_CHECK(esp_wifi_get_mac(WIFI_IF_STA,mac));ESP_ERROR_CHECK(esp_now_init());esp_now_register_recv_cb(recv_cb);esp_now_register_send_cb(sent_cb);echo_queue=xQueueCreate(16,64);xTaskCreate(echo_task,"echo",4096,NULL,8,NULL);xTaskCreate(probe,"probe",4096,NULL,8,NULL);
 uart_config_t u={.baud_rate=115200,.data_bits=UART_DATA_8_BITS,.parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,.flow_ctrl=UART_HW_FLOWCTRL_DISABLE,.source_clk=UART_SCLK_DEFAULT};uart_param_config(UART_NUM_0,&u);uart_driver_install(UART_NUM_0,2048,0,0,NULL,0);puts("READY ESPNOW_LINK v1");char line[128];int n=0;for(;;){uint8_t c;if(uart_read_bytes(UART_NUM_0,&c,1,pdMS_TO_TICKS(100))==1){if(c=='\r'||c=='\n'){if(n){line[n]=0;command(line);n=0;}}else if(n<sizeof(line)-1)line[n++]=c;}}
}
