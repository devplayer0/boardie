import argparse
import os.path
import random

import evdev
import pyaudio
import pydub
import yaml

class Sound:
    def __init__(self, combo, files, bit_depth=16, sample_rate=44100, channels=2):
        keys = []
        for k in combo.upper().split('-'):
            match k:
                case 'SHIFT':
                    k = 'LEFTSHIFT'
            keys.append(evdev.ecodes.ecodes[f'KEY_{k}'])
        self.held = set(keys[:-1])
        self.key = keys[-1]

        self.sounds = []
        for fname in files:
            self.sounds.append((
                fname,
                pydub.AudioSegment.from_file(fname)
                    .set_sample_width(bit_depth // 8)
                    .set_frame_rate(sample_rate)
                    .set_channels(channels)
                    .normalize()))

        self.active = None

    def stop(self):
        self.active = None

    def play(self):
        name, self.active = random.choice(self.sounds)
        print(f'Playing {name}')

    def next_chunk(self, frame_count):
        if not self.active:
            return pydub.AudioSegment.silent(0)

        chunk = self.active.get_sample_slice(end_sample=frame_count)
        self.active = self.active.get_sample_slice(start_sample=frame_count)
        if self.active.frame_count == 0:
            self.active = None
        return chunk

class Boardie:
    bit_depth = 16
    channels = 2

    def __init__(self, config_file, device, audio_device=None):
        self.config_file = config_file
        self.sounds = []

        self.device = evdev.InputDevice(device)
        self.device.grab()

        self.pa = pyaudio.PyAudio()
        dev_info = self.pa.get_device_info_by_index(audio_device)
        self.sample_rate = int(dev_info['defaultSampleRate'])
        self.stream = self.pa.open(
            output_device_index=audio_device,
            format=self.pa.get_format_from_width(self.bit_depth // 8),
            rate=self.sample_rate,
            channels=self.channels,
            output=True,
            stream_callback=self._acallback)

        self.reload()

    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, tb):
        for s in self.sounds:
            s.stop()

        self.stream.close()
        self.pa.terminate()

        self.device.ungrab()
        self.device.close()

    def reload(self):
        print('Loading config')
        for s in self.sounds:
            s.stop()

        with open(self.config_file) as f:
            data = yaml.full_load(f)

        dir_ = data['dir']
        self.sounds = []
        for combo, fnames in data['sounds'].items():
            if not isinstance(fnames, list):
                fnames = [fnames]
            files = list(map(lambda f: os.path.join(dir_, f), fnames))
            self.sounds.append(Sound(
                combo, files,
                bit_depth=self.bit_depth, sample_rate=self.sample_rate, channels=self.channels))

    def _acallback(self, _in_data, frame_count, time_info, status):
        seg = pydub.AudioSegment(
            data=frame_count * self.channels * (self.bit_depth // 2) * b'\0',
            frame_rate=self.sample_rate,
            sample_width=self.bit_depth // 8,
            channels=self.channels)

        for s in self.sounds:
            seg = seg.overlay(s.next_chunk(frame_count))

        return seg.raw_data, pyaudio.paContinue

    def run(self):
        for ev in self.device.read_loop():
            if ev.type != evdev.ecodes.EV_KEY:
                continue
            ev = evdev.categorize(ev)
            if ev.keystate != ev.key_down:
                continue

            held = set(self.device.active_keys()) & {evdev.ecodes.KEY_LEFTSHIFT, evdev.ecodes.KEY_LEFTCTRL}
            if ev.scancode == evdev.ecodes.KEY_ESC:
                if evdev.ecodes.KEY_LEFTSHIFT in held:
                    self.reload()
                else:
                    for s in self.sounds:
                        s.stop()
                continue
            for s in self.sounds:
                if ev.scancode == s.key and s.held == held:
                    s.play()
                    break

def main():
    parser = argparse.ArgumentParser(
        'boardie', description='Linux soundboard',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-a', '--audio-device', help='Audio device to use, pass ? to list')
    parser.add_argument('-f', '--config', help='Config file', default='boardie.yaml')
    parser.add_argument('device', help='Keyboard event device')

    args = parser.parse_args()
    if args.audio_device == '?':
        pa = pyaudio.PyAudio()
        apis = []
        for i in range(pa.get_host_api_count()):
            apis.append(pa.get_host_api_info_by_index(i)['name'])
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info['maxOutputChannels'] == 0:
                continue

            print(f"{info['index']}: ({apis[info['hostApi']]}) {info['name']}")
        return

    audio_dev = int(args.audio_device) if args.audio_device is not None else None
    with Boardie(args.config, args.device, audio_device=audio_dev) as boardie:
        boardie.run()
