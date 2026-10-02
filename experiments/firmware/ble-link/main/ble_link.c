/* Standard BLE advertisements and GATT notification load, on owned test boards. */
#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "driver/uart.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"
static int role=0,period_ms=0;static int64_t until=0;
static uint16_t connection=BLE_HS_CONN_HANDLE_NONE,value_handle=0;
static uint8_t own_addr_type=0;static bool synced=false,subscribed=false;
static uint64_t tx_bytes=0,rx_bytes=0,tx_messages=0,rx_messages=0,tx_errors=0,advertisements=0;
static const ble_uuid128_t svc_uuid=BLE_UUID128_INIT(0x61,0x18,0x91,0x53,0xb5,0x81,0x42,0x2a,0x98,0x47,0x22,0x49,0x4e,0x12,0xc5,0x70);
static const ble_uuid128_t chr_uuid=BLE_UUID128_INIT(0x62,0x18,0x91,0x53,0xb5,0x81,0x42,0x2a,0x98,0x47,0x22,0x49,0x4e,0x12,0xc5,0x70);
static int access_cb(uint16_t c,uint16_t a,struct ble_gatt_access_ctxt*x,void*p){uint8_t z=0;return os_mbuf_append(x->om,&z,1)==0?0:BLE_ATT_ERR_INSUFFICIENT_RES;}
static const struct ble_gatt_svc_def svcs[]={ {.type=BLE_GATT_SVC_TYPE_PRIMARY,.uuid=&svc_uuid.u,.characteristics=(struct ble_gatt_chr_def[]){ {.uuid=&chr_uuid.u,.access_cb=access_cb,.flags=BLE_GATT_CHR_F_READ|BLE_GATT_CHR_F_NOTIFY,.val_handle=&value_handle},{0}}},{0}};
static int gap_event(struct ble_gap_event*e,void*a);static void begin(void);
static void advertise(bool connectable){struct ble_hs_adv_fields f={0};f.flags=BLE_HS_ADV_F_DISC_GEN|BLE_HS_ADV_F_BREDR_UNSUP;f.name=(uint8_t*)"C5LABBLE";f.name_len=8;f.name_is_complete=1;ble_gap_adv_set_fields(&f);struct ble_gap_adv_params p={0};p.conn_mode=connectable?BLE_GAP_CONN_MODE_UND:BLE_GAP_CONN_MODE_NON;p.disc_mode=BLE_GAP_DISC_MODE_GEN;p.itvl_min=32;p.itvl_max=32;ble_gap_adv_start(own_addr_type,NULL,BLE_HS_FOREVER,&p,gap_event,NULL);}
static void scan(void){struct ble_gap_disc_params p={0};p.passive=1;p.itvl=32;p.window=32;p.filter_duplicates=role==4?0:1;ble_gap_disc(own_addr_type,BLE_HS_FOREVER,&p,gap_event,NULL);}
static void begin(void){if(!synced)return;if(role==1)advertise(true);else if(role==2||role==4)scan();else if(role==3)advertise(false);}
static int gap_event(struct ble_gap_event*e,void*a){switch(e->type){case BLE_GAP_EVENT_DISC:{struct ble_hs_adv_fields f;if((role==2||role==4)&&ble_hs_adv_parse_fields(&f,e->disc.data,e->disc.length_data)==0&&f.name_len==8&&!memcmp(f.name,"C5LABBLE",8)){advertisements++;if(role==4)break;ble_gap_disc_cancel();struct ble_gap_conn_params p={.scan_itvl=16,.scan_window=16,.itvl_min=6,.itvl_max=6,.latency=0,.supervision_timeout=400,.min_ce_len=0,.max_ce_len=0};ble_gap_connect(own_addr_type,&e->disc.addr,10000,&p,gap_event,NULL);}break;}case BLE_GAP_EVENT_CONNECT:if(e->connect.status==0){connection=e->connect.conn_handle;ble_gattc_exchange_mtu(connection,NULL,NULL);}else begin();break;case BLE_GAP_EVENT_DISCONNECT:connection=BLE_HS_CONN_HANDLE_NONE;subscribed=false;begin();break;case BLE_GAP_EVENT_SUBSCRIBE:subscribed=e->subscribe.cur_notify;break;case BLE_GAP_EVENT_NOTIFY_RX:rx_bytes+=OS_MBUF_PKTLEN(e->notify_rx.om);rx_messages++;break;case BLE_GAP_EVENT_ADV_COMPLETE:begin();break;default:break;}return 0;}
static void sync_cb(void){ble_hs_id_infer_auto(0,&own_addr_type);synced=true;begin();}
static void host_task(void*unused){nimble_port_run();nimble_port_freertos_deinit();}
static void sender(void*unused){static uint8_t payload[244];memset(payload,0xa5,sizeof(payload));for(;;){if(role==1&&connection!=BLE_HS_CONN_HANDLE_NONE&&subscribed&&period_ms>0&&esp_timer_get_time()<until){int size=ble_att_mtu(connection)-3;if(size>244)size=244;struct os_mbuf*om=ble_hs_mbuf_from_flat(payload,size);if(om){int rc=ble_gatts_notify_custom(connection,value_handle,om);if(rc==0){tx_bytes+=size;tx_messages++;}else tx_errors++;}else tx_errors++;vTaskDelay(pdMS_TO_TICKS(period_ms));}else vTaskDelay(5);}}
static void state(void){struct ble_gap_conn_desc d={0};int rc=connection!=BLE_HS_CONN_HANDLE_NONE?ble_gap_conn_find(connection,&d):-1;printf("STATE {\"version\":1,\"role\":%d,\"synced\":%d,\"connected\":%d,\"subscribed\":%d,\"value_handle\":%u,\"mtu\":%u,\"interval_units\":%u,\"tx_bytes\":%"PRIu64",\"rx_bytes\":%"PRIu64",\"tx_messages\":%"PRIu64",\"rx_messages\":%"PRIu64",\"tx_errors\":%"PRIu64",\"advertisements\":%"PRIu64"}\n",role,synced,rc==0,subscribed,value_handle,rc==0?ble_att_mtu(connection):0,d.conn_itvl,tx_bytes,rx_bytes,tx_messages,rx_messages,tx_errors,advertisements);}
static int subscribed_cb(uint16_t c,const struct ble_gatt_error*e,struct ble_gatt_attr*a,void*arg){printf("SUBSCRIBED %d\n",e->status);return 0;}
static void command(char*line){if(!strcmp(line,"STATUS"))state();else if(!strncmp(line,"ROLE ",5)){role=0;period_ms=0;ble_gap_disc_cancel();ble_gap_adv_stop();if(connection!=BLE_HS_CONN_HANDLE_NONE)ble_gap_terminate(connection,BLE_ERR_REM_USER_CONN_TERM);vTaskDelay(100);sscanf(line,"ROLE %d",&role);begin();puts("OK ROLE");}else if(!strncmp(line,"SUB ",4)){int h=0;sscanf(line,"SUB %d",&h);uint8_t one[2]={1,0};int rc=ble_gattc_write_flat(connection,h+1,one,2,subscribed_cb,NULL);printf("OK SUB %d\n",rc);}else if(!strncmp(line,"LOAD ",5)){int ms=0,seconds=0;sscanf(line,"LOAD %d %d",&ms,&seconds);period_ms=ms;until=esp_timer_get_time()+(int64_t)seconds*1000000;puts("OK LOAD");}else puts("ERR COMMAND");fflush(stdout);}
void app_main(void){esp_log_level_set("*",ESP_LOG_WARN);setvbuf(stdout,NULL,_IONBF,0);esp_err_t e=nvs_flash_init();if(e==ESP_ERR_NVS_NO_FREE_PAGES||e==ESP_ERR_NVS_NEW_VERSION_FOUND){nvs_flash_erase();e=nvs_flash_init();}ESP_ERROR_CHECK(e);ESP_ERROR_CHECK(nimble_port_init());ble_svc_gap_init();ble_svc_gatt_init();ble_gatts_count_cfg(svcs);ble_gatts_add_svcs(svcs);ble_svc_gap_device_name_set("C5LABBLE");ble_att_set_preferred_mtu(247);ble_hs_cfg.sync_cb=sync_cb;nimble_port_freertos_init(host_task);xTaskCreate(sender,"notify_load",4096,NULL,4,NULL);uart_config_t u={.baud_rate=115200,.data_bits=UART_DATA_8_BITS,.parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,.flow_ctrl=UART_HW_FLOWCTRL_DISABLE,.source_clk=UART_SCLK_DEFAULT};uart_param_config(UART_NUM_0,&u);uart_driver_install(UART_NUM_0,2048,0,0,NULL,0);puts("READY BLE_LINK v1");char line[128];int n=0;for(;;){uint8_t x;if(uart_read_bytes(UART_NUM_0,&x,1,pdMS_TO_TICKS(100))==1){if(x=='\r'||x=='\n'){if(n){line[n]=0;command(line);n=0;}}else if(n<sizeof(line)-1)line[n++]=x;}}}
