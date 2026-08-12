import pygame
import sys
import random
import json
import os
import math
import asyncio

# --- Config & Constants ---
pygame.init()
WIDTH, HEIGHT = 600, 800
FPS = 60

TILE_SIZE = 60
ROWS_AHEAD = 20
ROWS_BEHIND = 8
MAX_STAMINA = 100
STAMINA_COST = 8
STAMINA_REGEN = 15  # per sec
MANGO_STAMINA = 25

# Colors (Fallback if assets fail)
C_BG = (34, 34, 34)
C_GRASS = (124, 252, 0)
C_ROAD = (105, 105, 105)
C_RIVER = (30, 144, 255)
C_WHITE = (255, 255, 255)
C_BLACK = (0, 0, 0)
C_STAMINA = (0, 255, 0)
C_STAMINA_LOW = (255, 0, 0)
C_MANGO = (255, 215, 0)

CHARACTERS = [
    {'id': 'chicken', 'color': (255, 255, 255), 'name': 'White Chicken'},
    {'id': 'dog', 'color': (150, 100, 60), 'name': 'Brown Dog'},
    {'id': 'cat', 'color': (255, 165, 0), 'name': 'Orange Cat'},
    {'id': 'sheep', 'color': (245, 245, 245), 'name': 'Fluffy Sheep'},
    {'id': 'robot', 'color': (150, 150, 150), 'name': 'Silver Robot'},
    {'id': 'ninja', 'color': (20, 20, 20), 'name': 'Black Ninja'},
    {'id': 'alien', 'color': (0, 255, 0), 'name': 'Green Alien'}
]

WEATHER_TYPES = [
    {'id': 'sunny', 'name': 'Sunny', 'color': (0, 0, 0, 0)},
    {'id': 'rainy', 'name': 'Rainy', 'color': (0, 0, 60, 100)},
    {'id': 'snowy', 'name': 'Snowy', 'color': (255, 255, 255, 40)},
    {'id': 'foggy', 'name': 'Foggy', 'color': (180, 180, 180, 80)}
]

SAVE_FILE = 'save_data.json'

# --- Initialization ---
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Endless Hopper (Pygame)")
clock = pygame.time.Clock()

def build_vision_vignette(width, height, side_span=170, back_span=220, max_alpha=235):
    """Builds a darkness overlay that hides the left edge, right edge, and the
    area behind the player, while leaving the forward view (top of screen) clear
    so you can still see upcoming rows to plan your hops."""
    vignette = pygame.Surface((width, height), pygame.SRCALPHA)

    def gradient_layer(vertical, from_far_edge, span):
        layer = pygame.Surface((width, height), pygame.SRCALPHA)
        for i in range(span):
            t = 1 - (i / span)  # 1 at the outer edge -> 0 further in
            a = int(max_alpha * (t ** 1.4))
            if vertical:
                y = (height - 1 - i) if from_far_edge else i
                pygame.draw.line(layer, (0, 0, 0, a), (0, y), (width, y))
            else:
                x = (width - 1 - i) if from_far_edge else i
                pygame.draw.line(layer, (0, 0, 0, a), (x, 0), (x, height))
        vignette.blit(layer, (0, 0), special_flags=pygame.BLEND_RGBA_MAX)

    gradient_layer(vertical=False, from_far_edge=False, span=side_span)  # left
    gradient_layer(vertical=False, from_far_edge=True, span=side_span)   # right
    gradient_layer(vertical=True, from_far_edge=True, span=back_span)    # behind (bottom of screen)
    return vignette

VISION_VIGNETTE = build_vision_vignette(WIDTH, HEIGHT)

font_large = pygame.font.SysFont('arial', 64, bold=True)
font_medium = pygame.font.SysFont('arial', 36, bold=True)
font_small = pygame.font.SysFont('arial', 24)
font_tiny = pygame.font.SysFont('arial', 18)

# --- Asset Loading ---
ASSETS = {}
def load_assets():
    try:
        def load_sprite(name):
            path = os.path.join('assets', name)
            if os.path.exists(path):
                img = pygame.image.load(path).convert()
                img.set_colorkey((255, 0, 255)) # Magenta transparency
                return img
            return None
            
        def load_tex(name):
            path = os.path.join('assets', name)
            if os.path.exists(path):
                img = pygame.image.load(path).convert()
                return pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE))
            return None

        # Sprites
        ASSETS['chicken'] = load_sprite('chicken.png')
        if ASSETS['chicken']: ASSETS['chicken'] = pygame.transform.scale(ASSETS['chicken'], (TILE_SIZE, TILE_SIZE))
        
        ASSETS['car'] = load_sprite('car.png')
        ASSETS['log'] = load_sprite('log.png')
        
        ASSETS['mango'] = load_sprite('mango.png')
        if ASSETS['mango']: ASSETS['mango'] = pygame.transform.scale(ASSETS['mango'], (int(TILE_SIZE*0.8), int(TILE_SIZE*0.8)))

        # Textures
        ASSETS['grass'] = load_tex('grass.png')
        ASSETS['road'] = load_tex('road.png')
        ASSETS['water'] = load_tex('water.png')
    except Exception as e:
        print("Error loading assets:", e)

load_assets()

def load_data():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'selectedChar': 'chicken', 'totalMangoes': 0, 'highScore': 0}

def save_data(data):
    with open(SAVE_FILE, 'w') as f:
        json.dump(data, f)

save_state = load_data()

# --- Classes ---
class Player:
    def __init__(self):
        self.tx = 0
        self.ty = 0
        self.px = 0
        self.py = 0
        self.dead = False
        self.stamina = MAX_STAMINA
        self.mangoes_this_run = 0
        self.score = 0
        self.update_pixels()

    def update_pixels(self):
        self.px = self.tx * TILE_SIZE
        self.py = self.ty * TILE_SIZE
        
    def move(self, dx, dy):
        if self.dead: return False
        if self.stamina < STAMINA_COST: return False
        
        if self.ty + dy < self.score - ROWS_BEHIND + 3: return False
        
        max_t = (WIDTH // TILE_SIZE) // 2
        if self.tx + dx < -max_t or self.tx + dx > max_t: return False
        
        self.tx += dx
        self.ty += dy
        self.stamina -= STAMINA_COST
        
        if self.ty > self.score:
            self.score = self.ty
            
        return True

    def update(self, dt):
        if not self.dead:
            if self.tx * TILE_SIZE == self.px and self.ty * TILE_SIZE == self.py:
                self.stamina = min(MAX_STAMINA, self.stamina + STAMINA_REGEN * dt)
                
        dx = self.tx * TILE_SIZE - self.px
        dy = self.ty * TILE_SIZE - self.py
        
        speed = 800 * dt  # Faster snappy movement
        if abs(dx) > speed:
            self.px += math.copysign(speed, dx)
        else:
            self.px = self.tx * TILE_SIZE
            
        if abs(dy) > speed:
            self.py += math.copysign(speed, dy)
        else:
            self.py = self.ty * TILE_SIZE

    def draw(self, surface, cx, cy):
        px_screen = cx + self.px
        py_screen = cy - self.py
        
        arc = 0
        if self.tx * TILE_SIZE != self.px or self.ty * TILE_SIZE != self.py:
            dist = abs((self.tx*TILE_SIZE - self.px) + (self.ty*TILE_SIZE - self.py))
            arc = math.sin((1 - dist/TILE_SIZE) * math.pi) * 35  # Increased hop height
            if arc < 0: arc = 0

        # Shadow
        shadow_rect = pygame.Rect(0,0,30,15)
        shadow_rect.center = (px_screen, py_screen + TILE_SIZE//2 - 5)
        shadow_surf = pygame.Surface((30,15), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0,0,0,100), (0,0,30,15))
        surface.blit(shadow_surf, shadow_rect.topleft)
        
        # Sprite - only use a real asset if one exists for THIS character
        char_id = save_state['selectedChar']
        img = ASSETS.get(char_id)
        if img:
            rect = img.get_rect(center=(px_screen, py_screen - arc))
            surface.blit(img, rect)
        else:
            # Fallback: draw a simple distinct silhouette per animal
            char = next((c for c in CHARACTERS if c['id'] == char_id), CHARACTERS[0])
            draw_character_fallback(surface, char_id, char['color'], px_screen, py_screen - arc)

class Row:
    def __init__(self, y_index, row_type, score):
        self.y_index = y_index
        self.type = row_type
        self.obstacles = []
        self.mango = None
        
        if self.type == 'road':
            speed = (random.uniform(100, 200)) * (1 + score / 100)
            direction = 1 if random.random() > 0.5 else -1
            spacing = random.uniform(3, 5) * TILE_SIZE
            for i in range(5):
                self.obstacles.append({
                    'x': i * spacing,
                    'w': TILE_SIZE * 1.6,
                    'speed': speed * direction,
                    'color': random.choice([(231,76,60), (52,152,219), (241,196,15), (155,89,182), (46,204,113)])
                })
        elif self.type == 'river':
            speed = random.uniform(50, 100)
            direction = 1 if random.random() > 0.5 else -1
            spacing = random.uniform(3.5, 5) * TILE_SIZE
            for i in range(5):
                self.obstacles.append({
                    'x': i * spacing,
                    'w': TILE_SIZE * (2.5 if random.random() > 0.5 else 3.5),
                    'speed': speed * direction,
                    'color': (139, 69, 19)
                })
        elif self.type == 'grass':
            if random.random() < 0.15 and y_index > 0:
                self.mango = {'x': random.randint(-3, 3)}

class GameInfo:
    def __init__(self, old_game=None):
        self.rows = []
        self.player = Player()
        self.camera_y = 0
        self.state = 'menu'
        if old_game:
            self.weather_timer = old_game.weather_timer
            self.weather_idx = old_game.weather_idx
            self.particles = old_game.particles
            self.weather_toast = old_game.weather_toast
            self.weather_toast_timer = old_game.weather_toast_timer
        else:
            self.weather_timer = 0
            self.weather_idx = 0
            self.particles = []
            self.weather_toast = ""
            self.weather_toast_timer = 0
        self.go_reason = ""
        self.generate_initial()

    def generate_initial(self):
        self.rows = []
        for i in range(-5, ROWS_AHEAD):
            self.add_row(i)

    def add_row(self, y_index):
        rtype = 'grass'
        if y_index > 0: # Road and rivers can spawn immediately after start line
            prev = self.rows[-1].type if len(self.rows) > 0 else 'grass'
            pprev = self.rows[-2].type if len(self.rows) > 1 else 'grass'
            r = random.random()
            if prev == 'road' and pprev == 'road':
                rtype = 'grass' if r > 0.5 else 'river'
            elif prev == 'river' and pprev == 'river':
                rtype = 'grass' if r > 0.5 else 'road'
            else:
                if r < 0.45: rtype = 'road'
                elif r < 0.75: rtype = 'river'
                else: rtype = 'grass'
                
        self.rows.append(Row(y_index, rtype, self.player.score))

    def update_rows(self):
        highest_y = self.rows[-1].y_index if self.rows else -1
        while highest_y < self.player.ty + ROWS_AHEAD:
            highest_y += 1
            self.add_row(highest_y)
        
        while self.rows and self.rows[0].y_index < self.player.ty - ROWS_BEHIND:
            self.rows.pop(0)

    def cycle_weather(self):
        choices = [i for i in range(len(WEATHER_TYPES)) if i != self.weather_idx]
        self.weather_idx = random.choice(choices)
        w = WEATHER_TYPES[self.weather_idx]['id']
        self.weather_toast = f"Weather: {WEATHER_TYPES[self.weather_idx]['name']}"
        self.weather_toast_timer = 2.5
        self.particles = []
        if w == 'rainy':
            for _ in range(150):
                self.particles.append({'x': random.randint(0, WIDTH), 'y': random.randint(0, HEIGHT), 's': random.uniform(400, 600), 't': 'rain'})
        elif w == 'snowy':
            for _ in range(150):
                self.particles.append({'x': random.randint(0, WIDTH), 'y': random.randint(0, HEIGHT), 's': random.uniform(50, 150), 't': 'snow', 'sway': random.random()*math.pi*2})

# --- Draw Functions ---
def draw_character_fallback(surface, char_id, color, cx, cy):
    """Simple procedural silhouette so every character reads as distinct
    even when no sprite art exists for it."""
    body = pygame.Rect(0, 0, 40, 40)
    body.center = (cx, cy + 10)
    pygame.draw.rect(surface, color, body, border_radius=10)

    if char_id == 'dog':
        # floppy ears
        pygame.draw.ellipse(surface, (90, 55, 30), (cx-24, cy-8, 14, 20))
        pygame.draw.ellipse(surface, (90, 55, 30), (cx+10, cy-8, 14, 20))
        pygame.draw.circle(surface, (40, 25, 15), (cx-8, cy+2), 3)  # nose/snout
        pygame.draw.circle(surface, (40, 25, 15), (cx+8, cy+2), 3)
    elif char_id == 'cat':
        # pointed ears
        pygame.draw.polygon(surface, color, [(cx-18, cy-6), (cx-8, cy-6), (cx-16, cy-22)])
        pygame.draw.polygon(surface, color, [(cx+18, cy-6), (cx+8, cy-6), (cx+16, cy-22)])
        pygame.draw.line(surface, (0,0,0), (cx-15, cy+8), (cx-2, cy+10), 1)
        pygame.draw.line(surface, (0,0,0), (cx+15, cy+8), (cx+2, cy+10), 1)
    elif char_id == 'sheep':
        # fluffy wool bumps
        for ox, oy in [(-14,-14), (0,-18), (14,-14), (-18,0), (18,0)]:
            pygame.draw.circle(surface, (255,255,255), (cx+ox, cy+oy), 10)
        pygame.draw.rect(surface, (40,40,40), (cx-10, cy+22, 20, 12), border_radius=4)  # dark face
    elif char_id == 'robot':
        pygame.draw.rect(surface, (80,80,80), (cx-6, cy-24, 12, 10))
        pygame.draw.circle(surface, (255,60,60), (cx, cy-28), 3)  # antenna light
    elif char_id == 'ninja':
        pygame.draw.rect(surface, (200,30,30), (cx-22, cy-4, 44, 8))  # headband
    elif char_id == 'alien':
        pygame.draw.ellipse(surface, color, (cx-14, cy-26, 28, 22))  # big head
    else:
        # chicken-ish default: little comb
        pygame.draw.polygon(surface, (255,80,80), [(cx-6,cy-18),(cx,cy-28),(cx+6,cy-18)])

    # simple eyes for everyone
    pygame.draw.circle(surface, (20,20,20), (cx-7, cy+6), 3)
    pygame.draw.circle(surface, (20,20,20), (cx+7, cy+6), 3)

def draw_text(surf, text, font, color, x, y, align='topleft'):
    img = font.render(text, True, color)
    rect = img.get_rect()
    setattr(rect, align, (x, y))
    surf.blit(img, rect)
    return rect

def draw_tiled(surface, texture, y_pos):
    if not texture: return False
    for x in range(0, WIDTH, TILE_SIZE):
        surface.blit(texture, (x, y_pos))
    return True

# --- Main Game ---
async def main():
    game = GameInfo()
    
    char_idx = next(i for i, c in enumerate(CHARACTERS) if c['id'] == save_state['selectedChar'])

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        if dt > 0.1: dt = 0.1
        
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
                
            if game.state == 'menu':
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_LEFT:
                        char_idx = (char_idx - 1) % len(CHARACTERS)
                        save_state['selectedChar'] = CHARACTERS[char_idx]['id']
                        save_data(save_state)
                    elif event.key == pygame.K_RIGHT:
                        char_idx = (char_idx + 1) % len(CHARACTERS)
                        save_state['selectedChar'] = CHARACTERS[char_idx]['id']
                        save_data(save_state)
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        game = GameInfo(game) # Reset
                        game.state = 'playing'
                        
            elif game.state == 'playing':
                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_UP, pygame.K_w]:
                        if game.player.move(0, 1): game.update_rows()
                    elif event.key in [pygame.K_DOWN, pygame.K_s]:
                        if game.player.move(0, -1): game.update_rows()
                    elif event.key in [pygame.K_LEFT, pygame.K_a]:
                        if game.player.move(-1, 0): game.update_rows()
                    elif event.key in [pygame.K_RIGHT, pygame.K_d]:
                        if game.player.move(1, 0): game.update_rows()
                        
            elif game.state == 'gameover':
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        game = GameInfo(game)
                        game.state = 'playing'

        # --- Update Weather ---
        game.weather_timer += dt
        if game.weather_timer > 15:
            game.weather_timer = 0
            game.cycle_weather()

        if game.weather_toast_timer > 0:
            game.weather_toast_timer -= dt
            
        for p in game.particles:
            p['y'] += p['s'] * dt
            if p['t'] == 'snow':
                p['sway'] += dt * 2
                p['x'] += math.sin(p['sway']) * 0.5
            if p['y'] > HEIGHT:
                p['y'] = -20
                p['x'] = random.randint(0, WIDTH)

        # --- Update Game ---
        if game.state == 'playing':
            game.player.update(dt)
            
            target_cy = game.player.ty * TILE_SIZE - HEIGHT * 0.3
            game.camera_y += (target_cy - game.camera_y) * 8 * dt
            
            cx = WIDTH // 2
            cy = HEIGHT - 150
            
            curr_row = next((r for r in game.rows if r.y_index == game.player.ty), None)
            
            for row in game.rows:
                for obs in row.obstacles:
                    obs['x'] += obs['speed'] * dt
                    if obs['speed'] > 0 and obs['x'] > WIDTH/2 + 300: obs['x'] = -WIDTH/2 - 300
                    if obs['speed'] < 0 and obs['x'] < -WIDTH/2 - 300: obs['x'] = WIDTH/2 + 300
            
            if curr_row and not game.player.dead:
                px = game.player.px
                
                if curr_row.mango and curr_row.mango['x'] == game.player.tx:
                    curr_row.mango = None
                    game.player.mangoes_this_run += 1
                    game.player.score += 5
                    game.player.stamina = min(MAX_STAMINA, game.player.stamina + MANGO_STAMINA)
                    
                if curr_row.type == 'road':
                    hit = any(abs(px - o['x']) < (TILE_SIZE + o['w'])/2 * 0.65 for o in curr_row.obstacles)
                    if hit:
                        game.player.dead = True
                        game.go_reason = "Splat! You got run over."
                elif curr_row.type == 'river':
                    on_log = next((o for o in curr_row.obstacles if abs(px - o['x']) < o['w']/2), None)
                    if on_log:
                        game.player.px += on_log['speed'] * dt
                        game.player.tx = round(game.player.px / TILE_SIZE)
                        
                        max_t = (WIDTH // TILE_SIZE) // 2 + 1
                        if abs(game.player.tx) > max_t:
                            game.player.dead = True
                            game.go_reason = "Carried away by the river!"
                    else:
                        game.player.dead = True
                        game.go_reason = "Splash! You drowned."
            
            if game.player.dead:
                game.state = 'gameover'
                if game.player.score > save_state['highScore']:
                    save_state['highScore'] = game.player.score
                save_state['totalMangoes'] += game.player.mangoes_this_run
                save_data(save_state)

        # --- Draw ---
        screen.fill(C_BG)
        cx = WIDTH // 2
        cy = HEIGHT - 150
        
        # Draw game board always
        for row in game.rows:
            sy = cy - (row.y_index * TILE_SIZE - game.camera_y)
            if sy > HEIGHT or sy < -TILE_SIZE*2: continue
            
            # Terrain
            if row.type == 'grass': 
                if not draw_tiled(screen, ASSETS.get('grass'), sy):
                    pygame.draw.rect(screen, C_GRASS, (0, sy, WIDTH, TILE_SIZE))
            elif row.type == 'road':
                if not draw_tiled(screen, ASSETS.get('road'), sy):
                    pygame.draw.rect(screen, C_ROAD, (0, sy, WIDTH, TILE_SIZE))
                elif row.type == 'river':
                    if not draw_tiled(screen, ASSETS.get('water'), sy):
                        pygame.draw.rect(screen, C_RIVER, (0, sy, WIDTH, TILE_SIZE))
                        
                if row.mango:
                    mx = cx + row.mango['x'] * TILE_SIZE
                    my = sy + TILE_SIZE//2 + math.sin(pygame.time.get_ticks()/150.0)*5
                    m_img = ASSETS.get('mango')
                    if m_img:
                        rect = m_img.get_rect(center=(mx, my))
                        screen.blit(m_img, rect)
                    else:
                        pygame.draw.circle(screen, C_MANGO, (mx, my), 12)
                    
                for obs in row.obstacles:
                    ox = cx + obs['x']
                    if row.type == 'road':
                        car_img = ASSETS.get('car')
                        if car_img:
                            # Scale the car to match its logical width
                            scaled = pygame.transform.scale(car_img, (int(obs['w']), TILE_SIZE))
                            # Flip if going left
                            if obs['speed'] < 0: scaled = pygame.transform.flip(scaled, True, False)
                            rect = scaled.get_rect(center=(ox, sy + TILE_SIZE//2))
                            screen.blit(scaled, rect)
                        else:
                            pygame.draw.rect(screen, obs['color'], (ox - obs['w']/2, sy + 8, obs['w'], TILE_SIZE-16), border_radius=8)
                            
                    elif row.type == 'river':
                        log_img = ASSETS.get('log')
                        if log_img:
                            scaled = pygame.transform.scale(log_img, (int(obs['w']), TILE_SIZE))
                            rect = scaled.get_rect(center=(ox, sy + TILE_SIZE//2))
                            screen.blit(scaled, rect)
                        else:
                            pygame.draw.rect(screen, obs['color'], (ox - obs['w']/2, sy + 8, obs['w'], TILE_SIZE-16), border_radius=12)

        if not game.player.dead or (pygame.time.get_ticks()//200)%2 == 0:
            game.player.draw(screen, cx, cy)
            
        weather_color = WEATHER_TYPES[game.weather_idx]['color']
        if weather_color[3] > 0:
            wsurf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            wsurf.fill(weather_color)
            screen.blit(wsurf, (0,0))
            
        rain_surf = pygame.Surface((2, 15), pygame.SRCALPHA)
        rain_surf.fill((150,200,255,150))
        for p in game.particles:
            if p['t'] == 'rain':
                screen.blit(rain_surf, (p['x'], p['y']))
                else:
                    pygame.draw.circle(screen, (255,255,255), (int(p['x']), int(p['y'])), 3)

            # Limit visibility: hide the left/right/back boundary lines
            screen.blit(VISION_VIGNETTE, (0, 0))

            # HUD
            if game.state == 'playing':
                draw_text(screen, f"Score: {game.player.score}", font_small, C_WHITE, 15, 15)
                draw_text(screen, f"High: {max(game.player.score, save_state['highScore'])}", font_tiny, (200,200,200), 15, 45)
                
                draw_text(screen, f"Mangoes: {game.player.mangoes_this_run}", font_small, C_MANGO, WIDTH-15, 15, 'topright')
                
                # Stamina
                s_width = 150
                s_pct = max(0, min(1, game.player.stamina / MAX_STAMINA))
                c_stam = C_STAMINA if game.player.stamina >= STAMINA_COST else C_STAMINA_LOW
                pygame.draw.rect(screen, (50,50,50), (WIDTH-s_width-15, 50, s_width, 15), border_radius=5)
                pygame.draw.rect(screen, c_stam, (WIDTH-s_width-15, 50, s_width*s_pct, 15), border_radius=5)
                pygame.draw.rect(screen, C_WHITE, (WIDTH-s_width-15, 50, s_width, 15), 2, border_radius=5)

                # Weather-change toast (fades out over its last second)
                if game.weather_toast_timer > 0:
                    alpha = 255 if game.weather_toast_timer > 1 else int(255 * game.weather_toast_timer)
                    toast_surf = pygame.Surface((WIDTH, 50), pygame.SRCALPHA)
                    txt = font_small.render(game.weather_toast, True, C_WHITE)
                    txt.set_alpha(alpha)
                    bg_rect = txt.get_rect(center=(WIDTH//2, 25))
                    bg = pygame.Surface((bg_rect.width+30, bg_rect.height+16), pygame.SRCALPHA)
                    bg.fill((0,0,0, min(160, alpha)))
                    toast_surf.blit(bg, bg.get_rect(center=(WIDTH//2, 25)))
                    toast_surf.blit(txt, bg_rect)
                    screen.blit(toast_surf, (0,0))

        if game.state == 'menu':
            # Semi transparent overlay
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0,0,0,200))
            screen.blit(overlay, (0,0))
            
            draw_text(screen, "Endless Hopper", font_large, C_WHITE, WIDTH//2, HEIGHT//2 - 150, 'center')
            draw_text(screen, f"High Score: {save_state['highScore']}", font_small, C_GRASS, WIDTH//2, HEIGHT//2 - 80, 'center')
            draw_text(screen, f"Total Mangoes: {save_state['totalMangoes']}", font_small, C_MANGO, WIDTH//2, HEIGHT//2 - 50, 'center')
            
            draw_text(screen, "< [Left] / [Right] to select character >", font_tiny, (200,200,200), WIDTH//2, HEIGHT//2 + 30, 'center')
            
            char = CHARACTERS[char_idx]
            
            img = ASSETS.get(char['id'])
            preview_center = (WIDTH//2, HEIGHT//2 + 110)
            if img:
                rect = img.get_rect(center=preview_center)
                screen.blit(img, rect)
                pygame.draw.rect(screen, C_WHITE, rect.inflate(20, 20), 3, border_radius=15)
            else:
                frame = pygame.Rect(0, 0, 90, 90)
                frame.center = preview_center
                draw_character_fallback(screen, char['id'], char['color'], preview_center[0], preview_center[1]-10)
                pygame.draw.rect(screen, C_WHITE, frame, 3, border_radius=15)
                
            draw_text(screen, char['name'], font_small, C_WHITE, WIDTH//2, HEIGHT//2 + 180, 'center')
            
            draw_text(screen, "Press [SPACE] to Play", font_medium, C_WHITE, WIDTH//2, HEIGHT - 150, 'center')
            
        elif game.state == 'gameover':
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0,0,0,200))
            screen.blit(overlay, (0,0))
            
            draw_text(screen, "GAME OVER", font_large, (255,50,50), WIDTH//2, HEIGHT//2 - 100, 'center')
            draw_text(screen, game.go_reason, font_small, C_WHITE, WIDTH//2, HEIGHT//2 - 30, 'center')
            draw_text(screen, f"Score: {game.player.score}", font_medium, C_WHITE, WIDTH//2, HEIGHT//2 + 30, 'center')
            draw_text(screen, f"Mangoes Collected: {game.player.mangoes_this_run}", font_small, C_MANGO, WIDTH//2, HEIGHT//2 + 80, 'center')
            
            draw_text(screen, "Press [SPACE] to Retry", font_medium, C_WHITE, WIDTH//2, HEIGHT - 150, 'center')

        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    asyncio.run(main())