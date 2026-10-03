#!/usr/bin/env python3
"""Check delivery files and extract frames from the actual encoded video."""
import json
import struct
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)
    ], text=True))


def fast_start(path):
    """Find top-level MP4 atoms without reading the media payload into memory."""
    atoms = []
    with path.open('rb') as stream:
        while header := stream.read(8):
            size, kind = struct.unpack('>I4s', header)
            header_size = 8
            if size == 1:
                size = struct.unpack('>Q', stream.read(8))[0]
                header_size = 16
            atoms.append(kind)
            if size == 0:
                break
            assert size >= header_size
            stream.seek(size - header_size, 1)
    return atoms.index(b'moov') < atoms.index(b'mdat')


def main():
    timeline = json.loads((ROOT / 'src/generated/timeline.json').read_text())
    files = []
    for name in ('wifi-robocon-short-no-subs.mp4', 'wifi-robocon-short-x-no-subs.mp4'):
        path = OUT / name
        data = probe(path)
        assert not any(s['codec_type'] == 'subtitle' for s in data['streams'])
        assert not any(path.with_suffix('.' + ext).exists() for ext in ('srt', 'vtt', 'ass'))
        video = next(s for s in data['streams'] if s['codec_type'] == 'video')
        audio = next(s for s in data['streams'] if s['codec_type'] == 'audio')
        assert video['codec_name'] == 'h264' and audio['codec_name'] == 'aac'
        assert (video['width'], video['height']) == (1080, 1920)
        assert video['r_frame_rate'] == '30/1'
        assert int(video['nb_frames']) == timeline['durationInFrames']
        assert float(data['format']['duration']) < 60
        assert abs(float(video['duration']) - float(audio['duration'])) < .1
        assert fast_start(path)
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                        '-f', 'null', '-'], check=True)
        files.append({'name': name, 'bytes': path.stat().st_size,
                      'seconds': float(data['format']['duration']), 'full_decode': 'passed',
                      'subtitle_tracks': 0, 'subtitle_sidecars': 0})

    review = OUT / 'final-review'
    review.mkdir(exist_ok=True)
    frames = [('first', 0), ('last', timeline['durationInFrames'] - 1)]
    frames += [(s['id'], s['from'] + int(s['duration'] * .65)) for s in timeline['scenes']]
    sheet = Image.new('RGB', (1080, 640 * 4), '#F3EFE5')
    for index, (name, frame) in enumerate(frames):
        dest = review / f'{name}.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(frame / 30),
                        '-i', str(OUT / files[0]['name']), '-frames:v', '1', str(dest)], check=True)
        picture = Image.open(dest).convert('RGB')
        picture.thumbnail((340, 605))
        x, y = index % 3 * 360 + 10, index // 3 * 640 + 25
        sheet.paste(picture, (x, y))
        ImageDraw.Draw(sheet).text((x, y - 20), f'{name} @ {frame / 30:.2f}s', fill='black')
    sheet.save(review / 'contact.png')

    result = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(OUT / files[0]['name']),
        '-af', 'loudnorm=I=-14:TP=-1.5:LRA=8:print_format=json', '-f', 'null', '-'],
        check=True, capture_output=True, text=True)
    loudness = json.loads(result.stderr[result.stderr.rfind('{'):])
    assert -15 < float(loudness['input_i']) < -13
    assert float(loudness['input_tp']) < -.5
    report = {'files': files, 'encoded_audio_loudness': loudness,
              'review_frames': len(frames), 'contact_sheet': 'final-review/contact.png'}
    (OUT / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
