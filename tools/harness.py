"""Headless PSP runner: drives the PPSSPP libretro core with scripted input and saves
screenshots, so text changes can be checked without a GPU or a desktop window.

The core falls back to its software renderer when the frontend declines a hardware
context, which is what this frontend does.

Input script (one step per line, '#' comments):
  wait N                  run N frames with no input
  press BTN [BTN..] [N]   hold buttons for N frames (default 4), then release for 4
  shot NAME               save the current frame as NAME.png
  repeat K press ...      repeat a press K times
  save NAME / load NAME   save or restore an emulator state (<workdir>/states/NAME.state)
  poke ADDR VAL [SIZE]    write VAL (hex) to RAM at ADDR (hex), SIZE bytes little endian
  peek ADDR [SIZE]        print SIZE bytes of RAM at ADDR
  dump NAME               write all of RAM to <out>/NAME.ram (diff two dumps to find flags)
Buttons: circle cross square triangle start select up down left right l r;
analog stick: sleft sright sup sdown
"""
import argparse
import ctypes as C
import os
import shutil
import sys
import time

from PIL import Image

ENV_SET_PIXEL_FORMAT = 10
ENV_GET_SYSTEM_DIRECTORY = 9
ENV_GET_VARIABLE = 15
ENV_GET_VARIABLE_UPDATE = 17
ENV_GET_LOG_INTERFACE = 27
ENV_GET_SAVE_DIRECTORY = 31
ENV_GET_CAN_DUPE = 3
ENV_GET_CORE_OPTIONS_VERSION = 52
ENV_GET_INPUT_BITMASKS = 51 | 0x10000

PIXFMT_0RGB1555, PIXFMT_XRGB8888, PIXFMT_RGB565 = 0, 1, 2

RETRO_MEMORY_SYSTEM_RAM = 2
RAM_BASE = 0x08000000      # PPSSPP exposes PSP RAM from the kernel base

# libretro joypad ids; PPSSPP maps A->circle, B->cross, X->triangle, Y->square
BUTTONS = {"cross": 0, "square": 1, "select": 2, "start": 3, "up": 4, "down": 5,
           "left": 6, "right": 7, "circle": 8, "triangle": 9, "l": 10, "r": 11}
# analog stick directions: (axis, value)
STICK = {"sleft": (0, -0x7FFF), "sright": (0, 0x7FFF), "sup": (1, -0x7FFF), "sdown": (1, 0x7FFF)}

OPTIONS = {
    b"ppsspp_software_rendering": b"enabled",
    b"ppsspp_internal_resolution": b"480x272",
    b"ppsspp_frameskip": b"0",
    b"ppsspp_fast_memory": b"enabled",
    b"ppsspp_cpu_core": b"JIT",
    b"ppsspp_language": b"Japanese",
    b"ppsspp_button_preference": b"Circle",
}


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


class Variable(C.Structure):
    _fields_ = [("key", C.c_char_p), ("value", C.c_char_p)]


ENV_CB = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO_CB = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO_CB = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDIO_BATCH_CB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL_CB = C.CFUNCTYPE(None)
STATE_CB = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
# retro_log_printf_t is variadic; on the Win64 ABI variadic args arrive like normal ones, so
# taking a fixed set of pointer-sized slots and handing them to snprintf recovers the text.
LOG_CB = C.CFUNCTYPE(None, C.c_int, C.c_char_p, *([C.c_void_p] * 8))
try:
    _snprintf = C.cdll.msvcrt._snprintf
except (AttributeError, OSError):
    _snprintf = None


class LogInterface(C.Structure):
    _fields_ = [("log", LOG_CB)]


class Runner:
    def __init__(self, core, system_dir, save_dir, verbose=False):
        self.core = C.CDLL(core)
        self.system_dir = os.path.abspath(system_dir).encode()
        self.save_dir = os.path.abspath(save_dir).encode()
        self.verbose = verbose
        self.pixfmt = PIXFMT_0RGB1555
        self.frame = None
        self.held = set()
        self._keep = []
        self._opt_bufs = {k: C.c_char_p(v) for k, v in OPTIONS.items()}
        cbs = [
            ("retro_set_environment", ENV_CB(self._env)),
            ("retro_set_video_refresh", VIDEO_CB(self._video)),
            ("retro_set_audio_sample", AUDIO_CB(lambda l, r: None)),
            ("retro_set_audio_sample_batch", AUDIO_BATCH_CB(lambda d, n: n)),
            ("retro_set_input_poll", POLL_CB(lambda: None)),
            ("retro_set_input_state", STATE_CB(self._input)),
        ]
        for name, cb in cbs:
            self._keep.append(cb)
            getattr(self.core, name)(cb)
        self._log = LogInterface(LOG_CB(self._logmsg))
        self.core.retro_init()

    def _logmsg(self, level, fmt, *args):
        if not self.verbose:
            return
        text = fmt
        if _snprintf is not None:
            buf = C.create_string_buffer(4096)
            _snprintf(buf, 4095, fmt, *[C.c_void_p(a) for a in args])
            text = buf.value
        sys.stderr.write(f"[core {level}] {text.decode(errors='replace')}")

    def _env(self, cmd, data):
        cmd &= 0xFFFF | 0x10000
        if cmd == ENV_SET_PIXEL_FORMAT:
            self.pixfmt = C.cast(data, C.POINTER(C.c_int))[0]
            return True
        if cmd in (ENV_GET_SYSTEM_DIRECTORY, ENV_GET_SAVE_DIRECTORY):
            C.cast(data, C.POINTER(C.c_char_p))[0] = self.system_dir if cmd == ENV_GET_SYSTEM_DIRECTORY else self.save_dir
            return True
        if cmd == ENV_GET_VARIABLE:
            var = C.cast(data, C.POINTER(Variable))[0]
            v = self._opt_bufs.get(var.key)
            if v is None:
                return False
            C.cast(data, C.POINTER(Variable))[0].value = v.value
            return True
        if cmd == ENV_GET_VARIABLE_UPDATE:
            C.cast(data, C.POINTER(C.c_bool))[0] = False
            return True
        if cmd == ENV_GET_CAN_DUPE:
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        if cmd == ENV_GET_LOG_INTERFACE:
            C.cast(data, C.POINTER(LogInterface))[0] = self._log
            return True
        if cmd == ENV_GET_INPUT_BITMASKS:
            return True
        if cmd == ENV_GET_CORE_OPTIONS_VERSION:
            C.cast(data, C.POINTER(C.c_uint))[0] = 0
            return True
        return False

    def _video(self, data, w, h, pitch):
        if not data or data == C.c_void_p(-1).value:
            return
        # copy now (the buffer is only valid during the callback), convert on demand
        self.frame = (C.string_at(data, pitch * h), w, h, pitch)

    def _input(self, port, device, index, button_id):
        if port != 0:
            return 0
        if device == 5:  # RETRO_DEVICE_ANALOG: index 0 = left stick, id 0 = x, 1 = y
            if index != 0:
                return 0
            return sum(v for b, (axis, v) in STICK.items() if b in self.held and axis == button_id)
        if device != 1:
            return 0
        pad = [b for b in self.held if b in BUTTONS]
        if button_id == 256:  # RETRO_DEVICE_ID_JOYPAD_MASK
            return sum(1 << BUTTONS[b] for b in pad)
        return int(any(BUTTONS[b] == button_id for b in pad))

    def load(self, iso, boot_wait=10.0):
        self._iso = os.path.abspath(iso).encode()
        info = GameInfo(self._iso, None, 0, None)
        self.core.retro_load_game.argtypes = [C.POINTER(GameInfo)]
        if not self.core.retro_load_game(C.byref(info)):
            raise RuntimeError("core refused the game")
        av = (C.c_byte * 256)()
        self.core.retro_get_system_av_info(av)
        self.core.retro_set_controller_port_device(0, 1)
        # PPSSPP 1.17's software context swaps buffers while the async loader is still
        # booting and dereferences the not-yet-created GPU; let the boot finish first.
        time.sleep(boot_wait)

    def run(self, frames):
        for _ in range(frames):
            self.core.retro_run()

    def press(self, buttons, hold=4, release=4):
        self.held = set(buttons)
        self.run(hold)
        self.held = set()
        self.run(release)

    def image(self):
        if self.frame is None:
            raise RuntimeError("no frame rendered yet")
        raw, w, h, pitch = self.frame
        if self.pixfmt == PIXFMT_XRGB8888:
            img = Image.frombuffer("RGBX", (w, h), raw, "raw", "BGRX", pitch, 1)
        else:
            img = Image.frombuffer("RGB", (w, h), raw, "raw", "BGR;16", pitch, 1)
        return img.convert("RGB")

    def shot(self, path):
        self.image().save(path)

    def save_state(self, path):
        self.core.retro_serialize_size.restype = C.c_size_t
        n = self.core.retro_serialize_size()
        buf = C.create_string_buffer(n)
        if not self.core.retro_serialize(buf, C.c_size_t(n)):
            raise RuntimeError("core could not save a state")
        with open(path, "wb") as f:
            f.write(buf.raw)

    def load_state(self, path):
        with open(path, "rb") as f:
            data = f.read()
        if not self.core.retro_unserialize(data, C.c_size_t(len(data))):
            raise RuntimeError(f"core refused the state {path}")

    def ram(self):
        """-> ctypes byte array over PSP RAM, index 0 = address RAM_BASE."""
        self.core.retro_get_memory_data.restype = C.c_void_p
        self.core.retro_get_memory_size.restype = C.c_size_t
        base = self.core.retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM)
        size = self.core.retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM)
        if not base or not size:
            raise RuntimeError("core exposes no system RAM")
        return (C.c_ubyte * size).from_address(base)

    def poke(self, addr, value, size=1):
        mem = self.ram()
        off = addr - RAM_BASE
        for i in range(size):
            mem[off + i] = (value >> (8 * i)) & 0xFF

    def peek(self, addr, size=4):
        mem = self.ram()
        off = addr - RAM_BASE
        return bytes(mem[off:off + size])


def state_path(statedir, name):
    return os.path.join(statedir, name + ".state")


def run_script(r, script, outdir, statedir):
    for raw in script.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        times = 1
        if parts[0] == "repeat":
            times, parts = int(parts[1]), parts[2:]
        for _ in range(times):
            cmd, args = parts[0], parts[1:]
            if cmd == "wait":
                r.run(int(args[0]))
            elif cmd == "press":
                hold = int(args[-1]) if args[-1].isdigit() else 4
                r.press([a for a in args if not a.isdigit()], hold)
            elif cmd == "shot":
                r.shot(os.path.join(outdir, args[0] + ".png"))
                print("shot", args[0], flush=True)
            elif cmd == "save":
                r.save_state(state_path(statedir, args[0]))
                print("saved", args[0], flush=True)
            elif cmd == "load":
                r.load_state(state_path(statedir, args[0]))
            elif cmd == "poke":
                size = int(args[2]) if len(args) > 2 else 1
                r.poke(int(args[0], 16), int(args[1], 16), size)
            elif cmd == "peek":
                size = int(args[1]) if len(args) > 1 else 4
                print("peek", args[0], r.peek(int(args[0], 16), size).hex(" "), flush=True)
            elif cmd == "dump":
                with open(os.path.join(outdir, args[0] + ".ram"), "wb") as f:
                    f.write(bytes(r.ram()))
                print("dumped", args[0], flush=True)
            else:
                raise ValueError(f"bad script line: {raw}")


def prepare_system_dir(system_dir, ppsspp_assets):
    dst = os.path.join(system_dir, "PPSSPP")
    if not os.path.isdir(dst) and ppsspp_assets and os.path.isdir(ppsspp_assets):
        shutil.copytree(ppsspp_assets, dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--core", required=True, help="path to ppsspp_libretro.dll/.so")
    ap.add_argument("--assets", help="PPSSPP assets folder to seed <system>/PPSSPP")
    ap.add_argument("--workdir", default="work/harness")
    ap.add_argument("--out", default="work/shots")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--fresh", action="store_true",
                    help="delete <workdir>/saves first (the game autosaves its settings there)")
    ap.add_argument("--state", help="start from this saved state (a name in <workdir>/states or a path)")
    ap.add_argument("--boot-wait", type=float, default=10.0,
                    help="seconds to let the async loader finish before the first frame")
    ap.add_argument("iso")
    ap.add_argument("script", help="input script file")
    a = ap.parse_args()
    system_dir = os.path.join(a.workdir, "system")
    save_dir = os.path.join(a.workdir, "saves")
    state_dir = os.path.join(a.workdir, "states")
    if a.fresh and os.path.isdir(save_dir):
        shutil.rmtree(save_dir)
    for d in (system_dir, save_dir, state_dir, a.out):
        os.makedirs(d, exist_ok=True)
    prepare_system_dir(system_dir, a.assets)
    r = Runner(a.core, system_dir, save_dir, a.verbose)
    r.load(a.iso, a.boot_wait)
    if a.state:
        r.run(1)
        r.load_state(a.state if os.path.exists(a.state) else state_path(state_dir, a.state))
    with open(a.script) as f:
        run_script(r, f.read(), a.out, state_dir)


if __name__ == "__main__":
    sys.exit(main())
