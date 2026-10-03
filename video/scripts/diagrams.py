"""Manim concept animations, separate from the measured SDR imagery."""
from manim import *
import numpy as np

config.pixel_width=1080
config.pixel_height=900
config.frame_width=10
config.frame_height=25/3
config.frame_rate=30
config.background_color='#FFFDF8'

BLUE='#2167AD'; GREEN='#38754B'; RED='#CC4935'; GOLD='#A76B14'; MUTED='#71736C'; INK='#242721'
FONT='Noto Sans CJK JP'


def label(s,size=30,color=INK):
    return Text(s,font=FONT,font_size=size,color=color,weight=BOLD)


def tag(s,color=BLUE):
    t=label(s,26,color);r=RoundedRectangle(width=t.width+.5,height=.55,corner_radius=.12,
                 stroke_color=color,stroke_opacity=.7,fill_color=color,fill_opacity=.09)
    return VGroup(r,t)


def robot(color=BLUE):
    body=RoundedRectangle(width=1.5,height=.8,corner_radius=.14,stroke_color=color,
                          fill_color='#E5EEF4',fill_opacity=1)
    wheels=VGroup(*[RoundedRectangle(width=.35,height=.35,corner_radius=.08,
                         fill_color='#E0E7E5',fill_opacity=1,stroke_color=color).move_to([x,-.48,0]) for x in (-.5,.5)])
    eye=VGroup(*[Circle(radius=.09,fill_color=GREEN,fill_opacity=1,stroke_width=0).move_to([x,.12,0]) for x in (-.3,.3)])
    lidar=VGroup(Rectangle(width=.6,height=.14,fill_color=color,fill_opacity=.6,stroke_width=0).move_to([0,.5,0]),
                 Line([0,.43,0],[0,.8,0],color=color))
    return VGroup(body,wheels,eye,lidar)


def ap():
    body=RoundedRectangle(width=1.6,height=.55,corner_radius=.13,fill_color='#EAF0E2',fill_opacity=1,stroke_color=GREEN)
    poles=VGroup(*[Line([x,.15,0],[x,.8,0],color=GREEN,stroke_width=6) for x in (-.6,.6)])
    return VGroup(body,poles,*[Dot([x,-.02,0],color=GREEN,radius=.045) for x in (-.35,0,.35)])


class RadioField(Scene):
    def construct(self):
        phone=VGroup(RoundedRectangle(width=.9,height=1.5,corner_radius=.14,stroke_color=BLUE,
                   fill_color='#E5EEF4',fill_opacity=1),Circle(radius=.12,stroke_color=BLUE).shift(DOWN*.45)).move_to([-3.2,0,0])
        router=ap().move_to([0,0,0]);bot=robot().move_to([3.1,0,0])
        text=VGroup(label('コントローラー',26).move_to([-3.2,-1.25,0]),label('AP',30,GREEN).move_to([0,-1.25,0]),
                    label('ロボット',28).move_to([3.1,-1.25,0]))
        a1=Arrow([-2.5,0,0],[-1.0,0,0],color=BLUE,buff=.05)
        a2=Arrow([1,0,0],[2.2,0,0],color=BLUE,buff=.05)
        title=tag('映像・点群・指令を同じWi-Fiへ',BLUE).move_to([0,2.25,0])
        # Begin with the complete route so the first frame is useful as a cover.
        self.add(phone,router,bot,text,a1,a2,title)
        self.wait(.6)
        for i in range(3):
            packet=Square(side_length=.2,fill_color=GREEN,fill_opacity=1,stroke_width=0).move_to([-2.4,0,0])
            self.add(packet)
            self.play(packet.animate.move_to([-1.0,0,0]),run_time=.22,rate_func=linear)
            self.play(packet.animate.move_to([2.2,0,0]),run_time=.35,rate_func=linear)
            self.remove(packet)
        enemy=tag('他チームも通信中',RED).move_to([0,1.15,0]);self.play(FadeIn(enemy),run_time=.25)
        waves=VGroup(*[Arc(radius=r,start_angle=.3,angle=2.5,color=RED,stroke_width=5).move_to([2,1.2,0]) for r in (.4,.75,1.1)])
        self.play(LaggedStart(*[Create(w) for w in waves],lag_ratio=.15),bot.animate.shift(RIGHT*.13),run_time=.6)
        self.play(Indicate(bot,color=RED,scale_factor=1.04),run_time=.4)
        self.wait(.4)


def frequency_axis(scene,minimum=2410,maximum=2480):
    ax=Axes(x_range=[minimum,maximum,10],y_range=[0,1.3,.5],x_length=8.6,y_length=2.4,
            axis_config={'color':MUTED,'include_tip':False},y_axis_config={'include_ticks':False}).shift(DOWN*.4)
    scene.add(ax)
    ticks=VGroup(*[label(str(f),22,MUTED).move_to(ax.c2p(f,0)+DOWN*.35) for f in range(minimum,maximum+1,10)])
    scene.add(ticks,label('周波数 [MHz]',24,MUTED).move_to([2.7,-2.65,0]))
    return ax


def band(ax,low,high,color,height=1.3):
    left,right=ax.c2p(low,0),ax.c2p(high,0)
    points=[left,left+UP*height*.85,left+RIGHT*.16+UP*height*1.6,
            right+LEFT*.16+UP*height*1.6,right+UP*height*.85,right,left]
    area=Polygon(*points,stroke_color=color,stroke_width=4,fill_color=color,fill_opacity=.23)
    return area


class ChannelOverlap(Scene):
    def construct(self):
        ax=frequency_axis(self)
        own=band(ax,2427,2447,BLUE);other=band(ax,2432,2452,RED)
        l1=tag('自チーム Ch6',BLUE).move_to([-2.25,2.8,0]);l2=tag('他チーム Ch7',RED).move_to([2.2,2.8,0])
        self.play(FadeIn(l1),FadeIn(l2),DrawBorderThenFill(own),run_time=.65)
        self.play(DrawBorderThenFill(other),run_time=.55)
        inter=band(ax,2432,2447,GOLD).set_stroke(width=0).set_fill(opacity=.36)
        centers=VGroup(*[DashedLine(ax.c2p(x,0),ax.c2p(x,0)+UP*2.85,color=GOLD,stroke_width=2) for x in (2437,2442)])
        shift=DoubleArrow(ax.c2p(2437,0)+UP*2.85,ax.c2p(2442,0)+UP*2.85,buff=0,color=GOLD)
        shiftlabel=label('中心の差 5 MHz',34,GOLD).move_to([0,1.6,0])
        widthlabel=label('幅は20 MHz',36,BLUE).move_to([-2.2,.75,0])
        self.play(FadeIn(inter),Create(centers),GrowArrow(shift),FadeIn(shiftlabel),FadeIn(widthlabel),run_time=.5)
        self.wait(.8)
        note=label('重なる部分は15 MHz',38,RED).move_to([0,-3.45,0])
        self.play(FadeIn(note,shift=UP*.15),run_time=.3)
        self.wait(3.5)


class Bandwidth(Scene):
    def construct(self):
        ax=frequency_axis(self,2390,2460)
        own=band(ax,2427,2447,BLUE);other=band(ax,2402,2422,GREEN)
        labels=VGroup(tag('自チーム Ch6 / 20 MHz',BLUE).move_to([0,2.9,0]),
                      tag('他チーム Ch1 / 20 MHz',GREEN).move_to([0,2.05,0]))
        self.play(FadeIn(labels),DrawBorderThenFill(own),DrawBorderThenFill(other),run_time=.6)
        self.wait(.65)
        newlabel=tag('他チーム Ch1＋副Ch5 / 40 MHz',RED).move_to([0,2.05,0])
        self.play(Transform(other,band(ax,2402,2442,RED)),Transform(labels[1],newlabel),run_time=.9)
        inter=band(ax,2427,2442,GOLD).set_stroke(width=0).set_fill(opacity=.3)
        self.play(FadeIn(inter),run_time=.25)
        self.wait(1.2)
        note=label('重なりは増加 ≠ 遅延が必ず悪化',29,GOLD).move_to([0,1.03,0]);self.play(FadeIn(note),run_time=.3)
        self.wait(1.9)


class QueueSplit(Scene):
    def construct(self):
        self.add(tag('端末処理・送信待ちも原因候補',BLUE).move_to([0,2.7,0]))
        tracks=VGroup(*[Line([-4,y,0],[4,y,0],color='#D1D7D1',stroke_width=4) for y in (.6,-.9)])
        self.play(Create(tracks),run_time=.4)
        images=VGroup(*[RoundedRectangle(width=.95,height=.95,corner_radius=.08,fill_color=BLUE,
                   fill_opacity=.25,stroke_color=BLUE).move_to([x,.6,0]) for x in (-2.8,-1.7,-.6,.5)])
        captions=VGroup(*[label('画像',22,BLUE).move_to(p.get_center()) for p in images])
        critical=VGroup(Square(side_length=.55,fill_color=GREEN,fill_opacity=.9,stroke_color=GREEN),
                        label('指令',21,WHITE)).move_to([-3.0,-.9,0])
        gate=Line([1.45,-1.8,0],[1.45,1.5,0],color=RED,stroke_width=9)
        self.play(LaggedStart(*[FadeIn(p) for p in images],lag_ratio=.15),FadeIn(captions),FadeIn(critical),Create(gate),run_time=.7)
        wait=label('送信待ち',38,RED).move_to([2.85,-.9,0]);self.play(critical.animate.move_to([.9,-.9,0]),FadeIn(wait),run_time=.8)
        for p,c in zip(images,captions):
            self.play(p.animate.shift(RIGHT*.65),c.animate.shift(RIGHT*.65),run_time=.17)
        self.play(Indicate(critical,color=RED),run_time=.45)
        self.wait(.6)
        note=label('チャネル分離だけでは解消しない',31,GOLD).move_to([0,-2.65,0]);self.play(FadeIn(note),run_time=.25)
        self.wait(.7)


class RadioProtocols(Scene):
    def construct(self):
        top=tag('ESP-NOW：固定チャネル',GREEN).move_to([0,2.9,0])
        bottom=tag('BLE接続データ：ホッピング',BLUE).move_to([0,-.1,0])
        self.play(FadeIn(top),FadeIn(bottom),run_time=.35)
        xs=np.linspace(-3.8,3.8,12)
        upper=VGroup(*[RoundedRectangle(width=.52,height=1,corner_radius=.08,stroke_color='#BCC9D2',stroke_opacity=.8).move_to([x,1.55,0]) for x in xs])
        lower=upper.copy().shift(DOWN*3)
        self.add(upper,lower)
        wifi=Rectangle(width=3.2,height=1.35,fill_color=RED,fill_opacity=.15,stroke_color=RED,stroke_opacity=.45).move_to([0,-1.45,0])
        wn=label('Wi-Fiの帯域',25,RED).move_to([0,-2.6,0]);self.add(wifi,wn)
        fixed=RoundedRectangle(width=.5,height=.96,corner_radius=.08,fill_color=GREEN,fill_opacity=.85,stroke_width=0).move_to(upper[5].get_center())
        hop=RoundedRectangle(width=.35,height=.95,corner_radius=.08,fill_color=BLUE,fill_opacity=.85,stroke_width=0).move_to(lower[0].get_center())
        self.play(FadeIn(fixed),FadeIn(hop),run_time=.3)
        for i in [3,9,5,1,7,10,4,8,2,6,11,5]:
            self.play(hop.animate.move_to(lower[i].get_center()),Indicate(fixed,scale_factor=1.08),run_time=.22)
        note=label('37チャネルから選択（図は一部）',26,MUTED).move_to([0,-3.4,0]);self.play(FadeIn(note),run_time=.3)
        self.wait(2.8)


class Sampling(Scene):
    def construct(self):
        self.add(tag('50 ms間隔で取得する例',BLUE).move_to([0,2.8,0]))
        line=Line([-4,1.45,0],[4,1.45,0],color=MUTED,stroke_width=4)
        windows=VGroup(*[Rectangle(width=.045,height=.7,fill_color=GREEN,fill_opacity=1,stroke_width=0).move_to([x,1.45,0]) for x in (-3.5,0,3.5)])
        self.play(Create(line),FadeIn(windows),run_time=.4)
        self.add(label('記録',25,GREEN).move_to([-3.5,2.1,0]))
        rows=VGroup(*[Rectangle(width=5.4,height=.28,fill_color=BLUE,fill_opacity=.5,stroke_color=BLUE,stroke_width=1).move_to([0,-.9-i*.34,0]) for i in range(4)])
        arrows=VGroup(*[Arrow(windows[i].get_bottom(),rows[i].get_top()+RIGHT*(i-1)*1.8,color=GREEN,stroke_width=2,buff=.1) for i in range(3)])
        self.play(LaggedStart(*[FadeIn(row,shift=DOWN*.15) for row in rows],lag_ratio=.2),run_time=.5)
        self.play(LaggedStart(*[GrowArrow(a) for a in arrows],lag_ratio=.1),run_time=.6)
        gap=label('約49.8 msは未記録',34,RED).move_to([0,.65,0])
        self.add(BackgroundRectangle(gap,color=config.background_color,fill_opacity=1,buff=.08),gap)
        self.add(label('1行 ≈ 205 µsの受信記録',32,GREEN).move_to([0,-2.65,0]))
        self.wait(1.7)
