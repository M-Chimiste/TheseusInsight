import os
import math
import random
import numpy as np
import pygame
from pydub import AudioSegment
from moviepy import VideoClip, AudioFileClip

# --------------------------------------------------------------------
# 1) COLOR PARSING: Accept (R,G,B) tuples or hex strings
# --------------------------------------------------------------------
def parse_color(c):
    """
    Parses a color c, which can be:
      - An (R,G,B) tuple of ints 0-255, or
      - A hex string in formats: "#RRGGBB", "#RGB", "0xRRGGBB", "RRGGBB", "RGB"
    Returns an (r, g, b) tuple.
    """
    if isinstance(c, tuple) and len(c) == 3:
        return c
    if isinstance(c, str):
        c = c.strip().lower()
        if c.startswith('#'):
            c = c[1:]
        elif c.startswith('0x'):
            c = c[2:]
        if len(c) == 3:
            r = int(c[0]*2, 16)
            g = int(c[1]*2, 16)
            b = int(c[2]*2, 16)
            return (r, g, b)
        elif len(c) == 6:
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
            return (r, g, b)
        else:
            raise ValueError(f"Invalid hex color length for string '{c}'")
    raise ValueError(f"Invalid color format: {c}. Must be (R,G,B) or a hex string like '#RRGGBB'.")

# --------------------------------------------------------------------
# 2) AUDIO LOADING (MP3 or WAV)
# --------------------------------------------------------------------
def load_audio_wave_data(filepath):
    """
    Loads audio data from:
      - WAV (via wave module) if extension is .wav
      - MP3 or other ffmpeg‑supported formats (via pydub) otherwise.
    Returns (audio_array as float32 in [-1,1], framerate).
    """
    import wave
    ext = os.path.splitext(filepath.lower())[1]
    if ext == ".wav":
        with wave.open(filepath, 'rb') as wf:
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_data = wf.readframes(n_frames)
            if sample_width == 2:
                dtype = np.int16
            elif sample_width == 4:
                dtype = np.int32
            else:
                raise ValueError(f"Unsupported sample width: {sample_width}")
            audio_array = np.frombuffer(raw_data, dtype=dtype)
            if num_channels > 1:
                audio_array = audio_array[0::num_channels]
    else:
        audio_segment = AudioSegment.from_file(filepath)
        framerate = audio_segment.frame_rate
        audio_segment = audio_segment.set_channels(1)
        samples = audio_segment.get_array_of_samples()
        audio_array = np.array(samples)
    audio_array = audio_array.astype(np.float32)
    mx = np.max(np.abs(audio_array))
    if mx > 0:
        audio_array /= mx
    return audio_array, framerate

# --------------------------------------------------------------------
# 3) RANDOM UNICODE CHAR: Use half‑width Katakana (U+FF66 to U+FF9D)
# --------------------------------------------------------------------
def random_unicode_char():
    """
    Returns a random character from the half‑width Katakana range (U+FF66–U+FF9D).
    This range produces interesting symbols and avoids the boxes seen with some fonts.
    """
    return chr(random.randint(0xFF66, 0xFF9D))

# --------------------------------------------------------------------
# 4) FADECHAR (TRAILING CHARACTER)
# --------------------------------------------------------------------
class FadeChar:
    """
    A trailing character that fades from alpha=255 at birth to 0 at birth_time + life_time.
    """
    def __init__(self, char, x, y, birth_time, life_time=5.0):
        self.char = char
        self.x = x
        self.y = y
        self.birth_time = birth_time
        self.life_time = life_time

    def alpha(self, now):
        age = now - self.birth_time
        fade = 1.0 - (age / self.life_time)
        if fade < 0:
            fade = 0
        return int(255 * fade)

    def is_dead(self, now):
        return (now - self.birth_time) > self.life_time

# --------------------------------------------------------------------
# 5) DISCRETE HEAD: Moves in discrete steps (one char height per step).
#    Each step spawns the old character behind it and picks a new one.
#    The head is drawn with a glow in head_color.
#    A sawtooth modulation is applied to the head’s brightness.
# --------------------------------------------------------------------
class DiscreteHead:
    def __init__(self, x, birth_time, font, head_color=(0,255,0), tail_color=(0,180,0),
                 char_height=20, head_step_time=0.3, head_glow_passes=3, head_glow_alpha_decay=50,
                 random_x_jitter=3.0, fade_time=5.0, head_saw_period=0.5):
        self.x = x
        self.y = 0.0
        self.birth_time = birth_time
        self.time_since_step = 0.0
        self.head_step_time = head_step_time

        self.font = font
        self.head_color = head_color
        self.tail_color = tail_color
        self.char_height = char_height
        self.head_glow_passes = head_glow_passes
        self.head_glow_alpha_decay = head_glow_alpha_decay
        self.random_x_jitter = random_x_jitter
        self.fade_time = fade_time

        self.head_saw_period = head_saw_period

        self.current_char = random_unicode_char()
        self.trail_chars = []
        self.y_index = 0

    def update(self, dt, now):
        self.time_since_step += dt
        while self.time_since_step >= self.head_step_time:
            self.time_since_step -= self.head_step_time
            self.do_step(now)
        self.trail_chars = [c for c in self.trail_chars if not c.is_dead(now)]

    def do_step(self, now):
        fc = FadeChar(self.current_char,
                      self.x + random.uniform(-self.random_x_jitter, self.random_x_jitter),
                      self.y,
                      now,
                      life_time=self.fade_time)
        self.trail_chars.append(fc)
        self.current_char = random_unicode_char()
        self.y += self.char_height
        self.y_index += 1

    def offscreen(self, screen_height):
        return self.y > screen_height + 2 * self.char_height

    def draw(self, surface, now):
        for c in self.trail_chars:
            a = c.alpha(now)
            if a > 0:
                surf = self.font.render(c.char, True, self.tail_color)
                surf.set_alpha(a)
                surface.blit(surf, (c.x, c.y))
        # Compute a sawtooth factor based on time so that brightness resets every head_saw_period.
        saw_factor = 1 - (((now - self.birth_time) % self.head_saw_period) / self.head_saw_period)
        head_surf_orig = self.font.render(self.current_char, True, self.head_color)
        for gp in range(self.head_glow_passes):
            base_alpha = 255 - gp * self.head_glow_alpha_decay
            if base_alpha < 0:
                base_alpha = 0
            # Apply the sawtooth modulation:
            alpha_val = int(base_alpha * saw_factor)
            head_surf = pygame.Surface(head_surf_orig.get_size(), pygame.SRCALPHA)
            head_surf.blit(head_surf_orig, (0, 0))
            head_surf.set_alpha(alpha_val)
            surface.blit(head_surf, (self.x, self.y))

# --------------------------------------------------------------------
# 6) MATRIX COLUMN: Spawns multiple discrete heads.
# --------------------------------------------------------------------
class DiscreteMatrixColumn:
    def __init__(self, x, screen_height, font, head_color=(0,255,0), tail_color=(0,180,0),
                 char_height=20, head_step_time=0.3, random_x_jitter=3.0, fade_time=5.0,
                 head_glow_passes=3, head_glow_alpha_decay=50, head_spawn_delay_range=(2.0,5.0),
                 head_saw_period=0.5):
        self.x = x
        self.screen_height = screen_height
        self.font = font
        self.head_color = head_color
        self.tail_color = tail_color
        self.char_height = char_height
        self.head_step_time = head_step_time
        self.random_x_jitter = random_x_jitter
        self.fade_time = fade_time
        self.head_glow_passes = head_glow_passes
        self.head_glow_alpha_decay = head_glow_alpha_decay
        self.head_spawn_delay_range = head_spawn_delay_range
        self.head_saw_period = head_saw_period

        self.heads = []
        self.last_head_time = 0.0
        self.next_head_delay = random.uniform(*head_spawn_delay_range)

    def update(self, dt, now):
        if (now - self.last_head_time) >= self.next_head_delay:
            self.spawn_head(now)
        alive_heads = []
        for h in self.heads:
            h.update(dt, now)
            if not h.offscreen(self.screen_height):
                alive_heads.append(h)
        self.heads = alive_heads

    def spawn_head(self, now):
        h = DiscreteHead(self.x, now, self.font,
                         head_color=self.head_color,
                         tail_color=self.tail_color,
                         char_height=self.char_height,
                         head_step_time=self.head_step_time,
                         head_glow_passes=self.head_glow_passes,
                         head_glow_alpha_decay=self.head_glow_alpha_decay,
                         random_x_jitter=self.random_x_jitter,
                         fade_time=self.fade_time,
                         head_saw_period=self.head_saw_period)
        self.heads.append(h)
        self.last_head_time = now
        self.next_head_delay = random.uniform(*self.head_spawn_delay_range)

    def draw(self, surface, now):
        for h in self.heads:
            h.draw(surface, now)

# --------------------------------------------------------------------
# 7) NEON WAVE VISUALIZER: Combines discrete matrix columns with a neon wave.
# --------------------------------------------------------------------
class NeonWaveVisualizer:
    def __init__(self, audio_path, resolution=(1280,720), fps=30,
                 # matrix parameters:
                 matrix_count=8,
                 matrix_head_color=(0,255,0),
                 matrix_tail_color=(0,180,0),
                 matrix_char_size=24,
                 head_step_time=0.3,
                 random_x_jitter=3.0,
                 fade_time=5.0,
                 head_glow_passes=3,
                 head_glow_alpha_decay=50,
                 head_spawn_delay_range=(2.0,5.0),
                 head_saw_period=0.5,
                 # wave parameters:
                 wave_color=(0,255,128),
                 trail_colors=[(0,192,96),(0,128,64),(0,64,32)],
                 glow_passes=3,
                 glow_alpha_decay=40,
                 line_width=3,
                 # font:
                 font_path=None):
        self.width, self.height = resolution
        self.fps = fps
        self.line_width = line_width

        pygame.init()
        pygame.display.set_mode((1,1), 0, 32)
        self.surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        self.audio_data, self.framerate = load_audio_wave_data(audio_path)
        self.audio_duration = len(self.audio_data) / float(self.framerate)

        if font_path is not None:
            self.font = pygame.font.Font(font_path, matrix_char_size)
        else:
            self.font = pygame.font.Font(None, matrix_char_size)
        char_height = self.font.get_height()

        self.columns = []
        for _ in range(matrix_count):
            x_pos = random.randint(0, self.width-1)
            col = DiscreteMatrixColumn(x_pos, self.height, self.font,
                                       head_color=matrix_head_color,
                                       tail_color=matrix_tail_color,
                                       char_height=char_height,
                                       head_step_time=head_step_time,
                                       random_x_jitter=random_x_jitter,
                                       fade_time=fade_time,
                                       head_glow_passes=head_glow_passes,
                                       head_glow_alpha_decay=head_glow_alpha_decay,
                                       head_spawn_delay_range=head_spawn_delay_range,
                                       head_saw_period=head_saw_period)
            self.columns.append(col)

        self.wave_color = wave_color
        self.trail_colors = trail_colors
        self.glow_passes = glow_passes
        self.glow_alpha_decay = glow_alpha_decay

        self.prev_time = 0.0

    def make_frame(self, t):
        dt = t - self.prev_time
        if dt < 0:
            dt = 0
        self.prev_time = t

        self.surface.fill((0,0,0,255))
        for col in self.columns:
            col.update(dt, t)
            col.draw(self.surface, t)
        self.draw_wave(t)
        frame = pygame.surfarray.array3d(self.surface)
        frame = np.swapaxes(frame, 0, 1)
        return frame

    def draw_wave(self, t):
        samples_per_frame = int(self.framerate / self.fps)
        audio_index = int(t * self.framerate)

        wave_indices = np.linspace(audio_index, audio_index + samples_per_frame,
                                   self.width, endpoint=False).astype(np.int32)
        wave_indices = np.clip(wave_indices, 0, len(self.audio_data)-1)
        wave_chunk = self.audio_data[wave_indices]

        center_y = self.height // 2
        amplitude = (self.height // 2) * 0.8

        wave_points = []
        for x in range(self.width):
            sample_val = wave_chunk[x]
            y = center_y - int(sample_val * amplitude)
            wave_points.append((x, y))

        for gp in range(self.glow_passes):
            alpha_val = 255 - gp * self.glow_alpha_decay
            if alpha_val < 0:
                alpha_val = 0
            wave_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.lines(wave_surf, self.wave_color + (alpha_val,), False, wave_points, self.line_width)
            self.surface.blit(wave_surf, (0, 0))

        for i, color in enumerate(self.trail_colors):
            shift = (i+1) * samples_per_frame * 0.02
            wave_indices_trail = np.linspace(audio_index - shift, audio_index - shift + samples_per_frame,
                                               self.width, endpoint=False).astype(np.int32)
            wave_indices_trail = np.clip(wave_indices_trail, 0, len(self.audio_data)-1)
            wave_chunk_trail = self.audio_data[wave_indices_trail]
            points_trail = []
            for x in range(self.width):
                sample_val = wave_chunk_trail[x]
                yy = center_y - int(sample_val * amplitude)
                points_trail.append((x, yy))
            trail_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            for gp in range(self.glow_passes):
                alpha_val = 180 - gp * self.glow_alpha_decay
                if alpha_val < 0:
                    alpha_val = 0
                pygame.draw.lines(trail_surf, color + (alpha_val,), False, points_trail, self.line_width)
            self.surface.blit(trail_surf, (0, 0))

# --------------------------------------------------------------------
# 8) GENERATE VIDEO FUNCTION (WITH COLOR PARSING)
# --------------------------------------------------------------------
def generate_visualizer_video(audio_filepath, output_filepath, resolution=(1280,720), fps=30,
                              # matrix parameters:
                              matrix_count=8,
                              matrix_head_color=(0,255,0),   # can be tuple or hex string
                              matrix_tail_color=(0,180,0),   # can be tuple or hex string
                              matrix_char_size=24,
                              head_step_time=0.3,
                              random_x_jitter=3.0,
                              fade_time=5.0,
                              head_glow_passes=3,
                              head_glow_alpha_decay=50,
                              head_spawn_delay_range=(2.0,5.0),
                              head_saw_period=0.5,
                              line_width=3,
                              # wave parameters:
                              wave_color=(0,255,128),        # can be tuple or hex string
                              trail_colors=[(0,192,96),(0,128,64),(0,64,32)],  # list of colors
                              glow_passes=3,
                              glow_alpha_decay=40,
                              # font:
                              font_path=None):
    """
    Creates an MP4 with:
      - Discrete matrix columns whose heads move step-by-step (one char at a time)
      - The head (spawning character) flashes in a lighter (head_color) using a sawtooth modulation,
        while trailing characters are rendered in tail_color.
      - Random horizontal jitter in trailing characters.
      - Neon wave overlay.
      - Audio from 'audio_filepath'.
    Color parameters can be provided as (R,G,B) tuples or as hex strings.
    """
    matrix_head_color = parse_color(matrix_head_color)
    matrix_tail_color = parse_color(matrix_tail_color)
    wave_color = parse_color(wave_color)
    parsed_trail_colors = [parse_color(c) for c in trail_colors]
    trail_colors = parsed_trail_colors

    vis = NeonWaveVisualizer(audio_filepath, resolution, fps,
                             matrix_count=matrix_count,
                             matrix_head_color=matrix_head_color,
                             matrix_tail_color=matrix_tail_color,
                             matrix_char_size=matrix_char_size,
                             head_step_time=head_step_time,
                             random_x_jitter=random_x_jitter,
                             fade_time=fade_time,
                             head_glow_passes=head_glow_passes,
                             head_glow_alpha_decay=head_glow_alpha_decay,
                             head_spawn_delay_range=head_spawn_delay_range,
                             head_saw_period=head_saw_period,
                             wave_color=wave_color,
                             trail_colors=trail_colors,
                             glow_passes=glow_passes,
                             glow_alpha_decay=glow_alpha_decay,
                             line_width=line_width,
                             font_path=font_path)
    duration = vis.audio_duration
    clip = VideoClip(lambda t: vis.make_frame(t), duration=duration)
    audio_clip = AudioFileClip(audio_filepath)
    clip = clip.with_audio(audio_clip)
    clip.write_videofile(output_filepath, fps=fps, codec="libx264", audio_codec="aac")

# --------------------------------------------------------------------
# 9) EXAMPLE USAGE
# --------------------------------------------------------------------
if __name__=="__main__":
    generate_visualizer_video(
        audio_filepath="example.mp3",
        output_filepath="example_output.mp4",
        resolution=(1280,720),
        fps=30,
        matrix_count=8,
        matrix_head_color="#0F0",      # bright green (hex)
        matrix_tail_color="0x00B000",   # darker green (hex)
        matrix_char_size=24,
        head_step_time=0.25,
        random_x_jitter=2.0,
        fade_time=5.0,
        head_glow_passes=3,
        head_glow_alpha_decay=50,
        head_spawn_delay_range=(1.0,3.0),
        head_saw_period=0.5,
        wave_color="#00FF80",
        trail_colors=["#00C060", "#008040", "#004020"],
        glow_passes=3,
        glow_alpha_decay=40,
        font_path=None  # Or e.g. "NotoSansCJK-Regular.ttf" for broader glyph support
    )