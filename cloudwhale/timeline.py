"""Shared timeline for «Облачный кит» (The Cloud Whale).

Single source of truth for shot boundaries and sound-sync events: picture and
sound both import this module. Times are seconds unless a name says frames.
"""

FPS = 24
W, H = 1920, 804
N_FRAMES = 1440            # 60.0 s
DURATION = N_FRAMES / FPS
SAMPLE_RATE = 48000

# Music grid: 3/4 waltz at 90 BPM -> one bar = 2.0 s = 48 frames, 30 bars.
BPM = 90
BEATS_PER_BAR = 3
BAR_SEC = 2.0


def f2t(frame):
    return frame / FPS


def t2f(t):
    return int(round(t * FPS))


SHOTS = [
    # name, start frame, end frame (exclusive), what we see
    ("s1_establish", 0, 192,
     "Fade in. Wide summer landscape: deep blue sky, towering cumulus, rolling hills "
     "with wind waves in the grass, a lone big tree on a hill. Slow camera tilt down "
     "from the sky to the land."),
    ("s2_run", 192, 384,
     "Side tracking shot: the girl in a coral-red sundress and straw hat runs left->right "
     "through tall grass. Foreground grass whips past."),
    ("s3_hilltop", 384, 528,
     "She runs into frame, slows and stops on the hilltop by the big tree. A strong gust "
     "from behind: grass waves, the tree rustles, her straw hat lifts off and flies away "
     "up-right."),
    ("s4_closeup", 528, 624,
     "Close-up, low angle: her face looking up-right at the sky, wind in her hair. "
     "She blinks; wide-eyed wonder."),
    ("s5_hat_sky", 624, 720,
     "The hat tumbles upward through the sky; the camera tilts up after it past clouds."),
    ("s6_whale", 720, 912,
     "A huge cumulus awakens: a giant gentle whale made of cloud. Its eye opens, it glides "
     "out of the cloud bank; the hat settles on its head."),
    ("s7_below", 912, 1152,
     "Wide from the hillside: the tiny girl under the tree looks up as the whale crosses "
     "the sky, its shadow sweeping the hills. The whale breathes out a puff of mist; the "
     "hat slides off and drifts down, spiralling."),
    ("s8_catch", 1152, 1296,
     "Medium side shot: the hat floats down into her raised hands. She puts it on, smiles "
     "and waves to the sky."),
    ("s9_sunset", 1296, 1440,
     "Golden sunset: hill, tree and girl in silhouette, the whale far off among pink-gold "
     "clouds. Title «Облачный кит» appears. Fade to black."),
]

# Sound-sync events (seconds).
EVENTS = {
    "fade_in": (0.0, 1.5),
    "fade_out": (58.5, 60.0),
    "wind_chime": [1.2, 5.0],
    "birds": [2.4, 3.3, 6.2],
    # S2 run: foot contacts every 8 frames (3 steps/s = 2 per beat), alternating, right first.
    "run_footfalls": [f2t(f) for f in range(196, 384, 8)],
    # S3: decelerating steps, then feet come together.
    "stop_footfalls": [f2t(f) for f in (388, 397, 407, 418)],
    "stop_feet_together": f2t(426),
    "gust": (18.6, 19.5, 21.5),          # start, peak, end
    "hat_lift_off": 19.5,
    "close_up_blink": 23.6,
    "hat_whoosh_sky": [26.3, 28.2],
    "whale_shimmer": 31.0,               # magic shimmer as the cloud awakens
    "whale_eye_open": 31.5,
    "whale_call_1": (32.0, 35.0),
    "hat_lands_on_whale": 35.5,
    "whale_blow": 41.5,                  # the whale breathes out a puff of mist
    "whale_call_2": (42.0, 44.5),
    "hat_drift_down": (42.0, 47.5),
    "hat_catch": 50.0,
    "hat_put_on": 51.0,
    "wave": (51.8, 54.0),
    "evening_cicadas": [54.4, 57.0],     # higurashi calls at dusk
    "title_in": (55.5, 56.8),
}
