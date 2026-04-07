from machine import Pin, SPI, PWM
from time import ticks_ms, ticks_diff, sleep_ms, sleep_us
import network
import urequests
import framebuf
import max7219

# ----------------------------
# User settings
# ----------------------------
WIFI_SSID = "STUHI"
WIFI_PASSWORD = "sarcasm-reimburse-attitude-thesaurus-amendable-hunter"
BLYNK_TOKEN = "JZwjwopZMpxZJLJdoQCChbciR2DT8D0P"

BLYNK_URL = "https://blynk.cloud/external/api/get?token={}&V1".format(BLYNK_TOKEN)

LABEL_TEXT = "People here"
LABEL_INTERVAL_MS = 10000
BLYNK_POLL_MS = 1200

LABEL_SCROLL_MS = 40
VALUE_SCROLL_MS = 110

SPEAKER_PIN = 25

# Audio settings
SOUND_IN_FILE = "in.wav"
SOUND_OUT_FILE = "out.wav"
AUDIO_SAMPLE_RATE = 8000
WAV_HEADER_BYTES = 44
PWM_CARRIER_HZ = 40000
PWM_CENTER = 512
AUDIO_GAIN = 320

# Matrix pins:
# GPIO13 -> DIN
# GPIO27 -> CLK
# GPIO26 -> CS

# ----------------------------
# Matrix setup
# ----------------------------
spi = SPI(
    1,
    baudrate=10_000_000,
    polarity=1,
    phase=0,
    sck=Pin(27),
    mosi=Pin(13)
)

cs = Pin(26, Pin.OUT)
display = max7219.Matrix8x8(spi, cs, 1)
display.brightness(15)

# ----------------------------
# Speaker setup
# ----------------------------
speaker = PWM(Pin(SPEAKER_PIN))
speaker.freq(PWM_CARRIER_HZ)
speaker.duty(0)

def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v

def speaker_off():
    speaker.duty(0)
    speaker.freq(PWM_CARRIER_HZ)

def beep(freq, duration_ms, duty=180):
    speaker.freq(freq)
    speaker.duty(duty)
    sleep_ms(duration_ms)
    speaker_off()

def play_wav_pwm(filename, sample_rate=AUDIO_SAMPLE_RATE, gain=AUDIO_GAIN):
    try:
        f = open(filename, "rb")
    except OSError:
        return False

    us_per_sample = int(1000000 / sample_rate)

    try:
        f.seek(WAV_HEADER_BYTES)

        while True:
            data = f.read(128)
            if not data:
                break

            for b in data:
                signed = b - 128
                duty = PWM_CENTER + (signed * gain) // 128
                speaker.duty(clamp(duty, 0, 1023))
                sleep_us(us_per_sample)

        speaker_off()
        return True

    except Exception:
        speaker_off()
        return False

    finally:
        f.close()

def positive_sound():
    if not play_wav_pwm(SOUND_IN_FILE):
        beep(1319, 90, 220)
        sleep_ms(40)
        beep(1760, 130, 220)

def negative_sound():
    if not play_wav_pwm(SOUND_OUT_FILE):
        speaker.freq(1400)
        speaker.duty(220)
        for f in range(1400, 350, -45):
            speaker.freq(f)
            sleep_ms(12)
        speaker_off()

# ----------------------------
# Wi-Fi
# ----------------------------
def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            sleep_ms(300)

    return wlan

# ----------------------------
# Drawing helpers
# ----------------------------
def clear():
    display.fill(0)
    display.show()

def show_text(text):
    display.fill(0)
    display.text(str(text), 0, 0, 1)
    display.show()

def show_rotated_char(ch):
    buf = bytearray(8)
    fb = framebuf.FrameBuffer(buf, 8, 8, framebuf.MONO_HLSB)

    fb.fill(0)
    fb.text(str(ch), 0, 0, 1)

    display.fill(0)
    for y in range(8):
        for x in range(8):
            if fb.pixel(x, y):
                display.pixel(7 - y, x, 1)

    display.show()

def show_bitmap(rows):
    display.fill(0)
    for y in range(8):
        row = rows[y]
        for x in range(8):
            if row & (1 << (7 - x)):
                display.pixel(x, y, 1)
    display.show()

def scroll_text(msg, delay_ms):
    text_width = len(msg) * 8
    for x in range(8, -text_width - 1, -1):
        display.fill(0)
        display.text(msg, x, 0, 1)
        display.show()
        sleep_ms(delay_ms)

def draw_rotated_window(fb, offset):
    display.fill(0)
    for y in range(8):
        for x in range(8):
            if fb.pixel(offset + x, y):
                display.pixel(7 - y, x, 1)
    display.show()

def build_rotated_text_fb(msg):
    src_width = len(msg) * 8 + 16
    buf = bytearray(src_width)
    fb = framebuf.FrameBuffer(buf, src_width, 8, framebuf.MONO_HLSB)
    fb.fill(0)
    fb.text(msg, 8, 0, 1)
    return fb, src_width

def scroll_rotated_text(msg, delay_ms):
    fb, src_width = build_rotated_text_fb(msg)
    for offset in range(src_width - 7):
        draw_rotated_window(fb, offset)
        sleep_ms(delay_ms)

# ----------------------------
# Faces
# ----------------------------
SMILE_FACE = [
    0b00000000,
    0b00100010,
    0b01000000,
    0b01000000,
    0b01000000,
    0b01000000,
    0b00100010,
    0b00000000,
]

SAD_FACE = [
    0b00000000,
    0b01000010,
    0b00100000,
    0b00100000,
    0b00100000,
    0b00100000,
    0b01000010,
    0b00000000,
]

def positive_effect():
    show_bitmap(SMILE_FACE)
    positive_sound()
    sleep_ms(600)
    clear()

def negative_effect():
    show_bitmap(SAD_FACE)
    negative_sound()
    sleep_ms(600)
    clear()

# ----------------------------
# Helpers
# ----------------------------
def show_value(value):
    s = str(value).strip()

    if len(s) <= 1:
        show_rotated_char(s)
    else:
        scroll_text(s, VALUE_SCROLL_MS)

def to_int_or_none(value):
    try:
        return int(str(value).strip())
    except:
        return None

# ----------------------------
# Blynk
# ----------------------------
def get_blynk_v1():
    try:
        r = urequests.get(BLYNK_URL)
        value = r.text.strip()
        r.close()
        return value
    except Exception:
        return None

# ----------------------------
# Main
# ----------------------------
wifi_connect()

current_value = None
last_poll = ticks_ms() - BLYNK_POLL_MS
last_label = ticks_ms()

while True:
    now = ticks_ms()

    if ticks_diff(now, last_poll) >= BLYNK_POLL_MS:
        new_value = get_blynk_v1()
        last_poll = ticks_ms()

        if new_value is not None and new_value != "":
            if current_value is None:
                current_value = new_value
            elif new_value != current_value:
                old_num = to_int_or_none(current_value)
                new_num = to_int_or_none(new_value)

                current_value = new_value

                if old_num is not None and new_num is not None:
                    if new_num > old_num:
                        positive_effect()
                    elif new_num < old_num:
                        negative_effect()
                else:
                    positive_effect()

    now = ticks_ms()
    if ticks_diff(now, last_label) >= LABEL_INTERVAL_MS:
        scroll_rotated_text(LABEL_TEXT, LABEL_SCROLL_MS)
        last_label = ticks_ms()

    if current_value is None:
        show_text("?")
    else:
        show_value(current_value)

    sleep_ms(80)
