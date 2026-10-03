/* Continuous, owned-peer ESP-NOW application echo with bounded UART telemetry.
 * UART events are [kind, sequence, relative_us, argument], all uint32 LE.
 * MAC callback results are aggregate counters, never attributed to a sequence.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <assert.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "esp_wifi.h"
#include "esp_now.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_rom_crc.h"
#include "nvs_flash.h"
#include "driver/uart.h"

#define REQUEST 0xc5e52001u
#define RESPONSE 0xc5e52002u
#define TRACE_TX 1u
#define TRACE_RX 2u
#define TRACE_SKIP 3u
#define TRACE_END 4u

typedef struct { uint32_t kind, sequence, time_us, argument; } trace_t;
_Static_assert(sizeof(trace_t) == 16, "UART event layout");
static uint8_t mac[6], peer[6];
static bool paired = false;
static volatile int role = 0;
static volatile bool running = false, done = false;
static volatile uint32_t run_id = 0, rate_hz = 100, seconds = 600, planned = 0;
static int64_t base_us = 0;
static volatile uint32_t tx_success = 0, tx_fail = 0, tx_api_errors = 0;
static volatile uint32_t rx_messages = 0, echo_queue_drops = 0, trace_drops = 0;
static volatile uint32_t sent_calls = 0, skipped_schedules = 0, duplicates_unclassified = 0;
static volatile int rssi = -127, rx_rate = -1, rx_sig_mode = -1;
static QueueHandle_t echo_queue, trace_queue;
static SemaphoreHandle_t uart_lock;

static void trace_event(uint32_t kind, uint32_t sequence, uint32_t time_us, uint32_t argument) {
    trace_t event = {kind, sequence, time_us, argument};
    if (xQueueSend(trace_queue, &event, 0) != pdTRUE) trace_drops++;
}

static void send_callback(const esp_now_send_info_t *info, esp_now_send_status_t status) {
    if (status == ESP_NOW_SEND_SUCCESS) tx_success++; else tx_fail++;
}

static void receive_callback(const esp_now_recv_info_t *info, const uint8_t *data, int length) {
    if (!paired || memcmp(info->src_addr, peer, 6) || length != 64) return;
    uint32_t packet[16]; memcpy(packet, data, sizeof(packet));
    rx_messages++; rssi = info->rx_ctrl->rssi;
    rx_rate = info->rx_ctrl->rate; rx_sig_mode = info->rx_ctrl->sig_mode;
    if (role == 1 && packet[0] == REQUEST) {
        packet[0] = RESPONSE;
        if (xQueueSend(echo_queue, packet, 0) != pdTRUE) echo_queue_drops++;
    } else if (role == 2 && running && packet[0] == RESPONSE && packet[1] == run_id && packet[2] < planned) {
        // All valid replies are logged. The host identifies the first reply
        // and duplicates using sequence plus the original sender timestamp.
        trace_event(TRACE_RX, packet[2], (uint32_t)(esp_timer_get_time()-base_us), packet[3]);
        duplicates_unclassified++;
    }
}

static void echo_task(void *unused) {
    uint32_t packet[16];
    for (;;) {
        if (xQueueReceive(echo_queue, packet, portMAX_DELAY) == pdTRUE && role == 1) {
            sent_calls++;
            if (esp_now_send(peer, (uint8_t *)packet, sizeof(packet)) != ESP_OK) tx_api_errors++;
        }
    }
}

static void emit_block(trace_t *events, size_t count) {
    if (!count) return;
    size_t size = count*sizeof(trace_t);
    uint32_t crc = esp_rom_crc32_le(0, (uint8_t *)events, size);
    xSemaphoreTake(uart_lock, portMAX_DELAY);
    printf("EVT %u %08"PRIx32"\n", (unsigned)size, crc);
    uart_write_bytes(UART_NUM_0, events, size);
    uart_wait_tx_done(UART_NUM_0, pdMS_TO_TICKS(3000));
    xSemaphoreGive(uart_lock);
}

static void trace_task(void *unused) {
    trace_t events[128]; size_t count = 0;
    for (;;) {
        trace_t event;
        if (xQueueReceive(trace_queue, &event, pdMS_TO_TICKS(100)) == pdTRUE) {
            events[count++] = event;
            if (count == 128 || event.kind == TRACE_END) { emit_block(events, count); count = 0; }
        } else if (count) { emit_block(events, count); count = 0; }
    }
}

static void probe_task(void *unused) {
    for (;;) {
        if (!running) { vTaskDelay(1); continue; }
        const uint32_t total = planned, frequency = rate_hz, id = run_id;
        const uint32_t period = 1000000/frequency;
        const int64_t duration = (int64_t)seconds*1000000;
        uint32_t sequence = 0, packet[16] = {0};
        base_us = esp_timer_get_time();
        while (running && esp_timer_get_time()-base_us < duration+2000000) {
            int64_t now = esp_timer_get_time()-base_us;
            if (now < duration && sequence < total && now >= (int64_t)sequence*period) {
                uint32_t slot = (uint32_t)(now/period);
                if (slot > sequence) {
                    skipped_schedules += slot-sequence;
                    trace_event(TRACE_SKIP, sequence, (uint32_t)now, slot-sequence);
                    sequence = slot;
                }
                packet[0] = REQUEST; packet[1] = id; packet[2] = sequence; packet[3] = (uint32_t)now;
                esp_err_t error = esp_now_send(peer, (uint8_t *)packet, sizeof(packet));
                sent_calls++; if (error != ESP_OK) tx_api_errors++;
                trace_event(TRACE_TX, sequence, (uint32_t)now, (uint32_t)error);
                sequence++;
            }
            vTaskDelay(1);
        }
        if (sequence < total) {
            skipped_schedules += total-sequence;
            trace_event(TRACE_SKIP, sequence, (uint32_t)(esp_timer_get_time()-base_us), total-sequence);
        }
        running = false; done = true;
        // End is enqueued after receive recording has stopped. Unlike the
        // Wi-Fi callback, this task can wait for a free telemetry slot.
        trace_t end = {TRACE_END, total, (uint32_t)(esp_timer_get_time()-base_us), id};
        xQueueSend(trace_queue, &end, portMAX_DELAY);
    }
}

static void state(void) {
    uint8_t channel = 0; wifi_second_chan_t secondary = 0;
    esp_wifi_get_channel(&channel, &secondary);
    int8_t power = 0; esp_wifi_get_max_tx_power(&power);
    wifi_ps_type_t ps = WIFI_PS_NONE; esp_wifi_get_ps(&ps);
    printf("STATE {\"version\":2,\"role\":%d,\"paired\":%d,\"running\":%d,\"done\":%d,"
           "\"run_id\":%"PRIu32",\"hz\":%"PRIu32",\"seconds\":%"PRIu32",\"planned\":%"PRIu32","
           "\"primary\":%u,\"tx_qdbm\":%d,\"power_save\":%d,\"rssi\":%d,\"rx_rate\":%d,\"rx_sig_mode\":%d,"
           "\"tx_success\":%"PRIu32",\"tx_fail\":%"PRIu32",\"tx_api_errors\":%"PRIu32","
           "\"rx_messages\":%"PRIu32",\"echo_queue_drops\":%"PRIu32",\"trace_drops\":%"PRIu32","
           "\"sent_calls\":%"PRIu32",\"skipped_schedules\":%"PRIu32",\"reply_callbacks\":%"PRIu32","
           "\"mac\":\"%02x:%02x:%02x:%02x:%02x:%02x\"}\n",
           role, paired, running, done, run_id, rate_hz, seconds, planned, channel, power, ps, rssi, rx_rate, rx_sig_mode,
           tx_success, tx_fail, tx_api_errors, rx_messages, echo_queue_drops, trace_drops, sent_calls, skipped_schedules,
           duplicates_unclassified, mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

static void reset_counters(void) {
    tx_success = tx_fail = tx_api_errors = rx_messages = echo_queue_drops = trace_drops = 0;
    sent_calls = skipped_schedules = duplicates_unclassified = 0;
}

static void command(char *line) {
    xSemaphoreTake(uart_lock, portMAX_DELAY);
    if (!strcmp(line, "STATUS")) state();
    else if (!strncmp(line, "PEER ", 5)) {
        unsigned p[6];
        if (running || sscanf(line, "PEER %x:%x:%x:%x:%x:%x", p, p+1, p+2, p+3, p+4, p+5) != 6) puts("ERR PEER");
        else {
            if (paired) esp_now_del_peer(peer);
            for (int i=0; i<6; i++) peer[i] = p[i];
            esp_now_peer_info_t config = {0}; memcpy(config.peer_addr, peer, 6);
            config.ifidx = WIFI_IF_STA; config.channel = 0; config.encrypt = false;
            ESP_ERROR_CHECK(esp_now_add_peer(&config));
            esp_now_rate_config_t rate = {.phymode=WIFI_PHY_MODE_11B, .rate=WIFI_PHY_RATE_1M_L};
            ESP_ERROR_CHECK(esp_now_set_peer_rate_config(peer, &rate));
            paired = true; puts("OK PEER");
        }
    } else if (!strncmp(line, "CHANNEL ", 8)) {
        int channel = 0; sscanf(line, "CHANNEL %d", &channel);
        if (running || (channel != 6 && channel != 7 && channel != 11)) puts("ERR CHANNEL");
        else { ESP_ERROR_CHECK(esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE)); puts("OK CHANNEL"); }
    } else if (!strncmp(line, "ROLE ", 5)) {
        int value = -1; sscanf(line, "ROLE %d", &value);
        if (running || value < 0 || value > 2) puts("ERR ROLE");
        else { role = value; done = false; reset_counters(); xQueueReset(echo_queue); puts("OK ROLE"); }
    } else if (!strncmp(line, "RUN ", 4)) {
        unsigned id = 0, frequency = 0, duration = 0;
        if (sscanf(line, "RUN %u %u %u", &id, &frequency, &duration) != 3 || !paired || role != 2 || running ||
            !id || (frequency != 20 && frequency != 50 && frequency != 100 && frequency != 200) || duration < 1 || duration > 1200) puts("ERR RUN");
        else {
            run_id = id; rate_hz = frequency; seconds = duration; planned = frequency*duration;
            reset_counters(); done = false; xQueueReset(trace_queue);
            puts("OK RUN"); running = true;
        }
    } else if (!strcmp(line, "STOP")) { running = false; role = 0; puts("OK STOP"); }
    else puts("ERR COMMAND");
    xSemaphoreGive(uart_lock);
}

void app_main(void) {
    esp_log_level_set("*", ESP_LOG_NONE); setvbuf(stdout, NULL, _IONBF, 0);
    esp_err_t error = nvs_flash_init();
    if (error == ESP_ERR_NVS_NO_FREE_PAGES || error == ESP_ERR_NVS_NEW_VERSION_FOUND) { nvs_flash_erase(); error = nvs_flash_init(); }
    ESP_ERROR_CHECK(error); ESP_ERROR_CHECK(esp_netif_init()); ESP_ERROR_CHECK(esp_event_loop_create_default());
    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT(); ESP_ERROR_CHECK(esp_wifi_init(&config));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM)); ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA, WIFI_BW20)); ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE)); ESP_ERROR_CHECK(esp_wifi_set_channel(6, WIFI_SECOND_CHAN_NONE));
    ESP_ERROR_CHECK(esp_wifi_get_mac(WIFI_IF_STA, mac)); ESP_ERROR_CHECK(esp_now_init());
    echo_queue = xQueueCreate(64, 64); trace_queue = xQueueCreate(512, sizeof(trace_t));
    uart_lock = xSemaphoreCreateMutex(); assert(echo_queue && trace_queue && uart_lock);
    ESP_ERROR_CHECK(esp_now_register_recv_cb(receive_callback)); ESP_ERROR_CHECK(esp_now_register_send_cb(send_callback));
    uart_config_t uart = {.baud_rate=115200, .data_bits=UART_DATA_8_BITS, .parity=UART_PARITY_DISABLE,
        .stop_bits=UART_STOP_BITS_1, .flow_ctrl=UART_HW_FLOWCTRL_DISABLE, .source_clk=UART_SCLK_DEFAULT};
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0, &uart)); ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 2048, 0, 0, NULL, 0));
    xTaskCreate(echo_task, "echo", 4096, NULL, 8, NULL);
    xTaskCreate(trace_task, "trace", 4096, NULL, 6, NULL);
    xTaskCreate(probe_task, "probe", 4096, NULL, 8, NULL);
    puts("READY ESPNOW_STREAM v2");
    char line[128]; int length = 0;
    for (;;) {
        uint8_t c;
        if (uart_read_bytes(UART_NUM_0, &c, 1, pdMS_TO_TICKS(100)) == 1) {
            if (c == '\r' || c == '\n') { if (length) { line[length] = 0; command(line); length = 0; } }
            else if (length < sizeof(line)-1) line[length++] = c;
        }
    }
}
