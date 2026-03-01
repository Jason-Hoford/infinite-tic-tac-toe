import pygame
import sys
import random
import math
from engine import Engine

pygame.init()
ai_engine = Engine()

# Window dimensions
WIDTH, HEIGHT = 1200, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Infinite Tic-Tac-Toe - Play vs AI")

# Colors
BG_COLOR = (240, 244, 248)
PANEL_BG = (220, 226, 230)
CARD_COLOR = (255, 255, 255)
CARD_SHADOW = (220, 226, 230)

COLOR_X = (255, 107, 107) # Coral
COLOR_O = (72, 219, 251)  # Light Blue
FADED_X = (255, 200, 200)
FADED_O = (200, 240, 255)

TREE_LINE = (150, 160, 170)
TREE_NODE = (255, 255, 255)
TREE_NODE_PRUNED = (190, 195, 200)
TREE_NODE_BEST = (100, 255, 150)
TREE_TEXT = (50, 60, 70)

# Fonts
try:
    font_large = pygame.font.SysFont("Segoe UI", 36, bold=True)
    font_med = pygame.font.SysFont("Segoe UI", 24, bold=True)
    font_small = pygame.font.SysFont("Segoe UI", 14, bold=True)
except:
    font_large = pygame.font.SysFont(None, 45, bold=True)
    font_med = pygame.font.SysFont(None, 30, bold=True)
    font_small = pygame.font.SysFont(None, 18, bold=True)

# Game State (Dummy board)
board = [[None]*3 for _ in range(3)]
turn = 'X'
moves_X = []
moves_O = []
full_history = []
winner = None

# Player Choice State
game_state = "SELECT_PLAYER" # Options: "SELECT_PLAYER", "PLAYING"
player_side = None # 'X' or 'O'
engine_side = None # 'O' or 'X'

def check_win():
    for row in range(3):
        if board[row][0] and board[row][1] and board[row][2] and board[row][0] == board[row][1] == board[row][2]:
            return board[row][0]
    for col in range(3):
        if board[0][col] and board[1][col] and board[2][col] and board[0][col] == board[1][col] == board[2][col]:
            return board[0][col]
    if board[0][0] and board[1][1] and board[2][2] and board[0][0] == board[1][1] == board[2][2]:
        return board[0][0]
    if board[0][2] and board[1][1] and board[2][0] and board[0][2] == board[1][1] == board[2][0]:
        return board[0][2]
    return None

def draw_rounded_rect(surface, color, rect, radius=20):
    pygame.draw.rect(surface, color, rect, border_radius=radius)

def count_empty():
    count = 0
    for r in range(3):
        for c in range(3):
            if not board[r][c]: count += 1
    return count

# --- Scrollable Tree Prototyping ---

class TreeNode:
    def __init__(self, move, eval_score, depth_layer=0, parent=None, is_pruned=False):
        self.move = move
        self.eval_score = eval_score
        self.depth_layer = depth_layer
        self.parent = parent
        self.children = []
        self.is_pruned = is_pruned
        self.is_best = False
        self.rect = None
        
        # Computed Layout Width (how much horizontal space this node's entire subtree needs)
        self.subtree_width = 0
        
        # Absolute World Coordinates
        self.world_x = 0
        self.world_y = 0

def get_valid_moves(sim_board):
    moves = []
    for r in range(3):
        for c in range(3):
            if not sim_board[r][c]:
                moves.append((r, c))
    return moves

def calculate_subtree_widths(node, h_spacing=80):
    if not node.children:
        node.subtree_width = h_spacing
        return h_spacing
    total_width = 0
    for child in node.children:
        total_width += calculate_subtree_widths(child, h_spacing)
    node.subtree_width = max(h_spacing, total_width)
    return node.subtree_width

def assign_world_coordinates(node, current_x, current_y, v_spacing=120):
    node.world_x = current_x
    node.world_y = current_y
    if not node.children: return
    start_x = current_x - (node.subtree_width / 2)
    current_child_start_x = start_x
    for child in node.children:
        child_center_x = current_child_start_x + (child.subtree_width / 2)
        assign_world_coordinates(child, child_center_x, current_y + v_spacing, v_spacing)
        current_child_start_x += child.subtree_width

MOVE_NAMES = {
    (0,0): "Top-L", (0,1): "Top-M", (0,2): "Top-R",
    (1,0): "Mid-L", (1,1): "Center",  (1,2): "Mid-R",
    (2,0): "Bot-L", (2,1): "Bot-M", (2,2): "Bot-R"
}

def build_actual_tree(history):
    root = TreeNode(move="ROOT", eval_score=0.0, depth_layer=0)
    current_node = root
    
    sim_board = [[None]*3 for _ in range(3)]
    sim_moves_X = []
    sim_moves_O = []
    
    # Replay History to form the Spine
    for i, move in enumerate(history):
        r, c, p = move
        valid_moves = get_valid_moves(sim_board)
        
        chosen_node_to_advance = None
        for vm in valid_moves:
            m_str = MOVE_NAMES.get((vm[0], vm[1]), "Err")
            if vm == (r, c):
                next_node = TreeNode(move=m_str, eval_score=0.0, depth_layer=current_node.depth_layer+1, parent=current_node)
                current_node.children.append(next_node)
                chosen_node_to_advance = next_node
            else:
                stub = TreeNode(move=m_str, eval_score=0.0, depth_layer=current_node.depth_layer+1, parent=current_node, is_pruned=True)
                current_node.children.append(stub)
        
        current_node = chosen_node_to_advance
        
        sim_board[r][c] = p
        if p == 'X':
            sim_moves_X.append((r,c))
            if len(sim_moves_X) > 3:
                old_r, old_c = sim_moves_X.pop(0)
                sim_board[old_r][old_c] = None
        else:
            sim_moves_O.append((r,c))
            if len(sim_moves_O) > 3:
                old_r, old_c = sim_moves_O.pop(0)
                sim_board[old_r][old_c] = None

    # Recursively expand from the Current Board State (2 layers deep)
    def generate_future(node, db, dmX, dmO, turn_p, depth):
        if depth == 0: return
        v_moves = get_valid_moves(db)
        for vm in v_moves:
            m_str = MOVE_NAMES.get((vm[0], vm[1]), "Err")
            
            next_db = [row[:] for row in db]
            next_dmX = dmX[:]
            next_dmO = dmO[:]
            
            next_db[vm[0]][vm[1]] = turn_p
            if turn_p == 'X':
                next_dmX.append(vm)
                if len(next_dmX) > 3:
                    old_r, old_c = next_dmX.pop(0)
                    next_db[old_r][old_c] = None
            else:
                next_dmO.append(vm)
                if len(next_dmO) > 3:
                    old_r, old_c = next_dmO.pop(0)
                    next_db[old_r][old_c] = None
                    
            next_turn = 'O' if turn_p == 'X' else 'X'
            
            # --- AI EVALUATION INTEGRATION ---
            # Convert 2D arrays to 1D tuples for engine processing
            board_1d = tuple(next_db[r][c] for r in range(3) for c in range(3))
            hx_1d = tuple(r*3+c for r, c in next_dmX)
            ho_1d = tuple(r*3+c for r, c in next_dmO)
            
            # Use depth 1 minimax to get an accurate immediate-threat evaluation for the tree node
            score = ai_engine.minimax(board_1d, hx_1d, ho_1d, depth=1, alpha=-math.inf, beta=math.inf, is_maximizing=(next_turn=='X'))
            
            child = TreeNode(move=m_str, eval_score=score, depth_layer=node.depth_layer+1, parent=node)
            node.children.append(child)
            
            generate_future(child, next_db, next_dmX, next_dmO, next_turn, depth - 1)

    curr_turn = 'X'
    if len(history) > 0:
         curr_turn = 'O' if history[-1][2] == 'X' else 'X'

    generate_future(current_node, sim_board, sim_moves_X, sim_moves_O, curr_turn, depth=2)
    
    calculate_subtree_widths(root, h_spacing=60)
    assign_world_coordinates(root, current_x=900, current_y=100, v_spacing=120)
    return root, current_node

# UI State
root_node, active_node = build_actual_tree(full_history)

# Camera / Panning / Zoom state
zoom_level = 1.0
camera_x = 900 - int(active_node.world_x)
camera_y = 150 - int(active_node.world_y)
is_dragging = False
drag_start_mouse = (0, 0)
drag_start_camera = (0, 0)
hovered_node = None


def get_node_color(score, is_pruned):
    if is_pruned: return TREE_NODE_PRUNED
    
    # Normal scores range from -15 to 15. Wins are +/- 1000.
    val = max(-15, min(15, score))
    ratio = abs(val) / 15.0
    
    if score >= 900 or score <= -900: ratio = 1.0
        
    bg = (255, 255, 255)
    target = COLOR_X if score > 0 else COLOR_O
    if score == 0: return bg
    
    r = int(bg[0] + (target[0] - bg[0]) * ratio)
    g = int(bg[1] + (target[1] - bg[1]) * ratio)
    b = int(bg[2] + (target[2] - bg[2]) * ratio)
    return (r, g, b)

def render_node(node, cx, cy, radius, show_text=True, depth_scale=1.0, zoom_level=1.0):
    r_rect = pygame.Rect(cx - radius, cy - radius, radius*2, radius*2)
    c_fill = get_node_color(node.eval_score, getattr(node, 'is_pruned', False))
    draw_rounded_rect(screen, c_fill, r_rect, radius)
    pygame.draw.rect(screen, TREE_LINE, r_rect, max(1, int(3 * zoom_level)), border_radius=radius)
    
    if show_text and radius > 8:
        # Re-adjusted font sizes to guarantee they show up
        font_size = max(10, int(18 * zoom_level))
        font = pygame.font.SysFont(None, font_size)
        text_color = TREE_TEXT # Changed from white to dark gray so it's visible on white nodes
        text_surf = font.render(node.move, True, text_color)
        
        # Constrain text to fit safely inside the circle bounds
        max_w = int(radius * 1.5)
        if text_surf.get_width() > max_w:
            ratio = max_w / text_surf.get_width()
            text_surf = pygame.transform.smoothscale(text_surf, (max_w, int(text_surf.get_height() * ratio)))
            
        text_rect = text_surf.get_rect(center=(cx, cy))
        screen.blit(text_surf, text_rect)
        
    # Store screen rect for hover detection
    node.rect = r_rect

def render_tree_recursive(node, cam_x, cam_y, zoom, clip_rect):
    """
    Recursively renders lines and nodes.
    Applies camera offset and zoom to world coordinates before drawing.
    Only draws nodes that intersect with clip_rect.
    """
    screen_x = int(node.world_x * zoom) + cam_x
    screen_y = int(node.world_y * zoom) + cam_y
    
    # Scale nodes to be smaller the deeper they are
    depth_scale = max(0.3, 1.0 - (node.depth_layer * 0.2))
    base_radius = 20 * depth_scale
    scaled_radius = max(3, int(base_radius * zoom))
    
    is_visible = clip_rect.inflate(scaled_radius*4, scaled_radius*4).collidepoint(screen_x, screen_y)

    for child in node.children:
        c_screen_x = int(child.world_x * zoom) + cam_x
        c_screen_y = int(child.world_y * zoom) + cam_y
        
        # Calculate child's specific scale for its connecting line
        child_depth_scale = max(0.3, 1.0 - (child.depth_layer * 0.2))
        child_radius = max(3, int((20 * child_depth_scale) * zoom))
        
        # Only draw line if either parent or child is somewhat visible
        if clip_rect.inflate(300,300).collidepoint(screen_x, screen_y) or clip_rect.inflate(300,300).collidepoint(c_screen_x, c_screen_y):
            l_color = TREE_NODE_PRUNED if child.is_pruned else (COLOR_O if child.is_best else TREE_LINE)
            base_thickness = (4 if child.is_best else 2) * child_depth_scale
            scaled_thickness = max(1, int(base_thickness * zoom))
            pygame.draw.line(screen, l_color, (screen_x, screen_y+scaled_radius), (c_screen_x, c_screen_y-child_radius), scaled_thickness)
            
        render_tree_recursive(child, cam_x, cam_y, zoom, clip_rect)

    if is_visible:
        render_node(node, screen_x, screen_y, scaled_radius)

def check_hover_recursive(node, mouse_pos):
    if node.rect and node.rect.collidepoint(mouse_pos):
        return node
    for child in node.children:
        res = check_hover_recursive(child, mouse_pos)
        if res: return res
    return None

def main():
    global turn, winner, root_node, game_state, player_side, engine_side
    global camera_x, camera_y, zoom_level, is_dragging, drag_start_mouse, drag_start_camera, hovered_node
    
    clock = pygame.time.Clock()
    running = True

    while running:
        screen.fill(BG_COLOR)
        
        if game_state == "SELECT_PLAYER":
            text_title = font_large.render("Infinite Tic-Tac-Toe", True, TREE_TEXT)
            text_sub = font_med.render("Choose your side:", True, (100, 110, 120))
            
            screen.blit(text_title, text_title.get_rect(center=(WIDTH//2, HEIGHT//2 - 80)))
            screen.blit(text_sub, text_sub.get_rect(center=(WIDTH//2, HEIGHT//2 - 30)))
            
            # Draw X Button
            rect_x = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 20, 120, 60)
            draw_rounded_rect(screen, COLOR_X, rect_x, 15)
            lbl_x = font_med.render("Play as X", True, (255, 255, 255))
            screen.blit(lbl_x, lbl_x.get_rect(center=rect_x.center))
            
            # Draw O Button
            rect_o = pygame.Rect(WIDTH//2 + 30, HEIGHT//2 + 20, 120, 60)
            draw_rounded_rect(screen, COLOR_O, rect_o, 15)
            lbl_o = font_med.render("Play as O", True, (255, 255, 255))
            screen.blit(lbl_o, lbl_o.get_rect(center=rect_o.center))
            
            pygame.display.flip()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if rect_x.collidepoint(event.pos):
                        player_side = 'X'
                        engine_side = 'O'
                        game_state = "PLAYING"
                    elif rect_o.collidepoint(event.pos):
                        player_side = 'O'
                        engine_side = 'X'
                        game_state = "PLAYING"
            continue
            
        # --- 1. Left Game Board (0-600) ---
        game_rect = pygame.Rect(0, 0, 600, 600)
        pad = 20
        card_size = (600 - 4*pad) // 3
        for r in range(3):
            for c in range(3):
                x = pad + c * (card_size + pad)
                y = pad + r * (card_size + pad)
                shadow_rect = pygame.Rect(x, y+4, card_size, card_size)
                draw_rounded_rect(screen, CARD_SHADOW, shadow_rect)
                card_rect = pygame.Rect(x, y, card_size, card_size)
                draw_rounded_rect(screen, CARD_COLOR, card_rect)
                
                if board[r][c]:
                    p = board[r][c]
                    is_old = False
                    if p == 'X' and len(moves_X) == 3 and moves_X[0] == (r, c): is_old = True
                    if p == 'O' and len(moves_O) == 3 and moves_O[0] == (r, c): is_old = True
                    
                    center_x, center_y = x + card_size//2, y + card_size//2
                    if p == 'X':
                        color = FADED_X if is_old else COLOR_X
                        off = int(card_size * 0.25)
                        thick = max(3, int(card_size * 0.1))
                        pygame.draw.line(screen, color, (center_x-off, center_y-off), (center_x+off, center_y+off), thick)
                        pygame.draw.line(screen, color, (center_x+off, center_y-off), (center_x-off, center_y+off), thick)
                    elif p == 'O':
                        color = FADED_O if is_old else COLOR_O
                        pygame.draw.circle(screen, color, (center_x, center_y), int(card_size*0.3), max(3, int(card_size*0.1)))

        if winner:
            text = font_large.render(f" Player {winner} Wins! Click to restart ", True, (50, 50, 50))
            text_rect = text.get_rect(center=(300, 300))
            bg_rect = text_rect.inflate(40, 40)
            draw_rounded_rect(screen, CARD_SHADOW, bg_rect.move(0, 4), 20)
            draw_rounded_rect(screen, CARD_COLOR, bg_rect, 20)
            pygame.draw.rect(screen, COLOR_X if winner == 'X' else COLOR_O, bg_rect, 4, border_radius=20)
            screen.blit(text, text_rect)

        # --- 2. Right Canvas Panel (600-1200) ---
        panel_rect = pygame.Rect(600, 0, 600, 600)
        
        # We draw the tree inside a subsurface so it gets clipped at x=600 perfectly
        screen.set_clip(panel_rect)
        pygame.draw.rect(screen, PANEL_BG, panel_rect)
        
        # Render dynamic panning tree
        render_tree_recursive(root_node, camera_x, camera_y, zoom_level, panel_rect)
        
        # Resolve hover state
        pos = pygame.mouse.get_pos()
        hovered_node = None
        if panel_rect.collidepoint(pos):
             hovered_node = check_hover_recursive(root_node, pos)
             
        if hovered_node:
            t_surf = pygame.Surface((150, 70))
            t_surf.fill((40, 40, 50))
            t_surf.blit(font_small.render(f"Eval: {hovered_node.eval_score:+.2f}", True, (255,255,255)), (10, 10))
            t_surf.blit(font_small.render("Pruned" if hovered_node.is_pruned else "Searched", True, (200,200,200)), (10, 35))
            tx, ty = pos[0] + 15, pos[1] + 15
            if tx + 150 > WIDTH: tx -= 165
            screen.blit(t_surf, (tx, ty))

        # Top Overlay UI (Stats)
        overlay_h = 60
        pygame.draw.rect(screen, CARD_COLOR, (600, 0, 600, overlay_h))
        pygame.draw.line(screen, TREE_LINE, (600, overlay_h), (1200, overlay_h), 3)
        lbl = font_med.render("Scroll or Click+Drag to Explore Infinite Tree", True, TREE_TEXT)
        screen.blit(lbl, (620, 15))

        # Remove clip
        screen.set_clip(None)
        
        # Center divider
        pygame.draw.line(screen, TREE_LINE, (600, 0), (600, HEIGHT), 4)

        # Draw Hover Highlight on Left Board (AFTER removing clip so it's visible on left half)
        if hovered_node and hovered_node.move != "ROOT":
            m_str = hovered_node.move
            inv_map = {"Top-L":(0,0), "Top-M":(0,1), "Top-R":(0,2),
                       "Mid-L":(1,0), "Center":(1,1), "Mid-R":(1,2),
                       "Bot-L":(2,0), "Bot-M":(2,1), "Bot-R":(2,2)}
            if m_str in inv_map:
                hr, hc = inv_map[m_str]
                # Overlay a glowing gold square on the corresponding physical board slot
                pad = 20
                card_size = (600 - 4*pad) // 3
                hx = pad + hc * (card_size + pad)
                hy = pad + hr * (card_size + pad)
                
                h_surf = pygame.Surface((card_size, card_size), pygame.SRCALPHA)
                h_surf.fill((255, 215, 0, 100)) # Transparent Gold Glow
                pygame.draw.rect(h_surf, (255, 215, 0), h_surf.get_rect(), 4, border_radius=20)
                screen.blit(h_surf, (hx, hy))

        pygame.display.flip()

        # AI TURN LOGIC
        if turn == engine_side and not winner:
            pygame.display.flip() # Ensure player move is visible before AI thinks
            
            board_1d = tuple(board[r][c] for r in range(3) for c in range(3))
            hx_1d = tuple(r*3+c for r, c in moves_X)
            ho_1d = tuple(r*3+c for r, c in moves_O)
            
            # Hybrid Dynamic Engine Scaling
            spaces_left = 9 - (len(moves_X) + len(moves_O))
            if spaces_left >= 7: target_depth = 6
            elif spaces_left >= 5: target_depth = 8
            else: target_depth = 12 # Infinite endgame phase where tree shrinks
            
            best_move_idx = ai_engine.get_best_move(board_1d, hx_1d, ho_1d, engine_side, max_time=0.15, max_depth=target_depth)
            
            if best_move_idx is not None:
                r, c = best_move_idx // 3, best_move_idx % 3
                board[r][c] = engine_side
                full_history.append((r, c, engine_side))
                if engine_side == 'X':
                    moves_X.append((r, c))
                    if len(moves_X) > 3:
                        old_r, old_c = moves_X.pop(0)
                        board[old_r][old_c] = None
                else:
                    moves_O.append((r, c))
                    if len(moves_O) > 3:
                        old_r, old_c = moves_O.pop(0)
                        board[old_r][old_c] = None
                
                winner = check_win()
                if not winner: turn = player_side
                
                try:
                    root_node, active_node = build_actual_tree(full_history)
                    camera_x = 900 - int(active_node.world_x * zoom_level)
                    camera_y = 150 - int(active_node.world_y * zoom_level)
                except Exception as e:
                    print(f"Failed to build tree: {e}")

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            # -- Mouse Dragging Logic --
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and event.pos[0] > 600:
                    is_dragging = True
                    drag_start_mouse = event.pos
                    drag_start_camera = (camera_x, camera_y)
                elif event.button == 1 and event.pos[0] <= 600:
                     if winner:
                        for r in range(3):
                            for c in range(3): board[r][c] = None
                        moves_X.clear(); moves_O.clear(); full_history.clear()
                        turn = 'X'; winner = None; game_state = "SELECT_PLAYER"
                        root_node, active_node = build_actual_tree(full_history)
                        camera_x = 900 - int(active_node.world_x * zoom_level)
                        camera_y = 150 - int(active_node.world_y * zoom_level)
                        continue
                        
                     if turn != player_side: continue # Ignore clicks if it's the engine's turn
                     
                     col = event.pos[0] // (600 // 3)
                     row = event.pos[1] // (600 // 3)
                     if 0 <= col <= 2 and 0 <= row <= 2 and not board[row][col]:
                         # 1. Place the piece
                         board[row][col] = turn
                         full_history.append((row, col, turn))
                         
                         if turn == 'X':
                             moves_X.append((row,col))
                             # 2. Infinite Tic Tac Toe Rule (remove old piece)
                             if len(moves_X) > 3:
                                 old_r, old_c = moves_X.pop(0)
                                 board[old_r][old_c] = None
                         else:
                             moves_O.append((row,col))
                             if len(moves_O) > 3:
                                 old_r, old_c = moves_O.pop(0)
                                 board[old_r][old_c] = None
                             
                         # 3. Check for win
                         winner = check_win()
                         
                         # 4. Swap Turn
                         if not winner: 
                             turn = 'O' if turn == 'X' else 'X'
                             
                         # 5. Rebuild the tree based on new board capacity
                         try:
                             root_node, active_node = build_actual_tree(full_history)
                             camera_x = 900 - int(active_node.world_x * zoom_level)
                             camera_y = 150 - int(active_node.world_y * zoom_level)
                         except Exception as e:
                             print(f"Failed to build tree: {e}")
                             root_node = TreeNode(move="ERROR", eval_score=0.0)
                             active_node = root_node
                             camera_x = 0; camera_y = 0

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    is_dragging = False

            if event.type == pygame.MOUSEMOTION:
                if is_dragging:
                    dx = event.pos[0] - drag_start_mouse[0]
                    dy = event.pos[1] - drag_start_mouse[1]
                    camera_x = drag_start_camera[0] + dx
                    camera_y = drag_start_camera[1] + dy

            # Mouse wheel for zooming
            if event.type == pygame.MOUSEWHEEL:
                if pygame.mouse.get_pos()[0] > 600:
                    mx, my = pygame.mouse.get_pos()
                    
                    # Store world coordinate under mouse before zoom
                    world_x = (mx - camera_x) / zoom_level
                    world_y = (my - camera_y) / zoom_level
                    
                    # Apply zoom
                    # event.y is positive for scrolling up (zoom in), negative for down (zoom out)
                    zoom_delta = 0.1 * event.y
                    zoom_level = max(0.1, min(3.0, zoom_level + zoom_delta))
                    
                    # Adjust camera so the world coordinate under the mouse stays the same
                    camera_x = mx - (world_x * zoom_level)
                    camera_y = my - (world_y * zoom_level)
        
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
