import time
import math

class Engine:
    def __init__(self):
        # Transposition table: hash(board, turn_is_X) -> (depth, score, flag)
        # flag: 0 = exact, 1 = lower bound (alpha), -1 = upper bound (beta)
        self.transposition_table = {}
        self.nodes_evaluated = 0

    def check_win(self, board):
        """
        Board is a tuple of 9 elements: None, 'X', or 'O'
        Indices:
        0 1 2
        3 4 5
        6 7 8
        """
        lines = [
            (0,1,2), (3,4,5), (6,7,8), # rows
            (0,3,6), (1,4,7), (2,5,8), # cols
            (0,4,8), (2,4,6)           # diags
        ]
        for a, b, c in lines:
            if board[a] and board[a] == board[b] == board[c]:
                return board[a]
        return None

    def get_valid_moves(self, board):
        """Returns a list of indices where a piece can be placed."""
        return [i for i, val in enumerate(board) if val is None]

    def advance_state(self, board, history_X, history_O, move_idx, turn):
        """
        Play a move and enforce Infinite Tic-Tac-Toe rules.
        Returns newly generated (board, history_X, history_O)
        """
        new_board = list(board)
        new_hx = list(history_X)
        new_ho = list(history_O)

        new_board[move_idx] = turn
        if turn == 'X':
            new_hx.append(move_idx)
            if len(new_hx) > 3:
                old_idx = new_hx.pop(0)
                new_board[old_idx] = None
        else:
            new_ho.append(move_idx)
            if len(new_ho) > 3:
                old_idx = new_ho.pop(0)
                new_board[old_idx] = None
                
        return tuple(new_board), tuple(new_hx), tuple(new_ho)

    def evaluate(self, board, history_X, history_O, turn):
        """
        The 'Grader'. Positively scores 'X' advantages, negatively scores 'O'.
        """
        winner = self.check_win(board)
        if winner == 'X': return 1000
        elif winner == 'O': return -1000

        score = 0
        lines = [
            (0,1,2), (3,4,5), (6,7,8), 
            (0,3,6), (1,4,7), (2,5,8), 
            (0,4,8), (2,4,6)
        ]

        # Center control is good, but temporal penalty applies if it's the oldest piece
        center_weight = 3
        if board[4] == 'X':
            score += center_weight if len(history_X) < 3 or history_X[0] != 4 else 0
        elif board[4] == 'O':
            score -= center_weight if len(history_O) < 3 or history_O[0] != 4 else 0

        for a, b, c in lines:
            line_vals = [board[a], board[b], board[c]]
            x_count = line_vals.count('X')
            o_count = line_vals.count('O')
            empty_count = line_vals.count(None)

            if x_count == 2 and empty_count == 1:
                # 2 in a row. Check temporal penalty: are either of these about to disappear?
                penalty = 0
                if len(history_X) == 3:
                    if a == history_X[0] or b == history_X[0] or c == history_X[0]:
                        # About to lose one of the two pieces!
                        penalty = 8
                score += (10 - penalty)
                
            elif o_count == 2 and empty_count == 1:
                penalty = 0
                if len(history_O) == 3:
                    if a == history_O[0] or b == history_O[0] or c == history_O[0]:
                        penalty = 8
                score -= (10 - penalty)
                
        # Slight bonus for having pieces on the board overall
        score += len(history_X) * 0.5
        score -= len(history_O) * 0.5

        return score

    def order_moves(self, board, valid_moves):
        """Move Optimization: Check Center, then Corners, then Edges."""
        def move_score(move):
            if move == 4: return 3
            if move in [0, 2, 6, 8]: return 2
            return 1
        return sorted(valid_moves, key=move_score, reverse=True)

    def minimax(self, board, history_X, history_O, depth, alpha, beta, is_maximizing):
        self.nodes_evaluated += 1
        
        # Check Transposition Table
        state_key = (board, is_maximizing)
        if state_key in self.transposition_table:
            cached_depth, cached_score, flag = self.transposition_table[state_key]
            if cached_depth >= depth:
                if flag == 0: return cached_score
                if flag == 1: alpha = max(alpha, cached_score)
                if flag == -1: beta = min(beta, cached_score)
                if alpha >= beta: return cached_score

        winner = self.check_win(board)
        if winner == 'X': return 1000 + depth # Favor faster wins
        if winner == 'O': return -1000 - depth
        if depth == 0:
            turn = 'X' if is_maximizing else 'O'
            return self.evaluate(board, history_X, history_O, turn)

        valid_moves = self.get_valid_moves(board)
        ordered_moves = self.order_moves(board, valid_moves)
        
        orig_alpha = alpha

        if is_maximizing:
            max_eval = -math.inf
            for move in ordered_moves:
                nb, nhX, nhO = self.advance_state(board, history_X, history_O, move, 'X')
                ev = self.minimax(nb, nhX, nhO, depth - 1, alpha, beta, False)
                max_eval = max(max_eval, ev)
                alpha = max(alpha, ev)
                if beta <= alpha: break
                
            # Store in TT
            flag = 0
            if max_eval <= orig_alpha: flag = -1
            elif max_eval >= beta: flag = 1
            self.transposition_table[state_key] = (depth, max_eval, flag)
            
            return max_eval
        else:
            min_eval = math.inf
            for move in ordered_moves:
                nb, nhX, nhO = self.advance_state(board, history_X, history_O, move, 'O')
                ev = self.minimax(nb, nhX, nhO, depth - 1, alpha, beta, True)
                min_eval = min(min_eval, ev)
                beta = min(beta, ev)
                if beta <= alpha: break
                
            flag = 0
            if min_eval <= orig_alpha: flag = -1
            elif min_eval >= beta: flag = 1
            self.transposition_table[state_key] = (depth, min_eval, flag)
            
            return min_eval

    def get_best_move(self, board, history_X, history_O, turn, max_time=0.5, max_depth=10):
        """
        Iterative Deepening Search.
        """
        start_time = time.time()
        self.nodes_evaluated = 0
        self.transposition_table.clear() # Clear specific to this move to save RAM, or keep across turns if memory permits

        best_move = None
        is_maximizing = (turn == 'X')
        valid_moves = self.get_valid_moves(board)
        ordered_moves = self.order_moves(board, valid_moves)

        for depth in range(1, max_depth + 1):
            if time.time() - start_time > max_time:
                print(f"Time limit reached at depth {depth-1}. Halting.")
                break
                
            current_best_move = None
            if is_maximizing:
                best_val = -math.inf
                for move in ordered_moves:
                    nb, nhX, nhO = self.advance_state(board, history_X, history_O, move, 'X')
                    score = self.minimax(nb, nhX, nhO, depth - 1, -math.inf, math.inf, False)
                    if score > best_val:
                        best_val = score
                        current_best_move = move
            else:
                best_val = math.inf
                for move in ordered_moves:
                    nb, nhX, nhO = self.advance_state(board, history_X, history_O, move, 'O')
                    score = self.minimax(nb, nhX, nhO, depth - 1, -math.inf, math.inf, True)
                    if score < best_val:
                        best_val = score
                        current_best_move = move
                        
            if current_best_move is not None:
                best_move = current_best_move
                print(f"Depth {depth} completed. Eval: {best_val}. Nodes: {self.nodes_evaluated}. Best move so far: {best_move}")
                
            # If forced win found, no need to search deeper
            if abs(best_val) >= 900: 
                break

        print(f"Turn {turn} finished thinking in {time.time() - start_time:.3f}s. Total Nodes: {self.nodes_evaluated}. Chosen Move: {best_move}")
        return best_move

if __name__ == "__main__":
    engine = Engine()
    b = (None, None, None, None, None, None, None, None, None)
    hx = ()
    ho = ()
    
    print("Testing First Move (Depth 6 - Should Pick Center 4)")
    m = engine.get_best_move(b, hx, ho, 'X', max_depth=6)
    print(f"Engine played index: {m}\n")
    
    print("Testing Blocking Move")
    b2 = ('X', 'X', None, None, 'O', None, None, None, None)
    hx2 = (0, 1)
    ho2 = (4,)
    m2 = engine.get_best_move(b2, hx2, ho2, 'O', max_depth=6)
    print(f"Engine ('O') played index: {m2} to block X's 0-1 threat.\n")
