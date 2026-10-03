"""Portrait Manim diagrams; measured SDR images are composed separately."""
import json
from pathlib import Path
from manim import *
import numpy as np

config.pixel_width=1080
config.pixel_height=1920
config.frame_width=10
config.frame_height=160/9
config.frame_rate=30
config.background_color='#FFFDF8'
BLUE='#2167AD'; GREEN='#38754B'; RED='#CC4935'; GOLD='#A76B14'; MUTED='#71736C'; INK='#242721'
FONT='Noto Sans CJK JP'


def label(s,size=40,color=INK):
    return Text(s,font=FONT,font_size=size,color=color,weight=BOLD)


def tag(s,color=BLUE,size=36):
    t=label(s,size,color)
    r=RoundedRectangle(width=t.width+.45,height=t.height+.3,corner_radius=.1,
        stroke_color=color,stroke_opacity=.7,fill_color=color,fill_opacity=.07)
    return VGroup(r,t)


def robot():
    body=RoundedRectangle(width=2,height=1.1,corner_radius=.14,stroke_color=BLUE,
        fill_color='#E5EEF4',fill_opacity=1)
    wheels=VGroup(*[RoundedRectangle(width=.45,height=.4,corner_radius=.08,
        fill_color='#E0E7E5',fill_opacity=1,stroke_color=BLUE).move_to([x,-.65,0]) for x in (-.65,.65)])
    eyes=VGroup(*[Circle(radius=.12,fill_color=GREEN,fill_opacity=1,stroke_width=0).move_to([x,.12,0]) for x in (-.4,.4)])
    lidar=VGroup(Rectangle(width=.7,height=.18,fill_color=BLUE,fill_opacity=.7,stroke_width=0).shift(UP*.7),Line([0,.6,0],[0,1,0],color=BLUE))
    return VGroup(body,wheels,eyes,lidar)


def ap():
    body=RoundedRectangle(width=2.1,height=.7,corner_radius=.13,fill_color='#EAF0E2',fill_opacity=1,stroke_color=GREEN)
    poles=VGroup(*[Line([x,.15,0],[x,1,0],color=GREEN,stroke_width=7) for x in (-.8,.8)])
    return VGroup(body,poles,*[Dot([x,-.02,0],color=GREEN,radius=.07) for x in (-.5,0,.5)])


def axes_at(y,minimum=2410,maximum=2480):
    ax=Axes(x_range=[minimum,maximum,10],y_range=[0,1,.5],x_length=8.6,y_length=1.7,
        axis_config={'color':MUTED,'include_tip':False},y_axis_config={'include_ticks':False})
    ax.shift(UP*(y-ax.c2p(minimum,0)[1]))
    numbers=VGroup(*[label(str(f),27,MUTED).move_to(ax.c2p(f,0)+DOWN*.4) for f in range(minimum,maximum+1,10)])
    return ax,numbers


def band(ax,lo,hi,color,height=1.8):
    left,right=ax.c2p(lo,0),ax.c2p(hi,0)
    return Polygon(left,left+UP*height*.55,left+RIGHT*.18+UP*height,
        right+LEFT*.18+UP*height,right+UP*height*.55,right,
        stroke_color=color,stroke_width=5,fill_color=color,fill_opacity=.25)


class RadioField(Scene):
    def construct(self):
        phone=VGroup(RoundedRectangle(width=1.3,height=2.1,corner_radius=.16,stroke_color=BLUE,
            fill_color='#E5EEF4',fill_opacity=1),Circle(radius=.16,stroke_color=BLUE).shift(DOWN*.7)).move_to([0,4.6,0])
        router=ap().move_to([0,.2,0]);bot=robot().move_to([0,-4.4,0])
        route1=Arrow([0,3.3,0],[0,1.5,0],color=BLUE,buff=.05,stroke_width=7)
        route2=Arrow([0,-.5,0],[0,-3,0],color=BLUE,buff=.05,stroke_width=7)
        texts=VGroup(label('コントローラー',38).move_to([0,6.3,0]),label('AP',42,GREEN).move_to([-2.4,.2,0]),label('ロボット',42).move_to([0,-6,0]))
        self.add(phone,router,bot,route1,route2,texts)
        payload=tag('映像・点群・指令',BLUE,34).move_to([0,7.5,0]);self.add(payload)
        for i in range(3):
            packets=VGroup(*[Square(side_length=.28,fill_color=c,fill_opacity=1,stroke_width=0).move_to([.45*j-.45,3.15,0]) for j,c in enumerate((BLUE,GREEN,GOLD))])
            self.add(packets)
            self.play(packets.animate.move_to([0,1.4,0]),run_time=.35,rate_func=linear)
            self.play(packets.animate.move_to([0,-2.8,0]),run_time=.55,rate_func=linear)
            self.remove(packets)
        enemy=tag('他チーム',RED,32).move_to([2.8,-1.7,0])
        waves=VGroup(*[Arc(radius=r,start_angle=2.1,angle=1.8,color=RED,stroke_width=7).move_to([1.5,-2.5,0]) for r in (.45,.85,1.25)])
        self.play(FadeIn(enemy),LaggedStart(*[Create(w) for w in waves],lag_ratio=.18),run_time=.7)
        self.play(Indicate(bot,color=RED,scale_factor=1.1),run_time=.5)
        self.wait(.45)


class SensorPipeline(Scene):
    def construct(self):
        chip=RoundedRectangle(width=4.4,height=1.4,corner_radius=.12,fill_color='#EAF0E2',fill_opacity=1,stroke_color=GREEN)
        chip.move_to([0,6.5,0]);name=label('ESP32-C5',60,GREEN).move_to(chip)
        pins=VGroup(*[Line([x,5.65,0],[x,5.95,0],color=GREEN,stroke_width=6) for x in np.linspace(-1.8,1.8,9)])
        self.add(chip,name,pins)
        waveaxes=Axes(x_range=[0,2*PI,PI],y_range=[-1,1,1],x_length=4.7,y_length=1,
            axis_config={'include_tip':False,'color':'#D2D7D2'})
        a=waveaxes.copy().move_to([.7,4.45,0]);b=waveaxes.copy().move_to([.7,2.8,0])
        i=a.plot(lambda x:np.cos(x),color=BLUE,stroke_width=6);q=b.plot(lambda x:np.sin(x),color=GREEN,stroke_width=6)
        self.add(a,b,label('I',47,BLUE).move_to([-2.7,4.45,0]),label('Q',47,GREEN).move_to([-2.7,2.8,0]))
        self.play(Create(i),Create(q),run_time=.75)
        samples=VGroup(*[Dot(a.c2p(x,np.cos(x)),radius=.06,color=RED) for x in np.linspace(0,2*PI,12)])
        self.play(LaggedStart(*[FadeIn(d) for d in samples],lag_ratio=.06),run_time=.6)
        fft=tag('I/Q → FFT',BLUE,43).move_to([0,.95,0]);self.play(FadeIn(fft),run_time=.45)
        for k in range(3):
            dot=Dot(a.c2p(0,1),radius=.12,color=RED)
            qdot=Dot(b.c2p(0,0),radius=.12,color=GOLD);self.add(dot,qdot)
            self.play(MoveAlongPath(dot,i),MoveAlongPath(qdot,q),run_time=.55,rate_func=linear)
            self.remove(dot,qdot)
        targets=VGroup(*[Dot(fft.get_top()+RIGHT*(j-5.5)*.15,radius=.045,color=BLUE) for j in range(12)])
        self.play(Transform(samples,targets),Indicate(fft,color=BLUE,scale_factor=1.04),run_time=.65)
        self.wait(1.7)


class ChannelOverlap(Scene):
    def construct(self):
        ax,ticks=axes_at(-3.2);self.add(ax,ticks)
        own=band(ax,2427,2447,BLUE,2.6);other=band(ax,2432,2452,RED,2.6)
        self.add(tag('自チーム Ch6',BLUE).move_to([-2.1,6.6,0]),tag('他チーム Ch7',RED).move_to([2.1,6.6,0]))
        width=VGroup(Line([-3.3,4.7,0],[-.84,4.7,0],color=BLUE,stroke_width=18),Line([-2.69,3.6,0],[-.23,3.6,0],color=RED,stroke_width=18))
        self.play(Create(width),run_time=.55)
        self.add(label('幅 20 MHz',50,BLUE).move_to([0,5.6,0]))
        center=VGroup(DashedLine([-2.07,3.25,0],[-2.07,4.95,0],color=GOLD),DashedLine([-1.46,3.25,0],[-1.46,4.95,0],color=GOLD))
        self.play(Create(center),run_time=.35)
        delta=DoubleArrow([-2.07,2.6,0],[-1.46,2.6,0],buff=0,color=GOLD,stroke_width=5)
        self.play(GrowArrow(delta),FadeIn(label('中心の差は5 MHz',47,GOLD).move_to([0,1.65,0])),run_time=.4)
        self.play(DrawBorderThenFill(own),run_time=.6);self.play(DrawBorderThenFill(other),run_time=.6)
        overlap=band(ax,2432,2447,GOLD,2.6).set_stroke(width=0).set_fill(opacity=.42)
        self.play(FadeIn(overlap),run_time=.35)
        brace=DoubleArrow(ax.c2p(2432,0)+DOWN*1.25,ax.c2p(2447,0)+DOWN*1.25,color=RED,buff=0,stroke_width=5)
        self.play(GrowArrow(brace),FadeIn(label('15 MHzが重なる',49,RED).move_to([0,-6.3,0])),run_time=.4)
        self.add(label('周波数 [MHz]',31,MUTED).move_to([2.6,-4.1,0]))
        for _ in range(3):
            self.play(overlap.animate.set_fill(opacity=.63),run_time=.4)
            self.play(overlap.animate.set_fill(opacity=.32),run_time=.4)
        self.wait(.7)


class LatencyBars(Scene):
    def construct(self):
        metrics=json.loads((Path(__file__).resolve().parents[1]/'src/generated/metrics.json').read_text())
        self.add(label('他チーム負荷による追加遅延',42).move_to([0,2.8,0]),label('RTT p99差 [ms]',38,MUTED).move_to([0,1.8,0]))
        bars=[]
        for index,(m,color,title) in enumerate(zip(metrics,(RED,GOLD,GREEN),('同一 Ch6','隣接 Ch7','分離 Ch11'))):
            y=.1-index*2.1
            self.add(label(title,40,color).move_to([-2.75,y+.65,0]))
            track=RoundedRectangle(width=5,height=.6,corner_radius=.08,fill_color='#E7E4DC',fill_opacity=1,stroke_width=0).move_to([-.8,y-.3,0]);self.add(track)
            value=ValueTracker(0);left=track.get_left()
            bar=always_redraw(lambda v=value,c=color,l=left:Rectangle(width=max(.02,v.get_value()/23*5),height=.6,fill_color=c,fill_opacity=1,stroke_width=0).move_to(l+RIGHT*max(.02,v.get_value()/23*5)/2))
            number=DecimalNumber(0,num_decimal_places=0,include_sign=True,mob_class=Text,font_size=68,color=color).move_to([2.8,y-.3,0])
            number.add_updater(lambda obj,v=value:obj.set_value(v.get_value()))
            self.add(bar,number);bars.append((value,m['increase']))
        self.wait(2.5)
        for value,target in bars:self.play(value.animate.set_value(target),run_time=.6,rate_func=smooth)
        total=label('分離後の総RTT p99',38,GREEN).move_to([0,-6.0,0]);num=label(f'約{metrics[-1]["after"]:.0f} ms',61,GREEN).move_to([0,-7.1,0])
        self.play(FadeIn(total),FadeIn(num),run_time=.4)
        self.wait(2.7)


class Bandwidth(Scene):
    def construct(self):
        a,at=axes_at(2.9,2390,2460);b,bt=axes_at(-2.1,2390,2460)
        own=band(a,2427,2447,BLUE,2);other=band(b,2402,2422,GREEN,2)
        self.add(a,b,at,bt,tag('自チーム Ch6',BLUE).move_to([0,6.6,0]),label('20 MHz',47,BLUE).move_to([0,5.55,0]))
        other_tag=tag('他チーム Ch1',GREEN).move_to([0,1.15,0]);self.add(other_tag)
        self.play(DrawBorderThenFill(own),DrawBorderThenFill(other),run_time=.65)
        width=label('20 MHz',58,GREEN).move_to([0,-3.65,0]);self.add(width);self.wait(.8)
        wider=band(b,2402,2442,RED,2)
        self.play(Transform(other,wider),Transform(width,label('40 MHz',58,RED).move_to(width)),
            Transform(other_tag,tag('他チーム Ch1＋副Ch5',RED,32).move_to(other_tag)),run_time=1.0)
        region=Rectangle(width=(2442-2427)/70*8.6,height=7.0,fill_color=GOLD,fill_opacity=.14,stroke_color=GOLD,stroke_opacity=.5)
        region.move_to([(a.c2p(2427,0)[0]+a.c2p(2442,0)[0])/2,1.1,0]);self.play(FadeIn(region),run_time=.45)
        self.add(label('Ch1 ＋ 副Ch5',36,RED).move_to([0,-4.6,0]))
        result=label('遅延は単純には増えず',43,INK).move_to([0,-6.7,0])
        self.play(Indicate(region,color=GOLD,scale_factor=1.03),FadeIn(result),run_time=.8)
        self.wait(1.4)


class QueueSplit(Scene):
    def construct(self):
        self.add(tag('指令',GREEN,40).move_to([-2.8,6.6,0]),tag('映像・点群',BLUE,40).move_to([1.7,6.6,0]))
        track=VGroup(Line([-2.8,5.6,0],[-2.8,.2,0],color='#D2D7D2',stroke_width=5),Line([1.7,5.6,0],[1.7,-2.5,0],color='#D2D7D2',stroke_width=5))
        self.add(track)
        packets=VGroup(*[RoundedRectangle(width=2.4,height=1.1,corner_radius=.1,fill_color=BLUE,fill_opacity=.22,stroke_color=BLUE).move_to([1.7,4.9-i*1.4,0]) for i in range(4)])
        payloads=VGroup(*[label('画像' if i%2==0 else '点群',35,BLUE).move_to(packet) for i,packet in enumerate(packets)])
        command=VGroup(Square(side_length=.8,fill_color=GREEN,fill_opacity=1,stroke_width=0),label('指令',27,WHITE)).move_to([-2.8,4.8,0])
        gate=Line([-.1,-2.75,0],[3.5,-2.75,0],color=RED,stroke_width=9)
        route=Arrow([-2.8,.1,0],[.25,-2.1,0],color=GREEN,stroke_width=5,buff=.1)
        self.add(gate,route)
        self.play(LaggedStart(*[FadeIn(p) for p in packets],lag_ratio=.1),FadeIn(payloads),FadeIn(command),run_time=.5)
        self.play(command.animate.move_to([-2.8,.5,0]),run_time=.6,rate_func=linear)
        self.play(command.animate.move_to([.2,-2.15,0]),run_time=.6,rate_func=linear)
        waiting=tag('送信待ち',RED,42).move_to([-2.5,-3.65,0]);self.play(FadeIn(waiting),run_time=.3)
        for _ in range(3):
            self.play(packets.animate.shift(DOWN*.17),payloads.animate.shift(DOWN*.17),Indicate(command,color=RED,scale_factor=1.1),run_time=.5)
        self.add(label('共通の送信経路',35,MUTED).move_to([1.6,-3.55,0]))
        bot=robot().scale(.9).move_to([1.7,-6,0]);self.play(FadeIn(bot),run_time=.35)
        self.play(Indicate(bot,color=RED),run_time=.55)
        self.wait(.4)


class RadioProtocols(Scene):
    def construct(self):
        self.add(tag('ESP-NOW：固定チャネル',GREEN,40).move_to([0,7.2,0]))
        upper=VGroup(*[RoundedRectangle(width=2.1,height=.9,corner_radius=.1,stroke_color='#BDC8CC').move_to([x,5.6,0]) for x in (-2.7,0,2.7)])
        captions=VGroup(*[label(t,32,MUTED).move_to(rect) for t,rect in zip(('Ch1','Ch6','Ch11'),upper)])
        selected=upper[1].copy().set_fill(GREEN,opacity=.22).set_stroke(GREEN,width=5)
        self.add(upper,captions,selected)
        self.add(tag('BLE接続データ：ホッピング',BLUE,37).move_to([0,3.6,0]))
        freqs=[f for f in range(2404,2480,2) if f!=2426]
        xs=np.array([(f-2404)/(2478-2404)*8.4-4.2 for f in freqs])
        boxes=VGroup(*[RoundedRectangle(width=.18,height=1,corner_radius=.025,stroke_color='#BDC8CC',stroke_width=2).move_to([x,2,0]) for x in xs])
        low=(2427-2404)/74*8.4-4.2;high=(2447-2404)/74*8.4-4.2
        wifi=Rectangle(width=high-low,height=1.6,fill_color=RED,fill_opacity=.12,stroke_color=RED,stroke_opacity=.5).move_to([(low+high)/2,2,0])
        self.add(boxes,wifi,label('Wi-Fi Ch6の帯域',31,RED).move_to([0,.75,0]))
        self.add(label('2404',26,MUTED).move_to([-4,1.12,0]),label('2478 MHz',26,MUTED).move_to([3.75,1.12,0]))
        hop=RoundedRectangle(width=.17,height=.96,corner_radius=.03,fill_color=BLUE,fill_opacity=1,stroke_width=0).move_to(boxes[0])
        self.add(hop)
        for i in (9,28,15,3,22,35,12,30,7,18,32,16,26,2,20,11,34,5):
            self.play(hop.animate.move_to(boxes[i]),selected.animate.set_fill(GREEN,opacity=.42),run_time=.18)
            self.play(selected.animate.set_fill(GREEN,opacity=.22),run_time=.08)
        self.wait(1.6)


class Sampling(Scene):
    def construct(self):
        self.add(tag('50 ms間隔で取得する例',BLUE,40).move_to([0,6.8,0]))
        line=Line([-4.1,4.3,0],[4.1,4.3,0],color=MUTED,stroke_width=5)
        windows=VGroup(*[Rectangle(width=.055,height=1.0,fill_color=GREEN,fill_opacity=1,stroke_width=0).move_to([x,4.3,0]) for x in (-3.7,0,3.7)])
        self.add(line,windows,label('記録',37,GREEN).move_to([-3.7,5.4,0]))
        gap=DoubleArrow([-3.65,3.25,0],[-.05,3.25,0],buff=0,color=RED,stroke_width=5)
        gap_text=label('約49.8 msは未記録',43,RED).move_to([0,2.25,0]).set_z_index(5)
        gap_bg=BackgroundRectangle(gap_text,color=config.background_color,fill_opacity=1,buff=.12).set_z_index(4)
        self.add(label('1行 ≈ 205 µs',55,GREEN).move_to([0,-5.9,0]))
        self.play(GrowArrow(gap),FadeIn(gap_bg),FadeIn(gap_text),run_time=.45)
        rows=VGroup(*[Rectangle(width=7.4,height=.65,fill_color=BLUE,fill_opacity=.36,stroke_color=BLUE,stroke_width=2).move_to([0,-1.3-i*.85,0]) for i in range(4)])
        for i in range(3):
            arrow=Arrow(windows[i].get_bottom(),rows[i].get_top()+RIGHT*(i-1)*2.4,color=GREEN,stroke_width=4,buff=.15)
            self.play(Indicate(windows[i],color=GREEN,scale_factor=1.6),GrowArrow(arrow),run_time=.35)
            self.play(FadeIn(rows[i],shift=DOWN*.15),run_time=.2)
        self.play(FadeIn(rows[3]),run_time=.25)
        self.wait(.95)
