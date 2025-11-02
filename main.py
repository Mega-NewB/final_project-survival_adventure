'''
MOUSE KNIGHT'S SURVIVAL ADVENTURE
Run this script to start
Might need `pip install keyboard` to run for MAC or Linux
'''

import os
import sys
import time
import random

try:
    import msvcrt
    have_msvcrt = True
except ImportError:
    have_msvcrt = False
    try:
        import keyboard
    except ImportError:
        print("keyboard library not found. Please install it with `pip install keyboard`.")
        sys.exit(1)



# --- Color Support ------------------------------------------------------------
SUPPORT_COLOR = True
RESET = "\033[0m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_RED = "\033[91m"
BRIGHT_GREEN = "\033[92m"
try:
    from colorama import just_fix_windows_console
    just_fix_windows_console()
except Exception:
    pass

def colorize_char(ch: str) -> str:
    """Return colored character according to entity type; fallback to plain if unsupported."""
    if not SUPPORT_COLOR: return ch
    if ch == '@':
        return f"{BRIGHT_YELLOW}{ch}{RESET}"
    if ch == '!' or ch in MONSTER_CHAR_SET:
        return f"{BRIGHT_RED}{ch}{RESET}"
    if ch in ITEM_CHAR_SET:
        return f"{BRIGHT_GREEN}{ch}{RESET}"
    return ch
# ------------------------------------------------------------------------------



# --- Cursor & Screen Control --------------------------------------------------
HIDE_CURSOR    = "\x1b[?25l"
SHOW_CURSOR    = "\x1b[?25h"
ALT_SCREEN_ON  = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"
CURSOR_HOME    = "\x1b[H"
ERASE_LINE     = "\x1b[K"   # clear from cursor to end of line
ERASE_DOWN     = "\x1b[J"   # clear from cursor to end of screen

def goto(row: int, col: int = 1) -> str:
    """ANSI absolute cursor addressing (1-based)."""
    return f"\x1b[{row};{col}H"
# ------------------------------------------------------------------------------



# --- Global Settings ----------------------------------------------------------
WIDTH = 40
HEIGHT = 20
OBSTACLE_DENSITY = 0.02
FRAME_INTERVAL_SEC = 0.012

# player initial attributes
PLAYER_MAX_HP = 100
PLAYER_ATTACK = 10
PLAYER_WEAPON_LENGTH = 3

# magic auto-shoot
MAGIC_SHOOT_INTERVAL = 50

# bullet pacing
BULLET_STEP_FRAMES = 8

# visuals
DEATH_MARK_DURATION = 25

# population caps
MONSTER_CAP = 25
ITEM_CAP = 4

# item spawn interval (frames)
ITEM_SPAWN_INTERVAL_FRAMES = 600
# ------------------------------------------------------------------------------



# --- Monster / Item Stats (type: config) --------------------------------------
monster_stats = {
    1: {'char': '^', 'max_hp': 1, 'atk': 10,  'speed': -1, 'score': 10, 'weight': 1},
    2: {'char': '%', 'max_hp': 1, 'atk': 12, 'speed': 25, 'score': 20, 'weight': 3},
    3: {'char': '&', 'max_hp': 1, 'atk': 18, 'speed': 45, 'score': 30, 'weight': 2},
    4: {'char': '$', 'max_hp': 1, 'atk': 10, 'speed': 40, 'score': 40, 'weight': 2, 'bullet_cooldown': 100}
}
MONSTER_CHAR_SET = {monster_stats[t]['char'] for t in monster_stats}
ITEM_CHAR_SET = {'H', 'S', 'M', 'D'}
# ------------------------------------------------------------------------------



# --- Entity Classes -----------------------------------------------------------
class Player:
    def __init__(self, row, col):
        self.row = row
        self.col = col
        self.max_hp = PLAYER_MAX_HP
        self.hp = PLAYER_MAX_HP
        self.base_attack = PLAYER_ATTACK
        self.attack = PLAYER_ATTACK
        self.length = PLAYER_WEAPON_LENGTH
        self.strength_timer = 0
        self.magic_timer = 0
        self.shield_timer = 0
        self.magic_cooldown = 0

    def reset(self):
        self.hp = self.max_hp
        self.attack = self.base_attack
        self.length = PLAYER_WEAPON_LENGTH
        self.strength_timer = 0
        self.magic_timer = 0
        self.shield_timer = 0
        self.magic_cooldown = 0
        self.row = HEIGHT // 2
        self.col = WIDTH // 2


class Monster:
    def __init__(self, mtype, row, col):
        s = monster_stats[mtype]
        self.type = mtype
        self.char = s['char']
        self.max_hp = s['max_hp']
        self.hp = self.max_hp
        self.atk = s['atk']
        self.speed = s['speed']
        self.score = s['score']
        self.row = row
        self.col = col
        self.frame_since_action = 0
        self.target_row = None
        self.target_col = None
        self.bullet_timer = s['bullet_cooldown'] if mtype == 4 else None
        self.lifespan = 2000
        self.age = 0


class Bullet:
    def __init__(self, row, col, dr, dc, damage, from_player):
        self.row = row
        self.col = col
        self.dr = dr
        self.dc = dc
        self.damage = damage
        self.from_player = from_player
        self.dx = 0
        self.dy = 0
        self.sx = 0
        self.sy = 0
        self.err = 0
        self.has_target = False
        self.move_counter = 0


class Item:
    def __init__(self, itype, row, col):
        self.type = itype
        self.row = row
        self.col = col
        self.char = itype if itype in ITEM_CHAR_SET else '?'
# ------------------------------------------------------------------------------



# --- Adjective Functions ------------------------------------------------------
def random_location():
    """Generate a random (r, c) in the map."""
    r = random.randint(1, HEIGHT - 2)
    c = random.randint(1, WIDTH - 2)
    return r, c


def is_location_valid(r, c):
    return 0 < r < HEIGHT-1 and 0 < c < WIDTH-1


def is_location_empty(r, c):
    if not is_location_valid (r, c): return False
    if (r, c) == (player.row, player.col): return False
    if (r, c) in obstacle_set: return False
    if any((r, c) == (m.row, m.col) for m in monsters): return False
    if any((r, c) == (it.row, it.col) for it in items): return False
    if any((r, c) == (w['row'], w['col']) for w in spawn_warnings): return False
    return True


def set_grid(grid, row, col, ch):
    if is_location_valid(row, col):
        grid[row][col] = ch


def update_death_marks():
    """Tick death mark timers and remove expired ones."""
    for dm in death_marks[:]:
        dm['timer'] -= 1
        if dm['timer'] <= 0:
            death_marks.remove(dm)

def wait_any_key_blocking():
    """Block until any key is pressed (no echo)."""
    if have_msvcrt:
        _ = msvcrt.getch()
    else:
        _ = keyboard.read_key()


def _flush_pending_keys():
    """Flush leftover keypress after pause/countdown to avoid immediate re-trigger."""
    if have_msvcrt:
        while msvcrt.kbhit():
            try:
                _ = msvcrt.getch()
            except:
                break
    else:
        global pause_key_down
        t0 = time.time()
        while time.time() - t0 < 0.05:
            if not keyboard.is_pressed('p'):
                break
            time.sleep(0.01)
        pause_key_down = False


def monster_should_act(mon):
    """Return True if monster should take an action this frame (speed gating)."""
    if mon.speed is None or mon.speed == -1:
        return False
    mon.frame_since_action += 1
    if mon.frame_since_action >= mon.speed:
        mon.frame_since_action = 0
        return True
    return False
# ------------------------------------------------------------------------------



# --- Screen-Related Functions --------------------------------------------------------
def clear_screen():
    """Fallback full clear (used for pause screen only)."""
    os.system('cls')


def print_map():
    """Compose the frame and paint it via absolute cursor addressing (no scrolling).
    Rendering order (later ones can visually overwrite earlier ones if overlapping):
      1) Borders
      2) Obstacles
      3) Items
      4) Bullets
      5) Monsters
      6) Player
      7) Sword trail (only draws over blank floor)
      8) Spawn warnings ('!') – flashing phases
      9) Death marks ('x') – cosmetic, non-blocking
    Header lines (time/hp/score/status) are written before the map rows.
    """
    grid = [[' ' for _ in range(WIDTH)] for _ in range(HEIGHT)]

    # Borders
    for x in range(WIDTH):
        grid[0][x] = '+'
        grid[HEIGHT - 1][x] = '+'

    for y in range(HEIGHT):
        grid[y][0] = '+'
        grid[y][WIDTH - 1] = '+'

    # Obstacles
    for (r, c) in obstacle_set:
        set_grid(grid, r, c, '#')

    # Items
    for it in items:
        set_grid(grid, it.row, it.col, it.char)

    # Bullets
    for b in bullets:
        set_grid(grid, b.row, b.col, '*')

    # Monsters
    for m in monsters:
        set_grid(grid, m.row, m.col, m.char)

    # Player
    set_grid(grid, player.row, player.col, '@')

    # Sword effects
    if sword_effect_cells:
        for (r, c, ch) in sword_effect_cells:
            # Only draw sword effects on empty floor to avoid hiding entities.
            if grid[r][c] == ' ':
                set_grid(grid, r, c, ch)

    # Spawn warnings
    for w in spawn_warnings:
        if w.get('phase', 0) % 2 == 0:
            set_grid(grid, w['row'], w['col'], '!')

    # Death marks
    for dm in death_marks:
        set_grid(grid, dm['row'], dm['col'], 'x')

    # Compose header lines (with colors on Time/Score in yellow, HP in green)
    lines = []
    elapsed_secs = int(time.time() - start_time)

    if SUPPORT_COLOR:
        hp_part    = f"HP: {BRIGHT_GREEN}{player.hp}/{player.max_hp}{RESET}"
        time_part  = f"Time: {BRIGHT_YELLOW}{elapsed_secs} s{RESET}"
        score_part = f"Score: {BRIGHT_YELLOW}{score}{RESET}"
        kill_part = f"Kills: {BRIGHT_YELLOW}{kill_count}{RESET}"
    else:
        hp_part    = f"HP: {player.hp}/{player.max_hp}"
        time_part  = f"Time: {elapsed_secs}s"
        score_part = f"Score: {score}"
        kill_part = f"Kills: {kill_count}"

    # Keep the rest (kills/monsters/items) uncolored
    lines.append(
        f"{hp_part}  {time_part}  {score_part}  {kill_part}"
        f"  Monsters: {len(monsters)}/{MONSTER_CAP}  Items: {len(items)}/{ITEM_CAP}"
    )
    effects = []
    if SUPPORT_COLOR:
        if player.strength_timer > 0: effects.append(f"{BRIGHT_YELLOW}Strength{RESET}")
        if player.magic_timer > 0:    effects.append(f"{BRIGHT_YELLOW}Magic{RESET}")
        if player.shield_timer > 0:   effects.append(f"{BRIGHT_YELLOW}Defense{RESET}")
    else:
        if player.strength_timer > 0: effects.append("Strength")
        if player.magic_timer > 0:    effects.append("Magic")
        if player.shield_timer > 0:   effects.append("Defense")
    lines.append("Status: " + (", ".join(effects) if effects else "None"))

    # Map rows – add a space between characters for readability; colorize per char.
    for y in range(HEIGHT):
        colored_row = [colorize_char(ch) for ch in grid[y]]
        lines.append(" ".join(colored_row))

    # Absolute painting without newlines to avoid terminal scrolling
    total = len(lines)
    sys.stdout.write(CURSOR_HOME)
    for i, line in enumerate(lines, start=1):
        sys.stdout.write(goto(i, 1))
        sys.stdout.write(line)
        sys.stdout.write(ERASE_LINE)
    sys.stdout.write(goto(total + 1, 1))
    sys.stdout.write(ERASE_DOWN)
    sys.stdout.flush()


def pause_and_countdown():
    """Pause page and 3-2-1 resume; returns paused seconds for timers compensation."""
    t0 = time.time()
    clear_screen()
    print("========= PAUSED =========")
    print("Press any key to continue...")
    wait_any_key_blocking()
    for sec in [3, 2, 1]:
        clear_screen()
        print(f"Continuing in {sec}...")
        time.sleep(1)
    _flush_pending_keys()
    return time.time() - t0


def show_start_screen():
    """Simple start page on the normal console buffer, with a short game intro."""
    clear_screen()
    print("============== MOUSE KNIGHT'S SURVIVAL ADVENTURE ==============")
    print("Move: WASD   Attack: IJKL   Pause: P   Quit: Q")
    print()

    # Short goal/introduction (concise English)
    print("Your Goal: Survive in this strange land. Slash the monsters, grab helpful items,and stay alive as long as you can.")
    print()

    # Legends: use the same colors as in the game for consistency
    sym = colorize_char  # alias for brevity

    print("Entities:")
    print(f"  {sym('@')}  You — the brave mouse knight.")
    print(f"  {sym('^')}  Thorn Beast — hurts you when you get next to it, keep your distance.")
    print(f"  {sym('%')}  Giant Spider — wanders randomly, don't run into it.")
    print(f"  {sym('&')}  Zombie — follows your scent, slow but persistent.")
    print(f"  {sym('$')}  Skeleton — shoots arrows, dodge them or swat them with your sword.")
    print()

    print("Magic Items:")
    print(f"  {sym('H')}  Healing Potion — restore some HP.")
    print(f"  {sym('S')}  Strength Potion — your sword becomes super long for a short time.")
    print(f"  {sym('D')}  Defense Potion — briefly ignore incoming damage.")
    print(f"  {sym('M')}  Magic Potion — auto-cast shots at nearby enemies.")
    print()

    print("Press any key to start...")
    wait_any_key_blocking()


def show_game_over():
    """Game over page: full clear once (on alt buffer), then restore console.
    Added: small delay before showing, and wait for any key to continue.
    """

    clear_screen()
    print("Game Over!")
    survived_secs = int(time.time() - start_time)
    print(f"Time: {survived_secs} s    Kills: {kill_count}    Final Score: {score}")

    time.sleep(1.5)
    if have_msvcrt:
        while msvcrt.kbhit(): _ = msvcrt.getch()
    else: time.sleep(0.1)

    print("Press any key to continue...")

    wait_any_key_blocking()
    clear_screen()
# ------------------------------------------------------------------------------



# --- Utility Functions --------------------------------------------------------
def spawn_obstacles():
    """Generate interior obstacles according to density."""
    obstacle_set = set()
    area = (WIDTH - 2) * (HEIGHT - 2)
    target_count = int(area * OBSTACLE_DENSITY)
    while len(obstacle_set) < target_count:
        r, c = random_location()
        if (r, c) != (player.row, player.col):
            obstacle_set.add((r, c))
    return obstacle_set


def spawn_monster():
    """Propose a new monster at a free interior cell, with weights."""
    types = list(monster_stats.keys())
    weights = [monster_stats[t].get('weight', 1) for t in types]
    mtype = random.choices(types, weights=weights, k=1)[0]

    for _ in range(100):
        r, c = random_location()
        if is_location_empty(r, c):
            return Monster(mtype, r, c)
    return None

def kill_monster(monster):
    death_marks.append({'row': monster.row, 'col': monster.col, 'timer': DEATH_MARK_DURATION})
    monsters.remove(monster)


def spawn_item():
    """Propose a new item at a free interior cell (random type)."""
    itype = random.choice(['H', 'S', 'M', 'D'])
    for _ in range(100):
        r, c = random_location()
        if is_location_empty(r, c):
            return Item(itype, r, c)
    return None


def apply_item_effect(t):
    """Apply item effect and timers."""
    if t == 'H':
        player.hp = min(player.max_hp, player.hp + 25)
    elif t == 'S':
        player.length = 10
        player.strength_timer = 600
    elif t == 'M':
        player.magic_cooldown = 0
        player.magic_timer = 800
    elif t == 'D':
        player.shield_timer = 500


def process_player_action(key):
    """Handle movement and melee attack (IJKL), with obstacle blocking."""
    global sword_effect_cells, kill_count, score
    sword_effect_cells = []

    # Movement
    if key == 'w':
        nr, nc = player.row - 1, player.col
    elif key == 's':
        nr, nc = player.row + 1, player.col
    elif key == 'a':
        nr, nc = player.row, player.col - 1
    elif key == 'd':
        nr, nc = player.row, player.col + 1
    else:
        nr, nc = player.row, player.col

    if key in ['w', 'a', 's', 'd']:
        if is_location_valid(nr, nc) and not ((nr, nc) in obstacle_set):
            collided = False
            for m in monsters:
                if (m.row, m.col) == (nr, nc):
                    collided = True
                    if m.type in (1, 2, 3):
                        if player.shield_timer <= 0:
                            player.hp -= m.atk
                        kill_monster(m)
                    break
            if not collided:
                for it in items:
                    if (it.row, it.col) == (nr, nc):
                        apply_item_effect(it.type)
                        items.remove(it)
                        break
                player.row, player.col = nr, nc

    # Attack
    if key in ['i', 'j', 'k', 'l']:
        if key == 'i':   dr, dc, sym = -1, 0, '|'
        elif key == 'k': dr, dc, sym = 1,  0, '|'
        elif key == 'j': dr, dc, sym = 0, -1, '-'
        else:            dr, dc, sym = 0,  1, '-'
        r, c = player.row, player.col
        for step in range(1, player.length + 1):
            tr, tc = r + dr * step, c + dc * step
            if not is_location_valid(tr, tc): break
            if (tr, tc) in obstacle_set: break
            hit = False
            for m in monsters:
                if (m.row, m.col) == (tr, tc):
                    m.hp -= player.attack
                    if m.hp <= 0:
                        kill_monster(m)
                        kill_count += 1
                        score += m.score
                    hit = True
                    break
            if not hit:
                for b in bullets:
                    if (b.row, b.col) == (tr, tc):
                        bullets.remove(b)
                        break
            sword_effect_cells.append((tr, tc, sym))


def update_player_buffs():
    """Tick down buff timers and auto-cast magic if active."""
    if player.strength_timer > 0:
        player.strength_timer -= 1
        if player.strength_timer == 0:
            player.length = PLAYER_WEAPON_LENGTH
    if player.magic_timer > 0:
        player.magic_timer -= 1
        auto_magic_shoot()
    if player.shield_timer > 0:
        player.shield_timer -= 1


pause_key_down = False
def get_player_input():
    """Return one of wasd/ijkl/p/q or None. 'p' is edge-triggered to avoid repeated pause."""
    global pause_key_down
    if have_msvcrt:
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):
                _ = msvcrt.getch()
                return None
            try:
                return ch.decode('utf-8').lower()
            except:
                return None
    else:
        if keyboard.is_pressed('p'):
            if not pause_key_down:
                pause_key_down = True
                return 'p'
        else:
            pause_key_down = False

        if keyboard.is_pressed('q'): return 'q'
        for k in ['w','a','s','d','i','j','k','l']:
            if keyboard.is_pressed(k):
                return k
    return None


def update_monsters():
    """Update monsters: lifespan, optional shooting, movement, and collisions."""
    for m in monsters[:]:
        m.age += 1
        if m.age >= m.lifespan:
            kill_monster(m)
            continue

        if m.bullet_timer is not None:
            m.bullet_timer -= 1
            if m.bullet_timer <= 0:
                bullets.append(make_bullet_towards(m.row, m.col, player.row, player.col, m.atk, False))
                m.bullet_timer = monster_stats[4]['bullet_cooldown']

        if monster_should_act(m):
            if m.type in (2, 4):  # random waypoint walker
                if m.target_row is None or (m.row == m.target_row and m.col == m.target_col):
                    for _ in range(50):
                        tr, tc = random_location()
                        if not ((tr, tc) in obstacle_set):
                            m.target_row, m.target_col = tr, tc
                            break
                dr = (-1 if m.target_row < m.row else 1 if m.target_row > m.row else 0)
                dc = (-1 if m.target_col < m.col else 1 if m.target_col > m.col else 0)
                if dr != 0 and dc != 0:
                    if random.random() < 0.5: dc = 0
                    else: dr = 0
                nr, nc = m.row + dr, m.col + dc
                if not is_location_valid(nr, nc):
                    m.target_row = None
                elif (nr, nc) in obstacle_set:
                    m.target_row = None
                elif any(o is not m and (o.row, o.col) == (nr, nc) for o in monsters):
                    m.target_row = None
                elif (nr, nc) == (player.row, player.col):
                    if player.shield_timer <= 0:
                        player.hp -= m.atk
                    if m.type == 2:
                        kill_monster(m)
                        continue
                    m.target_row = None
                else:
                    m.row, m.col = nr, nc

            elif m.type == 3:     # chaser
                dr = (-1 if player.row < m.row else 1 if player.row > m.row else 0)
                dc = (-1 if player.col < m.col else 1 if player.col > m.col else 0)
                if dr != 0 and dc != 0: dc = 0
                nr, nc = m.row + dr, m.col + dc
                if not is_location_valid(nr, nc) or ((nr, nc) in obstacle_set):
                    nr, nc = m.row, m.col
                    if dr != 0 and dc == 0:
                        nc = m.col + (-1 if player.col < m.col else 1 if player.col > m.col else 0)
                    elif dc != 0 and dr == 0:
                        nr = m.row + (-1 if player.row < m.row else 1 if player.row > m.row else 0)
                if (nr, nc) != (m.row, m.col):
                    if not any(o is not m and (o.row, o.col) == (nr, nc) for o in monsters):
                        if (nr, nc) == (player.row, player.col):
                            if player.shield_timer <= 0:
                                player.hp -= m.atk
                            if m.type in (1, 2, 3):
                                kill_monster(m)
                                continue
                        else:
                            m.row, m.col = nr, nc


def static_monster_attack():
    """Type-1 static monster triggers when player is adjacent, then disappears."""
    for m in monsters[:]:
        if m.type == 1:
            if abs(m.row - player.row) <= 1 and abs(m.col - player.col) <= 1 and (m.row, m.col) != (player.row, player.col):
                if player.shield_timer <= 0:
                    player.hp -= m.atk
                kill_monster(m)


def update_bullets():
    """Move bullets (Bresenham-like targeted steps) and resolve collisions."""
    global kill_count, score
    for b in bullets[:]:
        b.move_counter += 1
        if b.move_counter < BULLET_STEP_FRAMES:
            continue
        b.move_counter = 0

        if b.has_target:
            e2 = 2 * b.err
            nr, nc = b.row, b.col
            if e2 > -b.dy:
                b.err -= b.dy
                nc = b.col + b.sx
            if e2 < b.dx:
                b.err += b.dx
                nr = b.row + b.sy
        else:
            nr, nc = b.row + b.dr, b.col + b.dc

        if not is_location_valid(nr, nc) or ((nr, nc) in obstacle_set):
            bullets.remove(b)
            continue

        if b.from_player:
            hit = next((m for m in monsters if (m.row, m.col) == (nr, nc)), None)
            if hit:
                hit.hp -= b.damage
                if hit.hp <= 0:
                    death_marks.append({'row': hit.row, 'col': hit.col, 'timer': DEATH_MARK_DURATION})
                    kill_count += 1
                    score += hit.score
                    monsters.remove(hit)
                bullets.remove(b)
            else:
                b.row, b.col = nr, nc
        else:
            if (nr, nc) == (player.row, player.col):
                if player.shield_timer <= 0:
                    player.hp -= b.damage
                bullets.remove(b)
                continue
            if any((m.row, m.col) == (nr, nc) for m in monsters):
                bullets.remove(b)
            else:
                b.row, b.col = nr, nc


def spawn_monsters_check():
    """Countdown to spawn waves; create warning markers; respect monster cap."""
    global spawn_timer
    spawn_timer -= 1
    if spawn_timer <= 0:
        if len(monsters) < MONSTER_CAP:
            to_spawn = 1
            if score > 600: to_spawn = 3
            elif score > 300: to_spawn = 2
            to_spawn = min(to_spawn, MONSTER_CAP - len(monsters))
            for _ in range(to_spawn):
                m = spawn_monster()
                if m:
                    spawn_warnings.append({'row': m.row,'col': m.col,'phase': 0,'timer': 20,'monster': m})
        interval = base_spawn_interval - score // 200
        if interval < min_spawn_interval: interval = min_spawn_interval
        spawn_timer = interval


def process_spawn_warnings():
    """Flash '!' for 6 phases (each 20 frames), then spawn if cell is free."""
    for w in spawn_warnings[:]:
        w['timer'] -= 1
        if w['timer'] > 0: continue
        w['phase'] += 1
        if w['phase'] < 6:
            w['timer'] = 20
            continue
        r, c = w['row'], w['col']
        m = w['monster']
        blocked = ((r, c) == (player.row, player.col)
                   or (r, c) in obstacle_set
                   or any(mm.row == r and mm.col == c for mm in monsters)
                   or any(it.row == r and it.col == c for it in items))
        if not blocked and len(monsters) < MONSTER_CAP:
            monsters.append(m)
        spawn_warnings.remove(w)


def spawn_items_check():
    """Fixed-interval item spawns with global cap."""
    global item_spawn_timer
    item_spawn_timer -= 1
    if item_spawn_timer > 0: return
    item_spawn_timer = ITEM_SPAWN_INTERVAL_FRAMES
    if len(items) >= ITEM_CAP: return
    it = spawn_item()
    if it: items.append(it)


def find_nearest_monster(pr, pc):
    """Return nearest monster and direction hints (dr, dc) from player."""
    if not monsters: return (None, 0, 0)
    nearest = min(monsters, key=lambda m: abs(m.row - pr) + abs(m.col - pc))
    dr = 0 if nearest.row == pr else (1 if nearest.row > pr else -1)
    dc = 0 if nearest.col == pc else (1 if nearest.col > pc else -1)
    return nearest, dr, dc


def make_bullet_towards(sr, sc, tr, tc, damage, from_player):
    """Create a bullet that steps toward target using Bresenham-like deltas."""
    b = Bullet(sr, sc, 0, 0, damage, from_player)
    dx = abs(tc - sc); dy = abs(tr - sr)
    b.sx = 1 if tc > sc else (-1 if tc < sc else 0)
    b.sy = 1 if tr > sr else (-1 if tr < sr else 0)
    b.dx = dx; b.dy = dy
    b.err = (dx - dy)
    b.move_counter = 0
    b.has_target = True
    return b


def auto_magic_shoot():
    """Auto-shoot toward nearest monster while magic buff is active."""
    if player.magic_timer <= 0: return
    if player.magic_cooldown > 0:
        player.magic_cooldown -= 1; return
    target, _, _ = find_nearest_monster(player.row, player.col)
    if target is None:
        player.magic_cooldown = 3; return
    bullets.append(make_bullet_towards(player.row, player.col, target.row, target.col, player.attack, True))
    player.magic_cooldown = MAGIC_SHOOT_INTERVAL
# ------------------------------------------------------------------------------



# --- Initialization -----------------------------------------------------------
player = Player(HEIGHT//2, WIDTH//2)
obstacle_set = spawn_obstacles()
monsters, bullets, items = [], [], []
spawn_warnings, sword_effect_cells, death_marks = [], [], []
score = kill_count = frame_count = 0

# Monster spawn pacing
base_spawn_interval = 60
min_spawn_interval = 12
spawn_timer = base_spawn_interval

# Item spawn pacing
item_spawn_timer = ITEM_SPAWN_INTERVAL_FRAMES

show_start_screen()

# Switch to alternate screen buffer and hide cursor for smooth drawing
sys.stdout.write(ALT_SCREEN_ON + HIDE_CURSOR + CURSOR_HOME)
sys.stdout.flush()

game_start_real = time.time()
start_time = game_start_real
last_score_time = start_time
last_frame_time = time.time()
# ------------------------------------------------------------------------------



# --- Main Loop ----------------------------------------------------------------
def main():
    global last_frame_time
    global sword_effect_cells
    global frame_count
    global current_time
    global last_score_time
    global score
    global start_time

    game_over = False
    player_dead = False

    while not game_over:
        key = get_player_input()
        if key == 'q':
            game_over = True
            player_dead = False
            break
        if key == 'p':
            paused_seconds = pause_and_countdown()
            start_time += paused_seconds
            last_score_time += paused_seconds
            last_frame_time = time.time()
            continue

        current_time = time.time()
        if key or (current_time - last_frame_time >= FRAME_INTERVAL_SEC):
            if key: process_player_action(key)
            else:   sword_effect_cells = []

            update_player_buffs()
            update_monsters()
            static_monster_attack()
            update_bullets()
            update_death_marks()

            spawn_monsters_check()
            process_spawn_warnings()
            spawn_items_check()

            frame_count += 1

            # scoring: +1 per real second
            now = time.time()
            sec_gain = int(now - last_score_time)
            if sec_gain >= 1:
                score += sec_gain
                last_score_time += sec_gain

            last_frame_time = now
            print_map()

            if player.hp <= 0:
                game_over = True
                player_dead = True
                break
        else:
            time.sleep(0.005)

    show_game_over()
# ------------------------------------------------------------------------------

if __name__ == '__main__': main()