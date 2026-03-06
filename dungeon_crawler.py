# =============================================================================
#  DUNGEON CRAWLER — Full animated sprites (player 2f, enemy 4f, coin 12f)
# =============================================================================

import pygame, random, sys, os, math

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
C_HUD_BG    = (10,  10,  20)
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
SHIELD_DURATION = 300
MOVE_COOLDOWN   = 10

# Animation speeds (frames between image swaps)
PLAYER_ANIM_SPD = 8
ENEMY_ANIM_SPD  = 8
COIN_ANIM_SPD   = 5    # 12 frames × 5 ticks = 60 ticks per full spin (1 sec)

SPRITE_SIZE = 52
COIN_SIZE   = 28

BASE = os.path.dirname(os.path.abspath(__file__))


# ── SPRITE LOADING ────────────────────────────────────────────────────────────

def load_img(filename, size):
    path = os.path.join(BASE, filename)
    if os.path.exists(path):
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.scale(img, size)
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill((180, 60, 200, 200))
    return surf

def load_player_sprites():
    """
    Player: 2 frames per direction (front/back/left/right).
    Files: player_front_0..1, player_back_0..1,
           player_left_0..1,  player_right_0..1
    """
    sprites = {}
    for d in ("front", "back", "left", "right"):
        sprites[d] = [load_img(f"player_{d}_{i}.png", (SPRITE_SIZE, SPRITE_SIZE))
                      for i in range(2)]
    return sprites

def load_enemy_sprites():
    """
    Enemy: front/back = 2 frames, left/right = 4 frames.
    Files: enemy_front_0..1, enemy_back_0..1,
           enemy_left_0..3,  enemy_right_0..3
    """
    sprites = {}
    for d in ("front", "back"):
        sprites[d] = [load_img(f"enemy_{d}_{i}.png", (SPRITE_SIZE, SPRITE_SIZE))
                      for i in range(2)]
    for d in ("left", "right"):
        sprites[d] = [load_img(f"enemy_{d}_{i}.png", (SPRITE_SIZE, SPRITE_SIZE))
                      for i in range(4)]
    return sprites

def load_coin_frames():
    """12-frame full spin cycle. Files: coin_0 .. coin_11"""
    return [load_img(f"coin_{i}.png", (COIN_SIZE, COIN_SIZE)) for i in range(12)]

def make_shield_tinted(sprites):
    """Blue-tinted copy of every player frame for shield-active state."""
    tinted = {}
    for d, frames in sprites.items():
        tf = []
        for f in frames:
            t = f.copy()
            ov = pygame.Surface(t.get_size(), pygame.SRCALPHA)
            ov.fill((80, 180, 255, 90))
            t.blit(ov, (0, 0))
            tf.append(t)
        tinted[d] = tf
    return tinted


# ── HELPERS ───────────────────────────────────────────────────────────────────

def draw_rounded_rect(surf, colour, rect, r=6):
    pygame.draw.rect(surf, colour, rect, border_radius=r)


# ── PLAYER ────────────────────────────────────────────────────────────────────

class Player(pygame.sprite.Sprite):
    """
    2-frame walk animation per direction.
    Frame alternates every PLAYER_ANIM_SPD ticks while a key is held.
    Resets to frame 0 on idle.
    """
    def __init__(self, col, row, sprites, tinted):
        super().__init__()
        self.sprites, self.tinted = sprites, tinted
        self.direction  = "front"
        self.anim_frame = 0
        self.anim_tick  = 0
        self.image = sprites["front"][0]
        self.rect  = self.image.get_rect()
        self.col, self.row = col, row
        self.px = float(col * TILE + (TILE - SPRITE_SIZE) // 2)
        self.py = float(row * TILE + (TILE - SPRITE_SIZE) // 2)
        self.rect.topleft = (round(self.px), round(self.py))
        self.hp = PLAYER_MAX_HP
        self.score = 0
        self.damage_timer = self.shield_timer = self.move_timer = 0

    def update(self, keys, walls):
        dcol = drow = 0
        new_dir   = self.direction
        is_moving = False

        if   keys[pygame.K_w] or keys[pygame.K_UP]:    drow,new_dir,is_moving = -1,"back",True
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:   drow,new_dir,is_moving =  1,"front",True
        elif keys[pygame.K_a] or keys[pygame.K_LEFT]:   dcol,new_dir,is_moving = -1,"left",True
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:  dcol,new_dir,is_moving =  1,"right",True
        self.direction = new_dir

        if self.move_timer > 0:
            self.move_timer -= 1
        elif is_moving:
            nc,nr = self.col+dcol, self.row+drow
            if 0<=nc<COLS and 0<=nr<ROWS and (nc,nr) not in walls:
                self.col,self.row = nc,nr
            self.move_timer = MOVE_COOLDOWN

        if is_moving:
            self.anim_tick += 1
            if self.anim_tick >= PLAYER_ANIM_SPD:
                self.anim_tick  = 0
                self.anim_frame = 1 - self.anim_frame   # toggle 0↔1
        else:
            self.anim_frame = self.anim_tick = 0

        src = self.tinted if self.shield_timer > 0 else self.sprites
        self.image = src[self.direction][self.anim_frame]

        tx = float(self.col*TILE + (TILE-SPRITE_SIZE)//2)
        ty = float(self.row*TILE + (TILE-SPRITE_SIZE)//2)
        self.px += (tx-self.px)*0.35;  self.py += (ty-self.py)*0.35
        self.rect.topleft = (round(self.px), round(self.py))

        if self.damage_timer > 0: self.damage_timer -= 1
        if self.shield_timer > 0: self.shield_timer -= 1

    def take_damage(self):
        if self.shield_timer > 0 or self.damage_timer > 0: return
        self.hp -= 1;  self.damage_timer = DAMAGE_COOLDOWN

    def activate_shield(self): self.shield_timer = SHIELD_DURATION

    @property
    def alive_flag(self): return self.hp > 0


# ── ENEMY ─────────────────────────────────────────────────────────────────────

class Enemy(pygame.sprite.Sprite):
    """
    4-frame walk animation for left/right, 2-frame for front/back.
    Wanders randomly, changes direction on walls or timer.
    """
    DIRS     = [(0,-1),(0,1),(-1,0),(1,0)]
    DIR_NAME = {(0,-1):"back",(0,1):"front",(-1,0):"left",(1,0):"right"}

    def __init__(self, col, row, sprites):
        super().__init__()
        self.sprites    = sprites
        self.direction  = "front"
        self.anim_frame = 0
        self.anim_tick  = 0
        self.image = sprites["front"][0]
        self.rect  = self.image.get_rect()
        self.col, self.row = col, row
        self.px = float(col*TILE + (TILE-SPRITE_SIZE)//2)
        self.py = float(row*TILE + (TILE-SPRITE_SIZE)//2)
        self.rect.topleft = (round(self.px), round(self.py))
        self.dcol = random.choice([-1,0,1])
        self.drow = random.choice([-1,0,1])
        self.move_timer = random.randint(0, MOVE_COOLDOWN)
        self.dir_timer  = random.randint(30, 90)

    def _pick_dir(self, walls):
        dirs = self.DIRS[:]
        random.shuffle(dirs)
        for dc,dr in dirs:
            nc,nr = self.col+dc, self.row+dr
            if 0<=nc<COLS and 0<=nr<ROWS and (nc,nr) not in walls:
                self.dcol,self.drow = dc,dr; return
        self.dcol = self.drow = 0

    def update(self, walls):
        self.dir_timer -= 1
        if self.dir_timer <= 0:
            self._pick_dir(walls); self.dir_timer = random.randint(30,90)

        is_moving = False
        if self.move_timer > 0:
            self.move_timer -= 1
        else:
            nc,nr = self.col+self.dcol, self.row+self.drow
            if 0<=nc<COLS and 0<=nr<ROWS and (nc,nr) not in walls:
                self.col,self.row = nc,nr;  is_moving = True
            else:
                self._pick_dir(walls)
            self.move_timer = MOVE_COOLDOWN

        key = (self.dcol, self.drow)
        if key in self.DIR_NAME: self.direction = self.DIR_NAME[key]

        num_frames = len(self.sprites[self.direction])
        if is_moving:
            self.anim_tick += 1
            if self.anim_tick >= ENEMY_ANIM_SPD:
                self.anim_tick  = 0
                self.anim_frame = (self.anim_frame+1) % num_frames
        else:
            self.anim_frame = self.anim_tick = 0

        self.anim_frame = min(self.anim_frame, num_frames-1)
        self.image = self.sprites[self.direction][self.anim_frame]

        self.px += (self.col*TILE+(TILE-SPRITE_SIZE)//2 - self.px)*0.25
        self.py += (self.row*TILE+(TILE-SPRITE_SIZE)//2 - self.py)*0.25
        self.rect.topleft = (round(self.px), round(self.py))


# ── GOLD COIN ─────────────────────────────────────────────────────────────────

class Gold(pygame.sprite.Sprite):
    """
    12-frame spinning coin — full rotation every ~60 ticks (1 second).
    Also bobs up and down gently.
    """
    def __init__(self, col, row, frames):
        super().__init__()
        self.frames     = frames           # list of 12 Surfaces
        self.anim_frame = random.randint(0, 11)   # stagger so coins don't all sync
        self.anim_tick  = random.randint(0, COIN_ANIM_SPD)
        self.bob_tick   = random.randint(0, 60)
        self.image = frames[self.anim_frame]
        offset = (TILE - COIN_SIZE) // 2
        self.col, self.row = col, row
        self.base_x = col*TILE + offset
        self.base_y = row*TILE + offset
        self.rect = self.image.get_rect(topleft=(self.base_x, self.base_y))

    def update(self):
        # Advance spin
        self.anim_tick += 1
        if self.anim_tick >= COIN_ANIM_SPD:
            self.anim_tick  = 0
            self.anim_frame = (self.anim_frame+1) % 12
        self.image = self.frames[self.anim_frame]
        # Bob
        self.bob_tick += 1
        self.rect.topleft = (self.base_x,
                             self.base_y + int(math.sin(self.bob_tick*0.1)*2))


# ── SHIELD BOOSTER ────────────────────────────────────────────────────────────

class ShieldBooster(pygame.sprite.Sprite):
    def __init__(self, col, row):
        super().__init__()
        self.col, self.row = col, row
        self.tick = random.randint(0,60)
        self.image = self._make()
        self.rect  = self.image.get_rect(topleft=(col*TILE+2, row*TILE+2))

    def _make(self):
        s = TILE-4; cx,cy = s//2,s//2
        surf = pygame.Surface((s,s), pygame.SRCALPHA)
        r = s//2-2+int(math.sin(self.tick*0.08)*2)
        glow = pygame.Surface((s,s), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*C_SHIELD,55), (cx,cy), r+4)
        surf.blit(glow,(0,0))
        pts = [(cx+r*math.cos(math.radians(a+self.tick*2)),
                cy+r*math.sin(math.radians(a+self.tick*2))) for a in range(0,360,60)]
        pygame.draw.polygon(surf, C_SHIELD,    pts)
        pygame.draw.polygon(surf, C_SHIELD_HI, pts, 2)
        t = s//5
        pygame.draw.rect(surf, C_WHITE, (cx-1,cy-t,2,t*2))
        pygame.draw.rect(surf, C_WHITE, (cx-t,cy-1,t*2,2))
        return surf

    def update(self):
        self.tick += 1
        self.image = self._make()
        self.rect.topleft = (self.col*TILE+2,
                             self.row*TILE+2+int(math.sin(self.tick*0.1)*2))


# ── LEVEL GENERATION ──────────────────────────────────────────────────────────

def generate_level(coin_frames, enemy_sprites):
    walls = set()
    for c in range(COLS): walls.add((c,0)); walls.add((c,ROWS-1))
    for r in range(ROWS): walls.add((0,r)); walls.add((COLS-1,r))
    for _ in range(int(COLS*ROWS*0.12)):
        c,r = random.randint(1,COLS-2), random.randint(1,ROWS-2)
        if not (c in (1,2) and r in (1,2)): walls.add((c,r))

    free = [(c,r) for c in range(1,COLS-1) for r in range(1,ROWS-1)
            if (c,r) not in walls and (c,r) not in {(2,2),(3,2),(2,3),(3,3)}]
    random.shuffle(free)

    enemies=pygame.sprite.Group(); gold=pygame.sprite.Group(); shields=pygame.sprite.Group()
    for _ in range(min(ENEMY_COUNT,  len(free))): c,r=free.pop(); enemies.add(Enemy(c,r,enemy_sprites))
    for _ in range(min(GOLD_COUNT,   len(free))): c,r=free.pop(); gold.add(Gold(c,r,coin_frames))
    for _ in range(min(SHIELD_COUNT, len(free))): c,r=free.pop(); shields.add(ShieldBooster(c,r))
    return walls, enemies, gold, shields


# ── DRAWING ───────────────────────────────────────────────────────────────────

def draw_dungeon(surface, walls):
    for r in range(ROWS):
        for c in range(COLS):
            rect = pygame.Rect(c*TILE, r*TILE, TILE, TILE)
            col  = C_WALL if (c,r) in walls else C_FLOOR
            edge = (80,74,100) if (c,r) in walls else (50,45,65)
            pygame.draw.rect(surface, col,  rect)
            pygame.draw.rect(surface, edge, rect, 1)

def draw_shield_aura(surface, player, tick):
    if player.shield_timer <= 0: return
    cx = round(player.px)+SPRITE_SIZE//2;  cy = round(player.py)+SPRITE_SIZE//2
    radius = SPRITE_SIZE//2+10
    alpha  = 255 if player.shield_timer>60 else int(255*player.shield_timer/60)
    for i in range(8):
        a  = math.radians(i*45+tick*3)
        dot = pygame.Surface((8,8), pygame.SRCALPHA)
        pygame.draw.circle(dot, (*C_SHIELD,alpha), (4,4), 4)
        surface.blit(dot, (cx+int(radius*math.cos(a))-4, cy+int(radius*math.sin(a))-4))
    ring = pygame.Surface((SPRITE_SIZE+24,SPRITE_SIZE+24), pygame.SRCALPHA)
    pygame.draw.circle(ring, (*C_SHIELD,alpha//3),
                       ((SPRITE_SIZE+24)//2,(SPRITE_SIZE+24)//2), radius, 2)
    surface.blit(ring, (cx-(SPRITE_SIZE+24)//2, cy-(SPRITE_SIZE+24)//2))

def draw_hud(surface, fm, fs, player, level):
    pygame.draw.rect(surface, C_HUD_BG, (0,ROWS*TILE,SCREEN_W,80))
    pygame.draw.line(surface, C_GRAY,   (0,ROWS*TILE),(SCREEN_W,ROWS*TILE),2)
    surface.blit(fs.render("HP:",True,C_WHITE),(10,ROWS*TILE+8))
    for i in range(PLAYER_MAX_HP):
        pygame.draw.rect(surface, C_RED if i<player.hp else (60,40,40),
                         (55+i*22,ROWS*TILE+8,16,16), border_radius=3)
    surface.blit(fm.render(f"Gold: {player.score}",True,C_YELLOW),(10, ROWS*TILE+32))
    surface.blit(fm.render(f"Level: {level}",      True,C_GREEN), (180,ROWS*TILE+32))
    if player.shield_timer > 0:
        bw = int(200*player.shield_timer/SHIELD_DURATION)
        pygame.draw.rect(surface,(30,60,90),(360,ROWS*TILE+10,200,14),border_radius=4)
        pygame.draw.rect(surface,C_SHIELD,  (360,ROWS*TILE+10,bw, 14),border_radius=4)
        surface.blit(fs.render("SHIELD ACTIVE",True,C_SHIELD_HI),(370,ROWS*TILE+28))
    surface.blit(fs.render("WASD/Arrows=move   Gold=+10pts   Blue shield=invincibility",
                            True,C_GRAY),(10,ROWS*TILE+58))

def draw_intro(surface, fl, fs):
    ov=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA); ov.fill((0,0,0,185)); surface.blit(ov,(0,0))
    t=fl.render("DUNGEON CRAWLER",True,C_YELLOW); surface.blit(t,t.get_rect(center=(SCREEN_W//2,160)))
    for i,(line,col) in enumerate([
        ("Use  WASD / Arrow Keys  to move",             C_WHITE),
        ("Collect  GOLD  →  +10 score each",            C_YELLOW),
        ("Grab  BLUE SHIELD  →  5 sec invincibility",   C_SHIELD),
        ("Avoid  RED  demons  →  they drain your HP",   C_RED),
        ("Clear all gold to advance to the next level", C_GREEN),
        ("",C_WHITE),
        ("Press  SPACE  or  ENTER  to begin",           C_GRAY),
    ]):
        txt=fs.render(line,True,col); surface.blit(txt,txt.get_rect(center=(SCREEN_W//2,250+i*34)))

def draw_game_over(surface, fl, fm, fs, player, level):
    ov=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA); ov.fill((0,0,0,210)); surface.blit(ov,(0,0))
    draw_rounded_rect(surface,(30,20,50),pygame.Rect(190,130,420,320),12)
    pygame.draw.rect(surface,C_RED,pygame.Rect(190,130,420,320),2,border_radius=12)
    t=fl.render("GAME  OVER",True,C_RED); surface.blit(t,t.get_rect(center=(SCREEN_W//2,168)))
    for i,(label,value,col) in enumerate([
        ("Final Score",   f"{player.score} Gold",   C_YELLOW),
        ("Levels Reached",str(level),               C_GREEN),
        ("Result",        "Defeated by the dungeon",C_GRAY),
    ]):
        y=230+i*52
        lbl=fs.render(f"{label}:",True,C_WHITE); val=fm.render(value,True,col)
        surface.blit(lbl,lbl.get_rect(right=SCREEN_W//2-10,centery=y))
        surface.blit(val,val.get_rect(left=SCREEN_W//2+10, centery=y))
    h=fs.render("Press  R  to Restart   or   ESC  to Quit",True,C_GRAY)
    surface.blit(h,h.get_rect(center=(SCREEN_W//2,430)))


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W,SCREEN_H))
    pygame.display.set_caption(CAPTION)
    fl = pygame.font.SysFont("consolas",42,bold=True)
    fm = pygame.font.SysFont("consolas",22)
    fs = pygame.font.SysFont("consolas",16)
    clock = pygame.time.Clock()
    tick  = 0

    player_sprites = load_player_sprites()
    tinted_sprites = make_shield_tinted(player_sprites)
    enemy_sprites  = load_enemy_sprites()
    coin_frames    = load_coin_frames()

    SI, SP, SG = "intro","playing","gameover"
    walls,enemies,gold,shields = set(),pygame.sprite.Group(),pygame.sprite.Group(),pygame.sprite.Group()
    player = Player(2,2,player_sprites,tinted_sprites)
    pg     = pygame.sprite.GroupSingle(player)
    level  = 1;  state = SI

    def new_game():
        nonlocal walls,enemies,gold,shields,player,level,state
        level = 1
        walls,enemies,gold,shields = generate_level(coin_frames, enemy_sprites)
        player = Player(2,2,player_sprites,tinted_sprites);  pg.add(player)
        state  = SP

    running = True
    while running:
        tick += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running=False
            if event.type == pygame.KEYDOWN:
                if   state==SI and event.key in (pygame.K_SPACE,pygame.K_RETURN): new_game()
                elif state==SG:
                    if   event.key==pygame.K_r:      new_game()
                    elif event.key==pygame.K_ESCAPE: running=False
                elif state==SP and event.key==pygame.K_ESCAPE: running=False

        if state == SP:
            keys = pygame.key.get_pressed()
            player.update(keys,walls); enemies.update(walls); gold.update(); shields.update()

            for _ in pygame.sprite.spritecollide(player,gold,True,
                        collided=lambda p,g:(p.col,p.row)==(g.col,g.row)):
                player.score += 10

            if pygame.sprite.spritecollide(player,shields,True,
                   collided=lambda p,s:(p.col,p.row)==(s.col,s.row)):
                player.activate_shield()

            if not gold:
                level+=1; walls,enemies,gold,shields = generate_level(coin_frames,enemy_sprites)
                player.col,player.row = 2,2

            if pygame.sprite.spritecollide(player,enemies,False,
                   collided=lambda p,e:(p.col,p.row)==(e.col,e.row)):
                player.take_damage()

            if not player.alive_flag: state=SG

        screen.fill(C_BG)
        if state in (SP,SG):
            draw_dungeon(screen,walls); gold.draw(screen); shields.draw(screen)
            enemies.draw(screen); draw_shield_aura(screen,player,tick)
            show = (state==SG or player.shield_timer>0
                    or player.damage_timer==0 or player.damage_timer%8<4)
            if show: pg.draw(screen)
            draw_hud(screen,fm,fs,player,level)
        if state==SI: draw_dungeon(screen,walls); draw_intro(screen,fl,fs)
        if state==SG: draw_game_over(screen,fl,fm,fs,player,level)

        pygame.display.flip(); clock.tick(FPS)

    pygame.quit(); sys.exit()

if __name__ == "__main__":
    main()
