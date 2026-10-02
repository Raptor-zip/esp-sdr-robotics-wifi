/* Portable on-chip spectra for targets without a validated continuous backend.
 * Each frame is an independent snapshot. Frame indices use elapsed wall time,
 * and flag bit 3 explicitly marks the gaps between acquisitions. */
#include "spectrum.h"
#include "spectrum_dc.h"
#include "spectrum_stats.h"
#include "esp_cpu.h"
#include "burst_serial.h"
#include "dsps_fft2r.h"
#include "esp_rom_crc.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#if CONFIG_IDF_TARGET_ESP32C61
#define MAX_FFT 1024u
#else
#define MAX_FFT 2048u
#endif
#define HEADER_BYTES 28u
static int16_t fft_data[2 * MAX_FFT] __attribute__((aligned(16)));
static int16_t window[MAX_FFT];
static float powers[MAX_FFT];
static uint8_t frame[HEADER_BYTES + MAX_FFT + 4];
static unsigned setup_n;
static bool ready;
spectrum_workspace_t spectrum_workspace(void) {
    setup_n=0;
    return (spectrum_workspace_t){fft_data,window,powers,frame};
}

static int16_t twiddles[MAX_FFT] __attribute__((aligned(16)));
bool spectrum_fft_init(void) {
    if(!ready) ready=dsps_fft2r_init_sc16(twiddles,MAX_FFT)==ESP_OK;
    return ready;
}

static const unsigned rates[] = {
#if CONFIG_IDF_TARGET_ESP32C3 || CONFIG_IDF_TARGET_ESP32C6
    80000000
#elif CONFIG_IDF_TARGET_ESP32 || CONFIG_IDF_TARGET_ESP32S2
    80000000, 40000000, 0, 0, 0, 0, 16000000
#else
    80000000, 40000000, 20000000, 10000000, 8000000, 4000000
#endif
};
static unsigned rate_hz(unsigned code) {
    return code < sizeof(rates)/sizeof(rates[0]) ? rates[code] : 0;
}
static bool send_text(const char *s) { return burst_serial_send(s, strlen(s)); }
static void put16(unsigned at, uint16_t v) { frame[at]=v; frame[at+1]=v>>8; }
static void put32(unsigned at, uint32_t v) { put16(at,v); put16(at+2,v>>16); }
static void put64(unsigned at, uint64_t v) { put32(at,v); put32(at+4,v>>32); }
static unsigned reverse(unsigned x, unsigned bits) {
    unsigned r=0; while(bits--) {r=(r<<1)|(x&1); x>>=1;} return r;
}
static int16_t clamp16(int32_t v) {return v>32767?32767:v< -32768?-32768:v;}

static void capabilities(void) {
    send_text("SPECINFO {\"continuous\":false,\"transports\":[\"USB\",\"UART\"],\"profiles\":[");
    bool first=true;
    for(unsigned r=0;r<sizeof(rates)/sizeof(rates[0]);r++) if(rates[r]) {
        for(unsigned n=256;n<=MAX_FFT;n*=2) {
            char text[96];
            snprintf(text,sizeof(text),"%s[%u,%u,%u,1,1,%u]",first?"":",",rates[r],r,n,
#if CONFIG_IDF_TARGET_ESP32C61 || CONFIG_IDF_TARGET_ESP32C6 || CONFIG_IDF_TARGET_ESP32C3
                     n==256 && burst_serial_port()!=BURST_SERIAL_UART
#else
                     0u
#endif
            );
            send_text(text); first=false;
        }
    }
    send_text("]}\n");
}

bool spectrum_command(const char *line, unsigned frequency_mhz, spectrum_acquire_fn acquire) {
    unsigned dc_mode;char dc_extra;
    if(!strcmp(line,"DC?")){char text[16];snprintf(text,sizeof(text),"DC %u\n",spectrum_dc_mode);send_text(text);return true;}
    if(sscanf(line,"DC %u %c",&dc_mode,&dc_extra)==1 && dc_mode<2){spectrum_dc_mode=dc_mode;send_text("OK\n");return true;}
    if(!strcmp(line,"SPECINFO?")) {capabilities();return true;}
    if(strncmp(line,"SPEC ",5)) return false;
    unsigned ms,stride,units,det,rate,n,stats=0; char extra;
    int fields=sscanf(line,"SPEC %u %u %u %u %u %u %u %c",&ms,&stride,&units,&det,&rate,&n,&stats,&extra);
    if((fields!=6 && fields!=7) || stats>1 || ms>86400000u || stride!=1 || !units || units>8 || det>1 ||
       !rate_hz(rate) || n<256 || n>MAX_FFT || (n&(n-1))) {
        send_text("ERR spec_args\n");return true;
    }
    spectrum_fft_init();
    if(!ready) {send_text("ERR spectrum_memory\n");return true;}
    if(setup_n!=n) {
        for(unsigned j=0;j<n;j++) window[j]=(int16_t)lrintf(16383.5f*(1-cosf(2*M_PI*j/n)));
        setup_n=n;
    }
    unsigned log2n=0;while((1u<<log2n)<n)log2n++;
    char text[192];
    snprintf(text,sizeof(text),"SPEC %u %u %u %u\n",n,rate_hz(rate),n,frequency_mhz);
    if(!send_text(text)) return true;
    int64_t start=esp_timer_get_time(),yield_at=start;
    uint32_t frames=0,ffts=0,status=0;uint64_t pairs=0;
    bool stopped=false;
    spectrum_dc_t dc={0};spectrum_stats_t telemetry;spectrum_stats_init(&telemetry);
    do {
        if(burst_serial_stop_requested()) {stopped=true;break;}
        memset(powers,0,n*sizeof(*powers));
        uint64_t index=(uint64_t)(esp_timer_get_time()-start)*rate_hz(rate)/1000000u;
        uint8_t gain=0;
        uint32_t busy_start=esp_cpu_get_cycle_count();
        for(unsigned u=0;u<units;u++) {
            const uint32_t *words; unsigned elapsed;
            if(!acquire(n,rate,&words,&elapsed)) {status=1;break;}
            if(!u) gain=words[0]>>20;
            for(unsigned j=0;j<n;j++) {
                int32_t i=((int32_t)(words[j]<<22)>>22), q=((int32_t)(words[j]<<12)>>22);
                fft_data[2*j]=clamp16((i*window[j])>>9);
                fft_data[2*j+1]=clamp16((q*window[j])>>9);
            }
            /* The ANSI kernel rounds correctly on all architectures. */
            dsps_fft2r_sc16_ansi(fft_data,n);
            spectrum_dc_apply(&dc,fft_data,n);
            for(unsigned j=0;j<n;j++) {
                float re=fft_data[2*j],im=fft_data[2*j+1],p=re*re+im*im;
                unsigned k=reverse(j,log2n);
                powers[k]=det?fmaxf(powers[k],p):powers[k]+p;
            }
            ffts++;pairs+=n;
        }
        if(status) break;
        memcpy(frame,"SPC1",4);put32(4,frames);put64(8,index);put32(16,n*units);
        put16(20,units);frame[22]=8|(det?1:0);frame[23]=gain;put16(24,0);
        frame[26]=log2n;frame[27]=2;
        for(unsigned j=0;j<n;j++) {
            float p=det?powers[j]:powers[j]/units;
            float db=p>1?20*log10f(p):0;
            frame[HEADER_BYTES+j]=db>=255?255:(uint8_t)(db+0.5f);
        }
        put32(HEADER_BYTES+n,esp_rom_crc32_le(0,frame,HEADER_BYTES+n));
        telemetry.busy+=(uint32_t)(esp_cpu_get_cycle_count()-busy_start);
        if(!burst_serial_send(frame,HEADER_BYTES+n+4)) {status=7;break;}
        frames++;
        if(stats)spectrum_stats_emit(&telemetry,n,rate_hz(rate),ffts,0,0,0,0,burst_serial_send);
        if(esp_timer_get_time()-yield_at>=20000) {vTaskDelay(1);yield_at=esp_timer_get_time();}
    } while(!ms || esp_timer_get_time()-start<(int64_t)ms*1000);
    snprintf(text,sizeof(text),"SPECEND %u 0 %u %"PRIu64" %"PRIi64" 0 0 %u 0 0 %u %u\n",
             (unsigned)status,(unsigned)ffts,pairs,esp_timer_get_time()-start,(unsigned)frames,(unsigned)ffts,stopped);
    send_text(text);return true;
}
