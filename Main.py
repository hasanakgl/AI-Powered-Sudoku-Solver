import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageOps
import google.generativeai as genai
import json
import threading
import copy


MY_API_KEY = "API KEY"  
genai.configure(api_key=MY_API_KEY)

# --- 1. OCR / API HANDLING ---
def api_image_to_grid(image_path):
    """
    Pre-processes the image (grayscale, contrast) and sends it to Gemini
    to extract the Sudoku grid digits.
    """
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    try:
        img = Image.open(image_path)
        
        img = img.convert("L")  
        img = ImageOps.autocontrast(img) 
        
        enhancer_sharp = ImageEnhance.Sharpness(img)
        img = enhancer_sharp.enhance(2.0)

        
        prompt = """
        You are an expert OCR engine for Sudoku puzzles. 
        Analyze the uploaded image and extract the 9x9 Sudoku grid.

        STRICT RULES:
        1. Ignore grid lines, pencil marks, or noise.
        2. Recognize ONLY digits 1-9.
        3. Identify empty cells precisely and represent them as integer 0.
        4. Do NOT confuse vertical bars (|) with the number 1.
        5. Return the result strictly as a JSON array of arrays (9 rows, 9 columns).
        
        Example Output Format:
        [[5, 3, 0, ...], [6, 0, 0, ...], ...]

        Return ONLY the raw list. No Markdown, no code blocks, no text explanations.
        """
        
        response = model.generate_content([prompt, img])
         
        text = response.text.strip()
        
        text = text.replace("```json", "").replace("```python", "").replace("```", "").replace("\n", "")
        
        start = text.find("[[")
        end = text.rfind("]]") + 2
        
        if start != -1 and end != -1:
            json_str = text[start:end]
            grid = json.loads(json_str)
            
            if len(grid) == 9 and all(len(row) == 9 for row in grid):
                return grid
            else:
                print("API Error: Grid is not 9x9")
                return None
        
        return None

    except Exception as e:
        print(f"API Read Error: {e}")
        return None

# --- 2. SOLVER ALGORITHM (Support for Multiple Solutions) ---
class SudokuSolver:
    def __init__(self):
        self.solutions = []

    def is_valid(self, grid, r, c, num):
        """Checks if placing 'num' at (r, c) is valid."""
        # Row check
        for i in range(9):
            if grid[r][i] == num: return False
        # Col check
        for i in range(9):
            if grid[i][c] == num: return False
        # 3x3 Box check
        start_row, start_col = (r // 3) * 3, (c // 3) * 3
        for i in range(3):
            for j in range(3):
                if grid[start_row + i][start_col + j] == num: return False
        return True

    def solve_all(self, grid):
        """
        Finds multiple solutions (limit set to 10 to avoid freezing).
        Returns a list of 9x9 grids.
        """
        self.solutions = []
        self._backtrack(grid)
        return self.solutions

    def _backtrack(self, grid):
        if len(self.solutions) >= 10:
            return

        empty_loc = self.find_empty(grid)
        if not empty_loc:
            self.solutions.append(copy.deepcopy(grid))
            return 

        row, col = empty_loc

        for num in range(1, 10):
            if self.is_valid(grid, row, col, num):
                grid[row][col] = num
                
                self._backtrack(grid)
                
                grid[row][col] = 0

    def find_empty(self, grid):
        for r in range(9):
            for c in range(9):
                if grid[r][c] == 0:
                    return (r, c)
        return None

# --- 3. GUI APPLICATION ---
class SudokuApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sudoku Solver - AI & Multiple Solutions")
        self.root.geometry("1200x800")
        
        self.found_solutions = []
        self.current_solution_index = 0
        self.initial_grid = [] 

        # -- Layout --
        # Left Panel (Controls)
        left_frame = tk.Frame(root, width=400, bg="#f0f0f0")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Header
        tk.Label(left_frame, text="STEP 1: Load Image", bg="#f0f0f0", font=("Helvetica", 12, "bold")).pack(pady=10)
        
        self.btn_load = tk.Button(left_frame, text="📂 Select Image", command=self.load_image, bg="#2196F3", fg="white", font=("Arial", 11, "bold"), height=2)
        self.btn_load.pack(fill=tk.X, padx=10)

        # Image Preview
        self.panel_image = tk.Label(left_frame, text="[Image Preview]", bg="white", relief="sunken")
        self.panel_image.pack(fill=tk.BOTH, expand=True, padx=10, pady=15)

        # Solver Controls
        tk.Label(left_frame, text="STEP 2: Solve", bg="#f0f0f0", font=("Helvetica", 12, "bold")).pack(pady=5)
        
        self.btn_solve = tk.Button(left_frame, text="🧩 FIND ALL SOLUTIONS", command=self.run_solver, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2, state=tk.DISABLED)
        self.btn_solve.pack(fill=tk.X, padx=10)

        # Navigation Controls (Hidden initially)
        self.nav_frame = tk.Frame(left_frame, bg="#f0f0f0")
        self.nav_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.btn_prev = tk.Button(self.nav_frame, text="<< Prev", command=self.show_prev_solution, state=tk.DISABLED)
        self.btn_prev.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.lbl_sol_count = tk.Label(self.nav_frame, text="0 / 0", bg="#f0f0f0", font=("Arial", 10, "bold"))
        self.lbl_sol_count.pack(side=tk.LEFT, padx=5)
        
        self.btn_next = tk.Button(self.nav_frame, text="Next >>", command=self.show_next_solution, state=tk.DISABLED)
        self.btn_next.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Status Bar
        self.lbl_status = tk.Label(left_frame, text="Status: Ready", bg="white", wraplength=350, height=4, fg="gray", font=("Arial", 10))
        self.lbl_status.pack(fill=tk.X, padx=10, pady=20)

        # Right Panel (Grid)
        right_frame = tk.Frame(root)
        right_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        self.entries = {}
        self.create_grid(right_frame)

    def create_grid(self, parent):
        """Creates the 9x9 entry grid with visual separation for 3x3 boxes."""
        for r in range(9):
            for c in range(9):
                px = (2, 10) if c % 3 == 2 and c != 8 else (2, 2)
                py = (2, 10) if r % 3 == 2 and r != 8 else (2, 2)
                
                e = tk.Entry(parent, width=2, font=('Helvetica', 20, 'bold'), justify='center', bg="#f9f9f9", relief="solid", bd=1)
                e.grid(row=r, column=c, padx=px, pady=py)
                self.entries[(r, c)] = e

    def load_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg *.jpeg *.png")])
        if not file_path:
            return

        # Display Image
        img = Image.open(file_path)
        img.thumbnail((350, 350))
        img_tk = ImageTk.PhotoImage(img)
        self.panel_image.config(image=img_tk, text="")
        self.panel_image.image = img_tk 

        self.lbl_status.config(text="AI (Gemini) is analyzing the image...\nPlease wait.", fg="blue")
        self.btn_load.config(state=tk.DISABLED)
        self.btn_solve.config(state=tk.DISABLED)
        
        # Run API in background thread
        threading.Thread(target=self.process_api, args=(file_path,)).start()

    def process_api(self, file_path):
        grid = api_image_to_grid(file_path)
        
        # Update UI in main thread
        self.root.after(0, lambda: self.post_api_update(grid))

    def post_api_update(self, grid):
        self.btn_load.config(state=tk.NORMAL)
        if grid:
            self.populate_grid(grid)
            self.lbl_status.config(text="Scan Complete!\nPlease verify numbers in the grid.\nThen press 'FIND ALL SOLUTIONS'.", fg="green")
            self.btn_solve.config(state=tk.NORMAL)
        else:
            self.lbl_status.config(text="ERROR: Could not read Sudoku.\nPlease try a clearer image.", fg="red")

    def populate_grid(self, grid):
        """Fills the UI grid with numbers from the API."""
        for r in range(9):
            for c in range(9):
                e = self.entries[(r, c)]
                e.delete(0, tk.END)
                if grid[r][c] != 0:
                    e.insert(0, str(grid[r][c]))
                    e.config(fg="black", bg="#f9f9f9") 
                else:
                    e.config(bg="#f9f9f9")

    def get_grid_from_ui(self):
        """Reads the current numbers from the UI grid."""
        grid = [[0]*9 for _ in range(9)]
        for r in range(9):
            for c in range(9):
                val = self.entries[(r, c)].get()
                if val.isdigit():
                    grid[r][c] = int(val)
        return grid

    def run_solver(self):
        self.lbl_status.config(text="Searching for all solutions...", fg="orange")
        self.root.update()

        self.initial_grid = self.get_grid_from_ui()
        
        solver = SudokuSolver()
        self.found_solutions = solver.solve_all(copy.deepcopy(self.initial_grid))
        
        if self.found_solutions:
            self.current_solution_index = 0
            count = len(self.found_solutions)
            msg = f"Found {count} solution(s)!" if count < 10 else "Found 10+ solutions!"
            self.lbl_status.config(text=msg, fg="green")
            
            self.display_solution(0)
            self.update_nav_buttons()
        else:
            messagebox.showerror("No Solution", "This Sudoku is logically impossible.\nPlease check your input numbers.")
            self.lbl_status.config(text="No valid solution found.", fg="red")

    def display_solution(self, index):
        """Displays the solution at the specific index."""
        sol_grid = self.found_solutions[index]
        
        for r in range(9):
            for c in range(9):
                e = self.entries[(r, c)]
                original_val = self.initial_grid[r][c]
                new_val = sol_grid[r][c]
                
                if original_val == 0:
                    e.delete(0, tk.END)
                    e.insert(0, str(new_val))
                    e.config(fg="white", bg="#4CAF50") 
                else:
                    e.config(fg="black", bg="#f9f9f9") 

    def show_next_solution(self):
        if self.current_solution_index < len(self.found_solutions) - 1:
            self.current_solution_index += 1
            self.display_solution(self.current_solution_index)
            self.update_nav_buttons()

    def show_prev_solution(self):
        if self.current_solution_index > 0:
            self.current_solution_index -= 1
            self.display_solution(self.current_solution_index)
            self.update_nav_buttons()

    def update_nav_buttons(self):
        total = len(self.found_solutions)
        current = self.current_solution_index + 1
        self.lbl_sol_count.config(text=f"{current} / {total}")
        
        self.btn_prev.config(state=tk.NORMAL if current > 1 else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if current < total else tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = SudokuApp(root)
    root.mainloop()