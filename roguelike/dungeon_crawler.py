# =============================================================================
#  DUNGEON CRAWLER — Roguelike with Directional Sprites & Shield Booster
# =============================================================================

import pygame
import random
import sys
import os
import math

# ── CONSTANTS ─────────────────────────────────────────────────────────────────

SCREEN_W, SCREEN_H = 800, 600
CAPTION = "Dungeon Crawler"
FPS     = 60

TILE = 32
COLS = SCREEN_W // TILE
ROWS = (SCREEN_H - 80) // TILE

C_BG        = (20,  20,  35)
C_WALL      = (60,  55,  80)
C_FLOOR     = (45,  40,  60)
C_ENEMY     = (200,  50,  50)
C_GOLD      = (230, 190,  40)
C_HUD_BG    = (10,   10,  20)
C_WHITE     = (255, 255, 255)
C_YELLOW    = (255, 220,  60)
C_GREEN     = ( 60, 200,  80)
C_RED       = (220,  60,  60)
C_GRAY      = (130, 130, 150)
C_SHIELD    = ( 80, 180, 255)
C_SHIELD_HI = (180, 230, 255)

ENEMY_COUNT     = 6
GOLD_COUNT      = 10
SHIELD_COUNT    = 2
PLAYER_MAX_HP   = 5
DAMAGE_COOLDOWN = 60
SHIELD_DURATION = 300     # 5 seconds
MOVE_COOLDOWN   = 10
SPRITE_SIZE     = 52


# ── SPRITE LOADING ────────────────────────────────────────────────────────────

def load_player_sprites():
    """
    Load player_front/back/left/right.png from the same folder as this script.
    Returns: { "front": Surface, "back": Surface, "left": Surface, "right": Surface }
    """
    base    = os.path.dirname(os.path.abspath(__file__))
    sprites = {}
    for direction in ("front", "back", "left", "right"):
        path = os.path.join(base, f"player_{direction}.png")
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.scale(img, (SPRITE_SIZE, SPRITE_SIZE))
        else:
            # Fallback: coloured square
            img = pygame.Surface((SPRITE_SIZE, SPRITE_SIZE), pygame.SRCALPHA)
            img.fill((80, 140, 220))
        sprites[direction] = img
    return sprites


def make_shield_tinted(sprites):
    """Return a copy of every sprite with a blue tint for when shield is active."""
    tinted = {}
    for direction, img in sprites.items():
        t    = img.copy()
        tint = pygame.Surface(t.get_size(), pygame.SRCALPHA)
        tint.fill((80, 180, 255, 90))
        t.blit(tint, (0, 0))
        tinted[direction] = t
    return tinted


# ── HELPERS ───────────────────────────────────────────────────────────────────

def draw_rounded_rect(surface, colour, rect, radius=6):
    pygame.draw.rect(surface, colour, rect, border_radius=radius)


# ── PLAYER ────────────────────────────────────────────────────────────────────

class Player(pygame.sprite.Sprite):
    """
    Player sprite — switches between 4 directional images based on movement.
    No multi-frame animation; the correct face direction is shown at all times.
    """

    def __init__(self, col, row, sprites, tinted_sprites):
        super().__init__()
        self.sprites        = sprites
        self.tinted_sprites = tinted_sprites
        self.direction      = "front"
        self.image          = self.sprites[self.direction]
        self.rect           = self.image.get_rect()

        self.col, self.row = col, row
        self.px = float(col * TILE + (TILE - SPRITE_SIZE) // 2)
        self.py = float(row * TILE + (TILE - SPRITE_SIZE) // 2)
        self.rect.topleft = (round(self.px), round(self.py))

        self.hp            = PLAYER_MAX_HP
        self.score         = 0
        self.damage_timer  = 0
        self.shield_timer  = 0
        self.move_timer    = 0

    def update(self, keys, walls):
        # ── Read held keys ────────────────────────────────────────────────────
        dcol, drow   = 0, 0
        new_dir      = self.direction

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            drow, new_dir = -1, "back"
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            drow, new_dir =  1, "front"
        elif keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dcol, new_dir = -1, "left"
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dcol, new_dir =  1, "right"

        self.direction = new_dir

        # ── Attempt tile step ─────────────────────────────────────────────────
        if self.move_timer > 0:
            self.move_timer -= 1
        elif dcol != 0 or drow != 0:
            nc, nr = self.col + dcol, self.row + drow
            if 0 <= nc < COLS and 0 <= nr < ROWS and (nc, nr) not in walls:
                self.col, self.row = nc, nr
            self.move_timer = MOVE_COOLDOWN

        # ── Pick sprite (normal or shield-tinted) ─────────────────────────────
        src        = self.tinted_sprites if self.shield_timer > 0 else self.sprites
        self.image = src[self.direction]

        # ── Smooth pixel slide toward tile ────────────────────────────────────
        tx = float(self.col * TILE + (TILE - SPRITE_SIZE) // 2)
        ty = float(self.row * TILE + (TILE - SPRITE_SIZE) // 2)
        self.px += (tx - self.px) * 0.35
        self.py += (ty - self.py) * 0.35
        self.rect.topleft = (round(self.px), round(self.py))

        if self.damage_timer > 0: self.damage_timer -= 1
        if self.shield_timer > 0: self.shield_timer -= 1

    def take_damage(self):
        if self.shield_timer > 0 or self.damage_timer > 0:
            return
        self.hp -= 1
        self.damage_timer = DAMAGE_COOLDOWN

    def activate_shield(self):
        self.shield_timer = SHIELD_DURATION

    @property
    def alive_flag(self):
        return self.hp > 0


# ── ENEMY ─────────────────────────────────────────────────────────────────────

class Enemy(pygame.sprite.Sprite):
    DIRS = [(0,-1),(0,1),(-1,0),(1,0)]

    def __init__(self, col, row):
        super().__init__()
        self.image = pygame.Surface((TILE-4, TILE-4), pygame.SRCALPHA)
        self._draw()
        self.rect = self.image.get_rect()
        self.col, self.row = col, row
        self.px, self.py   = float(col*TILE+2), float(row*TILE+2)
        self.rect.topleft  = (round(self.px), round(self.py))
        self.dcol = random.choice([-1,0,1])
        self.drow = random.choice([-1,0,1])
        self.move_timer = random.randint(0, MOVE_COOLDOWN)
        self.dir_timer  = random.randint(30, 90)

    def _draw(self):
        self.image.fill((0,0,0,0))
        s = TILE - 4
        draw_rounded_rect(self.image, C_ENEMY, (0,0,s,s), 5)
        pygame.draw.rect(self.image, (150,30,30), (2,2,s-4,s-4), 2, border_radius=4)
        for ex in (8, s-8):
            pygame.draw.circle(self.image, (255,200,200), (ex,10), 3)
            pygame.draw.circle(self.image, (80,0,0),      (ex,10), 1)

    def _pick_dir(self, walls):
        dirs = self.DIRS[:]
        random.shuffle(dirs)
        for dc, dr in dirs:
            nc, nr = self.col+dc, self.row+dr
            if 0 <= nc < COLS and 0 <= nr < ROWS and (nc,nr) not in walls:
                self.dcol, self.drow = dc, dr
                return
        self.dcol, self.drow = 0, 0

    def update(self, walls):
        self.dir_timer -= 1
        if self.dir_timer <= 0:
            self._pick_dir(walls)
            self.dir_timer = random.randint(30, 90)
        if self.move_timer > 0:
            self.move_timer -= 1
        else:
            nc, nr = self.col+self.dcol, self.row+self.drow
            if 0 <= nc < COLS and 0 <= nr < ROWS and (nc,nr) not in walls:
                self.col, self.row = nc, nr
            else:
                self._pick_dir(walls)
            self.move_timer = MOVE_COOLDOWN
        self.px += (self.col*TILE+2 - self.px) * 0.25
        self.py += (self.row*TILE+2 - self.py) * 0.25
        self.rect.topleft = (round(self.px), round(self.py))


# ── GOLD ──────────────────────────────────────────────────────────────────────

class Gold(pygame.sprite.Sprite):
    def __init__(self, col, row):
        super().__init__()
        self.image = pygame.Surface((TILE-4, TILE-4), pygame.SRCALPHA)
        s = TILE-4; cx, cy = s//2, s//2
        pygame.draw.circle(self.image, C_GOLD,        (cx,cy), s//2-1)
        pygame.draw.circle(self.image, (255,240,120),  (cx-2,cy-2), s//6)
        self.rect      = self.image.get_rect(topleft=(col*TILE+2, row*TILE+2))
        self.col, self.row = col, row
        self.tick = random.randint(0, 60)

    def update(self):
        self.tick += 1
        self.rect.topleft = (self.col*TILE+2,
                             self.row*TILE+2 + int(math.sin(self.tick*0.1)*2))


# ── SHIELD BOOSTER ────────────────────────────────────────────────────────────

class ShieldBooster(pygame.sprite.Sprite):
    def __init__(self, col, row):
        super().__init__()
        self.col, self.row = col, row
        self.tick = random.randint(0, 60)
        self.image = self._make_frame()
        self.rect  = self.image.get_rect(topleft=(col*TILE+2, row*TILE+2))

    def _make_frame(self):
        s = TILE - 4
        cx, cy = s//2, s//2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        pulse = int(math.sin(self.tick * 0.08) * 2)
        r     = s//2 - 2 + pulse
        glow  = pygame.Surface((s, s), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*C_SHIELD, 55), (cx,cy), r+4)
        surf.blit(glow, (0,0))
        pts = [(cx + r*math.cos(math.radians(a + self.tick*2)),
                cy + r*math.sin(math.radians(a + self.tick*2)))
               for a in range(0, 360, 60)]
        pygame.draw.polygon(surf, C_SHIELD,    pts)
        pygame.draw.polygon(surf, C_SHIELD_HI, pts, 2)
        t = s//5
        pygame.draw.rect(surf, C_WHITE, (cx-1, cy-t, 2, t*2))
        pygame.draw.rect(surf, C_WHITE, (cx-t, cy-1, t*2, 2))
        return surf

    def update(self):
        self.tick += 1
        self.image = self._make_frame()
        self.rect.topleft = (self.col*TILE+2,
                             self.row*TILE+2 + int(math.sin(self.tick*0.1)*2))


# ── LEVEL GENERATION ──────────────────────────────────────────────────────────

def generate_level():
    walls = set()
    for c in range(COLS): walls.add((c,0));       walls.add((c,ROWS-1))
    for r in range(ROWS): walls.add((0,r));        walls.add((COLS-1,r))
    for _ in range(int(COLS*ROWS*0.12)):
        c, r = random.randint(1,COLS-2), random.randint(1,ROWS-2)
        if not (c in (1,2) and r in (1,2)):
            walls.add((c,r))

    free = [(c,r) for c in range(1,COLS-1)
                  for r in range(1,ROWS-1) if (c,r) not in walls]
    random.shuffle(free)
    free = [t for t in free if t not in {(2,2),(3,2),(2,3),(3,3)}]

    enemies      = pygame.sprite.Group()
    gold_group   = pygame.sprite.Group()
    shield_group = pygame.sprite.Group()
    for _ in range(min(ENEMY_COUNT,  len(free))): c,r=free.pop(); enemies.add(Enemy(c,r))
    for _ in range(min(GOLD_COUNT,   len(free))): c,r=free.pop(); gold_group.add(Gold(c,r))
    for _ in range(min(SHIELD_COUNT, len(free))): c,r=free.pop(); shield_group.add(ShieldBooster(c,r))
    return walls, enemies, gold_group, shield_group


# ── DRAWING ───────────────────────────────────────────────────────────────────

def draw_dungeon(surface, walls):
    for r in range(ROWS):
        for c in range(COLS):
            rect = pygame.Rect(c*TILE, r*TILE, TILE, TILE)
            if (c,r) in walls:
                pygame.draw.rect(surface, C_WALL,  rect)
                pygame.draw.rect(surface, (80,74,100), rect, 1)
            else:
                pygame.draw.rect(surface, C_FLOOR, rect)
                pygame.draw.rect(surface, (50,45,65),  rect, 1)


def draw_shield_aura(surface, player, tick):
    if player.shield_timer <= 0:
        return
    cx = round(player.px) + SPRITE_SIZE // 2
    cy = round(player.py) + SPRITE_SIZE // 2
    radius = SPRITE_SIZE // 2 + 10
    alpha  = 255 if player.shield_timer > 60 else int(255 * player.shield_timer / 60)
    for i in range(8):
        angle = math.radians(i * 45 + tick * 3)
        dot = pygame.Surface((8,8), pygame.SRCALPHA)
        pygame.draw.circle(dot, (*C_SHIELD, alpha), (4,4), 4)
        surface.blit(dot, (cx + int(radius*math.cos(angle)) - 4,
                           cy + int(radius*math.sin(angle)) - 4))
    ring = pygame.Surface((SPRITE_SIZE+24, SPRITE_SIZE+24), pygame.SRCALPHA)
    pygame.draw.circle(ring, (*C_SHIELD, alpha//3),
                       ((SPRITE_SIZE+24)//2, (SPRITE_SIZE+24)//2), radius, 2)
    surface.blit(ring, (cx-(SPRITE_SIZE+24)//2, cy-(SPRITE_SIZE+24)//2))


def draw_hud(surface, font_med, font_small, player, level, tick):
    pygame.draw.rect(surface, C_HUD_BG, (0, ROWS*TILE, SCREEN_W, 80))
    pygame.draw.line(surface, C_GRAY,   (0, ROWS*TILE), (SCREEN_W, ROWS*TILE), 2)
    surface.blit(font_small.render("HP:", True, C_WHITE), (10, ROWS*TILE+8))
    for i in range(PLAYER_MAX_HP):
        pygame.draw.rect(surface, C_RED if i < player.hp else (60,40,40),
                         (55+i*22, ROWS*TILE+8, 16, 16), border_radius=3)
    surface.blit(font_med.render(f"Gold: {player.score}", True, C_YELLOW), (10,  ROWS*TILE+32))
    surface.blit(font_med.render(f"Level: {level}",       True, C_GREEN),  (180, ROWS*TILE+32))
    if player.shield_timer > 0:
        bw = int(200 * player.shield_timer / SHIELD_DURATION)
        pygame.draw.rect(surface, (30,60,90), (360, ROWS*TILE+10, 200, 14), border_radius=4)
        pygame.draw.rect(surface, C_SHIELD,   (360, ROWS*TILE+10, bw,  14), border_radius=4)
        surface.blit(font_small.render("SHIELD ACTIVE", True, C_SHIELD_HI), (370, ROWS*TILE+28))
    surface.blit(font_small.render(
        "WASD/Arrows=move   Gold=+10pts   Blue shield=invincibility",
        True, C_GRAY), (10, ROWS*TILE+58))


def draw_intro(surface, font_large, font_small):
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    ov.fill((0,0,0,185)); surface.blit(ov,(0,0))
    t = font_large.render("DUNGEON CRAWLER", True, C_YELLOW)
    surface.blit(t, t.get_rect(center=(SCREEN_W//2, 160)))
    for i, (line, col) in enumerate([
        ("Use  WASD / Arrow Keys  to move",               C_WHITE),
        ("Collect  GOLD  →  +10 score each",              C_YELLOW),
        ("Grab  BLUE SHIELD  →  5 sec invincibility",     C_SHIELD),
        ("Avoid  RED  enemies  →  they drain your HP",    C_RED),
        ("Clear all gold to advance to the next level",   C_GREEN),
        ("", C_WHITE),
        ("Press  SPACE  or  ENTER  to begin",             C_GRAY),
    ]):
        txt = font_small.render(line, True, col)
        surface.blit(txt, txt.get_rect(center=(SCREEN_W//2, 250+i*34)))


def draw_game_over(surface, font_large, font_med, font_small, player, level):
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    ov.fill((0,0,0,210)); surface.blit(ov,(0,0))
    draw_rounded_rect(surface, (30,20,50), pygame.Rect(190,130,420,320), 12)
    pygame.draw.rect(surface, C_RED, pygame.Rect(190,130,420,320), 2, border_radius=12)
    t = font_large.render("GAME  OVER", True, C_RED)
    surface.blit(t, t.get_rect(center=(SCREEN_W//2, 168)))
    for i, (label, value, col) in enumerate([
        ("Final Score",    f"{player.score} Gold",    C_YELLOW),
        ("Levels Reached", str(level),                C_GREEN),
        ("Result",         "Defeated by the dungeon", C_GRAY),
    ]):
        y = 230+i*52
        lbl = font_small.render(f"{label}:", True, C_WHITE)
        val = font_med.render(value, True, col)
        surface.blit(lbl, lbl.get_rect(right=SCREEN_W//2-10, centery=y))
        surface.blit(val, val.get_rect(left=SCREEN_W//2+10,  centery=y))
    hint = font_small.render("Press  R  to Restart   or   ESC  to Quit", True, C_GRAY)
    surface.blit(hint, hint.get_rect(center=(SCREEN_W//2, 430)))


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption(CAPTION)
    font_large = pygame.font.SysFont("consolas", 42, bold=True)
    font_med   = pygame.font.SysFont("consolas", 22)
    font_small = pygame.font.SysFont("consolas", 16)
    clock      = pygame.time.Clock()
    tick       = 0

    player_sprites = load_player_sprites()
    tinted_sprites = make_shield_tinted(player_sprites)

    STATE_INTRO, STATE_PLAYING, STATE_GAMEOVER = "intro", "playing", "gameover"

    walls, enemies, gold_group, shield_group = set(), \
        pygame.sprite.Group(), pygame.sprite.Group(), pygame.sprite.Group()
    player       = Player(2, 2, player_sprites, tinted_sprites)
    player_group = pygame.sprite.GroupSingle(player)
    level        = 1
    state        = STATE_INTRO

    def new_game():
        nonlocal walls, enemies, gold_group, shield_group, player, level, state
        level  = 1
        walls, enemies, gold_group, shield_group = generate_level()
        player = Player(2, 2, player_sprites, tinted_sprites)
        player_group.add(player)
        state  = STATE_PLAYING

    running = True
    while running:
        tick += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if state == STATE_INTRO:
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN): new_game()
                elif state == STATE_GAMEOVER:
                    if   event.key == pygame.K_r:      new_game()
                    elif event.key == pygame.K_ESCAPE: running = False
                elif state == STATE_PLAYING:
                    if event.key == pygame.K_ESCAPE:   running = False

        if state == STATE_PLAYING:
            keys = pygame.key.get_pressed()
            player.update(keys, walls)
            enemies.update(walls)
            gold_group.update()
            shield_group.update()

            for _ in pygame.sprite.spritecollide(player, gold_group, True,
                        collided=lambda p,g: (p.col,p.row)==(g.col,g.row)):
                player.score += 10

            if pygame.sprite.spritecollide(player, shield_group, True,
                   collided=lambda p,s: (p.col,p.row)==(s.col,s.row)):
                player.activate_shield()

            if not gold_group:
                level += 1
                walls, enemies, gold_group, shield_group = generate_level()
                player.col, player.row = 2, 2

            if pygame.sprite.spritecollide(player, enemies, False,
                   collided=lambda p,e: (p.col,p.row)==(e.col,e.row)):
                player.take_damage()

            if not player.alive_flag:
                state = STATE_GAMEOVER

        screen.fill(C_BG)

        if state in (STATE_PLAYING, STATE_GAMEOVER):
            draw_dungeon(screen, walls)
            gold_group.draw(screen)
            shield_group.draw(screen)
            enemies.draw(screen)
            draw_shield_aura(screen, player, tick)
            show = (state == STATE_GAMEOVER
                    or player.shield_timer > 0
                    or player.damage_timer == 0
                    or player.damage_timer % 8 < 4)
            if show:
                player_group.draw(screen)
            draw_hud(screen, font_med, font_small, player, level, tick)

        if state == STATE_INTRO:
            draw_dungeon(screen, walls)
            draw_intro(screen, font_large, font_small)

        if state == STATE_GAMEOVER:
            draw_game_over(screen, font_large, font_med, font_small, player, level)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
