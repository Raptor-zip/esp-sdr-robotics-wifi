"""Numeric regression checks for the sliced FFT and wire power conversion."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class SpectrumMath(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'Host C compiler unavailable')
    def test_sliced_fft_complex_tones_and_power_quantization(self):
        source = r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#include <stdlib.h>
#define SPEC_MAGIC 0x31435053u
static unsigned spec_n=256, spec_log2=8;
static int16_t fft_buf[512], coefficients[1024];
static int16_t *dsps_fft_w_table_sc16=coefficients;
static uint16_t bin_of[256];
static uint8_t frame_out[288];
typedef struct __attribute__((packed)) {
 uint32_t magic,frame;uint64_t pair_index;uint32_t pairs;
 uint16_t ffts;uint8_t flags,gain;uint16_t drops;uint8_t nfft_log2,db_step;
} spec_header_t;
static struct {unsigned abandoned,frames,drops,ffts,work_max;} result;
static struct {bool max_hold;} config;
static struct {typeof(result)*res;typeof(config)*cfg;struct{bool pending;}work[3];bool dropped;uint64_t last_ok;}st={.res=&result,.cfg=&config};
typedef typeof(result) ring_result_t;
static uint32_t bank[256];
static const uint32_t *bank_ptr(unsigned b){return bank;}
static void spec_unpack(const uint32_t*p,unsigned f,unsigned a,unsigned b){}
static void spec_remove_dc(void){}
static unsigned esp_cpu_get_cycle_count(void){return 0;}
static unsigned esp_timer_get_time(void){return 0;}
static unsigned esp_rom_crc32_le(unsigned c,const void*p,unsigned n){return 0;}
static bool txq_push(const void*p,unsigned n){return true;}
#define scalar_telemetry(cycles,complete) ((void)0)
#include "ring_scalar.h"
static unsigned rev(unsigned x,unsigned bits){unsigned r=0;while(bits--){r=r*2+(x&1);x>>=1;}return r;}
int main(void){
 for(unsigned j=0;j<512;j++){
  unsigned k=rev(j,9);
  coefficients[2*j]=(int16_t)(32767*cos(2*M_PI*k/1024));
  coefficients[2*j+1]=(int16_t)(32767*sin(2*M_PI*k/1024));
 }
 for(unsigned j=0;j<256;j++)bin_of[j]=rev(j,8);
 const int tones[]={1,17,63,-23,-120};
 for(unsigned t=0;t<sizeof(tones)/sizeof(*tones);t++){
  for(unsigned j=0;j<256;j++){
   fft_buf[2*j]=(int16_t)lrint(12000*cos(2*M_PI*tones[t]*j/256));
   fft_buf[2*j+1]=(int16_t)lrint(12000*sin(2*M_PI*tones[t]*j/256));
  }
  memset(&scalar,0,sizeof(scalar));scalar.phase=1;scalar.half=128;scalar.groups=1;
  unsigned slices=0;while(scalar_work())assert(++slices<1000);
  unsigned peak=0;for(unsigned j=1;j<256;j++)if(frame_out[28+j]>frame_out[28+peak])peak=j;
  assert(peak==(unsigned)((tones[t]+256)%256));
  assert(abs((int)frame_out[28+peak]-(int)lrint(20*log10(12000.0*12000)))<=1);
  for(unsigned j=0;j<256;j++)if(j!=peak)assert(frame_out[28+j]+80<frame_out[28+peak]);
 }
 assert(spectrum_power_code(0)==0);
 for(uint64_t p=1;p<=UINT32_MAX;p=p*103/100+1){
  int expected=(int)lrint(20*log10((double)p));if(expected>255)expected=255;
  assert(abs((int)spectrum_power_code(p)-expected)<=1);
 }
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'numeric.c';src.write_text(source)
            exe=Path(tmp)/'numeric'
            subprocess.run(['cc','-std=gnu11','-O2','-I'+str(ROOT/'main/common'),str(src),'-lm','-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    @unittest.skipUnless(shutil.which('cc'), 'Host C compiler unavailable')
    def test_dc_tracker_preserves_changes_and_bounds_hann_correction(self):
        source = r'''
#include "spectrum_dc.h"
#include <assert.h>
#include <string.h>
unsigned spectrum_dc_mode=1;
int main(void) {
 for(unsigned n=256;n<=2048;n*=2) {
  spectrum_dc_t dc={0};int16_t x[4096]={0};
  x[0]=1000;x[1]=-800;x[n]=-500;x[n+1]=400;x[2*n-2]=-500;x[2*n-1]=400;
  spectrum_dc_apply(&dc,x,n);
  for(unsigned j=0;j<2*n;j++)assert(x[j]==0);
  x[0]=2000;x[1]=-1600;x[8]=1234;x[9]=-2345;
  spectrum_dc_apply(&dc,x,n);
  assert(x[0]>900 && x[1]<-700);assert(x[8]==1234 && x[9]==-2345);
  for(unsigned k=0;k<1024;k++){memset(x,0,sizeof(x));x[0]=2000;x[1]=-1600;spectrum_dc_apply(&dc,x,n);}
  assert(x[0]>=-1 && x[0]<=1);assert(x[1]>=-1 && x[1]<=1);
  spectrum_dc_mode=0;memset(x,0,sizeof(x));x[0]=32767;x[1]=-32768;x[n]=32767;x[n+1]=-32768;
  spectrum_dc_apply(&dc,x,n);assert(x[0]==0 && x[1]==0);assert(x[n]==32767 && x[n+1]==-32768);
  spectrum_dc_mode=1;
 }
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'dc.c';src.write_text(source)
            exe=Path(tmp)/'dc'
            subprocess.run(['cc','-std=c11','-O2','-fsanitize=undefined','-I'+str(ROOT/'main/common'),str(src),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
