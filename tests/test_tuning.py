"""Host checks of production tuning helpers/parsers; no RF hardware is used."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

MAIN = Path(__file__).resolve().parents[1] / 'main'

@unittest.skipUnless(shutil.which('cc'), 'Host C compiler unavailable')
class Tuning(unittest.TestCase):
    def compile_run(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp) / 'check.c'
            exe = Path(tmp) / 'check'
            c.write_text(source)
            subprocess.run(['cc', '-std=c11', '-Werror=implicit-function-declaration',
                            '-I'+str(MAIN/'common'), '-I'+str(MAIN), str(c), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_exact_mhz_reaches_each_chip_tuning_helper(self):
        stub = r'''
#include <assert.h>
#include <stdbool.h>
#include "rx_tuning.h"
static unsigned calibrated, pll, writes;
unsigned char phy_param[50] = {[49]=2};
void phy_chip_set_chan(unsigned f,unsigned m){assert(m==0);calibrated=pll=f;}
void chip_v7_set_chan(unsigned f,unsigned m){phy_chip_set_chan(f,m);}
void set_chanfreq(unsigned f,unsigned m){phy_chip_set_chan(f,m);}
void phy_set_chanfreq(unsigned f,unsigned m){phy_chip_set_chan(f,m);}
void phy_set_freq(unsigned f,int o){assert(o==0);pll=f;writes++;}
void set_rf_freq_offset(unsigned c,unsigned f,int o){assert(c==0);phy_set_freq(f,o);}
void rom_set_rf_freq_offset(unsigned c,unsigned f,int o){assert(c==0);phy_set_freq(f,o);}
void phy_set_rf_freq_offset(unsigned c,unsigned f,int o){assert(c==phy_param[49]);phy_set_freq(f,o);}
unsigned rtc_clk_xtal_freq_get(void){return 40;}
'''
        helpers = {}
        for target, start, end, call in [
            ('esp32', 'static void tune_rx(', 'static bool capture_rate(', 'tune_rx(f)'),
            ('esp32c3', 'static void tune_rx(', '#define send_bytes', 'tune_rx(f)'),
            ('esp32s2', 'static void s2_tune(', '#define S2_FREQ_MIN', 's2_tune(f)'),
            ('esp32s3', 'static void s3_tune(', '#define S3_FREQ_MIN', 's3_tune(f)'),
        ]:
            source = (MAIN/'targets'/target/'receiver.c').read_text()
            helpers[target] = (source[source.index(start):source.index(end)], call)
        source = (MAIN/'targets/esp32c6/chip.h').read_text()
        helpers['esp32c6'] = (source[source.index('static void c6_set_chan('):source.index('#define phy_chip_set_chan')], 'c6_set_chan(f,0)')
        for target, call in [('esp32c5','c5_set_chan(f,0)'), ('esp32c61','c61_set_chan(f,0)'), ('esp32s31','s31_tune(f)')]:
            helpers[target] = (f'#include "targets/{target}/tuning.h"\n', call)
        for target, (helper, call) in helpers.items():
            with self.subTest(target=target):
                self.compile_run(stub+helper+r'''
int main(void){
 assert(!rx_frequency_valid(99) && !rx_frequency_valid(6001));
 for(unsigned f=100;f<=6000;f++){
  assert(rx_frequency_valid(f));
  CALL;
  assert(pll==f);
  bool channel=(f>=2412 && f<=2472 && (f-2412)%5==0)||f==2484;
  assert(calibrated==EXPECTED);
 }
 assert(writes>5800);
}
'''.replace('CALL',call).replace('EXPECTED','(f>3000?5180u:2412u)' if target=='esp32c5' else '(channel?f:2412u)'))

    def test_c5_bandwidth_mode_survives_prepare_and_retuning(self):
        source = (MAIN/'families/c5_c6_c61/receiver.c').read_text()
        prepare = source[source.index('static void prepare_rx(void) {'):source.index('#include "filter_probe.h"')]
        self.compile_run(r'''
#include <assert.h>
#include <stdbool.h>
#define CONFIG_IDF_TARGET_ESP32C5 1
#define CONFIG_IDF_TARGET_ESP32C61 0
#define CONFIG_IDF_TARGET_ESP32C6 0
static unsigned frequency_mhz,rx_channel_mode,calls,calibrated,pll,last_mode;
static bool rx_ready;
static int rx_filter=-1;
unsigned char phy_param[50]={[49]=2};
void phy_set_chanfreq(unsigned f,unsigned m){calibrated=f;last_mode=m;calls++;}
void phy_set_rf_freq_offset(unsigned c,unsigned f,int o){assert(c==2 && o==0);pll=f;}
void phy_stop_tx_tone(unsigned x){assert(x==1);}
void phy_pbus_workmode(void){}
void phy_pbus_xpd_tx_off(void){}
void phy_pbus_xpd_rx_on(unsigned x){assert(x==1);}
void phy_set_rxclk_en(unsigned x){assert(x==1);}
void phy_rx_filter_mode(unsigned x){assert(x==12);}
void gain_apply(void){}
#include "targets/esp32c5/tuning.h"
''' + prepare + r'''
int main(void){
 for(unsigned mode=0;mode<=1;mode++)for(unsigned f=2300;f<=5500;f+=3200){
  frequency_mhz=f;rx_channel_mode=mode;rx_ready=false;
  unsigned before=calls;prepare_rx();
  assert(calls==before+1 && last_mode==mode && pll==f && rx_ready);
  assert(calibrated==(f>3000?5180u:2412u));
  prepare_rx();assert(calls==before+1);
 }
 rx_filter=12;rx_ready=false;prepare_rx();assert(last_mode==1);
}
''')

    def test_s2_s3_s31_production_parsers(self):
        stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "rx_tuning.h"
#include "rx_bandwidth.h"
#define S2_FREQ_MIN RX_FREQ_MIN
#define S2_FREQ_MAX RX_FREQ_MAX
#define S3_FREQ_MIN RX_FREQ_MIN
#define S3_FREQ_MAX RX_FREQ_MAX
#define IQ_WORDS 16380u
#define BURST_SERIAL_UART 1
#define RX_GAIN 0
#define REG_READ(r) 0u
static unsigned frequency_mhz,gain_max=72,gain_code;
static bool rx_ready,hardware_agc;
static int rx_filter;
static char response[256];
#define spectrum_acquire NULL
static bool s31_spectrum_command(const char *s){return false;}
static bool spectrum_command(const char *s,unsigned f,void *acquire){return false;}
static bool ring_test(const char *s){return false;}
static void reply(const char *fmt,...){va_list a;va_start(a,fmt);vsnprintf(response,sizeof(response),fmt,a);va_end(a);}
static int burst_serial_port(void){return 1;}
static unsigned burst_serial_baud(void){return 2000000;}
static bool gain_command(const char *s){return false;}
static bool ring_command(const char *s){return false;}
static bool limits_command(const char *s){return false;}
static bool capture(unsigned n,unsigned d,unsigned f){return true;}
static bool capture_rate(unsigned n,unsigned d,unsigned f){return true;}
static void prepare_rx(void){rx_ready=true;}
static void apply_gain(void){}
static void s31_tune(unsigned f){assert(frequency_mhz==f);}
static void vTaskDelay(unsigned t){}
static unsigned rom_chip_i2c_readReg(unsigned a,unsigned b,unsigned c){return 0;}
static unsigned phy_i2c_readReg(unsigned a,unsigned b,unsigned c){return 0;}
'''
        for target in ['esp32s2','esp32s3','esp32s31']:
            with self.subTest(target=target):
                source=(MAIN/'targets'/target/'receiver.c').read_text()
                name='command' if target=='esp32s31' else 'handle_command'
                handler=source[source.index('static void '+name+'('):source.index('void app_main(')]
                self.compile_run(f'#define CONFIG_IDF_TARGET_{target.upper()} 1\n'+stub+handler+r'''
static void send(const char *s){char line[128];snprintf(line,sizeof(line),"%s",s);HANDLER(line);}
int main(void){
 send("CAPS");assert(strstr(response,"TUNEEXT"));
#if CONFIG_IDF_TARGET_ESP32S31
 assert(strstr(response," SPEC ") && strstr(response," SPECN ") && strstr(response," SPECCAPS "));
#endif
 send("RANGE?");assert(!strcmp(response,"RANGE 100 6000 1\n"));
 for(unsigned f=100;f<=6000;f++){
  char cmd[40];snprintf(cmd,sizeof(cmd),"FREQ %u",f);send(cmd);
  assert(!strcmp(response,"OK\n") && frequency_mhz==f);
 }
 const char *invalid[]={"FREQ 99","FREQ 6001","FREQ 2612.5","FREQ -1","FREQ 2612 junk"};
 for(unsigned j=0;j<sizeof(invalid)/sizeof(invalid[0]);j++){send(invalid[j]);assert(!strcmp(response,"ERR command\n"));}
}
'''.replace('HANDLER',name))
