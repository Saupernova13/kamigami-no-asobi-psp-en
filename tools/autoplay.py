"""Play through the story unattended, for screenshots of screens a new game does not reach.

  python tools/autoplay.py --core <ppsspp_libretro.dll> --state story [--steps 150]
                           [--out work/shots/auto] [--every 10] [--prefix a] work/out/en.iso

Start from a state made by tests/setup_skip.txt (Message Skip All, R/START = Auto Skip).
Each step: if the game is in a quiz (screen word 7), circle a few times to answer, then
START (starts the quiz on its title screen; in a question it pauses, and down + circle
resume); a screen left unchanged by the previous step gets the same treatment; otherwise pick a choice (the pick rotates 1st/2nd/3rd so menus that
loop until every option is PASSED move on) and press R to skip to the next choice. A
screenshot <prefix>NNN.png after every step, a state <prefix>NNN every --every steps,
and a log line with the mode word, so a run can be resumed from any saved step.
"""
import argparse
import os
import struct
import sys

import harness

MODE = 0x089a6000     # screen: 6 story and map, 7 quiz (found by diffing RAM dumps)
QUIZ = 7


def mode(r):
    return struct.unpack("<I", r.peek(MODE, 4))[0]


def quiz_step(r):
    for _ in range(4):                  # answer (a no-op on the quiz title screen)
        r.press(["circle"], 8)
        r.run(150)
    r.press(["start"], 8)               # title: start the quiz; question: pause
    r.run(60)
    r.press(["down"], 8)                # pause menu: highlight Resume (no default cursor)
    r.run(30)
    r.press(["circle"], 8)
    r.run(150)


def story_step(r, i, offset=0):
    for _ in range((i + offset) % 3 + 1):
        r.press(["down"], 8)
        r.run(30)
    r.press(["circle"], 8)
    r.run(200)
    r.press(["r"], 8)
    r.run(900)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--core", required=True)
    ap.add_argument("--state", required=True, help="state name in <workdir>/states, or a path")
    ap.add_argument("--workdir", default="work/harness")
    ap.add_argument("--out", default="work/shots/auto")
    ap.add_argument("--steps", type=int, default=150)
    ap.add_argument("--every", type=int, default=10, help="save a state every N steps")
    ap.add_argument("--prefix", default="a")
    ap.add_argument("--pick-offset", type=int, default=0,
                    help="shift the rotating choice pick (1 or 2) to take other routes")
    ap.add_argument("--boot-wait", type=float, default=10.0)
    ap.add_argument("iso")
    a = ap.parse_args()
    system_dir = os.path.join(a.workdir, "system")
    save_dir = os.path.join(a.workdir, "saves")
    state_dir = os.path.join(a.workdir, "states")
    for d in (system_dir, save_dir, state_dir, a.out):
        os.makedirs(d, exist_ok=True)
    r = harness.Runner(a.core, system_dir, save_dir)
    r.load(a.iso, a.boot_wait)
    r.run(1)
    path = a.state if os.path.exists(a.state) else harness.state_path(state_dir, a.state)
    r.load_state(path)
    stuck = 0
    for i in range(1, a.steps + 1):
        m = mode(r)
        before = r.image().tobytes()
        # A step that changed nothing is either a quiz screen the word missed or a menu
        # pick that landed on a PASSED option: alternate quiz presses and the next pick.
        if m == QUIZ or stuck == 1:
            quiz_step(r)
        else:
            story_step(r, i, a.pick_offset)
        stuck = (stuck + 1) % 2 if r.image().tobytes() == before else 0
        name = f"{a.prefix}{i:03d}"
        r.shot(os.path.join(a.out, name + ".png"))
        line = f"{name} mode {m}"
        if i % a.every == 0:
            r.save_state(harness.state_path(state_dir, name))
            line += " saved"
        print(line, flush=True)


if __name__ == "__main__":
    sys.exit(main())
