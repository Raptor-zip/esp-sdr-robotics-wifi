/* Scalar FFT processing for cores without the S3 SIMD kernel. A completed
 * block is copied out of RF SRAM immediately, then processed in short slices
 * across as many bank rotations as necessary. Each frame describes exactly
 * that block; skipped RF time is visible in the sample indices. */
#include "spectrum_math.h"
static struct {
    unsigned phase, half, groups, group, offset, emit, bank, first, unpack;
    uint64_t index;
    uint8_t gain;
} scalar;

static void scalar_accept(unsigned bank, unsigned first, uint64_t index) {
    if(scalar.phase){st.res->abandoned++;return;}
    scalar.index=index;scalar.gain=bank_ptr(bank)[first]>>20;
    scalar.bank=bank;scalar.first=first;scalar.unpack=0;st.work[bank].pending=true;
    scalar.half=spec_n/2;scalar.groups=1;scalar.group=scalar.offset=0;scalar.phase=3;
}
static bool scalar_work(void) {
    if(!scalar.phase)return false;
    uint32_t start=esp_cpu_get_cycle_count();
    if(scalar.phase==3) {
        unsigned end=scalar.unpack+64<spec_n?scalar.unpack+64:spec_n;
        spec_unpack(bank_ptr(scalar.bank),scalar.first,scalar.unpack,end);
        scalar.unpack=end;
        if(end==spec_n){st.work[scalar.bank].pending=false;scalar.phase=1;}
    } else if(scalar.phase==1) {
        for(unsigned budget=0;budget<16 && scalar.half;budget++) {
            unsigned a=scalar.group*scalar.half*2+scalar.offset,b=a+scalar.half;
            int32_t wr=dsps_fft_w_table_sc16[2*scalar.group],wi=dsps_fft_w_table_sc16[2*scalar.group+1];
            int32_t ar=fft_buf[2*a],ai=fft_buf[2*a+1],br=fft_buf[2*b],bi=fft_buf[2*b+1];
            int64_t tr=(int64_t)wr*br+(int64_t)wi*bi,ti=(int64_t)wr*bi-(int64_t)wi*br;
            fft_buf[2*a]=(int16_t)(((int64_t)ar*32767+tr+32767)>>16);
            fft_buf[2*a+1]=(int16_t)(((int64_t)ai*32767+ti+32767)>>16);
            fft_buf[2*b]=(int16_t)(((int64_t)ar*32767-tr+32767)>>16);
            fft_buf[2*b+1]=(int16_t)(((int64_t)ai*32767-ti+32767)>>16);
            if(++scalar.offset==scalar.half) {
                scalar.offset=0;
                if(++scalar.group==scalar.groups){scalar.group=0;scalar.groups*=2;scalar.half/=2;}
            }
        }
        if(!scalar.half){spec_remove_dc();scalar.emit=0;scalar.phase=2;}
    } else {
        unsigned end=scalar.emit+16<spec_n?scalar.emit+16:spec_n;
        for(unsigned k=scalar.emit;k<end;k++) {
            int32_t re=fft_buf[2*k],im=fft_buf[2*k+1];
            uint32_t power=(uint32_t)((int64_t)re*re+(int64_t)im*im);
            frame_out[sizeof(spec_header_t)+bin_of[k]]=spectrum_power_code(power);
        }
        scalar.emit=end;
        if(end==spec_n) {
            ring_result_t *r=st.res;
            spec_header_t h={.magic=SPEC_MAGIC,.frame=r->frames+r->drops,.pair_index=scalar.index,.pairs=spec_n,
                .ffts=1,.flags=(st.cfg->max_hold?1:0)|(st.dropped?4:0)|2,.gain=scalar.gain,
                .drops=r->drops>65535?65535:r->drops,.nfft_log2=spec_log2,.db_step=2};
            memcpy(frame_out,&h,sizeof(h));
            unsigned len=sizeof(h)+spec_n;
            uint32_t crc=esp_rom_crc32_le(0,frame_out,len);memcpy(frame_out+len,&crc,4);
            if(txq_push(frame_out,len+4)){r->frames++;st.last_ok=esp_timer_get_time();st.dropped=false;}
            else{r->drops++;st.dropped=true;}
            r->ffts++;scalar.phase=0;
        }
    }
    uint32_t cycles=esp_cpu_get_cycle_count()-start;
    scalar_telemetry(cycles,scalar.phase==0);
    cycles=esp_cpu_get_cycle_count()-start;
    if(cycles>st.res->work_max)st.res->work_max=cycles;
    return true;
}
